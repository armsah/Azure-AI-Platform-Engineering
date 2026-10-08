from knowledge_graph import (
    GraphAccessDenied,
    GraphEntity,
    GraphRelationship,
    TenantKnowledgeGraph,
)
from request_context import RequestContext


class AuthorizedGraph:
    READ_ROLES = frozenset({
        "AI.User",
        "Graph.Ingest",
    })

    WRITE_ROLES = frozenset({
        "Graph.Ingest",
    })

    def __init__(
        self,
        graph: TenantKnowledgeGraph,
    ):
        self.graph = graph

    @staticmethod
    def _require_roles(
        context: RequestContext,
        allowed_roles: frozenset[str],
    ) -> None:
        if not set(context.roles).intersection(allowed_roles):
            raise GraphAccessDenied(
                "Insufficient graph permissions"
            )

    def add_entity(
        self,
        context: RequestContext,
        entity: GraphEntity,
    ) -> None:
        self._require_roles(
            context,
            self.WRITE_ROLES,
        )

        if entity.tenant_id != context.tenant_id:
            raise GraphAccessDenied(
                "Cross-tenant entity write denied"
            )

        self.graph.add_entity(entity)

    def add_relationship(
        self,
        context: RequestContext,
        relationship: GraphRelationship,
    ) -> None:
        self._require_roles(
            context,
            self.WRITE_ROLES,
        )

        if relationship.tenant_id != context.tenant_id:
            raise GraphAccessDenied(
                "Cross-tenant relationship write denied"
            )

        self.graph.add_relationship(relationship)

    def list_entities(
        self,
        context: RequestContext,
    ) -> list[GraphEntity]:
        self._require_roles(
            context,
            self.READ_ROLES,
        )

        return self.graph.list_entities(
            context.tenant_id
        )

    def list_relationships(
        self,
        context: RequestContext,
    ) -> list[GraphRelationship]:
        self._require_roles(
            context,
            self.READ_ROLES,
        )

        return self.graph.list_relationships(
            context.tenant_id
        )