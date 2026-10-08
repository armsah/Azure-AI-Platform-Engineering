from dataclasses import dataclass

from graph_document_access import (
    DocumentAccessPolicy,
)
from document_provenance import (
    DocumentProvenanceRegistry,
    ProvenanceError,
)
from multimodal_assets import (
    AssetNotFound,
    MultimodalAssetRegistry,
)
from multimodal_authorization import (
    InMemoryAssetAccessPolicy,
)
from multimodal_search_index import (
    InMemoryMultimodalSearchIndex,
    SearchModality,
)
from request_context import RequestContext
from tenant_boundary import TenantBoundary


class MultimodalRetrievalError(Exception):
    pass


@dataclass(frozen=True)
class AuthorizedMultimodalHit:
    search_id: str
    modality: SearchModality

    tenant_id: str
    resource_id: str
    resource_version: int
    source_sha256: str

    text: str
    score: float


class MultimodalRetrievalService:
    def __init__(
        self,
        *,
        index: InMemoryMultimodalSearchIndex,
        boundary: TenantBoundary,
        asset_registry: MultimodalAssetRegistry,
        asset_access: InMemoryAssetAccessPolicy,
        document_registry: DocumentProvenanceRegistry,
        document_access: DocumentAccessPolicy,
        embeddings,
    ):
        self.index = index
        self.boundary = boundary
        self.asset_registry = asset_registry
        self.asset_access = asset_access
        self.document_registry = document_registry
        self.document_access = document_access
        self.embeddings = embeddings

    def _authorized_image(
        self,
        *,
        context: RequestContext,
        hit,
    ) -> bool:

        document = hit.document

        if not self.asset_access.can_read(
            context=context,
            asset_id=document.resource_id,
        ):
            return False

        try:
            asset = self.asset_registry.get(
                tenant_id=context.tenant_id,
                asset_id=document.resource_id,
                version=document.resource_version,
            )
        except AssetNotFound:
            return False

        if (
            asset.content_sha256
            != document.source_sha256
        ):
            return False

        # A10.1 registry has no public current-version
        # accessor yet. Add one in Step 4.
        current_version = (
            self.asset_registry.current_version(
                tenant_id=context.tenant_id,
                asset_id=document.resource_id,
            )
        )

        return (
            asset.version == current_version
        )

    def _authorized_text(
        self,
        *,
        context: RequestContext,
        hit,
    ) -> bool:

        document = hit.document

        if not self.document_access.can_read(
            context=context,
            document_id=document.resource_id,
        ):
            return False

        try:
            manifest = (
                self.document_registry.get_manifest(
                    tenant_id=context.tenant_id,
                    document_id=document.resource_id,
                    version=document.resource_version,
                )
            )

            # A9.1's public verification method requires
            # source bytes. Here we use a metadata-level
            # current/revocation check introduced in Step 4.
            self.document_registry.assert_eligible(
                tenant_id=context.tenant_id,
                document_id=document.resource_id,
                version=document.resource_version,
            )

        except ProvenanceError:
            return False

        return (
            manifest.content_sha256
            == document.source_sha256
        )

    def search(
        self,
        *,
        context: RequestContext,
        question: str,
        top_k: int = 10,
    ) -> tuple[AuthorizedMultimodalHit, ...]:

        if not question.strip():
            raise MultimodalRetrievalError(
                "Question must not be empty"
            )

        self.boundary.authorize(
            context=context,
            requested_tenant_id=context.tenant_id,
        )

        vectors = self.embeddings.embed(
            [question]
        )

        if len(vectors) != 1:
            raise MultimodalRetrievalError(
                "Invalid query embedding response"
            )

        # Over-fetch because some results may fail ACL
        # or provenance checks.
        candidates = self.index.search(
            tenant_id=context.tenant_id,
            query_vector=tuple(vectors[0]),
            top_k=max(top_k * 5, 20),
        )

        authorized = []

        for hit in candidates:
            if hit.document.modality == SearchModality.IMAGE:
                allowed = self._authorized_image(
                    context=context,
                    hit=hit,
                )

            elif hit.document.modality == SearchModality.TEXT:
                allowed = self._authorized_text(
                    context=context,
                    hit=hit,
                )

            else:
                allowed = False

            if not allowed:
                continue

            authorized.append(
                AuthorizedMultimodalHit(
                    search_id=hit.document.search_id,
                    modality=hit.document.modality,
                    tenant_id=hit.document.tenant_id,
                    resource_id=hit.document.resource_id,
                    resource_version=(
                        hit.document.resource_version
                    ),
                    source_sha256=(
                        hit.document.source_sha256
                    ),
                    text=hit.document.text,
                    score=hit.score,
                )
            )

            if len(authorized) >= top_k:
                break

        return tuple(authorized)