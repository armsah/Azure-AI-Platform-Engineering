import hashlib

from dataclasses import dataclass


class ChunkingError(Exception):
    pass


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    tenant_id: str
    document_id: str
    content_hash: str
    chunk_index: int
    text: str


def chunk_document(
    *,
    tenant_id: str,
    document_id: str,
    content_hash: str,
    text: str,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[DocumentChunk]:

    if chunk_size <= 0:
        raise ChunkingError(
            "Chunk size must be positive"
        )

    if overlap < 0 or overlap >= chunk_size:
        raise ChunkingError(
            "Overlap must be smaller than chunk size"
        )

    if not text.strip():
        raise ChunkingError(
            "Cannot chunk empty text"
        )

    chunks = []
    start = 0
    index = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        chunk_text = text[start:end]

        identity = (
            f"{tenant_id}:"
            f"{document_id}:"
            f"{content_hash}:"
            f"{index}:"
            f"chunker-v1"
        )

        chunk_id = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()

        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                tenant_id=tenant_id,
                document_id=document_id,
                content_hash=content_hash,
                chunk_index=index,
                text=chunk_text,
            )
        )

        if end == len(text):
            break

        start = end - overlap
        index += 1

    return chunks