from dataclasses import dataclass

from chunk_provenance import (
    ChunkProvenance,
    ExtractionManifest,
)
from chunk_provenance_verifier import (
    ChunkProvenanceVerifier,
    VerifiedChunk,
)
from request_context import RequestContext


@dataclass(frozen=True)
class CandidateChunk:
    extraction: ExtractionManifest
    provenance: ChunkProvenance
    text: str


class VerifiedRAGEvidenceService:
    def __init__(
        self,
        *,
        verifier: ChunkProvenanceVerifier,
    ):
        self.verifier = verifier

    def verify_candidate(
        self,
        *,
        context: RequestContext,
        source_bytes: bytes,
        extracted_text: str,
        candidate: CandidateChunk,
    ) -> VerifiedChunk:

        return self.verifier.verify(
            context=context,
            source_bytes=source_bytes,
            extracted_text=extracted_text,
            extraction=candidate.extraction,
            chunk=candidate.provenance,
            chunk_text=candidate.text,
            require_current=True,
        )