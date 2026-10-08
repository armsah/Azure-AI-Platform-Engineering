import pytest

from agent_tool_authorization import (
    AgentToolAuthorizer,
    ToolAuthorizationError,
    ToolProposal,
)
from agent_tool_execution import AgentToolExecutor
from agent_tool_policies import DEFAULT_TOOL_POLICIES
from graph_document_access import (
    DocumentGrant,
    InMemoryDocumentAccessPolicy,
)
from request_context import RequestContext
from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantBoundary,
    TenantMembership,
)
from tenant_resource_access import TenantResource


def make_context(
    tenant="customer-a",
    user="user-1",
    roles=("AI.User",),
):
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id=tenant,
        user_id=user,
        groups=(),
        roles=roles,
    )


def make_authorizer(
    *,
    grant_document=True,
    memberships=None,
):
    if memberships is None:
        memberships = (
            TenantMembership(
                directory_tenant_id="entra-directory",
                user_id="user-1",
                business_tenant_id="customer-a",
            ),
        )

    grants = (
        (
            DocumentGrant(
                tenant_id="customer-a",
                document_id="doc-1",
                user_id="user-1",
            ),
        )
        if grant_document
        else ()
    )

    return AgentToolAuthorizer(
        boundary=TenantBoundary(
            InMemoryTenantMembershipStore(
                memberships
            )
        ),
        document_access=InMemoryDocumentAccessPolicy(
            grants
        ),
        policies=DEFAULT_TOOL_POLICIES,
    )


def make_resource(
    tenant="customer-a",
    resource_id="doc-1",
    resource_type="document",
):
    return TenantResource(
        resource_id=resource_id,
        tenant_id=tenant,
        resource_type=resource_type,
    )


def make_proposal(
    name="document.read",
    arguments=None,
):
    if arguments is None:
        arguments = {"resource_id": "doc-1"}

    return ToolProposal(
        name=name,
        arguments=arguments,
    )


def test_authorized_document_read():
    authorized = make_authorizer().authorize(
        context=make_context(),
        proposal=make_proposal(),
        resource=make_resource(),
    )

    assert authorized.tenant_id == "customer-a"
    assert authorized.resource_id == "doc-1"


def test_unknown_tool_rejected():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer().authorize(
            context=make_context(),
            proposal=make_proposal(
                name="system.shell"
            ),
            resource=make_resource(),
        )


def test_model_supplied_tenant_rejected():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer().authorize(
            context=make_context(),
            proposal=make_proposal(
                arguments={
                    "resource_id": "doc-1",
                    "tenant_id": "customer-b",
                }
            ),
            resource=make_resource(),
        )


def test_cross_tenant_resource_rejected():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer().authorize(
            context=make_context(),
            proposal=make_proposal(),
            resource=make_resource(
                tenant="customer-b"
            ),
        )


def test_document_acl_denied():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer(
            grant_document=False
        ).authorize(
            context=make_context(),
            proposal=make_proposal(),
            resource=make_resource(),
        )


def test_missing_role_rejected():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer().authorize(
            context=make_context(
                roles=()
            ),
            proposal=make_proposal(),
            resource=make_resource(),
        )


def test_privileged_reindex_requires_admin():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer().authorize(
            context=make_context(),
            proposal=make_proposal(
                name="document.reindex"
            ),
            resource=make_resource(),
        )


def test_privileged_reindex_admin_allowed():
    authorized = make_authorizer().authorize(
        context=make_context(
            roles=("Document.Admin",)
        ),
        proposal=make_proposal(
            name="document.reindex"
        ),
        resource=make_resource(),
    )

    assert authorized.name == "document.reindex"


def test_missing_resource_argument_rejected():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer().authorize(
            context=make_context(),
            proposal=make_proposal(
                arguments={}
            ),
            resource=make_resource(),
        )


def test_unexpected_argument_rejected():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer().authorize(
            context=make_context(),
            proposal=make_proposal(
                arguments={
                    "resource_id": "doc-1",
                    "command": "delete-all",
                }
            ),
            resource=make_resource(),
        )


def test_resource_id_mismatch_rejected():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer().authorize(
            context=make_context(),
            proposal=make_proposal(
                arguments={
                    "resource_id": "doc-secret",
                }
            ),
            resource=make_resource(),
        )


def test_resource_type_mismatch_rejected():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer().authorize(
            context=make_context(),
            proposal=make_proposal(),
            resource=make_resource(
                resource_type="knowledge_graph"
            ),
        )


def test_missing_membership_rejected():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer(
            memberships=()
        ).authorize(
            context=make_context(),
            proposal=make_proposal(),
            resource=make_resource(),
        )


def test_non_json_object_arguments_rejected():
    with pytest.raises(ToolAuthorizationError):
        make_authorizer().authorize(
            context=make_context(),
            proposal=ToolProposal(
                name="document.read",
                arguments=["doc-1"],
            ),
            resource=make_resource(),
        )


def test_executor_calls_trusted_handler():
    calls = []

    executor = AgentToolExecutor(
        authorizer=make_authorizer(),
        handlers={
            "document.read": lambda call: (
                calls.append(call)
                or "Document content"
            ),
        },
    )

    result = executor.execute(
        context=make_context(),
        proposal=make_proposal(),
        resource=make_resource(),
    )

    assert result.output == "Document content"
    assert calls[0].tenant_id == "customer-a"


def test_denied_tool_never_executes_handler():
    calls = []

    executor = AgentToolExecutor(
        authorizer=make_authorizer(),
        handlers={
            "document.read": lambda call: (
                calls.append(call)
                or "Document content"
            ),
        },
    )

    with pytest.raises(ToolAuthorizationError):
        executor.execute(
            context=make_context(),
            proposal=make_proposal(),
            resource=make_resource(
                tenant="customer-b"
            ),
        )

    assert calls == []


def test_unregistered_handler_rejected():
    executor = AgentToolExecutor(
        authorizer=make_authorizer(),
        handlers={},
    )

    with pytest.raises(ToolAuthorizationError):
        executor.execute(
            context=make_context(),
            proposal=make_proposal(),
            resource=make_resource(),
        )


def test_invalid_handler_output_rejected():
    executor = AgentToolExecutor(
        authorizer=make_authorizer(),
        handlers={
            "document.read": lambda call: {
                "unexpected": "object"
            },
        },
    )

    with pytest.raises(ToolAuthorizationError):
        executor.execute(
            context=make_context(),
            proposal=make_proposal(),
            resource=make_resource(),
        )