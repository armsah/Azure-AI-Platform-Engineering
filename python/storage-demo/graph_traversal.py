from collections import deque
from dataclasses import dataclass

from graph_access import AuthorizedGraph
from knowledge_graph import (
    GraphEntity,
    GraphIntegrityError,
    GraphRelationship,
)
from request_context import RequestContext


@dataclass(frozen=True)
class TraversalPolicy:
    max_depth: int = 3
    max_visited_nodes: int = 100
    max_paths: int = 50


@dataclass(frozen=True)
class GraphPath:
    entities: tuple[GraphEntity, ...]
    relationships: tuple[GraphRelationship, ...]

    @property
    def depth(self) -> int:
        return len(self.relationships)


@dataclass(frozen=True)
class TraversalResult:
    start_entity_id: str
    paths: tuple[GraphPath, ...]
    visited_nodes: int
    truncated: bool


class GraphTraversalService:
    def __init__(
        self,
        *,
        graph: AuthorizedGraph,
        policy: TraversalPolicy | None = None,
    ):
        self.graph = graph
        self.policy = policy or TraversalPolicy()

        if self.policy.max_depth < 1:
            raise ValueError(
                "max_depth must be at least 1"
            )

        if self.policy.max_visited_nodes < 1:
            raise ValueError(
                "max_visited_nodes must be at least 1"
            )

        if self.policy.max_paths < 1:
            raise ValueError(
                "max_paths must be at least 1"
            )

    def traverse(
        self,
        *,
        context: RequestContext,
        start_entity_id: str,
        relationship_types: frozenset[str] | None = None,
    ) -> TraversalResult:

        if not start_entity_id.strip():
            raise GraphIntegrityError(
                "Missing start entity ID"
            )

        # Authorization and tenant filtering occur
        # before constructing the traversal graph.
        entities = self.graph.list_entities(context)
        relationships = self.graph.list_relationships(context)

        entity_map = {
            entity.entity_id: entity
            for entity in entities
        }

        start = entity_map.get(start_entity_id)

        if start is None:
            raise GraphIntegrityError(
                "Start entity not found in authorized tenant"
            )

        adjacency: dict[
            str,
            list[GraphRelationship],
        ] = {}

        for relationship in relationships:

            # Defensive check even though AuthorizedGraph
            # already performs tenant-scoped reads.
            if relationship.tenant_id != context.tenant_id:
                raise GraphIntegrityError(
                    "Cross-tenant relationship detected"
                )

            if (
                relationship_types is not None
                and relationship.relationship_type
                not in relationship_types
            ):
                continue

            if (
                relationship.source_entity_id
                not in entity_map
                or relationship.target_entity_id
                not in entity_map
            ):
                raise GraphIntegrityError(
                    "Graph contains dangling relationship"
                )

            adjacency.setdefault(
                relationship.source_entity_id,
                [],
            ).append(relationship)

        for outgoing in adjacency.values():
            outgoing.sort(
                key=lambda item: (
                    item.relationship_type,
                    item.target_entity_id,
                    item.relationship_id,
                )
            )

        queue = deque([
            (
                (start,),
                (),
            )
        ])

        discovered_nodes = {start.entity_id}
        paths: list[GraphPath] = []
        truncated = False

        while queue:

            path_entities, path_relationships = queue.popleft()

            current = path_entities[-1]

            if (
                len(path_relationships)
                >= self.policy.max_depth
            ):
                continue

            outgoing = adjacency.get(
                current.entity_id,
                [],
            )

            for relationship in outgoing:

                target_id = relationship.target_entity_id

                # Reject cycles within a path.
                if target_id in {
                    entity.entity_id
                    for entity in path_entities
                }:
                    continue

                target = entity_map[target_id]

                # A global visited-node budget bounds
                # distinct entities explored.
                if target_id not in discovered_nodes:

                    if (
                        len(discovered_nodes)
                        >= self.policy.max_visited_nodes
                    ):
                        truncated = True
                        continue

                    discovered_nodes.add(target_id)

                next_entities = (
                    path_entities + (target,)
                )

                next_relationships = (
                    path_relationships + (relationship,)
                )

                paths.append(
                    GraphPath(
                        entities=next_entities,
                        relationships=next_relationships,
                    )
                )

                if len(paths) >= self.policy.max_paths:
                    truncated = True

                    return TraversalResult(
                        start_entity_id=start_entity_id,
                        paths=tuple(paths),
                        visited_nodes=len(discovered_nodes),
                        truncated=truncated,
                    )

                queue.append(
                    (
                        next_entities,
                        next_relationships,
                    )
                )

        return TraversalResult(
            start_entity_id=start_entity_id,
            paths=tuple(paths),
            visited_nodes=len(discovered_nodes),
            truncated=truncated,
        )
        