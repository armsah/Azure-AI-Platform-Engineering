from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EntityProposal:
    entity_id: str
    name: str
    entity_type: str


@dataclass(frozen=True)
class RelationshipProposal:
    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    evidence_text: str


@dataclass(frozen=True)
class GraphExtraction:
    entities: tuple[EntityProposal, ...]
    relationships: tuple[RelationshipProposal, ...]


class GraphExtractor(Protocol):
    def extract(
        self,
        *,
        document_text: str,
    ) -> GraphExtraction:
        ...