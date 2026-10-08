from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import RLock

from document_ingestion import IngestionStatus


class DocumentNotFound(Exception):
    pass


class InvalidDocumentTransition(Exception):
    pass


class DocumentAccessDenied(Exception):
    pass


ALLOWED_TRANSITIONS = {
    IngestionStatus.RECEIVED: {
        IngestionStatus.VALIDATED,
        IngestionStatus.QUARANTINED,
    },
    IngestionStatus.VALIDATED: {
        IngestionStatus.STORED,
        IngestionStatus.QUARANTINED,
    },
    IngestionStatus.STORED: {
        IngestionStatus.PROCESSING,
        IngestionStatus.QUARANTINED,
    },
    IngestionStatus.PROCESSING: {
        IngestionStatus.INDEXED,
        IngestionStatus.FAILED,
        IngestionStatus.QUARANTINED,
    },
    IngestionStatus.FAILED: {
        IngestionStatus.PROCESSING,
        IngestionStatus.QUARANTINED,
    },
    IngestionStatus.INDEXED: set(),
    IngestionStatus.QUARANTINED: set(),
}


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    tenant_id: str
    filename: str
    content_hash: str
    storage_key: str
    status: IngestionStatus
    created_at: datetime
    updated_at: datetime
    version: int = 1


class DocumentLifecycleStore:
    def __init__(self):
        self._records: dict[tuple[str, str], DocumentRecord] = {}
        self._lock = RLock()

    def create(self, record: DocumentRecord) -> None:
        key = (record.tenant_id, record.document_id)

        with self._lock:
            if key in self._records:
                raise ValueError("Document already exists")

            self._records[key] = record

    def get(self, tenant_id: str, document_id: str) -> DocumentRecord:
        with self._lock:
            record = self._records.get((tenant_id, document_id))

            if record is None:
                raise DocumentNotFound("Document not found")

            return record

    def transition(
        self,
        tenant_id: str,
        document_id: str,
        new_status: IngestionStatus,
        expected_version: int,
    ) -> DocumentRecord:

        with self._lock:
            current = self.get(tenant_id, document_id)

            if current.version != expected_version:
                raise InvalidDocumentTransition(
                    "Document version conflict"
                )

            allowed = ALLOWED_TRANSITIONS[current.status]

            if new_status not in allowed:
                raise InvalidDocumentTransition(
                    f"Invalid transition: "
                    f"{current.status.value} → {new_status.value}"
                )

            updated = replace(
                current,
                status=new_status,
                updated_at=datetime.now(timezone.utc),
                version=current.version + 1,
            )

            self._records[(tenant_id, document_id)] = updated

            return updated