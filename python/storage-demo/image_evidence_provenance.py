import hashlib
import json
import threading
from dataclasses import dataclass

from image_vision import VisionDescription


class ImageEvidenceError(Exception):
    pass


class ImageEvidenceConflict(ImageEvidenceError):
    pass


class ImageEvidenceNotFound(ImageEvidenceError):
    pass


class ImageEvidenceRevoked(ImageEvidenceError):
    pass


@dataclass(frozen=True)
class ImageDescriptionProvenance:
    evidence_id: str

    tenant_id: str
    asset_id: str
    asset_version: int

    source_sha256: str
    sanitized_sha256: str

    description_sha256: str

    provider: str
    model: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def create_image_description_provenance(
    description: VisionDescription,
) -> ImageDescriptionProvenance:

    if not description.description.strip():
        raise ImageEvidenceError(
            "Image description must not be empty"
        )

    if description.asset_version <= 0:
        raise ImageEvidenceError(
            "Invalid asset version"
        )

    description_digest = sha256_text(
        description.description
    )

    payload = {
        "schema": "image-evidence-v1",
        "tenant_id": description.tenant_id,
        "asset_id": description.asset_id,
        "asset_version": description.asset_version,
        "source_sha256": description.source_sha256,
        "sanitized_sha256": description.sanitized_sha256,
        "description_sha256": description_digest,
        "provider": description.provider,
        "model": description.model,
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    evidence_id = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    return ImageDescriptionProvenance(
        evidence_id=evidence_id,
        tenant_id=description.tenant_id,
        asset_id=description.asset_id,
        asset_version=description.asset_version,
        source_sha256=description.source_sha256,
        sanitized_sha256=description.sanitized_sha256,
        description_sha256=description_digest,
        provider=description.provider,
        model=description.model,
    )


class ImageDescriptionProvenanceRegistry:
    def __init__(self):
        self._lock = threading.RLock()

        self._records: dict[
            tuple[str, str],
            ImageDescriptionProvenance,
        ] = {}

        self._revoked: set[
            tuple[str, str]
        ] = set()

    def register(
        self,
        record: ImageDescriptionProvenance,
    ) -> None:

        key = (
            record.tenant_id,
            record.evidence_id,
        )

        with self._lock:
            existing = self._records.get(key)

            if (
                existing is not None
                and existing != record
            ):
                raise ImageEvidenceConflict(
                    "Conflicting evidence record"
                )

            if key in self._revoked:
                raise ImageEvidenceRevoked(
                    "Revoked evidence cannot be registered"
                )

            self._records[key] = record

    def get(
        self,
        *,
        tenant_id: str,
        evidence_id: str,
    ) -> ImageDescriptionProvenance:

        key = (
            tenant_id,
            evidence_id,
        )

        with self._lock:
            if key in self._revoked:
                raise ImageEvidenceRevoked(
                    "Image evidence revoked"
                )

            record = self._records.get(key)

        if record is None:
            raise ImageEvidenceNotFound(
                "Image evidence not registered"
            )

        return record

    def revoke(
        self,
        *,
        tenant_id: str,
        evidence_id: str,
    ) -> None:

        key = (
            tenant_id,
            evidence_id,
        )

        with self._lock:
            if key not in self._records:
                raise ImageEvidenceNotFound(
                    "Image evidence not registered"
                )

            self._revoked.add(key)