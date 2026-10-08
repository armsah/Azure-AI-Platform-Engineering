import pytest

from document_ingestion import IngestionStatus
from document_ingestion_service import DocumentIngestionService
from document_ingestion_pipeline import (
    DocumentIngestionPipeline,
    IngestionPipelineError,
)
from document_lifecycle import DocumentLifecycleStore
from document_search_index import InMemorySearchIndex
from ingestion_idempotency import IngestionIdempotencyStore
from tenant_document_storage import TenantDocumentStorage


class FakeEmbeddingProvider:
    def embed(self, texts):
        return [
            [0.1, 0.2, 0.3]
            for _ in texts
        ]


class FailingSearchIndex(InMemorySearchIndex):
    def __init__(self, failures):
        super().__init__()
        self.failures = failures
        self.calls = 0

    def upsert(self, documents):
        self.calls += 1

        if self.calls <= self.failures:
            raise RuntimeError("Temporary indexing failure")

        super().upsert(documents)


def build_pipeline(index=None, max_attempts=3):
    storage = TenantDocumentStorage()
    lifecycle = DocumentLifecycleStore()
    search_index = (
        index
        if index is not None
        else InMemorySearchIndex()
    )

    service = DocumentIngestionService(
        storage,
        lifecycle,
    )

    pipeline = DocumentIngestionPipeline(
        storage=storage,
        lifecycle=lifecycle,
        embedding_provider=FakeEmbeddingProvider(),
        search_index=search_index,
        idempotency=IngestionIdempotencyStore(),
        expected_dimensions=3,
        max_attempts=max_attempts,
    )

    return service, pipeline, lifecycle, search_index


def test_complete_ingestion_pipeline():
    service, pipeline, lifecycle, index = build_pipeline()

    record = service.upload(
        "customer-a",
        "architecture.txt",
        b"Azure AI platform architecture",
        "text/plain",
    )

    result = pipeline.process(
        "customer-a",
        record.document_id,
    )

    assert not result.duplicate
    assert result.chunk_count == 1

    updated = lifecycle.get(
        "customer-a",
        record.document_id,
    )

    assert updated.status == IngestionStatus.INDEXED
    assert len(index.list_for_tenant("customer-a")) == 1


def test_completed_ingestion_is_idempotent():
    service, pipeline, _, index = build_pipeline()

    first = service.upload(
        "customer-a",
        "notes.txt",
        b"same content",
        "text/plain",
    )

    first_result = pipeline.process(
        "customer-a",
        first.document_id,
    )

    second = service.upload(
        "customer-a",
        "duplicate.txt",
        b"same content",
        "text/plain",
    )

    second_result = pipeline.process(
        "customer-a",
        second.document_id,
    )

    assert not first_result.duplicate
    assert second_result.duplicate
    assert second_result.document_id == first.document_id
    assert len(index.list_for_tenant("customer-a")) == 1


def test_cross_tenant_processing_rejected():
    service, pipeline, _, _ = build_pipeline()

    record = service.upload(
        "customer-a",
        "private.txt",
        b"private tenant content",
        "text/plain",
    )

    with pytest.raises(Exception):
        pipeline.process(
            "customer-b",
            record.document_id,
        )


def test_quarantined_document_cannot_be_processed():
    service, pipeline, _, _ = build_pipeline()

    record = service.upload(
        "customer-a",
        "suspicious.txt",
        b"potentially unsafe",
        "text/plain",
    )

    service.quarantine(
        "customer-a",
        record.document_id,
    )

    with pytest.raises(IngestionPipelineError):
        pipeline.process(
            "customer-a",
            record.document_id,
        )


def test_indexing_retries_then_succeeds():
    index = FailingSearchIndex(failures=2)

    service, pipeline, lifecycle, _ = build_pipeline(
        index=index,
        max_attempts=3,
    )

    record = service.upload(
        "customer-a",
        "retry.txt",
        b"retry example",
        "text/plain",
    )

    pipeline.process(
        "customer-a",
        record.document_id,
    )

    assert index.calls == 3
    assert lifecycle.get(
        "customer-a",
        record.document_id,
    ).status == IngestionStatus.INDEXED


def test_exhausted_retries_mark_document_failed():
    index = FailingSearchIndex(failures=10)

    service, pipeline, lifecycle, _ = build_pipeline(
        index=index,
        max_attempts=2,
    )

    record = service.upload(
        "customer-a",
        "failure.txt",
        b"indexing will fail",
        "text/plain",
    )

    with pytest.raises(IngestionPipelineError):
        pipeline.process(
            "customer-a",
            record.document_id,
        )

    assert index.calls == 2
    assert lifecycle.get(
        "customer-a",
        record.document_id,
    ).status == IngestionStatus.FAILED


def test_failed_document_can_be_retried():
    index = FailingSearchIndex(failures=1)

    service, pipeline, lifecycle, _ = build_pipeline(
        index=index,
        max_attempts=1,
    )

    record = service.upload(
        "customer-a",
        "recover.txt",
        b"recoverable content",
        "text/plain",
    )

    with pytest.raises(IngestionPipelineError):
        pipeline.process(
            "customer-a",
            record.document_id,
        )

    result = pipeline.process(
        "customer-a",
        record.document_id,
    )

    assert not result.duplicate
    assert lifecycle.get(
        "customer-a",
        record.document_id,
    ).status == IngestionStatus.INDEXED


def test_identical_content_in_different_tenants_isolated():
    service, pipeline, _, index = build_pipeline()

    first = service.upload(
        "customer-a",
        "shared.txt",
        b"identical bytes",
        "text/plain",
    )

    second = service.upload(
        "customer-b",
        "shared.txt",
        b"identical bytes",
        "text/plain",
    )

    pipeline.process("customer-a", first.document_id)
    pipeline.process("customer-b", second.document_id)

    assert len(index.list_for_tenant("customer-a")) == 1
    assert len(index.list_for_tenant("customer-b")) == 1

    assert (
        index.list_for_tenant("customer-a")[0].chunk_id
        != index.list_for_tenant("customer-b")[0].chunk_id
    )