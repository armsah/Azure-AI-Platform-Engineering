from dataclasses import replace

import pytest

from agent_tool_authorization import (
    AgentToolAuthorizer,
    ToolAuthorizationError,
    ToolProposal,
)
from agent_tool_execution import AgentToolExecutor
from agent_tool_policies import DEFAULT_TOOL_POLICIES

from async_job_envelope import (
    JobEnvelopeSigner,
    JobSecurityError,
)
from async_job_submission import AsyncJobSubmissionService
from async_job_worker import (
    AsyncJobWorker,
    InMemoryJobLedger,
)

from graph_access import AuthorizedGraph
from graph_document_access import (
    DocumentGrant,
    InMemoryDocumentAccessPolicy,
)
from graph_rag_evidence import GraphRAGEvidenceService
from graph_traversal import GraphTraversalService

from knowledge_graph import (
    GraphAccessDenied,
    GraphEntity,
    GraphIntegrityError,
    GraphRelationship,
    TenantKnowledgeGraph,
)

from request_context import RequestContext

from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantAuthorizationError,
    TenantBoundary,
    TenantMembership,
)
from tenant_resource_access import TenantResource


SECRET = b"adversarial-test-signing-secret-32-bytes"


def context(
    *,
    tenant="customer-a",
    user="alice",
    roles=("AI.User",),
):
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id=tenant,
        user_id=user,
        groups=(),
        roles=roles,
    )


def boundary():
    return TenantBoundary(
        InMemoryTenantMembershipStore(
            (
                TenantMembership(
                    "entra-directory",
                    "alice",
                    "customer-a",
                ),
                TenantMembership(
                    "entra-directory",
                    "bob",
                    "customer-b",
                ),
            )
        )
    )


def signer():
    return JobEnvelopeSigner(
        secret=SECRET,
        audience="document-worker",
        ttl_seconds=300,
        clock=lambda: 1000,
    )


def document_access():
    return InMemoryDocumentAccessPolicy(
        (
            DocumentGrant(
                "customer-a",
                "doc-a",
                "alice",
            ),
            DocumentGrant(
                "customer-a",
                "edge-a",
                "alice",
            ),
            DocumentGrant(
                "customer-b",
                "doc-b",
                "bob",
            ),
            DocumentGrant(
                "customer-b",
                "edge-b",
                "bob",
            ),
        )
    )


def graph():
    store = TenantKnowledgeGraph()

    for tenant, prefix, document in (
        ("customer-a", "a", "doc-a"),
        ("customer-b", "b", "doc-b"),
    ):
        store.add_entity(
            GraphEntity(
                f"{prefix}-api",
                tenant,
                f"{prefix.upper()} API",
                "service",
                document,
            )
        )

        store.add_entity(
            GraphEntity(
                f"{prefix}-db",
                tenant,
                f"{prefix.upper()} Database",
                "database",
                document,
            )
        )

        store.add_relationship(
            GraphRelationship(
                f"{prefix}-edge",
                tenant,
                f"{prefix}-api",
                f"{prefix}-db",
                "depends_on",
                f"edge-{prefix}",
            )
        )

    return store


def graph_evidence():
    return GraphRAGEvidenceService(
        traversal=GraphTraversalService(
            graph=AuthorizedGraph(graph())
        ),
        document_access=document_access(),
    )


def tool_authorizer():
    return AgentToolAuthorizer(
        boundary=boundary(),
        document_access=document_access(),
        policies=DEFAULT_TOOL_POLICIES,
    )


def document_resource(
    *,
    tenant="customer-a",
    resource_id="doc-a",
):
    return TenantResource(
        resource_id=resource_id,
        tenant_id=tenant,
        resource_type="document",
    )


def proposal(
    *,
    name="document.read",
    resource_id="doc-a",
):
    return ToolProposal(
        name=name,
        arguments={"resource_id": resource_id},
    )


# -------------------------------------------------
# Attack 1: Client-controlled tenant override
# -------------------------------------------------

def test_attacker_cannot_override_business_tenant():
    with pytest.raises(TenantAuthorizationError):
        boundary().authorize(
            context=context(),
            requested_tenant_id="customer-b",
        )


# -------------------------------------------------
# Attack 2: Valid identity, wrong membership
# -------------------------------------------------

def test_valid_user_cannot_assume_other_membership():
    with pytest.raises(TenantAuthorizationError):
        boundary().authorize(
            context=context(tenant="customer-b"),
            requested_tenant_id="customer-b",
        )


# -------------------------------------------------
# Attack 3: Graph entity ID enumeration
# -------------------------------------------------

def test_graph_cannot_traverse_other_tenant_entity():
    with pytest.raises(GraphIntegrityError):
        graph_evidence().retrieve_evidence(
            context=context(),
            start_entity_id="b-api",
        )


# -------------------------------------------------
# Attack 4: Graph ACL prevents disclosure
# -------------------------------------------------

def test_graph_does_not_disclose_ungranted_document():
    service = graph_evidence()

    result = service.retrieve_evidence(
        context=context(),
        start_entity_id="a-api",
    )

    assert result.authorized_paths == 1

    unauthorized = service.retrieve_evidence(
        context=context(user="mallory"),
        start_entity_id="a-api",
    )

    assert unauthorized.context.chunks == ()


# -------------------------------------------------
# Attack 5: Graph role escalation
# -------------------------------------------------

def test_graph_requires_read_role():
    with pytest.raises(GraphAccessDenied):
        graph_evidence().retrieve_evidence(
            context=context(roles=()),
            start_entity_id="a-api",
        )


