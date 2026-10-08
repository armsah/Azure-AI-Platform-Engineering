import io

import pytest

from PIL import Image

from image_vision import (
    ImageVisionService,
    VisionProcessingError,
)
from multimodal_assets import (
    AssetIntegrityError,
    MultimodalAssetRegistry,
)
from multimodal_authorization import (
    AssetGrant,
    AuthorizedMultimodalAssetService,
    InMemoryAssetAccessPolicy,
)
from request_context import RequestContext
from secure_image_processing import (
    ImageSecurityError,
    sanitize_image,
)
from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantAuthorizationError,
    TenantBoundary,
    TenantMembership,
)


def image_bytes(
    *,
    format="PNG",
    width=16,
    height=12,
):
    output = io.BytesIO()

    with Image.new(
        "RGB",
        (width, height),
        (20, 80, 140),
    ) as image:
        image.save(
            output,
            format=format,
        )

    return output.getvalue()


PNG_BYTES = image_bytes()
JPEG_BYTES = image_bytes(format="JPEG")


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


class FakeVisionProvider:
    def __init__(
        self,
        *,
        result="A blue rectangular image.",
        fail=False,
    ):
        self.result = result
        self.fail = fail
        self.calls = 0
        self.last_image = None

    def describe(
        self,
        *,
        image,
        instruction,
    ):
        self.calls += 1
        self.last_image = image

        if self.fail:
            raise RuntimeError(
                "Provider unavailable"
            )

        return self.result


