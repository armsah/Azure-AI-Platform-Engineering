import pytest

from document_provenance import (
    DocumentProvenanceRegistry,
)
from graph_document_access import (
    DocumentGrant,
    InMemoryDocumentAccessPolicy,
)
from image_vision import VisionDescription
from multimodal_assets import (
    MultimodalAssetRegistry,
)
from multimodal_authorization import (
    AssetGrant,
    InMemoryAssetAccessPolicy,
)
from multimodal_indexing import (
    MultimodalIndexingService,
    TextEvidenceRecord,
)
from multimodal_retrieval import (
    MultimodalRetrievalError,
    MultimodalRetrievalService,
)
from multimodal_search_index import (
    InMemoryMultimodalSearchIndex,
    SearchModality,
)
from request_context import RequestContext
from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantAuthorizationError,
    TenantBoundary,
    TenantMembership,
)


IMAGE_BYTES = b"registered-image-bytes"
DOCUMENT_BYTES = b"Payment API uses Customer DB."


class FakeEmbeddings:
    def embed(self, texts):
        vectors = []

        for text in texts:
            lower = text.lower()

            if "database" in lower or "db" in lower:
                vectors.append([1.0, 0.0])

            elif "diagram" in lower or "image" in lower:
                vectors.append([0.0, 1.0])

            else:
                vectors.append([0.5, 0.5])

        return vectors


def context(
    *,
    tenant="customer-a",
    user="alice",
):
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id=tenant,
        user_id=user,
        groups=(),
        roles=("AI.User",),
    )


def make_fixture(
    *,
    asset_grant=True,
    document_grant=True,
):
    index = InMemoryMultimodalSearchIndex()
    embeddings = FakeEmbeddings()

    assets = MultimodalAssetRegistry()

    image = assets.register(
        tenant_id="customer-a",
        asset_id="diagram-1",
        filename="architecture.png",
        content_type="image/png",
        content=IMAGE_BYTES,
    )

    documents = DocumentProvenanceRegistry()

    manifest = documents.register(
        tenant_id="customer-a",
        document_id="doc-1",
        version=1,
        content=DOCUMENT_BYTES,
    )

    indexing = MultimodalIndexingService(
        index=index,
        embeddings=embeddings,
    )

    indexing.index_image_description(
        VisionDescription(
            tenant_id="customer-a",
            asset_id="diagram-1",
            asset_version=1,
            source_sha256=image.content_sha256,
            sanitized_sha256="a" * 64,
            width=100,
            height=100,
            description=(
                "Architecture diagram of an API."
            ),
            provider="mock",
            model="mock-vision",
        )
    )

    indexing.index_text(
        TextEvidenceRecord(
            tenant_id="customer-a",
            document_id="doc-1",
            document_version=1,
            source_sha256=manifest.content_sha256,
            chunk_id="chunk-1",
            text="Payment API uses Customer DB.",
        )
    )

    asset_grants = (
        (
            AssetGrant(
                tenant_id="customer-a",
                asset_id="diagram-1",
                user_id="alice",
            ),
        )
        if asset_grant
        else ()
    )

    document_grants = (
        (
            DocumentGrant(
                tenant_id="customer-a",
                document_id="doc-1",
                user_id="alice",
            ),
        )
        if document_grant
        else ()
    )

    boundary = TenantBoundary(
        InMemoryTenantMembershipStore(
            (
                TenantMembership(
                    directory_tenant_id="entra-directory",
                    user_id="alice",
                    business_tenant_id="customer-a",
                ),
            )
        )
    )

    retrieval = MultimodalRetrievalService(
        index=index,
        boundary=boundary,
        asset_registry=assets,
        asset_access=InMemoryAssetAccessPolicy(
            asset_grants
        ),
        document_registry=documents,
        document_access=InMemoryDocumentAccessPolicy(
            document_grants
        ),
        embeddings=embeddings,
    )

    return {
        "index": index,
        "assets": assets,
        "documents": documents,
        "indexing": indexing,
        "retrieval": retrieval,
    }


def test_image_is_indexed():
    fixture = make_fixture()

    hits = fixture["index"].search(
        tenant_id="customer-a",
        query_vector=(0.0, 1.0),
    )

    assert any(
        hit.document.modality == SearchModality.IMAGE
        for hit in hits
    )


def test_text_is_indexed():
    fixture = make_fixture()

    hits = fixture["index"].search(
        tenant_id="customer-a",
        query_vector=(1.0, 0.0),
    )

    assert any(
        hit.document.modality == SearchModality.TEXT
        for hit in hits
    )


def test_image_retrieval():
    fixture = make_fixture()

    hits = fixture["retrieval"].search(
        context=context(),
        question="Find the architecture diagram",
    )

    assert any(
        hit.resource_id == "diagram-1"
        for hit in hits
    )


