from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from document_embeddings import EmbeddedChunk


class SearchIndexError(Exception):
    pass


@dataclass(frozen=True)
class SearchDocument:
    chunk_id: str
    tenant_id: str
    document_id: str
    content_hash: str
    chunk_index: int
    content: str
    vector: tuple[float, ...]


class SearchIndex(Protocol):
    def upsert(self, documents: list[SearchDocument]) -> None:
        ...


def prepare_search_documents(
    embedded_chunks: list[EmbeddedChunk],
    *,
    tenant_id: str,
    document_id: str,
) -> list[SearchDocument]:

    documents = []

    for item in embedded_chunks:
        chunk = item.chunk

        if (
            chunk.tenant_id != tenant_id
            or chunk.document_id != document_id
        ):
            raise SearchIndexError(
                "Document ownership mismatch"
            )

        documents.append(
            SearchDocument(
                chunk_id=chunk.chunk_id,
                tenant_id=chunk.tenant_id,
                document_id=chunk.document_id,
                content_hash=chunk.content_hash,
                chunk_index=chunk.chunk_index,
                content=chunk.text,
                vector=item.vector,
            )
        )

    return documents


class InMemorySearchIndex:
    def __init__(self):
        self._documents: dict[str, SearchDocument] = {}
        self._lock = RLock()

    def upsert(self, documents: list[SearchDocument]) -> None:
        with self._lock:
            for document in documents:
                existing = self._documents.get(document.chunk_id)

                if existing is not None and (
                    existing.tenant_id != document.tenant_id
                    or existing.document_id != document.document_id
                ):
                    raise SearchIndexError(
                        "Chunk identity collision"
                    )

            for document in documents:
                self._documents[document.chunk_id] = document

    def list_for_tenant(
        self,
        tenant_id: str,
    ) -> list[SearchDocument]:

        with self._lock:
            return [
                document
                for document in self._documents.values()
                if document.tenant_id == tenant_id
            ]