from datetime import datetime, timezone

from document_ingestion import (
    IngestionStatus,
    validate_document,
)
from document_lifecycle import (
    DocumentLifecycleStore,
    DocumentRecord,
)
from tenant_document_storage import (
    TenantDocumentStorage,
)


class DocumentIngestionService:
    def __init__(
        self,
        storage: TenantDocumentStorage,
        lifecycle: DocumentLifecycleStore,
    ):
        self.storage = storage
        self.lifecycle = lifecycle

    def upload(
        self,
        tenant_id: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> DocumentRecord:

        document = validate_document(
            tenant_id=tenant_id,
            filename=filename,
            content=content,
            content_type=content_type,
        )

        storage_key = self.storage.put(
            tenant_id,
            document,
        )

        now = datetime.now(timezone.utc)

        record = DocumentRecord(
            document_id=document.document_id,
            tenant_id=tenant_id,
            filename=document.filename,
            content_hash=document.content_hash,
            storage_key=storage_key,
            status=IngestionStatus.VALIDATED,
            created_at=now,
            updated_at=now,
        )

        self.lifecycle.create(record)

        return self.lifecycle.transition(
            tenant_id=tenant_id,
            document_id=document.document_id,
            new_status=IngestionStatus.STORED,
            expected_version=record.version,
        )

    def quarantine(
        self,
        tenant_id: str,
        document_id: str,
    ) -> DocumentRecord:

        record = self.lifecycle.get(
            tenant_id,
            document_id,
        )

        return self.lifecycle.transition(
            tenant_id=tenant_id,
            document_id=document_id,
            new_status=IngestionStatus.QUARANTINED,
            expected_version=record.version,
        )