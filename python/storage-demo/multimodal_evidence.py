import hashlib
import threading
from dataclasses import dataclass


class MultimodalEvidenceError(Exception):
    pass


class DescriptionConflict(MultimodalEvidenceError):
    pass


class DescriptionNotFound(MultimodalEvidenceError):
    pass


class DescriptionIntegrityError(MultimodalEvidenceError):
    pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ImageDescriptionRecord:
    tenant_id: str
    asset_id: str
    asset_version: int

    source_sha256: str
    sanitized_sha256: str

    description: str
    description_sha256: str

    provider: str
    model: str


class ImageDescriptionRegistry:
    """
    Immutable, tenant-scoped image-description records.

    A record identifies one description for one
    registered asset version.

    Registration is intentionally separate from
    asset authorization. Only a trusted ingestion
    workflow should receive write access.
    """

    def __init__(self):
        self._lock = threading.RLock()

        self._records: dict[
            tuple[str, str, int],
            ImageDescriptionRecord,
        ] = {}

    def register(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        asset_version: int,
        source_sha256: str,
        sanitized_sha256: str,
        description: str,
        provider: str,
        model: str,
    ) -> ImageDescriptionRecord:

        if not tenant_id.strip():
            raise MultimodalEvidenceError(
                "Missing tenant ID"
            )

        if not asset_id.strip():
            raise MultimodalEvidenceError(
                "Missing asset ID"
            )

        if asset_version <= 0:
            raise MultimodalEvidenceError(
                "Invalid asset version"
            )

        if not description.strip():
            raise MultimodalEvidenceError(
                "Empty description"
            )

        if not provider.strip() or not model.strip():
            raise MultimodalEvidenceError(
                "Missing model identity"
            )

        for digest in (
            source_sha256,
            sanitized_sha256,
        ):
            if (
                len(digest) != 64
                or any(
                    char not in "0123456789abcdef"
                    for char in digest
                )
            ):
                raise MultimodalEvidenceError(
                    "Invalid SHA-256 digest"
                )

        record = ImageDescriptionRecord(
            tenant_id=tenant_id,
            asset_id=asset_id,
            asset_version=asset_version,
            source_sha256=source_sha256,
            sanitized_sha256=sanitized_sha256,
            description=description,
            description_sha256=sha256_text(
                description
            ),
            provider=provider,
            model=model,
        )

        key = (
            tenant_id,
            asset_id,
            asset_version,
        )

        with self._lock:
            existing = self._records.get(key)

            if existing is not None:
                if existing == record:
                    return existing

                raise DescriptionConflict(
                    "Asset version already has "
                    "a different description"
                )

            self._records[key] = record

        return record

    def get(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        asset_version: int,
    ) -> ImageDescriptionRecord:

        key = (
            tenant_id,
            asset_id,
            asset_version,
        )

        with self._lock:
            record = self._records.get(key)

        if record is None:
            raise DescriptionNotFound(
                "Description record not found"
            )

        return record

    def verify(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        asset_version: int,
        source_sha256: str,
        sanitized_sha256: str,
        description: str,
    ) -> ImageDescriptionRecord:

        record = self.get(
            tenant_id=tenant_id,
            asset_id=asset_id,
            asset_version=asset_version,
        )

        if record.source_sha256 != source_sha256:
            raise DescriptionIntegrityError(
                "Source digest mismatch"
            )

        if (
            record.sanitized_sha256
            != sanitized_sha256
        ):
            raise DescriptionIntegrityError(
                "Sanitized digest mismatch"
            )

        if record.description != description:
            raise DescriptionIntegrityError(
                "Description text mismatch"
            )

        if (
            record.description_sha256
            != sha256_text(description)
        ):
            raise DescriptionIntegrityError(
                "Description digest mismatch"
            )

        return record