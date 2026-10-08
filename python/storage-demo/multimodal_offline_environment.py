from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from document_provenance import DocumentProvenanceRegistry

from graph_document_access import InMemoryDocumentAccessPolicy

from multimodal_api import (
    MultimodalAPIDependencies,
    create_multimodal_app,
)

from multimodal_assets import MultimodalAssetRegistry

from multimodal_authorization import InMemoryAssetAccessPolicy

from multimodal_evidence import ImageDescriptionRegistry

from multimodal_evidence_gate import MultimodalEvidenceGate

from multimodal_indexing import MultimodalIndexingService

from multimodal_rag_answer import (
    MultimodalDraft,
    MultimodalRAGAnswerService,
)

from multimodal_retrieval import MultimodalRetrievalService

from multimodal_search_index import InMemoryMultimodalSearchIndex

from multimodal_test_stores import (
    InMemoryImageEvidenceStore,
    InMemoryTextEvidenceStore,
)

from multimodal_upload_workflow import MultimodalUploadWorkflow

from provenance_authorization import AuthorizedProvenanceService

from chunk_provenance_verifier import ChunkProvenanceVerifier

from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantBoundary,
    TenantMembership,
)


# ============================================================
# Offline embedding provider
# ============================================================

class OfflineEmbeddingProvider:
    """
    Deterministic embedding provider for offline integration tests.

    This implementation validates the retrieval pipeline,
    not real semantic embedding quality.
    """

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        vectors = []

        for text in texts:
            normalized = text.lower()

            vectors.append(
                [
                    1.0 if "architecture" in normalized else 0.1,
                    1.0 if "diagram" in normalized else 0.1,
                    1.0 if "payment" in normalized else 0.1,
                    1.0,
                ]
            )

        return vectors


# ============================================================
# Offline vision provider
# ============================================================

class OfflineVisionProvider:
    """
    Deterministic substitute for an Azure vision model.
    """

    def describe(
        self,
        *,
        image,
        instruction: str,
    ) -> str:

        return (
            "An architecture diagram showing "
            "a payment processing system."
        )


# ============================================================
# Offline multimodal answer model
# ============================================================

class OfflineMultimodalModel:
    """
    Deterministic answer model.

    Selects an existing citation ID from verified evidence.
    """

    def generate(
        self,
        *,
        question: str,
        evidence,
        citation_ids: tuple[str, ...],
    ) -> MultimodalDraft:

        if not evidence:
            raise AssertionError(
                "Model must not run without verified evidence"
            )

        if not citation_ids:
            raise AssertionError(
                "Verified evidence must provide citation IDs"
            )

        return MultimodalDraft(
            answer=(
                "The image depicts a payment "
                "processing architecture."
            ),
            citation_ids=(citation_ids[0],),
        )


# ============================================================
# Environment container
# ============================================================

@dataclass(frozen=True)
class OfflineMultimodalEnvironment:
    app: FastAPI
    assets: MultimodalAssetRegistry
    image_sources: InMemoryImageEvidenceStore
    descriptions: ImageDescriptionRegistry
    index: InMemoryMultimodalSearchIndex
    upload_workflow: MultimodalUploadWorkflow


# ============================================================
# Complete offline environment factory
# ============================================================

def create_offline_multimodal_environment(
    *,
    directory_tenant_id: str,
    tenant_id: str,
    user_id: str,
) -> OfflineMultimodalEnvironment:

    # --------------------------------------------------------
    # 1. Tenant membership
    # --------------------------------------------------------

    memberships = InMemoryTenantMembershipStore(
        (
            TenantMembership(
                directory_tenant_id=directory_tenant_id,
                user_id=user_id,
                business_tenant_id=tenant_id,
            ),
        )
    )

    boundary = TenantBoundary(memberships)

    # --------------------------------------------------------
    # 2. Multimodal asset infrastructure
    # --------------------------------------------------------

    assets = MultimodalAssetRegistry()

    asset_access = InMemoryAssetAccessPolicy()

    image_sources = InMemoryImageEvidenceStore()

    descriptions = ImageDescriptionRegistry()

    # --------------------------------------------------------
    # 3. Search index and embeddings
    # --------------------------------------------------------

    index = InMemoryMultimodalSearchIndex()

    embeddings = OfflineEmbeddingProvider()

    indexing = MultimodalIndexingService(
        index=index,
        embeddings=embeddings,
    )

    # --------------------------------------------------------
    # 4. Document provenance dependencies
    # --------------------------------------------------------

    document_registry = DocumentProvenanceRegistry()

    document_access = InMemoryDocumentAccessPolicy(())

    provenance_service = AuthorizedProvenanceService(
        registry=document_registry,
        boundary=boundary,
        document_access=document_access,
    )

    chunk_verifier = ChunkProvenanceVerifier(
        provenance_service=provenance_service,
    )

    text_sources = InMemoryTextEvidenceStore()

    # --------------------------------------------------------
    # 5. Tenant-safe multimodal retrieval
    # --------------------------------------------------------

    retrieval = MultimodalRetrievalService(
        index=index,
        boundary=boundary,
        asset_registry=assets,
        asset_access=asset_access,
        document_registry=document_registry,
        document_access=document_access,
        embeddings=embeddings,
    )

    # --------------------------------------------------------
    # 6. Provenance-aware evidence verification
    # --------------------------------------------------------

    evidence_gate = MultimodalEvidenceGate(
        boundary=boundary,
        asset_registry=assets,
        asset_access=asset_access,
        description_registry=descriptions,
        image_sources=image_sources,
        text_sources=text_sources,
        chunk_verifier=chunk_verifier,
    )

    # --------------------------------------------------------
    # 7. Citation-validated answer generation
    # --------------------------------------------------------

    answers = MultimodalRAGAnswerService(
        retrieval=retrieval,
        evidence_gate=evidence_gate,
        model=OfflineMultimodalModel(),
    )

    # --------------------------------------------------------
    # 8. Complete image upload workflow
    # --------------------------------------------------------

    upload_workflow = MultimodalUploadWorkflow(
        boundary=boundary,
        assets=assets,
        asset_access=asset_access,
        image_sources=image_sources,
        descriptions=descriptions,
        indexing=indexing,
        vision_provider=OfflineVisionProvider(),
    )

    # --------------------------------------------------------
    # 9. FastAPI application
    # --------------------------------------------------------

    app = create_multimodal_app(
        MultimodalAPIDependencies(
            boundary=boundary,
            assets=assets,
            answers=answers,
            upload_workflow=upload_workflow,
        )
    )

    # --------------------------------------------------------
    # 10. Return environment
    # --------------------------------------------------------

    return OfflineMultimodalEnvironment(
        app=app,
        assets=assets,
        image_sources=image_sources,
        descriptions=descriptions,
        index=index,
        upload_workflow=upload_workflow,
    )