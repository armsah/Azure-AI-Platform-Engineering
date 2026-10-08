import math
import threading
from dataclasses import dataclass
from enum import Enum


class MultimodalSearchError(Exception):
    pass


class SearchDocumentConflict(MultimodalSearchError):
    pass


class SearchModality(str, Enum):
    TEXT = "text"
    IMAGE = "image"


@dataclass(frozen=True)
class MultimodalSearchDocument:
    search_id: str
    tenant_id: str

    modality: SearchModality

    resource_id: str
    resource_version: int
    source_sha256: str

    text: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class MultimodalSearchHit:
    document: MultimodalSearchDocument
    score: float


def cosine_similarity(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> float:

    if len(left) != len(right):
        raise MultimodalSearchError(
            "Embedding dimensions do not match"
        )

    if not left:
        raise MultimodalSearchError(
            "Empty embedding"
        )

    if not all(
        math.isfinite(value)
        for value in left + right
    ):
        raise MultimodalSearchError(
            "Embedding contains non-finite values"
        )

    left_norm = math.sqrt(
        sum(value * value for value in left)
    )

    right_norm = math.sqrt(
        sum(value * value for value in right)
    )

    if left_norm == 0 or right_norm == 0:
        raise MultimodalSearchError(
            "Zero-length embedding vector"
        )

    return sum(
        a * b
        for a, b in zip(left, right, strict=True)
    ) / (left_norm * right_norm)


class InMemoryMultimodalSearchIndex:
    def __init__(self):
        self._lock = threading.RLock()

        self._documents: dict[
            tuple[str, str],
            MultimodalSearchDocument,
        ] = {}

    def upsert(
        self,
        document: MultimodalSearchDocument,
    ) -> None:

        if not document.tenant_id.strip():
            raise MultimodalSearchError(
                "Missing tenant ID"
            )

        if not document.search_id.strip():
            raise MultimodalSearchError(
                "Missing search ID"
            )

        if not document.resource_id.strip():
            raise MultimodalSearchError(
                "Missing resource ID"
            )

        if document.resource_version <= 0:
            raise MultimodalSearchError(
                "Invalid resource version"
            )

        if not document.text.strip():
            raise MultimodalSearchError(
                "Empty searchable text"
            )

        if not document.vector:
            raise MultimodalSearchError(
                "Empty embedding"
            )

        if not all(
            math.isfinite(value)
            for value in document.vector
        ):
            raise MultimodalSearchError(
                "Invalid embedding"
            )

        key = (
            document.tenant_id,
            document.search_id,
        )

        with self._lock:
            existing = self._documents.get(key)

            if (
                existing is not None
                and existing != document
            ):
                raise SearchDocumentConflict(
                    "Search ID already identifies "
                    "different content"
                )

            self._documents[key] = document

    def search(
        self,
        *,
        tenant_id: str,
        query_vector: tuple[float, ...],
        top_k: int = 10,
    ) -> tuple[MultimodalSearchHit, ...]:

        if top_k <= 0:
            raise MultimodalSearchError(
                "top_k must be positive"
            )

        with self._lock:
            # Tenant filtering occurs BEFORE scoring.
            candidates = [
                document
                for document in self._documents.values()
                if document.tenant_id == tenant_id
            ]

        hits = [
            MultimodalSearchHit(
                document=document,
                score=cosine_similarity(
                    query_vector,
                    document.vector,
                ),
            )
            for document in candidates
        ]

        hits.sort(
            key=lambda hit: (
                -hit.score,
                hit.document.search_id,
            )
        )

        return tuple(hits[:top_k])