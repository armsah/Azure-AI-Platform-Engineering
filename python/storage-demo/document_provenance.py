import hashlib
import threading
from dataclasses import dataclass
from datetime import datetime, timezone


class ProvenanceError(Exception):
    pass


class ProvenanceConflict(ProvenanceError):
    pass


class ProvenanceIntegrityError(ProvenanceError):
    pass


class ProvenanceAccessDenied(ProvenanceError):
    pass


@dataclass(frozen=True)
class DocumentVersionManifest:
    tenant_id: str
    document_id: str
    version: int
    content_sha256: str
    size_bytes: int
    created_at: datetime


@dataclass(frozen=True)
class VerifiedDocumentVersion:
    manifest: DocumentVersionManifest
    is_current: bool


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class DocumentProvenanceRegistry:
    def __init__(self):
        self._lock = threading.RLock()

        self._versions: dict[
            tuple[str, str, int],
            DocumentVersionManifest,
        ] = {}

        self._current: dict[
            tuple[str, str],
            int,
        ] = {}

        self._revoked: set[
            tuple[str, str, int]
        ] = set()

    def register(
        self,
        *,
        tenant_id: str,
        document_id: str,
        version: int,
        content: bytes,
    ) -> DocumentVersionManifest:

        if not tenant_id.strip():
            raise ProvenanceIntegrityError(
                "Missing tenant ID"
            )

        if not document_id.strip():
            raise ProvenanceIntegrityError(
                "Missing document ID"
            )

        if version <= 0:
            raise ProvenanceIntegrityError(
                "Document version must be positive"
            )

        if not isinstance(content, bytes):
            raise ProvenanceIntegrityError(
                "Document content must be bytes"
            )

        key = (
            tenant_id,
            document_id,
            version,
        )

        manifest = DocumentVersionManifest(
            tenant_id=tenant_id,
            document_id=document_id,
            version=version,
            content_sha256=sha256_bytes(content),
            size_bytes=len(content),
            created_at=datetime.now(timezone.utc),
        )

        with self._lock:
            if key in self._versions:
                raise ProvenanceConflict(
                    "Document version already registered"
                )

            document_key = (
                tenant_id,
                document_id,
            )

            current_version = self._current.get(
                document_key,
                0,
            )

            if version <= current_version:
                raise ProvenanceConflict(
                    "Version must increase monotonically"
                )

            self._versions[key] = manifest

            self._current[document_key] = version

        return manifest

    def get_manifest(
        self,
        *,
        tenant_id: str,
        document_id: str,
        version: int,
    ) -> DocumentVersionManifest:

        key = (
            tenant_id,
            document_id,
            version,
        )

        with self._lock:
            manifest = self._versions.get(key)

        if manifest is None:
            raise ProvenanceIntegrityError(
                "Document version not found"
            )

        return manifest

    def revoke(
        self,
        *,
        tenant_id: str,
        document_id: str,
        version: int,
    ) -> None:

        key = (
            tenant_id,
            document_id,
            version,
        )

        with self._lock:
            if key not in self._versions:
                raise ProvenanceIntegrityError(
                    "Cannot revoke missing version"
                )

            self._revoked.add(key)

    def verify(
        self,
        *,
        tenant_id: str,
        document_id: str,
        version: int,
        content: bytes,
        require_current: bool = True,
    ) -> VerifiedDocumentVersion:

        if not isinstance(content, bytes):
            raise ProvenanceIntegrityError(
                "Content must be bytes"
            )

        key = (
            tenant_id,
            document_id,
            version,
        )

        document_key = (
            tenant_id,
            document_id,
        )

        with self._lock:
            manifest = self._versions.get(key)

            if manifest is None:
                raise ProvenanceIntegrityError(
                    "Document version not found"
                )

            if key in self._revoked:
                raise ProvenanceIntegrityError(
                    "Document version revoked"
                )

            current_version = self._current.get(
                document_key
            )

            is_current = (
                current_version == version
            )

            if require_current and not is_current:
                raise ProvenanceIntegrityError(
                    "Stale document version"
                )

            if len(content) != manifest.size_bytes:
                raise ProvenanceIntegrityError(
                    "Document size mismatch"
                )

            if (
                sha256_bytes(content)
                != manifest.content_sha256
            ):
                raise ProvenanceIntegrityError(
                    "Document digest mismatch"
                )

            return VerifiedDocumentVersion(
                manifest=manifest,
                is_current=is_current,
            )
            
    def assert_eligible(
        self,
        *,
        tenant_id: str,
        document_id: str,
        version: int,
    ) -> None:
        key = (
            tenant_id,
            document_id,
            version,
        )

        with self._lock:
            if key not in self._versions:
                raise ProvenanceIntegrityError(
                    "Document version not found"
                )

            if key in self._revoked:
                raise ProvenanceIntegrityError(
                    "Document version revoked"
                )

            current = self._current.get(
                (tenant_id, document_id)
            )

            if current != version:
                raise ProvenanceIntegrityError(
                    "Document version is stale"
                )