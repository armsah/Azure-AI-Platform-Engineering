import hashlib
from dataclasses import dataclass

from document_provenance import (
    DocumentVersionManifest,
    ProvenanceIntegrityError,
    sha256_bytes,
)


CHUNK_PROVENANCE_VERSION = "chunk-provenance-v1"


def sha256_text(text: str) -> str:
    if not isinstance(text, str):
        raise ProvenanceIntegrityError(
            "Expected text"
        )

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ExtractionManifest:
    tenant_id: str
    document_id: str
    document_version: int
    source_sha256: str
    extraction_version: str
    extracted_text_sha256: str
    extracted_text_length: int


@dataclass(frozen=True)
class ChunkProvenance:
    tenant_id: str
    document_id: str
    document_version: int

    chunk_id: str
    chunk_index: int

    extraction_version: str
    extraction_sha256: str

    start_char: int
    end_char: int

    chunk_sha256: str
    provenance_version: str


def create_extraction_manifest(
    *,
    document_manifest: DocumentVersionManifest,
    extracted_text: str,
    extraction_version: str,
) -> ExtractionManifest:

    if not extraction_version.strip():
        raise ProvenanceIntegrityError(
            "Missing extraction version"
        )

    return ExtractionManifest(
        tenant_id=document_manifest.tenant_id,
        document_id=document_manifest.document_id,
        document_version=document_manifest.version,
        source_sha256=document_manifest.content_sha256,
        extraction_version=extraction_version,
        extracted_text_sha256=sha256_text(
            extracted_text
        ),
        extracted_text_length=len(extracted_text),
    )


def create_chunk_provenance(
    *,
    extraction: ExtractionManifest,
    extracted_text: str,
    chunk_index: int,
    start_char: int,
    end_char: int,
) -> ChunkProvenance:

    if chunk_index < 0:
        raise ProvenanceIntegrityError(
            "Invalid chunk index"
        )

    if (
        start_char < 0
        or end_char <= start_char
        or end_char > len(extracted_text)
    ):
        raise ProvenanceIntegrityError(
            "Invalid source span"
        )

    if (
        sha256_text(extracted_text)
        != extraction.extracted_text_sha256
    ):
        raise ProvenanceIntegrityError(
            "Extraction digest mismatch"
        )

    if (
        len(extracted_text)
        != extraction.extracted_text_length
    ):
        raise ProvenanceIntegrityError(
            "Extraction length mismatch"
        )

    chunk_text = extracted_text[
        start_char:end_char
    ]

    chunk_digest = sha256_text(
        chunk_text
    )

    identity = "|".join(
        (
            extraction.tenant_id,
            extraction.document_id,
            str(extraction.document_version),
            extraction.extraction_version,
            extraction.extracted_text_sha256,
            str(chunk_index),
            str(start_char),
            str(end_char),
            chunk_digest,
            CHUNK_PROVENANCE_VERSION,
        )
    )

    chunk_id = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()

    return ChunkProvenance(
        tenant_id=extraction.tenant_id,
        document_id=extraction.document_id,
        document_version=extraction.document_version,
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        extraction_version=extraction.extraction_version,
        extraction_sha256=(
            extraction.extracted_text_sha256
        ),
        start_char=start_char,
        end_char=end_char,
        chunk_sha256=chunk_digest,
        provenance_version=(
            CHUNK_PROVENANCE_VERSION
        ),
    )