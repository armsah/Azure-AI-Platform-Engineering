from dataclasses import dataclass

from graph_access import AuthorizedGraph
from graph_extraction import (
    GraphExtractor,
    GraphExtraction,
)
from knowledge_graph import (
    GraphEntity,
    GraphIntegrityError,
    GraphRelationship,
)
from request_context import RequestContext


ALLOWED_ENTITY_TYPES = frozenset({
    "service",
    "database",
    "application",
    "infrastructure",
    "team",
})

ALLOWED_RELATIONSHIP_TYPES = frozenset({
    "depends_on",
    "owned_by",
    "connects_to",
    "deployed_on",
})


@dataclass(frozen=True)
class GraphIngestionResult:
    entities_written: int
    relationships_written: int


class GraphIngestionService:
    def __init__(
        self,
        *,
        graph: AuthorizedGraph,
        extractor: GraphExtractor,
    ):
        self.graph = graph
        self.extractor = extractor

    @staticmethod
    def _validate(
        extraction: GraphExtraction,
        document_text: str,
    ) -> None:
        entity_ids: set[str] = set()
        relationship_ids: set[str] = set()

        for entity in extraction.entities:
            if not entity.entity_id.strip():
                raise GraphIntegrityError(
                    "Empty entity ID"
                )

            if not entity.name.strip():
                raise GraphIntegrityError(
                    "Empty entity name"
                )

            if entity.entity_type not in ALLOWED_ENTITY_TYPES:
                raise GraphIntegrityError(
                    "Disallowed entity type"
                )

            if entity.entity_id in entity_ids:
                raise GraphIntegrityError(
                    "Duplicate entity ID"
                )

            entity_ids.add(entity.entity_id)

        for relationship in extraction.relationships:
            if not relationship.relationship_id.strip():
                raise GraphIntegrityError(
                    "Empty relationship ID"
                )

            if (
                relationship.relationship_type
                not in ALLOWED_RELATIONSHIP_TYPES
            ):
                raise GraphIntegrityError(
                    "Disallowed relationship type"
                )

            if relationship.relationship_id in relationship_ids:
                raise GraphIntegrityError(
                    "Duplicate relationship ID"
                )

            relationship_ids.add(
                relationship.relationship_id
            )

            if (
                relationship.source_entity_id
                not in entity_ids
                or relationship.target_entity_id
                not in entity_ids
            ):
                raise GraphIntegrityError(
                    "Relationship references "
                    "an unknown extracted entity"
                )

            evidence = relationship.evidence_text.strip()

            if not evidence:
                raise GraphIntegrityError(
                    "Relationship has no evidence"
                )

            if evidence not in document_text:
                raise GraphIntegrityError(
                    "Relationship evidence is not "
                    "present in source document"
                )

    def ingest(
        self,
        *,
        context: RequestContext,
        document_id: str,
        document_text: str,
    ) -> GraphIngestionResult:

        if "Graph.Ingest" not in context.roles:
            raise GraphIntegrityError(
                "Dedicated graph ingestion role required"
            )

        if not document_id.strip():
            raise GraphIntegrityError(
                "Missing document ID"
            )

        if not document_text.strip():
            raise GraphIntegrityError(
                "Empty document text"
            )

        extraction = self.extractor.extract(
            document_text=document_text,
        )

        self._validate(
            extraction,
            document_text,
        )

        # Tenant and document provenance are supplied
        # by the trusted workflow, never the extractor.
        for entity in extraction.entities:
            self.graph.add_entity(
                context,
                GraphEntity(
                    entity_id=entity.entity_id,
                    tenant_id=context.tenant_id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                    source_document_id=document_id,
                ),
            )

        for relationship in extraction.relationships:
            self.graph.add_relationship(
                context,
                GraphRelationship(
                    relationship_id=relationship.relationship_id,
                    tenant_id=context.tenant_id,
                    source_entity_id=relationship.source_entity_id,
                    target_entity_id=relationship.target_entity_id,
                    relationship_type=relationship.relationship_type,
                    source_document_id=document_id,
                ),
            )

        return GraphIngestionResult(
            entities_written=len(extraction.entities),
            relationships_written=len(extraction.relationships),
        )