from hashlib import sha256
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from multimodal_api import (
    MultimodalAPIDependencies,
    create_multimodal_app,
    require_authenticated_context,
)
from multimodal_assets import MAX_ASSET_BYTES, MultimodalAssetRegistry
from multimodal_authorization import (
    AssetGrant,
    AuthorizedMultimodalAssetService,
    InMemoryAssetAccessPolicy,
)
from request_context import RequestContext
from secure_video_processing import VideoFrame
from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantBoundary,
    TenantMembership,
)
from video_intelligence import VideoIntelligenceService


DIRECTORY = "directory-1"
TENANT = "tenant-a"
USER = "alice"
VIDEO = b"\x00\x00\x00\x18ftypisomtest-video"


def context(*, tenant=TENANT, user=USER):
    return RequestContext(
        directory_tenant_id=DIRECTORY,
        tenant_id=tenant,
        user_id=user,
        groups=(),
        roles=("AI.User",),
    )


def make_environment(
    *,
    authenticated=True,
    tenant=TENANT,
    user=USER,
    grant=True,
    register=True,
    video_enabled=True,
):
    memberships = InMemoryTenantMembershipStore(
        (
            TenantMembership(
                directory_tenant_id=DIRECTORY,
                user_id=USER,
                business_tenant_id=TENANT,
            ),
        )
    )

    boundary = TenantBoundary(memberships)
    registry = MultimodalAssetRegistry()
    policy = InMemoryAssetAccessPolicy()

    if register:
        registry.register(
            tenant_id=TENANT,
            asset_id="video-1",
            filename="clip.mp4",
            content_type="video/mp4",
            content=VIDEO,
        )

    if grant:
        policy.grant(
            AssetGrant(
                tenant_id=TENANT,
                asset_id="video-1",
                user_id=USER,
            )
        )

    authorized_assets = AuthorizedMultimodalAssetService(
        registry=registry,
        boundary=boundary,
        access_policy=policy,
    )

    provider = Mock()
    provider.describe.return_value = "A person walking."

    service = VideoIntelligenceService(
        assets=authorized_assets,
        provider=provider,
        provider_name="test-vision",
        model_name="test-model",
    )

    app = create_multimodal_app(
        MultimodalAPIDependencies(
            boundary=boundary,
            assets=registry,
            answers=Mock(),
            video_intelligence=service if video_enabled else None,
        ),
        enable_entra_auth=False,
    )

    if authenticated:
        app.dependency_overrides[
            require_authenticated_context
        ] = lambda: context(tenant=tenant, user=user)

    return TestClient(app), provider


def analyze(client, content=VIDEO, content_type="video/mp4"):
    return client.post(
        "/api/v1/multimodal/videos/video-1/versions/1/analyze",
        files={
            "file": (
                "clip.mp4",
                content,
                content_type,
            )
        },
    )


def test_authorized_video_analysis_preserves_provenance():
    client, provider = make_environment()

    with patch(
        "video_intelligence.extract_video_frames_isolated",
        return_value=(
            VideoFrame(
                timestamp_seconds=1.5,
                jpeg_bytes=b"frame-data",
            ),
        ),
    ), patch(
        "video_intelligence.sanitize_image",
        return_value=Mock(
            sanitized_sha256="sanitized-frame-sha",
        ),
    ):
        response = analyze(client)

    assert response.status_code == 200
    body = response.json()

    assert body["tenant_id"] == TENANT
    assert body["asset_id"] == "video-1"
    assert body["asset_version"] == 1
    assert body["source_sha256"] == sha256(VIDEO).hexdigest()
    assert body["provider"] == "test-vision"
    assert body["model"] == "test-model"
    assert body["frames"][0]["timestamp_seconds"] == 1.5
    assert body["frames"][0]["description"] == "A person walking."
    assert body["frames"][0]["sanitized_sha256"] == "sanitized-frame-sha"

    provider.describe.assert_called_once()


def test_video_analysis_requires_authentication():
    client, provider = make_environment(authenticated=False)

    response = analyze(client)

    assert response.status_code == 401
    provider.describe.assert_not_called()


def test_video_analysis_rejects_unknown_user():
    client, provider = make_environment(user="mallory")

    response = analyze(client)

    assert response.status_code == 403
    provider.describe.assert_not_called()


def test_video_analysis_rejects_cross_tenant_request():
    client, provider = make_environment(tenant="tenant-b")

    response = analyze(client)

    assert response.status_code == 403
    provider.describe.assert_not_called()


def test_video_analysis_requires_asset_grant():
    client, provider = make_environment(grant=False)

    response = analyze(client)

    assert response.status_code == 403
    provider.describe.assert_not_called()


def test_video_analysis_rejects_unknown_asset():
    client, provider = make_environment(register=False)

    response = analyze(client)

    # The authorization policy grants access, but no asset exists.
    assert response.status_code == 404
    provider.describe.assert_not_called()


def test_video_analysis_rejects_tampered_source():
    client, provider = make_environment()

    response = analyze(client, content=b"tampered-video")

    assert response.status_code == 422
    provider.describe.assert_not_called()


def test_video_analysis_rejects_unsupported_media_type():
    client, provider = make_environment()

    response = analyze(
        client,
        content_type="text/plain",
    )

    assert response.status_code == 415
    provider.describe.assert_not_called()


def test_video_analysis_rejects_empty_video():
    client, provider = make_environment()

    response = analyze(client, content=b"")

    assert response.status_code == 400
    provider.describe.assert_not_called()


def test_video_analysis_rejects_oversized_video():
    client, provider = make_environment()

    response = analyze(
        client,
        content=b"x" * (MAX_ASSET_BYTES + 1),
    )

    assert response.status_code == 413
    provider.describe.assert_not_called()


def test_video_analysis_rejects_invalid_version():
    client, provider = make_environment()

    response = client.post(
        "/api/v1/multimodal/videos/video-1/versions/0/analyze",
        files={
            "file": (
                "clip.mp4",
                VIDEO,
                "video/mp4",
            )
        },
    )

    assert response.status_code == 422
    provider.describe.assert_not_called()


def test_video_analysis_service_unavailable():
    client, provider = make_environment(video_enabled=False)

    response = analyze(client)

    assert response.status_code == 503
    provider.describe.assert_not_called()
