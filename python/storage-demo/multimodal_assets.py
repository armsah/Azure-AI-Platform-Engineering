import hashlib
import threading
from dataclasses import dataclass
from enum import Enum


class MultimodalAssetError(Exception):
    pass


class AssetConflict(MultimodalAssetError):
    pass


class AssetNotFound(MultimodalAssetError):
    pass


class AssetIntegrityError(MultimodalAssetError):
    pass


class AssetModality(str, Enum):
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"


ALLOWED_CONTENT_TYPES = {
    "image/png": AssetModality.IMAGE,
    "image/jpeg": AssetModality.IMAGE,
    "image/webp": AssetModality.IMAGE,
    "application/pdf": AssetModality.DOCUMENT,
    "audio/wav": AssetModality.AUDIO,
    "audio/mpeg": AssetModality.AUDIO,
    "video/mp4": AssetModality.VIDEO,
}


MAX_ASSET_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class MultimodalAsset:
    tenant_id: str
    asset_id: str
    filename: str
    content_type: str
    modality: AssetModality
    content_sha256: str
    size_bytes: int
    storage_key: str
    version: int


def sha256_asset(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_asset(
    *,
    tenant_id: str,
    asset_id: str,
    filename: str,
    content_type: str,
    content: bytes,
) -> AssetModality:

    if not tenant_id or not tenant_id.strip():
        raise MultimodalAssetError(
            "Missing tenant ID"
        )

    if not asset_id or not asset_id.strip():
        raise MultimodalAssetError(
            "Missing asset ID"
        )

    if not filename or not filename.strip():
        raise MultimodalAssetError(
            "Missing filename"
        )

    if (
        "/" in filename
        or "\\" in filename
        or filename in {".", ".."}
    ):
        raise MultimodalAssetError(
            "Unsafe filename"
        )

    modality = ALLOWED_CONTENT_TYPES.get(
        content_type
    )

    if modality is None:
        raise MultimodalAssetError(
            "Unsupported content type"
        )

    if not isinstance(content, bytes):
        raise MultimodalAssetError(
            "Asset content must be bytes"
        )

    if not content:
        raise MultimodalAssetError(
            "Empty asset"
        )

    if len(content) > MAX_ASSET_BYTES:
        raise MultimodalAssetError(
            "Asset exceeds size limit"
        )

    return modality


class MultimodalAssetRegistry:
    def __init__(self):
        self._lock = threading.RLock()

        self._assets: dict[
            tuple[str, str, int],
            MultimodalAsset,
        ] = {}

        self._current: dict[
            tuple[str, str],
            int,
        ] = {}

    def register(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        filename: str,
        content_type: str,
        content: bytes,
        version: int = 1,
    ) -> MultimodalAsset:

        modality = validate_asset(
            tenant_id=tenant_id,
            asset_id=asset_id,
            filename=filename,
            content_type=content_type,
            content=content,
        )

        if version <= 0:
            raise MultimodalAssetError(
                "Version must be positive"
            )

        key = (
            tenant_id,
            asset_id,
            version,
        )

        document_key = (
            tenant_id,
            asset_id,
        )

        with self._lock:
            if key in self._assets:
                raise AssetConflict(
                    "Asset version already exists"
                )

            current = self._current.get(
                document_key,
                0,
            )

            if version <= current:
                raise AssetConflict(
                    "Asset version must increase"
                )

            digest = sha256_asset(content)

            storage_key = (
                f"tenants/{tenant_id}/"
                f"assets/{asset_id}/"
                f"versions/{version}/"
                f"{digest}"
            )

            asset = MultimodalAsset(
                tenant_id=tenant_id,
                asset_id=asset_id,
                filename=filename,
                content_type=content_type,
                modality=modality,
                content_sha256=digest,
                size_bytes=len(content),
                storage_key=storage_key,
                version=version,
            )

            self._assets[key] = asset
            self._current[document_key] = version

            return asset

    def get(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        version: int,
    ) -> MultimodalAsset:

        key = (
            tenant_id,
            asset_id,
            version,
        )

        with self._lock:
            asset = self._assets.get(key)

        if asset is None:
            raise AssetNotFound(
                "Asset not found"
            )

        return asset

    def verify(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        version: int,
        content: bytes,
    ) -> MultimodalAsset:

        asset = self.get(
            tenant_id=tenant_id,
            asset_id=asset_id,
            version=version,
        )

        if not isinstance(content, bytes):
            raise AssetIntegrityError(
                "Expected bytes"
            )

        if len(content) != asset.size_bytes:
            raise AssetIntegrityError(
                "Asset size mismatch"
            )

        if (
            sha256_asset(content)
            != asset.content_sha256
        ):
            raise AssetIntegrityError(
                "Asset digest mismatch"
            )

        return asset
    
    def current_version(
        self,
        *,
        tenant_id: str,
        asset_id: str,
    ) -> int:

        with self._lock:
            version = self._current.get(
                (tenant_id, asset_id)
            )

        if version is None:
            raise AssetNotFound(
                "Asset not found"
            )

        return version