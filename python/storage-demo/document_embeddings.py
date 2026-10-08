from dataclasses import dataclass
from typing import Protocol

from document_chunking import DocumentChunk


class EmbeddingError(Exception):
    pass


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk: DocumentChunk
    vector: tuple[float, ...]


def embed_chunks(
    chunks: list[DocumentChunk],
    provider: EmbeddingProvider,
    expected_dimensions: int,
) -> list[EmbeddedChunk]:

    if expected_dimensions <= 0:
        raise EmbeddingError(
            "Embedding dimensions must be positive"
        )

    if not chunks:
        return []

    tenant_ids = {chunk.tenant_id for chunk in chunks}

    if len(tenant_ids) != 1:
        raise EmbeddingError(
            "Cross-tenant embedding batches are prohibited"
        )

    vectors = provider.embed(
        [chunk.text for chunk in chunks]
    )

    if len(vectors) != len(chunks):
        raise EmbeddingError(
            "Embedding count mismatch"
        )

    embedded = []

    for chunk, vector in zip(chunks, vectors):
        if len(vector) != expected_dimensions:
            raise EmbeddingError(
                "Unexpected embedding dimensions"
            )

        embedded.append(
            EmbeddedChunk(
                chunk=chunk,
                vector=tuple(vector),
            )
        )

    return embedded