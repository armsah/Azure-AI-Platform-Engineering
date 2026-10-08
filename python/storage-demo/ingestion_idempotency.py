import hashlib

from dataclasses import dataclass
from threading import RLock


PIPELINE_VERSION = "ingestion-v1"


@dataclass(frozen=True)
class IngestionIdentity:
    tenant_id: str
    content_hash: str
    pipeline_version: str


def ingestion_key(
    tenant_id: str,
    content_hash: str,
    pipeline_version: str = PIPELINE_VERSION,
) -> str:

    identity = (
        f"{tenant_id}:"
        f"{content_hash}:"
        f"{pipeline_version}"
    )

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()


class IngestionIdempotencyStore:
    def __init__(self):
        self._completed: dict[str, str] = {}
        self._lock = RLock()

    def get_completed(
        self,
        key: str,
    ) -> str | None:

        with self._lock:
            return self._completed.get(key)

    def mark_completed(
        self,
        key: str,
        document_id: str,
    ) -> None:

        with self._lock:
            self._completed[key] = document_id