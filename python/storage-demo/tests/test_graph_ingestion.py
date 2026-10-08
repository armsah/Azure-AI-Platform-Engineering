import pytest

from graph_access import AuthorizedGraph
from graph_extraction import (
    EntityProposal,
    GraphExtraction,
    RelationshipProposal,
)
from graph_ingestion import GraphIngestionService
from knowledge_graph import (
    GraphAccessDenied,
    GraphIntegrityError,
    TenantKnowledgeGraph,
)
from request_context import RequestContext


DOCUMENT = (
    "The payment API depends on the orders database."
)


def make_context(
    tenant_id="customer-a",
    roles=("Graph.Ingest",),
):
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id=tenant_id,
        user_id="ingestion-service",
        groups=(),
        roles=roles,
    )


def valid_extraction():
    return GraphExtraction(
        entities=(
            EntityProposal(
                entity_id="payment-api",
                name="Payment API",
                entity_type="service",
            ),
            EntityProposal(
                entity_id="orders-db",
                name="Orders Database",
                entity_type="database",
            ),
        ),
        relationships=(
            RelationshipProposal(
                relationship_id="payment-orders",
                source_entity_id="payment-api",
                target_entity_id="orders-db",
                relationship_type="depends_on",
                evidence_text=DOCUMENT,
            ),
        ),
    )


class FakeExtractor:
    def __init__(self, result):
        self.result = result

    def extract(self, *, document_text):
        return self.result


def make_service(extraction=None):
    graph = TenantKnowledgeGraph()

    service = GraphIngestionService(
        graph=AuthorizedGraph(graph),
        extractor=FakeExtractor(
            extraction
            if extraction is not None
            else valid_extraction()
        ),
    )

    return service, graph


def test_valid_extraction_ingested():
    service, graph = make_service()

    result = service.ingest(
        context=make_context(),
        document_id="doc-1",
        document_text=DOCUMENT,
    )

    assert result.entities_written == 2
    assert result.relationships_written == 1

    relationship = graph.list_relationships(
        "customer-a"
    )[0]

    assert relationship.source_document_id == "doc-1"


def test_tenant_comes_from_trusted_context():
    service, graph = make_service()

    service.ingest(
        context=make_context("customer-b"),
        document_id="doc-1",
        document_text=DOCUMENT,
    )

    assert graph.list_entities("customer-a") == []
    assert len(graph.list_entities("customer-b")) == 2


def test_ai_user_cannot_ingest():
    service, _ = make_service()

    with pytest.raises(GraphIntegrityError):
        service.ingest(
            context=make_context(
                roles=("AI.User",)
            ),
            document_id="doc-1",
            document_text=DOCUMENT,
        )


def test_ai_user_cannot_write_directly():
    service, graph = make_service()

    with pytest.raises(GraphAccessDenied):
        service.graph.add_entity(
            make_context(roles=("AI.User",)),
            graph_entity(),
        )


def graph_entity():
    from knowledge_graph import GraphEntity

    return GraphEntity(
        entity_id="test",
        tenant_id="customer-a",
        name="Test",
        entity_type="service",
        source_document_id="doc-1",
    )


def test_unknown_relationship_endpoint_rejected():
    extraction = valid_extraction()

    invalid = GraphExtraction(
        entities=extraction.entities,
        relationships=(
            RelationshipProposal(
                relationship_id="invalid",
                source_entity_id="payment-api",
                target_entity_id="missing-db",
                relationship_type="depends_on",
                evidence_text=DOCUMENT,
            ),
        ),
    )

    service, _ = make_service(invalid)

    with pytest.raises(GraphIntegrityError):
        service.ingest(
            context=make_context(),
            document_id="doc-1",
            document_text=DOCUMENT,
        )


def test_fabricated_evidence_rejected():
    extraction = valid_extraction()

    invalid = GraphExtraction(
        entities=extraction.entities,
        relationships=(
            RelationshipProposal(
                relationship_id="fabricated",
                source_entity_id="payment-api",
                target_entity_id="orders-db",
                relationship_type="depends_on",
                evidence_text="A relationship not in the document.",
            ),
        ),
    )

    service, graph = make_service(invalid)

    with pytest.raises(GraphIntegrityError):
        service.ingest(
            context=make_context(),
            document_id="doc-1",
            document_text=DOCUMENT,
        )

    assert graph.list_entities("customer-a") == []


def test_disallowed_relationship_type_rejected():
    extraction = valid_extraction()

    invalid = GraphExtraction(
        entities=extraction.entities,
        relationships=(
            RelationshipProposal(
                relationship_id="invalid-type",
                source_entity_id="payment-api",
                target_entity_id="orders-db",
                relationship_type="controls_everything",
                evidence_text=DOCUMENT,
            ),
        ),
    )

    service, _ = make_service(invalid)

    with pytest.raises(GraphIntegrityError):
        service.ingest(
            context=make_context(),
            document_id="doc-1",
            document_text=DOCUMENT,
        )


def test_duplicate_entity_ids_rejected():
    extraction = valid_extraction()

    invalid = GraphExtraction(
        entities=(
            extraction.entities[0],
            extraction.entities[0],
        ),
        relationships=(),
    )

    service, _ = make_service(invalid)

    with pytest.raises(GraphIntegrityError):
        service.ingest(
            context=make_context(),
            document_id="doc-1",
            document_text=DOCUMENT,
        )


def test_empty_document_rejected():
    service, _ = make_service()

    with pytest.raises(GraphIntegrityError):
        service.ingest(
            context=make_context(),
            document_id="doc-1",
            document_text="",
        )


def test_cross_tenant_graph_reads_remain_isolated():
    service, graph = make_service()

    service.ingest(
        context=make_context("customer-a"),
        document_id="doc-1",
        document_text=DOCUMENT,
    )

    access = AuthorizedGraph(graph)

    reader = make_context(
        tenant_id="customer-b",
        roles=("AI.User",),
    )

    assert access.list_entities(reader) == []
    assert access.list_relationships(reader) == []