import pytest

from graph_access import AuthorizedGraph
from knowledge_graph import (
    GraphAccessDenied,
    GraphEntity,
    GraphIntegrityError,
    GraphRelationship,
    TenantKnowledgeGraph,
)
from request_context import RequestContext


def make_context(
    tenant_id="customer-a",
    roles=("AI.User",),
):
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id=tenant_id,
        user_id="user-1",
        groups=(),
        roles=roles,
    )


def entity(
    entity_id,
    tenant_id="customer-a",
):
    return GraphEntity(
        entity_id=entity_id,
        tenant_id=tenant_id,
        name=entity_id,
        entity_type="service",
        source_document_id="doc-1",
    )


def relationship(
    source,
    target,
    tenant_id="customer-a",
):
    return GraphRelationship(
        relationship_id=f"{source}-{target}",
        tenant_id=tenant_id,
        source_entity_id=source,
        target_entity_id=target,
        relationship_type="depends_on",
        source_document_id="doc-1",
    )


def test_add_and_list_entities():
    graph = TenantKnowledgeGraph()

    graph.add_entity(entity("api"))

    results = graph.list_entities("customer-a")

    assert len(results) == 1
    assert results[0].entity_id == "api"


def test_tenant_isolation():
    graph = TenantKnowledgeGraph()

    graph.add_entity(entity("api", "customer-a"))
    graph.add_entity(entity("api", "customer-b"))

    assert len(graph.list_entities("customer-a")) == 1
    assert len(graph.list_entities("customer-b")) == 1


def test_relationship_requires_existing_endpoints():
    graph = TenantKnowledgeGraph()

    graph.add_entity(entity("api"))

    with pytest.raises(GraphIntegrityError):
        graph.add_relationship(
            relationship("api", "database")
        )


def test_valid_relationship():
    graph = TenantKnowledgeGraph()

    graph.add_entity(entity("api"))
    graph.add_entity(entity("database"))

    graph.add_relationship(
        relationship("api", "database")
    )

    assert len(
        graph.list_relationships("customer-a")
    ) == 1


def test_cross_tenant_relationship_rejected():
    graph = TenantKnowledgeGraph()

    graph.add_entity(entity("api", "customer-a"))
    graph.add_entity(entity("database", "customer-b"))

    with pytest.raises(GraphIntegrityError):
        graph.add_relationship(
            relationship(
                "api",
                "database",
                "customer-a",
            )
        )


def test_conflicting_entity_identity_rejected():
    graph = TenantKnowledgeGraph()

    graph.add_entity(entity("api"))

    conflicting = GraphEntity(
        entity_id="api",
        tenant_id="customer-a",
        name="different",
        entity_type="service",
        source_document_id="doc-1",
    )

    with pytest.raises(GraphIntegrityError):
        graph.add_entity(conflicting)


def test_authorized_graph_read():
    graph = TenantKnowledgeGraph()
    access = AuthorizedGraph(graph)

    access.add_entity(
        make_context(roles=("Graph.Ingest",)),
        entity("api"),
    )

    assert len(
        access.list_entities(make_context())
    ) == 1


def test_unauthorized_role_rejected():
    access = AuthorizedGraph(
        TenantKnowledgeGraph()
    )

    with pytest.raises(GraphAccessDenied):
        access.list_entities(
            make_context(roles=())
        )


def test_cross_tenant_write_rejected():
    access = AuthorizedGraph(
        TenantKnowledgeGraph()
    )

    with pytest.raises(GraphAccessDenied):
        access.add_entity(
            make_context("customer-a"),
            entity("secret", "customer-b"),
        )


def test_duplicate_identical_entity_is_idempotent():
    graph = TenantKnowledgeGraph()

    graph.add_entity(entity("api"))
    graph.add_entity(entity("api"))

    assert len(graph.list_entities("customer-a")) == 1