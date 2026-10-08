import pytest

from graph_access import AuthorizedGraph
from graph_traversal import (
    GraphTraversalService,
    TraversalPolicy,
)
from knowledge_graph import (
    GraphAccessDenied,
    GraphEntity,
    GraphIntegrityError,
    GraphRelationship,
    TenantKnowledgeGraph,
)
from request_context import RequestContext


def context(
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


def entity(entity_id, tenant_id="customer-a"):
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
    relationship_type="depends_on",
):
    return GraphRelationship(
        relationship_id=f"{source}-{target}",
        tenant_id=tenant_id,
        source_entity_id=source,
        target_entity_id=target,
        relationship_type=relationship_type,
        source_document_id="doc-1",
    )


def build_graph(
    edges,
    tenant_id="customer-a",
):
    graph = TenantKnowledgeGraph()

    names = sorted({
        name
        for source, target in edges
        for name in (source, target)
    })

    for name in names:
        graph.add_entity(
            entity(name, tenant_id)
        )

    for source, target in edges:
        graph.add_relationship(
            relationship(
                source,
                target,
                tenant_id,
            )
        )

    return graph


def test_single_hop_traversal():
    graph = build_graph([
        ("api", "database"),
    ])

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph)
    )

    result = service.traverse(
        context=context(),
        start_entity_id="api",
    )

    assert len(result.paths) == 1
    assert result.paths[0].depth == 1


def test_multi_hop_traversal():
    graph = build_graph([
        ("api", "database"),
        ("database", "storage"),
    ])

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph)
    )

    result = service.traverse(
        context=context(),
        start_entity_id="api",
    )

    assert any(
        tuple(
            item.entity_id
            for item in path.entities
        ) == (
            "api",
            "database",
            "storage",
        )
        for path in result.paths
    )


def test_max_depth_enforced():
    graph = build_graph([
        ("a", "b"),
        ("b", "c"),
        ("c", "d"),
    ])

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph),
        policy=TraversalPolicy(
            max_depth=2,
        ),
    )

    result = service.traverse(
        context=context(),
        start_entity_id="a",
    )

    assert all(
        path.depth <= 2
        for path in result.paths
    )

    assert not any(
        path.entities[-1].entity_id == "d"
        for path in result.paths
    )


def test_cycle_does_not_repeat_entity():
    graph = build_graph([
        ("a", "b"),
        ("b", "c"),
        ("c", "a"),
    ])

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph)
    )

    result = service.traverse(
        context=context(),
        start_entity_id="a",
    )

    for path in result.paths:
        ids = [
            item.entity_id
            for item in path.entities
        ]

        assert len(ids) == len(set(ids))


def test_max_paths_enforced():
    graph = build_graph([
        ("a", "b"),
        ("a", "c"),
        ("a", "d"),
    ])

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph),
        policy=TraversalPolicy(
            max_paths=2,
        ),
    )

    result = service.traverse(
        context=context(),
        start_entity_id="a",
    )

    assert len(result.paths) == 2
    assert result.truncated


def test_max_visited_nodes_enforced():
    graph = build_graph([
        ("a", "b"),
        ("a", "c"),
        ("a", "d"),
    ])

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph),
        policy=TraversalPolicy(
            max_visited_nodes=2,
        ),
    )

    result = service.traverse(
        context=context(),
        start_entity_id="a",
    )

    assert result.visited_nodes <= 2
    assert result.truncated


def test_tenant_isolation():
    graph = build_graph([
        ("api", "database"),
    ], "customer-a")

    graph.add_entity(
        entity("secret", "customer-b")
    )

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph)
    )

    result = service.traverse(
        context=context("customer-a"),
        start_entity_id="api",
    )

    assert all(
        item.tenant_id == "customer-a"
        for path in result.paths
        for item in path.entities
    )


def test_cross_tenant_start_entity_hidden():
    graph = build_graph([
        ("api", "database"),
    ], "customer-a")

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph)
    )

    with pytest.raises(GraphIntegrityError):
        service.traverse(
            context=context("customer-b"),
            start_entity_id="api",
        )


def test_missing_role_rejected():
    graph = build_graph([
        ("api", "database"),
    ])

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph)
    )

    with pytest.raises(GraphAccessDenied):
        service.traverse(
            context=context(roles=()),
            start_entity_id="api",
        )


def test_deterministic_path_ordering():
    graph = build_graph([
        ("a", "d"),
        ("a", "b"),
        ("a", "c"),
    ])

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph)
    )

    result = service.traverse(
        context=context(),
        start_entity_id="a",
    )

    targets = [
        path.entities[-1].entity_id
        for path in result.paths
    ]

    assert targets == ["b", "c", "d"]


def test_relationship_type_filter():
    graph = TenantKnowledgeGraph()

    for name in ("api", "database", "cluster"):
        graph.add_entity(entity(name))

    graph.add_relationship(
        relationship(
            "api",
            "database",
            relationship_type="depends_on",
        )
    )

    graph.add_relationship(
        relationship(
            "api",
            "cluster",
            relationship_type="deployed_on",
        )
    )

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph)
    )

    result = service.traverse(
        context=context(),
        start_entity_id="api",
        relationship_types=frozenset({
            "depends_on",
        }),
    )

    assert len(result.paths) == 1
    assert (
        result.paths[0].entities[-1].entity_id
        == "database"
    )


def test_relationship_provenance_preserved():
    graph = build_graph([
        ("api", "database"),
    ])

    service = GraphTraversalService(
        graph=AuthorizedGraph(graph)
    )

    result = service.traverse(
        context=context(),
        start_entity_id="api",
    )

    assert (
        result.paths[0]
        .relationships[0]
        .source_document_id
        == "doc-1"
    )


def test_invalid_policy_rejected():
    graph = AuthorizedGraph(
        TenantKnowledgeGraph()
    )

    with pytest.raises(ValueError):
        GraphTraversalService(
            graph=graph,
            policy=TraversalPolicy(
                max_depth=0,
            ),
        )