def make_service(
    *,
    grant=True,
    content=PNG_BYTES,
    content_type="image/png",
    provider=None,
):
    registry = MultimodalAssetRegistry()

    registry.register(
        tenant_id="customer-a",
        asset_id="image-1",
        filename="diagram.png",
        content_type=content_type,
        content=content,
    )

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

    assets = AuthorizedMultimodalAssetService(
        registry=registry,
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

    if provider is None:
        provider = FakeVisionProvider()

    service = ImageVisionService(
        assets=assets,
        provider=provider,
        provider_name="mock",
        model_name="mock-vision-v1",
    )

    return service, provider


def test_valid_png_sanitized():
    result = sanitize_image(
        content_type="image/png",
        content=PNG_BYTES,
    )

    assert result.content_type == "image/png"
    assert result.width == 16
    assert result.height == 12


def test_valid_jpeg_sanitized_to_png():
    result = sanitize_image(
        content_type="image/jpeg",
        content=JPEG_BYTES,
    )

    assert result.content.startswith(
        b"\x89PNG\r\n\x1a\n"
    )


def test_sanitized_image_has_digest():
    result = sanitize_image(
        content_type="image/png",
        content=PNG_BYTES,
    )

    assert len(result.sanitized_sha256) == 64


def test_source_digest_preserved():
    import hashlib

    result = sanitize_image(
        content_type="image/png",
        content=PNG_BYTES,
    )

    assert result.source_sha256 == (
        hashlib.sha256(
            PNG_BYTES
        ).hexdigest()
    )


def test_mime_spoofing_rejected():
    with pytest.raises(ImageSecurityError):
        sanitize_image(
            content_type="image/png",
            content=JPEG_BYTES,
        )


def test_invalid_png_rejected():
    with pytest.raises(ImageSecurityError):
        sanitize_image(
            content_type="image/png",
            content=(
                b"\x89PNG\r\n\x1a\n"
                + b"invalid"
            ),
        )


def test_empty_image_rejected():
    with pytest.raises(ImageSecurityError):
        sanitize_image(
            content_type="image/png",
            content=b"",
        )


def test_unsupported_mime_rejected():
    with pytest.raises(ImageSecurityError):
        sanitize_image(
            content_type="image/gif",
            content=PNG_BYTES,
        )


def test_non_bytes_rejected():
    with pytest.raises(ImageSecurityError):
        sanitize_image(
            content_type="image/png",
            content="not bytes",
        )


def test_oversized_input_rejected():
    with pytest.raises(ImageSecurityError):
        sanitize_image(
            content_type="image/png",
            content=(
                PNG_BYTES
                + b"x" * (20 * 1024 * 1024)
            ),
        )


def test_excessive_width_rejected():
    content = image_bytes(
        width=8200,
        height=1,
    )

    with pytest.raises(ImageSecurityError):
        sanitize_image(
            content_type="image/png",
            content=content,
        )


def test_excessive_height_rejected():
    content = image_bytes(
        width=1,
        height=8200,
    )

    with pytest.raises(ImageSecurityError):
        sanitize_image(
            content_type="image/png",
            content=content,
        )


def test_valid_image_description():
    service, provider = make_service()

    result = service.describe_asset(
        context=context(),
        asset_id="image-1",
        version=1,
        source_bytes=PNG_BYTES,
    )

    assert result.description == (
        "A blue rectangular image."
    )

    assert provider.calls == 1


def test_provider_receives_sanitized_png():
    service, provider = make_service(
        content=JPEG_BYTES,
        content_type="image/jpeg",
    )

    service.describe_asset(
        context=context(),
        asset_id="image-1",
        version=1,
        source_bytes=JPEG_BYTES,
    )

    assert provider.last_image.content_type == (
        "image/png"
    )


def test_missing_asset_grant_blocks_provider():
    service, provider = make_service(
        grant=False
    )

    with pytest.raises(TenantAuthorizationError):
        service.describe_asset(
            context=context(),
            asset_id="image-1",
            version=1,
            source_bytes=PNG_BYTES,
        )

    assert provider.calls == 0


def test_other_user_blocks_provider():
    service, provider = make_service()

    with pytest.raises(TenantAuthorizationError):
        service.describe_asset(
            context=context(
                user="mallory"
            ),
            asset_id="image-1",
            version=1,
            source_bytes=PNG_BYTES,
        )

    assert provider.calls == 0


def test_cross_tenant_blocks_provider():
    service, provider = make_service()

    with pytest.raises(TenantAuthorizationError):
        service.describe_asset(
            context=context(
                tenant="customer-b"
            ),
            asset_id="image-1",
            version=1,
            source_bytes=PNG_BYTES,
        )

    assert provider.calls == 0


def test_modified_source_blocks_provider():
    service, provider = make_service()

    with pytest.raises(AssetIntegrityError):
        service.describe_asset(
            context=context(),
            asset_id="image-1",
            version=1,
            source_bytes=JPEG_BYTES,
        )

    assert provider.calls == 0


def test_invalid_registered_image_blocks_provider():
    service, provider = make_service(
        content=b"not-a-real-image",
    )

    with pytest.raises(ImageSecurityError):
        service.describe_asset(
            context=context(),
            asset_id="image-1",
            version=1,
            source_bytes=b"not-a-real-image",
        )

    assert provider.calls == 0


def test_empty_provider_description_rejected():
    provider = FakeVisionProvider(
        result=""
    )

    service, _ = make_service(
        provider=provider
    )

    with pytest.raises(VisionProcessingError):
        service.describe_asset(
            context=context(),
            asset_id="image-1",
            version=1,
            source_bytes=PNG_BYTES,
        )


def test_provider_failure_propagates():
    provider = FakeVisionProvider(
        fail=True
    )

    service, _ = make_service(
        provider=provider
    )

    with pytest.raises(RuntimeError):
        service.describe_asset(
            context=context(),
            asset_id="image-1",
            version=1,
            source_bytes=PNG_BYTES,
        )


def test_description_retains_asset_version():
    service, _ = make_service()

    result = service.describe_asset(
        context=context(),
        asset_id="image-1",
        version=1,
        source_bytes=PNG_BYTES,
    )

    assert result.asset_version == 1


def test_description_retains_source_digest():
    service, _ = make_service()

    result = service.describe_asset(
        context=context(),
        asset_id="image-1",
        version=1,
        source_bytes=PNG_BYTES,
    )

    assert len(result.source_sha256) == 64


def test_description_retains_model_identity():
    service, _ = make_service()

    result = service.describe_asset(
        context=context(),
        asset_id="image-1",
        version=1,
        source_bytes=PNG_BYTES,
    )

    assert result.provider == "mock"
    assert result.model == "mock-vision-v1"