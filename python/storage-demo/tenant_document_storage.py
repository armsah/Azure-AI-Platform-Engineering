import re

from threading import RLock

from document_ingestion import ValidatedDocument
from document_lifecycle import DocumentNotFound


class StorageAccessDenied(Exception):
    pass


class StorageConflict(Exception):
    pass


TENANT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def validate_tenant_id(tenant_id: str) -> str:
    if not TENANT_ID_PATTERN.fullmatch(tenant_id):
        raise StorageAccessDenied("Invalid tenant identifier")

    return tenant_id


def document_storage_key(
    tenant_id: str,
    document_id: str,
) -> str:

    tenant = validate_tenant_id(tenant_id)

    if not re.fullmatch(
        r"[a-f0-9-]{36}",
        document_id,
    ):
        raise StorageAccessDenied("Invalid document identifier")

    return f"tenants/{tenant}/documents/{document_id}/original"


class TenantDocumentStorage:
    def __init__(self):
        self._objects: dict[str, bytes] = {}
        self._lock = RLock()

    def put(
        self,
        tenant_id: str,
        document: ValidatedDocument,
    ) -> str:

        if tenant_id != document.tenant_id:
            raise StorageAccessDenied(
                "Tenant mismatch"
            )

        key = document_storage_key(
            tenant_id,
            document.document_id,
        )

        with self._lock:
            if key in self._objects:
                raise StorageConflict(
                    "Document already stored"
                )

            self._objects[key] = document.content

        return key

    def get(
        self,
        tenant_id: str,
        document_id: str,
    ) -> bytes:

        key = document_storage_key(
            tenant_id,
            document_id,
        )

        with self._lock:
            content = self._objects.get(key)

            if content is None:
                raise DocumentNotFound(
                    "Document not found"
                )

            return content