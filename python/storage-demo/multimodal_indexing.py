import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from image_vision import VisionDescription
from multimodal_search_index import (
    InMemoryMultimodalSearchIndex,
    MultimodalSearchDocument,
    SearchModality,
)


class MultimodalIndexingError(Exception):
    pass


class TextEmbeddingProvider(Protocol):
    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        ...


@dataclass(frozen=True)
class TextEvidenceRecord:
    tenant_id: str
    document_id: str
    document_version: int
    source_sha256: str
    chunk_id: str
    text: str


def _search_id(
    *,
    tenant_id: str,
    modality: SearchModality,
    resource_id: str,
    resource_version: int,
    evidence_id: str,
) -> str:

    payload = {
        "tenant_id": tenant_id,
        "modality": modality.value,
        "resource_id": resource_id,
        "resource_version": resource_version,
        "evidence_id": evidence_id,
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


class MultimodalIndexingService:
    def __init__(
        self,
        *,
        index: InMemoryMultimodalSearchIndex,
        embeddings: TextEmbeddingProvider,
    ):
        self.index = index
        self.embeddings = embeddings

    def _embed_one(
        self,
        text: str,
    ) -> tuple[float, ...]:

        vectors = self.embeddings.embed(
            [text]
        )

        if len(vectors) != 1:
            raise MultimodalIndexingError(
                "Expected exactly one embedding"
            )

        return tuple(vectors[0])

    def index_image_description(
        self,
        description: VisionDescription,
    ) -> MultimodalSearchDocument:

        if not description.description.strip():
            raise MultimodalIndexingError(
                "Empty image description"
            )

        search_id = _search_id(
            tenant_id=description.tenant_id,
            modality=SearchModality.IMAGE,
            resource_id=description.asset_id,
            resource_version=description.asset_version,
            evidence_id=description.sanitized_sha256,
        )

        document = MultimodalSearchDocument(
            search_id=search_id,
            tenant_id=description.tenant_id,
            modality=SearchModality.IMAGE,
            resource_id=description.asset_id,
            resource_version=description.asset_version,
            source_sha256=description.source_sha256,
            text=description.description,
            vector=self._embed_one(
                description.description
            ),
        )

        self.index.upsert(document)

        return document

    def index_text(
        self,
        record: TextEvidenceRecord,
    ) -> MultimodalSearchDocument:

        if not record.text.strip():
            raise MultimodalIndexingError(
                "Empty text evidence"
            )

        search_id = _search_id(
            tenant_id=record.tenant_id,
            modality=SearchModality.TEXT,
            resource_id=record.document_id,
            resource_version=record.document_version,
            evidence_id=record.chunk_id,
        )

        document = MultimodalSearchDocument(
            search_id=search_id,
            tenant_id=record.tenant_id,
            modality=SearchModality.TEXT,
            resource_id=record.document_id,
            resource_version=record.document_version,
            source_sha256=record.source_sha256,
            text=record.text,
            vector=self._embed_one(
                record.text
            ),
        )

        self.index.upsert(document)

        return document