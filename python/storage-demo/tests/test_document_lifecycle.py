from datetime import datetime, timezone

import pytest

from document_ingestion import IngestionStatus
from document_lifecycle import (
    DocumentLifecycleStore,
    DocumentNotFound,
    DocumentRecord,
    InvalidDocumentTransition,
)
from document_ingestion_service import DocumentIngestionService
from tenant_document_storage import (
    StorageAccessDenied,
    TenantDocumentStorage,
)


def make_record(
    tenant_id="customer-a",
    document_id="doc-1",
    status=IngestionStatus.STORED,
):
    now = datetime.now(timezone.utc)

    return DocumentRecord(
        document_id=document_id,
        tenant_id=tenant_id,
        filename="architecture.txt",
        content_hash="abc",
        storage_key="test-key",
        status=status,
        created_at=now,
        updated_at=now,
    )


def test_valid_lifecycle_transition():
    store = DocumentLifecycleStore()
    store.create(make_record())

    updated = store.transition(
        "customer-a",
        "doc-1",
        IngestionStatus.PROCESSING,
        expected_version=1,
    )

    assert updated.status == IngestionStatus.PROCESSING
    assert updated.version == 2


def test_rejects_invalid_transition():
    store = DocumentLifecycleStore()
    store.create(make_record())

    with pytest.raises(InvalidDocumentTransition):
        store.transition(
            "customer-a",
            "doc-1",
            IngestionStatus.INDEXED,
            expected_version=1,
        )


def test_rejects_stale_version():
    store = DocumentLifecycleStore()
    store.create(make_record())

    store.transition(
        "customer-a",
        "doc-1",
        IngestionStatus.PROCESSING,
        expected_version=1,
    )

    with pytest.raises(InvalidDocumentTransition):
        store.transition(
            "customer-a",
            "doc-1",
            IngestionStatus.INDEXED,
            expected_version=1,
        )


def test_tenant_cannot_access_another_tenants_document():
    store = DocumentLifecycleStore()
    store.create(make_record())

    with pytest.raises(DocumentNotFound):
        store.get("customer-b", "doc-1")


def test_quarantined_document_cannot_be_processed():
    store = DocumentLifecycleStore()
    store.create(
        make_record(
            status=IngestionStatus.QUARANTINED
        )
    )

    with pytest.raises(InvalidDocumentTransition):
        store.transition(
            "customer-a",
            "doc-1",
            IngestionStatus.PROCESSING,
            expected_version=1,
        )


def test_upload_creates_stored_document():
    service = DocumentIngestionService(
        TenantDocumentStorage(),
        DocumentLifecycleStore(),
    )

    record = service.upload(
        tenant_id="customer-a",
        filename="architecture.txt",
        content=b"Azure AI platform",
        content_type="text/plain",
    )

    assert record.status == IngestionStatus.STORED
    assert record.version == 2
    assert record.storage_key.startswith(
        "tenants/customer-a/documents/"
    )


def test_storage_rejects_tenant_mismatch():
    from document_ingestion import validate_document

    document = validate_document(
        "customer-a",
        "notes.txt",
        b"confidential",
        "text/plain",
    )

    storage = TenantDocumentStorage()

    with pytest.raises(StorageAccessDenied):
        storage.put(
            "customer-b",
            document,
        )


def test_storage_rejects_cross_tenant_read():
    from document_ingestion import validate_document

    document = validate_document(
        "customer-a",
        "notes.txt",
        b"confidential",
        "text/plain",
    )

    storage = TenantDocumentStorage()
    storage.put("customer-a", document)

    with pytest.raises(DocumentNotFound):
        storage.get(
            "customer-b",
            document.document_id,
        )


def test_quarantine_from_stored():
    service = DocumentIngestionService(
        TenantDocumentStorage(),
        DocumentLifecycleStore(),
    )

    record = service.upload(
        "customer-a",
        "notes.txt",
        b"potentially unsafe",
        "text/plain",
    )

    quarantined = service.quarantine(
        "customer-a",
        record.document_id,
    )

    assert quarantined.status == IngestionStatus.QUARANTINED


def test_quarantine_cannot_be_reversed():
    store = DocumentLifecycleStore()
    store.create(
        make_record(
            status=IngestionStatus.QUARANTINED
        )
    )

    with pytest.raises(InvalidDocumentTransition):
        store.transition(
            "customer-a",
            "doc-1",
            IngestionStatus.STORED,
            expected_version=1,
        )