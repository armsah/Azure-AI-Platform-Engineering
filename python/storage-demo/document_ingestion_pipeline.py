import time

from dataclasses import dataclass

from document_chunking import chunk_document
from document_embeddings import EmbeddingProvider, embed_chunks
from document_extraction import extract_text
from document_ingestion import IngestionStatus
from document_lifecycle import DocumentLifecycleStore
from document_search_index import (
    SearchIndex,
    prepare_search_documents,
)
from ingestion_idempotency import (
    IngestionIdempotencyStore,
    ingestion_key,
)
from tenant_document_storage import TenantDocumentStorage


class IngestionPipelineError(Exception):
    pass


@dataclass(frozen=True)
class IngestionResult:
    document_id: str
    tenant_id: str
    chunk_count: int
    duplicate: bool


class DocumentIngestionPipeline:
    def __init__(
        self,
        *,
        storage: TenantDocumentStorage,
        lifecycle: DocumentLifecycleStore,
        embedding_provider: EmbeddingProvider,
        search_index: SearchIndex,
        idempotency: IngestionIdempotencyStore,
        expected_dimensions: int,
        max_attempts: int = 3,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

        self.storage = storage
        self.lifecycle = lifecycle
        self.embedding_provider = embedding_provider
        self.search_index = search_index
        self.idempotency = idempotency
        self.expected_dimensions = expected_dimensions
        self.max_attempts = max_attempts

    def process(
        self,
        tenant_id: str,
        document_id: str,
    ) -> IngestionResult:

        record = self.lifecycle.get(
            tenant_id,
            document_id,
        )

        key = ingestion_key(
            tenant_id,
            record.content_hash,
        )

        completed = self.idempotency.get_completed(key)

        if completed is not None:
            return IngestionResult(
                document_id=completed,
                tenant_id=tenant_id,
                chunk_count=0,
                duplicate=True,
            )

        if record.status not in {
            IngestionStatus.STORED,
            IngestionStatus.FAILED,
        }:
            raise IngestionPipelineError(
                "Document is not eligible for processing"
            )

        record = self.lifecycle.transition(
            tenant_id,
            document_id,
            IngestionStatus.PROCESSING,
            expected_version=record.version,
        )

        try:
            content = self.storage.get(
                tenant_id,
                document_id,
            )

            text = extract_text(
                content,
                self._content_type(record.filename),
            )

            chunks = chunk_document(
                tenant_id=tenant_id,
                document_id=document_id,
                content_hash=record.content_hash,
                text=text,
            )

            embedded = embed_chunks(
                chunks,
                self.embedding_provider,
                self.expected_dimensions,
            )

            search_documents = prepare_search_documents(
                embedded,
                tenant_id=tenant_id,
                document_id=document_id,
            )

            self._index_with_retry(search_documents)

            indexed = self.lifecycle.transition(
                tenant_id,
                document_id,
                IngestionStatus.INDEXED,
                expected_version=record.version,
            )

            self.idempotency.mark_completed(
                key,
                indexed.document_id,
            )

            return IngestionResult(
                document_id=indexed.document_id,
                tenant_id=tenant_id,
                chunk_count=len(search_documents),
                duplicate=False,
            )

        except Exception as exc:
            current = self.lifecycle.get(
                tenant_id,
                document_id,
            )

            if current.status == IngestionStatus.PROCESSING:
                self.lifecycle.transition(
                    tenant_id,
                    document_id,
                    IngestionStatus.FAILED,
                    expected_version=current.version,
                )

            raise IngestionPipelineError(
                "Document ingestion failed"
            ) from exc

    def _index_with_retry(self, documents):
        for attempt in range(self.max_attempts):
            try:
                self.search_index.upsert(documents)
                return

            except Exception:
                if attempt == self.max_attempts - 1:
                    raise

                time.sleep(
                    min(0.1 * (2 ** attempt), 1.0)
                )

    @staticmethod
    def _content_type(filename: str) -> str:
        filename = filename.lower()

        if filename.endswith(".pdf"):
            return "application/pdf"

        if filename.endswith(".md"):
            return "text/markdown"

        if filename.endswith(".txt"):
            return "text/plain"

        raise IngestionPipelineError(
            "Unsupported document format"
        )