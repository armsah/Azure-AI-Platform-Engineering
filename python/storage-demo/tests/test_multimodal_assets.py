import pytest

from multimodal_assets import (
    AssetConflict,
    AssetIntegrityError,
    AssetModality,
    AssetNotFound,
    MultimodalAssetError,
    MultimodalAssetRegistry,
)
from multimodal_authorization import (
    AssetGrant,
    AuthorizedMultimodalAssetService,
    InMemoryAssetAccessPolicy,
)
from request_context import RequestContext
from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantAuthorizationError,
    TenantBoundary,
    TenantMembership,
)


IMAGE_BYTES = b"mock-image-content"


def make_context(
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


def make_registry():
    registry = MultimodalAssetRegistry()

    registry.register(
        tenant_id="customer-a",
        asset_id="image-1",
        filename="diagram.png",
        content_type="image/png",
        content=IMAGE_BYTES,
    )

    return registry


def make_service(*, grant=True):
    grants = (
        (
            AssetGrant(
                tenant_id="customer-a",
                asset_id="image-1",
                user_id="alice",
            ),
        )
        if grant
        else ()
    )

    return AuthorizedMultimodalAssetService(
        registry=make_registry(),
        boundary=TenantBoundary(
            InMemoryTenantMembershipStore(
                (
                    TenantMembership(
                        directory_tenant_id=(
                            "entra-directory"
                        ),
                        user_id="alice",
                        business_tenant_id="customer-a",
                    ),
                )
            )
        ),
        access_policy=InMemoryAssetAccessPolicy(
            grants
        ),
    )


def test_image_registration():
    asset = make_registry().get(
        tenant_id="customer-a",
        asset_id="image-1",
        version=1,
    )

    assert asset.modality == AssetModality.IMAGE


def test_storage_key_is_tenant_scoped():
    asset = make_registry().get(
        tenant_id="customer-a",
        asset_id="image-1",
        version=1,
    )

    assert asset.storage_key.startswith(
        "tenants/customer-a/"
    )


def test_asset_integrity_verifies():
    result = make_registry().verify(
        tenant_id="customer-a",
        asset_id="image-1",
        version=1,
        content=IMAGE_BYTES,
    )

    assert result.asset_id == "image-1"


def test_modified_asset_rejected():
    with pytest.raises(AssetIntegrityError):
        make_registry().verify(
            tenant_id="customer-a",
            asset_id="image-1",
            version=1,
            content=b"modified-image-content",
        )


def test_missing_asset_rejected():
    with pytest.raises(AssetNotFound):
        make_registry().get(
            tenant_id="customer-a",
            asset_id="missing",
            version=1,
        )


def test_cross_tenant_lookup_rejected():
    with pytest.raises(AssetNotFound):
        make_registry().get(
            tenant_id="customer-b",
            asset_id="image-1",
            version=1,
        )


def test_duplicate_version_rejected():
    registry = make_registry()

    with pytest.raises(AssetConflict):
        registry.register(
            tenant_id="customer-a",
            asset_id="image-1",
            filename="diagram.png",
            content_type="image/png",
            content=IMAGE_BYTES,
            version=1,
        )


def test_new_version_allowed():
    registry = make_registry()

    asset = registry.register(
        tenant_id="customer-a",
        asset_id="image-1",
        filename="diagram-v2.png",
        content_type="image/png",
        content=b"new-image-content",
        version=2,
    )

    assert asset.version == 2


def test_unsupported_content_type_rejected():
    with pytest.raises(MultimodalAssetError):
        MultimodalAssetRegistry().register(
            tenant_id="customer-a",
            asset_id="script-1",
            filename="script.exe",
            content_type="application/x-msdownload",
            content=b"binary",
        )


def test_unsafe_filename_rejected():
    with pytest.raises(MultimodalAssetError):
        MultimodalAssetRegistry().register(
            tenant_id="customer-a",
            asset_id="image-1",
            filename="../secret.png",
            content_type="image/png",
            content=IMAGE_BYTES,
        )


def test_empty_content_rejected():
    with pytest.raises(MultimodalAssetError):
        MultimodalAssetRegistry().register(
            tenant_id="customer-a",
            asset_id="image-1",
            filename="diagram.png",
            content_type="image/png",
            content=b"",
        )


def test_invalid_version_rejected():
    with pytest.raises(MultimodalAssetError):
        MultimodalAssetRegistry().register(
            tenant_id="customer-a",
            asset_id="image-1",
            filename="diagram.png",
            content_type="image/png",
            content=IMAGE_BYTES,
            version=0,
        )


def test_authorized_asset_read():
    asset = make_service().get_asset(
        context=make_context(),
        asset_id="image-1",
        version=1,
    )

    assert asset.asset_id == "image-1"


def test_missing_asset_grant_rejected():
    with pytest.raises(TenantAuthorizationError):
        make_service(
            grant=False
        ).get_asset(
            context=make_context(),
            asset_id="image-1",
            version=1,
        )


def test_other_user_rejected():
    with pytest.raises(TenantAuthorizationError):
        make_service().get_asset(
            context=make_context(
                user="mallory"
            ),
            asset_id="image-1",
            version=1,
        )


def test_cross_tenant_context_rejected():
    with pytest.raises(TenantAuthorizationError):
        make_service().get_asset(
            context=make_context(
                tenant="customer-b"
            ),
            asset_id="image-1",
            version=1,
        )


def test_authorized_asset_verification():
    result = make_service().verify_asset(
        context=make_context(),
        asset_id="image-1",
        version=1,
        content=IMAGE_BYTES,
    )

    assert result.content_sha256


def test_pdf_modality_classification():
    registry = MultimodalAssetRegistry()

    asset = registry.register(
        tenant_id="customer-a",
        asset_id="pdf-1",
        filename="report.pdf",
        content_type="application/pdf",
        content=b"%PDF-1.7",
    )

    assert asset.modality == AssetModality.DOCUMENT


def test_audio_modality_classification():
    registry = MultimodalAssetRegistry()

    asset = registry.register(
        tenant_id="customer-a",
        asset_id="audio-1",
        filename="meeting.wav",
        content_type="audio/wav",
        content=b"RIFF-mock-audio",
    )

    assert asset.modality == AssetModality.AUDIO


def test_video_modality_classification():
    registry = MultimodalAssetRegistry()

    asset = registry.register(
        tenant_id="customer-a",
        asset_id="video-1",
        filename="demo.mp4",
        content_type="video/mp4",
        content=b"mock-video-content",
    )

    assert asset.modality == AssetModality.VIDEO