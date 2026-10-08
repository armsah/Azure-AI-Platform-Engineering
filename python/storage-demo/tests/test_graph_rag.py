import json

import pytest

from graph_access import AuthorizedGraph
from graph_document_access import (
    DocumentGrant,
    InMemoryDocumentAccessPolicy,
)
from graph_rag_answer import GraphRAGAnswerService
from graph_rag_evidence import GraphRAGEvidenceService
from graph_traversal import GraphTraversalService
from knowledge_graph import (
    GraphAccessDenied,
    GraphEntity,
    GraphIntegrityError,
    GraphRelationship,
    TenantKnowledgeGraph,
)
from rag_citation_validation import CitationValidationError
from rag_grounding import GroundedDraft
from request_context import RequestContext


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


def make_graph():
    graph = TenantKnowledgeGraph()

    graph.add_entity(
        GraphEntity(
            "api",
            "customer-a",
            "Payment API",
            "service",
            "doc-api",
        )
    )

    graph.add_entity(
        GraphEntity(
            "database",
            "customer-a",
            "Orders Database",
            "database",
            "doc-db",
        )
    )

    graph.add_entity(
        GraphEntity(
            "storage",
            "customer-a",
            "Storage Account",
            "infrastructure",
            "doc-storage",
        )
    )

    graph.add_relationship(
        GraphRelationship(
            "api-db",
            "customer-a",
            "api",
            "database",
            "depends_on",
            "doc-dependency",
        )
    )

    graph.add_relationship(
        GraphRelationship(
            "db-storage",
            "customer-a",
            "database",
            "storage",
            "depends_on",
            "doc-storage-dependency",
        )
    )

    return graph


ALL_DOCUMENTS = (
    "doc-api",
    "doc-db",
    "doc-storage",
    "doc-dependency",
    "doc-storage-dependency",
)


def access_policy(
    documents=ALL_DOCUMENTS,
    tenant="customer-a",
    user="user-1",
):
    return InMemoryDocumentAccessPolicy(
        tuple(
            DocumentGrant(
                tenant_id=tenant,
                document_id=document_id,
                user_id=user,
            )
            for document_id in documents
        )
    )


def make_evidence_service(
    documents=ALL_DOCUMENTS,
    graph=None,
):
    graph = graph or make_graph()

    return GraphRAGEvidenceService(
        traversal=GraphTraversalService(
            graph=AuthorizedGraph(graph)
        ),
        document_access=access_policy(documents),
    )


class FakeModel:
    def __init__(self, draft):
        self.draft = draft
        self.calls = 0
        self.last_message = None

    def generate(
        self,
        *,
        system_instructions,
        user_message,
    ):
        self.calls += 1
        self.last_message = user_message
        return self.draft


def test_all_authorized_paths_available():
    service = make_evidence_service()

    result = service.retrieve_evidence(
        context=make_context(),
        start_entity_id="api",
    )

    assert result.authorized_paths == 2
    assert result.rejected_paths == 0
    assert len(result.context.chunks) == 2


def test_missing_document_permission_rejects_path():
    documents = tuple(
        document
        for document in ALL_DOCUMENTS
        if document != "doc-storage"
    )

    service = make_evidence_service(
        documents=documents
    )

    result = service.retrieve_evidence(
        context=make_context(),
        start_entity_id="api",
    )

    assert result.authorized_paths == 1
    assert result.rejected_paths == 1


def test_no_document_permissions_returns_no_evidence():
    service = make_evidence_service(
        documents=()
    )

    result = service.retrieve_evidence(
        context=make_context(),
        start_entity_id="api",
    )

    assert result.context.chunks == ()


def test_citation_ids_are_deterministic():
    service = make_evidence_service()

    first = service.retrieve_evidence(
        context=make_context(),
        start_entity_id="api",
    )

    second = service.retrieve_evidence(
        context=make_context(),
        start_entity_id="api",
    )

    assert [
        item.chunk.chunk_id
        for item in first.context.chunks
    ] == [
        item.chunk.chunk_id
        for item in second.context.chunks
    ]


def test_citations_do_not_cross_tenants():
    service = make_evidence_service()

    with pytest.raises(GraphIntegrityError):
        service.retrieve_evidence(
            context=make_context(
                tenant="customer-b"
            ),
            start_entity_id="api",
        )


def test_graph_role_required():
    service = make_evidence_service()

    with pytest.raises(GraphAccessDenied):
        service.retrieve_evidence(
            context=make_context(roles=()),
            start_entity_id="api",
        )


def test_document_acl_uses_requesting_user():
    service = make_evidence_service()

    result = service.retrieve_evidence(
        context=make_context(user="other-user"),
        start_entity_id="api",
    )

    assert result.context.chunks == ()


def test_relationship_provenance_in_evidence():
    service = make_evidence_service()

    result = service.retrieve_evidence(
        context=make_context(),
        start_entity_id="api",
    )

    combined = "\n".join(
        item.chunk.content
        for item in result.context.chunks
    )

    assert "doc-dependency" in combined
    assert "doc-storage-dependency" in combined


def test_answer_service_uses_verified_citation():
    evidence_service = make_evidence_service()

    evidence = evidence_service.retrieve_evidence(
        context=make_context(),
        start_entity_id="api",
    )

    citation_id = evidence.context.chunks[0].chunk.chunk_id

    model = FakeModel(
        GroundedDraft(
            answer="The Payment API depends on the Orders Database.",
            citation_ids=(citation_id,),
        )
    )

    service = GraphRAGAnswerService(
        evidence_service=evidence_service,
        model=model,
    )

    result = service.answer(
        context=make_context(),
        start_entity_id="api",
        question="What does the Payment API depend on?",
    )

    assert result.grounded
    assert result.citations[0].citation_id == citation_id


def test_fabricated_graph_citation_rejected():
    model = FakeModel(
        GroundedDraft(
            answer="Fabricated dependency.",
            citation_ids=("graph:nonexistent",),
        )
    )

    service = GraphRAGAnswerService(
        evidence_service=make_evidence_service(),
        model=model,
    )

    with pytest.raises(CitationValidationError):
        service.answer(
            context=make_context(),
            start_entity_id="api",
            question="What are the dependencies?",
        )


def test_no_authorized_evidence_skips_model():
    model = FakeModel(
        GroundedDraft(
            answer="Should never appear.",
            citation_ids=("fake",),
        )
    )

    service = GraphRAGAnswerService(
        evidence_service=make_evidence_service(
            documents=()
        ),
        model=model,
    )

    result = service.answer(
        context=make_context(),
        start_entity_id="api",
        question="What are the dependencies?",
    )

    assert not result.grounded
    assert model.calls == 0


def test_model_receives_only_authorized_paths():
    documents = tuple(
        document
        for document in ALL_DOCUMENTS
        if document != "doc-storage"
    )

    evidence_service = make_evidence_service(
        documents=documents
    )

    evidence = evidence_service.retrieve_evidence(
        context=make_context(),
        start_entity_id="api",
    )

    citation_id = evidence.context.chunks[0].chunk.chunk_id

    model = FakeModel(
        GroundedDraft(
            answer="Payment API depends on Orders Database.",
            citation_ids=(citation_id,),
        )
    )

    service = GraphRAGAnswerService(
        evidence_service=evidence_service,
        model=model,
    )

    service.answer(
        context=make_context(),
        start_entity_id="api",
        question="What does Payment API depend on?",
    )

    payload = json.loads(model.last_message)

    evidence_text = json.dumps(payload["evidence"])

    assert "Orders Database" in evidence_text
    assert "Storage Account" not in evidence_text