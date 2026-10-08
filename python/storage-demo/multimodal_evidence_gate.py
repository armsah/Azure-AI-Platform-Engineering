from dataclasses import dataclass
from typing import Protocol

from chunk_provenance import (
    ChunkProvenance,
    ExtractionManifest,
)
from chunk_provenance_verifier import (
    ChunkProvenanceVerifier,
)
from multimodal_assets import (
    MultimodalAssetRegistry,
)
from multimodal_authorization import (
    InMemoryAssetAccessPolicy,
)
from multimodal_evidence import (
    ImageDescriptionRegistry,
)
from multimodal_retrieval import (
    AuthorizedMultimodalHit,
)
from multimodal_search_index import (
    SearchModality,
)
from request_context import RequestContext
from secure_image_processing import (
    sanitize_image,
)
from tenant_boundary import (
    TenantBoundary,
)


class MultimodalEvidenceGateError(Exception):
    pass


@dataclass(frozen=True)
class TextEvidenceSource:
    source_bytes: bytes
    extracted_text: str
    extraction: ExtractionManifest
    chunk: ChunkProvenance
    chunk_text: str


class TextEvidenceSourceStore(Protocol):
    def get(
        self,
        *,
        tenant_id: str,
        document_id: str,
        document_version: int,
        search_id: str,
    ) -> TextEvidenceSource:
        ...


class ImageEvidenceSourceStore(Protocol):
    def get(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        asset_version: int,
    ) -> bytes:
        ...


@dataclass(frozen=True)
class VerifiedMultimodalEvidence:
    evidence_id: str
    modality: SearchModality

    tenant_id: str
    resource_id: str
    resource_version: int

    source_sha256: str
    text: str


class MultimodalEvidenceGate:
    def __init__(
        self,
        *,
        boundary: TenantBoundary,
        asset_registry: MultimodalAssetRegistry,
        asset_access: InMemoryAssetAccessPolicy,
        description_registry: ImageDescriptionRegistry,
        image_sources: ImageEvidenceSourceStore,
        text_sources: TextEvidenceSourceStore,
        chunk_verifier: ChunkProvenanceVerifier,
    ):
        self.boundary = boundary
        self.asset_registry = asset_registry
        self.asset_access = asset_access
        self.description_registry = (
            description_registry
        )
        self.image_sources = image_sources
        self.text_sources = text_sources
        self.chunk_verifier = chunk_verifier

    def verify(
        self,
        *,
        context: RequestContext,
        hit: AuthorizedMultimodalHit,
    ) -> VerifiedMultimodalEvidence:

        self.boundary.authorize(
            context=context,
            requested_tenant_id=context.tenant_id,
        )

        if hit.tenant_id != context.tenant_id:
            raise MultimodalEvidenceGateError(
                "Cross-tenant evidence"
            )

        if hit.modality == SearchModality.IMAGE:
            return self._verify_image(
                context=context,
                hit=hit,
            )

        if hit.modality == SearchModality.TEXT:
            return self._verify_text(
                context=context,
                hit=hit,
            )

        raise MultimodalEvidenceGateError(
            "Unsupported evidence modality"
        )

    def _verify_image(
        self,
        *,
        context: RequestContext,
        hit: AuthorizedMultimodalHit,
    ) -> VerifiedMultimodalEvidence:

        if not self.asset_access.can_read(
            context=context,
            asset_id=hit.resource_id,
        ):
            raise MultimodalEvidenceGateError(
                "Image access denied"
            )

        current = self.asset_registry.current_version(
            tenant_id=context.tenant_id,
            asset_id=hit.resource_id,
        )

        if current != hit.resource_version:
            raise MultimodalEvidenceGateError(
                "Image version is stale"
            )

        source_bytes = self.image_sources.get(
            tenant_id=context.tenant_id,
            asset_id=hit.resource_id,
            asset_version=hit.resource_version,
        )

        asset = self.asset_registry.verify(
            tenant_id=context.tenant_id,
            asset_id=hit.resource_id,
            version=hit.resource_version,
            content=source_bytes,
        )

        if asset.content_sha256 != hit.source_sha256:
            raise MultimodalEvidenceGateError(
                "Search image digest mismatch"
            )

        sanitized = sanitize_image(
            content_type=asset.content_type,
            content=source_bytes,
        )

        self.description_registry.verify(
            tenant_id=context.tenant_id,
            asset_id=hit.resource_id,
            asset_version=hit.resource_version,
            source_sha256=asset.content_sha256,
            sanitized_sha256=(
                sanitized.sanitized_sha256
            ),
            description=hit.text,
        )

        return VerifiedMultimodalEvidence(
            evidence_id=hit.search_id,
            modality=SearchModality.IMAGE,
            tenant_id=context.tenant_id,
            resource_id=hit.resource_id,
            resource_version=hit.resource_version,
            source_sha256=asset.content_sha256,
            text=hit.text,
        )

    def _verify_text(
        self,
        *,
        context: RequestContext,
        hit: AuthorizedMultimodalHit,
    ) -> VerifiedMultimodalEvidence:

        source = self.text_sources.get(
            tenant_id=context.tenant_id,
            document_id=hit.resource_id,
            document_version=hit.resource_version,
            search_id=hit.search_id,
        )

        verified = self.chunk_verifier.verify(
            context=context,
            source_bytes=source.source_bytes,
            extracted_text=source.extracted_text,
            extraction=source.extraction,
            chunk=source.chunk,
            chunk_text=source.chunk_text,
            require_current=True,
        )

        if source.chunk_text != hit.text:
            raise MultimodalEvidenceGateError(
                "Search text differs from verified chunk"
            )

        if (
            source.extraction.source_sha256
            != hit.source_sha256
        ):
            raise MultimodalEvidenceGateError(
                "Search document digest mismatch"
            )

        return VerifiedMultimodalEvidence(
            evidence_id=hit.search_id,
            modality=SearchModality.TEXT,
            tenant_id=context.tenant_id,
            resource_id=hit.resource_id,
            resource_version=hit.resource_version,
            source_sha256=hit.source_sha256,
            text=source.chunk_text,
        )