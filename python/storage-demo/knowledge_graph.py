from dataclasses import dataclass
from threading import RLock


class GraphError(Exception):
    pass


class GraphAccessDenied(GraphError):
    pass


class GraphIntegrityError(GraphError):
    pass


@dataclass(frozen=True)
class GraphEntity:
    entity_id: str
    tenant_id: str
    name: str
    entity_type: str
    source_document_id: str


@dataclass(frozen=True)
class GraphRelationship:
    relationship_id: str
    tenant_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    source_document_id: str


class TenantKnowledgeGraph:
    def __init__(self):
        self._entities: dict[
            tuple[str, str], GraphEntity
        ] = {}

        self._relationships: dict[
            tuple[str, str], GraphRelationship
        ] = {}

        self._lock = RLock()

    def add_entity(
        self,
        entity: GraphEntity,
    ) -> None:

        if not all([
            entity.tenant_id,
            entity.entity_id,
            entity.name,
            entity.entity_type,
            entity.source_document_id,
        ]):
            raise GraphIntegrityError(
                "Incomplete entity"
            )

        key = (
            entity.tenant_id,
            entity.entity_id,
        )

        with self._lock:
            existing = self._entities.get(key)

            if existing is not None and existing != entity:
                raise GraphIntegrityError(
                    "Conflicting entity identity"
                )

            self._entities[key] = entity

    def add_relationship(
        self,
        relationship: GraphRelationship,
    ) -> None:

        if not all([
            relationship.tenant_id,
            relationship.relationship_id,
            relationship.source_entity_id,
            relationship.target_entity_id,
            relationship.relationship_type,
            relationship.source_document_id,
        ]):
            raise GraphIntegrityError(
                "Incomplete relationship"
            )

        tenant = relationship.tenant_id

        with self._lock:
            source = self._entities.get(
                (
                    tenant,
                    relationship.source_entity_id,
                )
            )

            target = self._entities.get(
                (
                    tenant,
                    relationship.target_entity_id,
                )
            )

            if source is None or target is None:
                raise GraphIntegrityError(
                    "Relationship endpoints must exist "
                    "inside the same tenant"
                )

            key = (
                tenant,
                relationship.relationship_id,
            )

            existing = self._relationships.get(key)

            if (
                existing is not None
                and existing != relationship
            ):
                raise GraphIntegrityError(
                    "Conflicting relationship identity"
                )

            self._relationships[key] = relationship

    def get_entity(
        self,
        tenant_id: str,
        entity_id: str,
    ) -> GraphEntity | None:

        with self._lock:
            return self._entities.get(
                (
                    tenant_id,
                    entity_id,
                )
            )

    def list_entities(
        self,
        tenant_id: str,
    ) -> list[GraphEntity]:

        with self._lock:
            return [
                entity
                for (tenant, _), entity
                in self._entities.items()
                if tenant == tenant_id
            ]

    def list_relationships(
        self,
        tenant_id: str,
    ) -> list[GraphRelationship]:

        with self._lock:
            return [
                relationship
                for (tenant, _), relationship
                in self._relationships.items()
                if tenant == tenant_id
            ]