# -------------------------------------------------
# Attack 6: Cross-tenant job envelope tampering
# -------------------------------------------------

def test_attacker_cannot_modify_job_tenant():
    envelope = signer().sign(
        job_id="job-a",
        directory_tenant_id="entra-directory",
        tenant_id="customer-a",
        user_id="alice",
        operation="document.process",
        resource_id="doc-a",
    )

    forged = replace(
        envelope,
        tenant_id="customer-b",
    )

    with pytest.raises(JobSecurityError):
        signer().verify(forged)


# -------------------------------------------------
# Attack 7: Job operation substitution
# -------------------------------------------------

def test_attacker_cannot_substitute_job_operation():
    envelope = signer().sign(
        job_id="job-a",
        directory_tenant_id="entra-directory",
        tenant_id="customer-a",
        user_id="alice",
        operation="document.process",
        resource_id="doc-a",
    )

    forged = replace(
        envelope,
        operation="admin.delete",
    )

    with pytest.raises(JobSecurityError):
        signer().verify(forged)


# -------------------------------------------------
# Attack 8: Worker membership revocation
# -------------------------------------------------

def test_worker_denies_revoked_membership():
    envelope = signer().sign(
        job_id="job-a",
        directory_tenant_id="entra-directory",
        tenant_id="customer-a",
        user_id="alice",
        operation="document.process",
        resource_id="doc-a",
    )

    revoked = TenantBoundary(
        InMemoryTenantMembershipStore(())
    )

    worker = AsyncJobWorker(
        signer=signer(),
        boundary=revoked,
        ledger=InMemoryJobLedger(),
        handlers={
            "document.process": lambda ctx, rid: None,
        },
    )

    with pytest.raises(TenantAuthorizationError):
        worker.execute(envelope)


# -------------------------------------------------
# Attack 9: Unauthorized tool name
# -------------------------------------------------

def test_agent_cannot_invoke_unlisted_tool():
    with pytest.raises(ToolAuthorizationError):
        tool_authorizer().authorize(
            context=context(),
            proposal=proposal(
                name="system.shell",
            ),
            resource=document_resource(),
        )


# -------------------------------------------------
# Attack 10: Model-controlled tenant selection
# -------------------------------------------------

def test_agent_cannot_select_another_tenant():
    with pytest.raises(ToolAuthorizationError):
        tool_authorizer().authorize(
            context=context(),
            proposal=ToolProposal(
                name="document.read",
                arguments={
                    "resource_id": "doc-a",
                    "tenant_id": "customer-b",
                },
            ),
            resource=document_resource(),
        )


# -------------------------------------------------
# Attack 11: Cross-tenant resource ownership
# -------------------------------------------------

def test_agent_cannot_read_other_tenant_document():
    with pytest.raises(ToolAuthorizationError):
        tool_authorizer().authorize(
            context=context(),
            proposal=proposal(
                resource_id="doc-b",
            ),
            resource=document_resource(
                tenant="customer-b",
                resource_id="doc-b",
            ),
        )


# -------------------------------------------------
# Attack 12: Privileged tool escalation
# -------------------------------------------------

def test_agent_cannot_escalate_to_admin_operation():
    with pytest.raises(ToolAuthorizationError):
        tool_authorizer().authorize(
            context=context(),
            proposal=proposal(
                name="document.reindex",
            ),
            resource=document_resource(),
        )


# -------------------------------------------------
# Attack 13: Resource identifier substitution
# -------------------------------------------------

def test_agent_cannot_substitute_resource_id():
    with pytest.raises(ToolAuthorizationError):
        tool_authorizer().authorize(
            context=context(),
            proposal=proposal(
                resource_id="doc-b",
            ),
            resource=document_resource(),
        )


# -------------------------------------------------
# Attack 14: Denied tool must never run
# -------------------------------------------------

def test_denied_tool_never_reaches_handler():
    calls = []

    executor = AgentToolExecutor(
        authorizer=tool_authorizer(),
        handlers={
            "document.read": (
                lambda authorized: (
                    calls.append(authorized)
                    or "secret"
                )
            ),
        },
    )

    with pytest.raises(ToolAuthorizationError):
        executor.execute(
            context=context(),
            proposal=proposal(
                resource_id="doc-b",
            ),
            resource=document_resource(
                tenant="customer-b",
                resource_id="doc-b",
            ),
        )

    assert calls == []


# -------------------------------------------------
# Attack 15: Legitimate tenant B remains functional
# -------------------------------------------------

def test_authorized_second_tenant_can_access_own_data():
    authorized = tool_authorizer().authorize(
        context=context(
            tenant="customer-b",
            user="bob",
        ),
        proposal=proposal(
            resource_id="doc-b",
        ),
        resource=document_resource(
            tenant="customer-b",
            resource_id="doc-b",
        ),
    )

    assert authorized.tenant_id == "customer-b"
    assert authorized.user_id == "bob"


# -------------------------------------------------
# Attack 16: Tenant B graph remains isolated
# -------------------------------------------------

def test_second_tenant_graph_is_accessible_only_to_b():
    result = graph_evidence().retrieve_evidence(
        context=context(
            tenant="customer-b",
            user="bob",
        ),
        start_entity_id="b-api",
    )

    assert result.authorized_paths == 1

    content = "\n".join(
        chunk.chunk.content
        for chunk in result.context.chunks
    )

    assert "B Database" in content
    assert "A Database" not in content
    