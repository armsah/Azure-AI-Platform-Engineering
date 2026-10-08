from dataclasses import dataclass

from chunk_provenance import ExtractionManifest
from graph_relationship_provenance import (
    GraphRelationshipProvenance,
)
from graph_relationship_verifier import (
    GraphRelationshipVerifier,
    VerifiedGraphRelationship,
)
from request_context import RequestContext


@dataclass(frozen=True)
class GraphEvidenceCandidate:
    relationship: GraphRelationshipProvenance
    extraction: ExtractionManifest
    source_bytes: bytes
    extracted_text: str


@dataclass(frozen=True)
class VerifiedGraphEvidence:
    relationship_id: str
    tenant_id: str
    document_id: str
    document_version: int
    statement: str
    evidence_text: str
    source_sha256: str


class VerifiedGraphEvidenceService:
    def __init__(
        self,
        *,
        verifier: GraphRelationshipVerifier,
    ):
        self.verifier = verifier

    def verify_candidate(
        self,
        *,
        context: RequestContext,
        candidate: GraphEvidenceCandidate,
    ) -> VerifiedGraphEvidence:

        verified = self.verifier.verify(
            context=context,
            relationship=candidate.relationship,
            extraction=candidate.extraction,
            source_bytes=candidate.source_bytes,
            extracted_text=candidate.extracted_text,
            require_current=True,
        )

        statement = (
            f"{verified.source_entity_id} "
            f"{verified.relationship_type} "
            f"{verified.target_entity_id}"
        )

        return VerifiedGraphEvidence(
            relationship_id=verified.relationship_id,
            tenant_id=verified.tenant_id,
            document_id=verified.document_id,
            document_version=verified.document_version,
            statement=statement,
            evidence_text=verified.evidence_text,
            source_sha256=verified.source_sha256,
        )