def test_text_retrieval():
    fixture = make_fixture()

    hits = fixture["retrieval"].search(
        context=context(),
        question="Which database does the API use?",
    )

    assert any(
        hit.resource_id == "doc-1"
        for hit in hits
    )


def test_mixed_modality_retrieval():
    fixture = make_fixture()

    hits = fixture["retrieval"].search(
        context=context(),
        question="Explain the architecture",
    )

    assert {
        hit.modality
        for hit in hits
    } == {
        SearchModality.TEXT,
        SearchModality.IMAGE,
    }


def test_missing_image_grant_filters_image():
    fixture = make_fixture(
        asset_grant=False
    )

    hits = fixture["retrieval"].search(
        context=context(),
        question="Find diagram",
    )

    assert all(
        hit.modality != SearchModality.IMAGE
        for hit in hits
    )


def test_missing_document_grant_filters_text():
    fixture = make_fixture(
        document_grant=False
    )

    hits = fixture["retrieval"].search(
        context=context(),
        question="Find database",
    )

    assert all(
        hit.modality != SearchModality.TEXT
        for hit in hits
    )


def test_missing_all_grants_returns_empty():
    fixture = make_fixture(
        asset_grant=False,
        document_grant=False,
    )

    hits = fixture["retrieval"].search(
        context=context(),
        question="architecture",
    )

    assert hits == ()


def test_other_user_rejected():
    fixture = make_fixture()

    with pytest.raises(TenantAuthorizationError):
        fixture["retrieval"].search(
            context=context(
                user="mallory"
            ),
            question="architecture",
        )


def test_cross_tenant_context_rejected():
    fixture = make_fixture()

    with pytest.raises(TenantAuthorizationError):
        fixture["retrieval"].search(
            context=context(
                tenant="customer-b"
            ),
            question="architecture",
        )


def test_empty_question_rejected():
    fixture = make_fixture()

    with pytest.raises(MultimodalRetrievalError):
        fixture["retrieval"].search(
            context=context(),
            question=" ",
        )


def test_top_k_limits_results():
    fixture = make_fixture()

    hits = fixture["retrieval"].search(
        context=context(),
        question="architecture",
        top_k=1,
    )

    assert len(hits) == 1


def test_new_image_version_invalidates_old_hit():
    fixture = make_fixture()

    fixture["assets"].register(
        tenant_id="customer-a",
        asset_id="diagram-1",
        filename="architecture-v2.png",
        content_type="image/png",
        content=b"new-image-version",
        version=2,
    )

    hits = fixture["retrieval"].search(
        context=context(),
        question="Find diagram",
    )

    assert all(
        hit.modality != SearchModality.IMAGE
        for hit in hits
    )


def test_new_document_version_invalidates_old_hit():
    fixture = make_fixture()

    fixture["documents"].register(
        tenant_id="customer-a",
        document_id="doc-1",
        version=2,
        content=b"New document",
    )

    hits = fixture["retrieval"].search(
        context=context(),
        question="Find database",
    )

    assert all(
        hit.modality != SearchModality.TEXT
        for hit in hits
    )


def test_revoked_document_is_filtered():
    fixture = make_fixture()

    fixture["documents"].revoke(
        tenant_id="customer-a",
        document_id="doc-1",
        version=1,
    )

    hits = fixture["retrieval"].search(
        context=context(),
        question="Find database",
    )

    assert all(
        hit.modality != SearchModality.TEXT
        for hit in hits
    )


def test_search_is_tenant_filtered():
    fixture = make_fixture()

    hits = fixture["index"].search(
        tenant_id="customer-b",
        query_vector=(1.0, 0.0),
    )

    assert hits == ()


def test_image_source_digest_retained():
    fixture = make_fixture()

    hits = fixture["retrieval"].search(
        context=context(),
        question="diagram",
    )

    image_hit = next(
        hit
        for hit in hits
        if hit.modality == SearchModality.IMAGE
    )

    assert len(image_hit.source_sha256) == 64


def test_text_source_digest_retained():
    fixture = make_fixture()

    hits = fixture["retrieval"].search(
        context=context(),
        question="database",
    )

    text_hit = next(
        hit
        for hit in hits
        if hit.modality == SearchModality.TEXT
    )

    assert len(text_hit.source_sha256) == 64


def test_duplicate_index_document_is_idempotent():
    fixture = make_fixture()

    hits = fixture["index"].search(
        tenant_id="customer-a",
        query_vector=(1.0, 0.0),
    )

    original = hits[0].document

    fixture["index"].upsert(original)

    assert len(
        fixture["index"].search(
            tenant_id="customer-a",
            query_vector=(1.0, 0.0),
        )
    ) == 2


def test_search_scores_are_ordered():
    fixture = make_fixture()

    hits = fixture["index"].search(
        tenant_id="customer-a",
        query_vector=(1.0, 0.0),
    )

    scores = [
        hit.score
        for hit in hits
    ]

    assert scores == sorted(
        scores,
        reverse=True,
    )
    