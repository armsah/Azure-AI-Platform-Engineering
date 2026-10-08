from dataclasses import dataclass

from chunk_provenance import (
    CHUNK_PROVENANCE_VERSION,
    ChunkProvenance,
    ExtractionManifest,
    create_chunk_provenance,
    sha256_text,
)
from document_provenance import (
    ProvenanceIntegrityError,
    sha256_bytes,
)
from provenance_authorization import (
    AuthorizedProvenanceService,
)
from request_context import RequestContext


@dataclass(frozen=True)
class VerifiedChunk:
    chunk_id: str
    tenant_id: str
    document_id: str
    document_version: int
    text: str
    start_char: int
    end_char: int
    extraction_version: str
    source_sha256: str


class ChunkProvenanceVerifier:
    def __init__(
        self,
        *,
        provenance_service: AuthorizedProvenanceService,
    ):
        self.provenance_service = (
            provenance_service
        )

    def verify(
        self,
        *,
        context: RequestContext,
        source_bytes: bytes,
        extracted_text: str,
        extraction: ExtractionManifest,
        chunk: ChunkProvenance,
        chunk_text: str,
        require_current: bool = True,
    ) -> VerifiedChunk:

        if (
            extraction.tenant_id
            != context.tenant_id
            or chunk.tenant_id
            != context.tenant_id
        ):
            raise ProvenanceIntegrityError(
                "Cross-tenant provenance"
            )

        if (
            chunk.document_id
            != extraction.document_id
            or chunk.document_version
            != extraction.document_version
        ):
            raise ProvenanceIntegrityError(
                "Document lineage mismatch"
            )

        if (
            chunk.extraction_version
            != extraction.extraction_version
        ):
            raise ProvenanceIntegrityError(
                "Extraction version mismatch"
            )

        if (
            chunk.extraction_sha256
            != extraction.extracted_text_sha256
        ):
            raise ProvenanceIntegrityError(
                "Extraction lineage mismatch"
            )

        if (
            chunk.provenance_version
            != CHUNK_PROVENANCE_VERSION
        ):
            raise ProvenanceIntegrityError(
                "Unsupported provenance version"
            )

        verified_source = (
            self.provenance_service.verify_document(
                context=context,
                document_id=extraction.document_id,
                version=extraction.document_version,
                content=source_bytes,
                require_current=require_current,
            )
        )

        source_manifest = (
            verified_source.manifest
        )

        if (
            extraction.source_sha256
            != source_manifest.content_sha256
        ):
            raise ProvenanceIntegrityError(
                "Source lineage mismatch"
            )

        if (
            sha256_bytes(source_bytes)
            != extraction.source_sha256
        ):
            raise ProvenanceIntegrityError(
                "Source digest mismatch"
            )

        if (
            len(extracted_text)
            != extraction.extracted_text_length
        ):
            raise ProvenanceIntegrityError(
                "Extraction length mismatch"
            )

        if (
            sha256_text(extracted_text)
            != extraction.extracted_text_sha256
        ):
            raise ProvenanceIntegrityError(
                "Extraction digest mismatch"
            )

        if (
            chunk.start_char < 0
            or chunk.end_char <= chunk.start_char
            or chunk.end_char > len(extracted_text)
        ):
            raise ProvenanceIntegrityError(
                "Invalid chunk span"
            )

        expected_text = extracted_text[
            chunk.start_char:chunk.end_char
        ]

        if chunk_text != expected_text:
            raise ProvenanceIntegrityError(
                "Chunk text differs from source span"
            )

        if (
            sha256_text(chunk_text)
            != chunk.chunk_sha256
        ):
            raise ProvenanceIntegrityError(
                "Chunk digest mismatch"
            )

        expected_chunk = create_chunk_provenance(
            extraction=extraction,
            extracted_text=extracted_text,
            chunk_index=chunk.chunk_index,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
        )

        if expected_chunk != chunk:
            raise ProvenanceIntegrityError(
                "Chunk provenance identity mismatch"
            )

        return VerifiedChunk(
            chunk_id=chunk.chunk_id,
            tenant_id=context.tenant_id,
            document_id=chunk.document_id,
            document_version=chunk.document_version,
            text=chunk_text,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            extraction_version=(
                chunk.extraction_version
            ),
            source_sha256=(
                source_manifest.content_sha256
            ),
        )