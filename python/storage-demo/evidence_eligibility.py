from dataclasses import dataclass
from typing import Literal

from chunk_provenance_verifier import (
    ChunkProvenanceVerifier,
)
from document_provenance import ProvenanceError
from graph_relationship_verifier import (
    GraphRelationshipVerifier,
)
from request_context import RequestContext
from verified_rag_evidence import CandidateChunk
from graph_provenance_evidence import GraphEvidenceCandidate


EvidenceKind = Literal["chunk", "graph"]


class EvidenceEligibilityError(Exception):
    pass


@dataclass(frozen=True)
class EvidenceCandidate:
    kind: EvidenceKind
    payload: CandidateChunk | GraphEvidenceCandidate

    # For chunk candidates, these must come from
    # trusted version-specific storage.
    source_bytes: bytes | None = None
    extracted_text: str | None = None


@dataclass(frozen=True)
class EligibleEvidence:
    evidence_id: str
    kind: EvidenceKind
    tenant_id: str
    document_id: str
    document_version: int
    source_sha256: str
    text: str


class EvidenceEligibilityGate:
    def __init__(
        self,
        *,
        chunk_verifier: ChunkProvenanceVerifier,
        graph_verifier: GraphRelationshipVerifier,
    ):
        self.chunk_verifier = chunk_verifier
        self.graph_verifier = graph_verifier

    def verify(
        self,
        *,
        context: RequestContext,
        candidate: EvidenceCandidate,
    ) -> EligibleEvidence:

        try:
            if candidate.kind == "chunk":
                if not isinstance(
                    candidate.payload,
                    CandidateChunk,
                ):
                    raise EvidenceEligibilityError(
                        "Invalid chunk candidate"
                    )

                if (
                    candidate.source_bytes is None
                    or candidate.extracted_text is None
                ):
                    raise EvidenceEligibilityError(
                        "Missing trusted chunk source"
                    )

                verified = self.chunk_verifier.verify(
                    context=context,
                    source_bytes=candidate.source_bytes,
                    extracted_text=candidate.extracted_text,
                    extraction=candidate.payload.extraction,
                    chunk=candidate.payload.provenance,
                    chunk_text=candidate.payload.text,
                    require_current=True,
                )

                return EligibleEvidence(
                    evidence_id=verified.chunk_id,
                    kind="chunk",
                    tenant_id=verified.tenant_id,
                    document_id=verified.document_id,
                    document_version=verified.document_version,
                    source_sha256=verified.source_sha256,
                    text=verified.text,
                )

            if candidate.kind == "graph":
                if not isinstance(
                    candidate.payload,
                    GraphEvidenceCandidate,
                ):
                    raise EvidenceEligibilityError(
                        "Invalid graph candidate"
                    )

                verified = self.graph_verifier.verify(
                    context=context,
                    relationship=candidate.payload.relationship,
                    extraction=candidate.payload.extraction,
                    source_bytes=candidate.payload.source_bytes,
                    extracted_text=candidate.payload.extracted_text,
                    require_current=True,
                )

                statement = (
                    f"{verified.source_entity_id} "
                    f"{verified.relationship_type} "
                    f"{verified.target_entity_id}"
                )

                return EligibleEvidence(
                    evidence_id=verified.relationship_id,
                    kind="graph",
                    tenant_id=verified.tenant_id,
                    document_id=verified.document_id,
                    document_version=verified.document_version,
                    source_sha256=verified.source_sha256,
                    text=(
                        f"Graph claim: {statement}\n"
                        f"Source evidence: "
                        f"{verified.evidence_text}"
                    ),
                )

            raise EvidenceEligibilityError(
                "Unsupported evidence kind"
            )

        except ProvenanceError as exc:
            raise EvidenceEligibilityError(
                "Evidence provenance verification failed"
            ) from exc