import pytest

from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch

from multimodal_assets import AssetModality

from secure_video_processing import (
    VideoFrame,
    VideoLimits,
    VideoSecurityError,
    extract_video_frames,
)

from video_intelligence import (
    VideoIntelligenceError,
    VideoIntelligenceService,
)


def _video_service():
    content = b"registered-video-content"

    asset = SimpleNamespace(
        asset_id="video-1",
        version=1,
        modality=AssetModality.VIDEO,
        content_type="video/mp4",
        content_sha256=sha256(content).hexdigest(),
    )

    assets = Mock()
    assets.verify_asset.return_value = asset

    provider = Mock()
    provider.describe.return_value = "A person walking."

    service = VideoIntelligenceService(
        assets=assets,
        provider=provider,
        provider_name="test-provider",
        model_name="test-model",
    )

    context = SimpleNamespace(tenant_id="tenant-a")

    return service, assets, provider, context, content


def test_video_analysis_preserves_timestamps_and_provenance():
    service, assets, provider, context, content = _video_service()

    frames = [
        VideoFrame(
            timestamp_seconds=0.0,
            jpeg_bytes=b"frame-1",
        ),
        VideoFrame(
            timestamp_seconds=2.5,
            jpeg_bytes=b"frame-2",
        ),
    ]

    sanitized = SimpleNamespace(
        sanitized_sha256="sanitized-frame-hash",
    )

    with (
        patch(
            "video_intelligence.extract_video_frames",
            return_value=frames,
        ) as extractor,
        patch(
            "video_intelligence.sanitize_image",
            return_value=sanitized,
        ) as sanitizer,
    ):
        result = service.analyze_asset(
            context=context,
            asset_id="video-1",
            version=1,
            source_bytes=content,
        )

    assets.verify_asset.assert_called_once_with(
        context=context,
        asset_id="video-1",
        version=1,
        content=content,
    )

    extractor.assert_called_once()
    assert sanitizer.call_count == 2
    assert provider.describe.call_count == 2

    assert result.tenant_id == "tenant-a"
    assert result.asset_id == "video-1"
    assert result.source_sha256 == sha256(content).hexdigest()

    assert len(result.frames) == 2
    assert result.frames[0].timestamp_seconds == 0.0
    assert result.frames[1].timestamp_seconds == 2.5
    assert result.frames[0].sanitized_sha256 == "sanitized-frame-hash"


def test_video_analysis_rejects_tampered_source():
    service, assets, provider, context, content = _video_service()

    with patch(
        "video_intelligence.extract_video_frames"
    ) as extractor:
        with pytest.raises(
            VideoIntelligenceError,
            match="integrity mismatch",
        ):
            service.analyze_asset(
                context=context,
                asset_id="video-1",
                version=1,
                source_bytes=b"tampered-content",
            )

    extractor.assert_not_called()
    provider.describe.assert_not_called()


def test_video_analysis_rejects_empty_provider_output():
    service, assets, provider, context, content = _video_service()
    provider.describe.return_value = " "

    frames = [
        VideoFrame(
            timestamp_seconds=0.0,
            jpeg_bytes=b"frame-1",
        )
    ]

    with (
        patch(
            "video_intelligence.extract_video_frames",
            return_value=frames,
        ),
        patch(
            "video_intelligence.sanitize_image",
            return_value=SimpleNamespace(
                sanitized_sha256="hash",
            ),
        ),
    ):
        with pytest.raises(
            VideoIntelligenceError,
            match="empty description",
        ):
            service.analyze_asset(
                context=context,
                asset_id="video-1",
                version=1,
                source_bytes=content,
            )

def test_rejects_empty_video():
    with pytest.raises(VideoSecurityError, match="Empty video"):
        extract_video_frames(b"")


def test_rejects_invalid_mp4():
    with pytest.raises(VideoSecurityError, match="Invalid MP4"):
        extract_video_frames(b"not-an-mp4")


def test_rejects_oversized_video():
    limits = VideoLimits(max_bytes=8)

    with pytest.raises(VideoSecurityError, match="size limit"):
        extract_video_frames(b"x" * 16, limits=limits)


def test_rejects_invalid_frame_limit():
    limits = VideoLimits(max_frames=0)

    with pytest.raises(VideoSecurityError, match="frame limit"):
        extract_video_frames(
            b"\x00\x00\x00\x18ftypisom",
            limits=limits,
        )

def test_rejects_non_video_before_decoding():
    asset = Mock()
    asset.modality = AssetModality.IMAGE

    assets = Mock()
    assets.verify_asset.return_value = asset

    service = VideoIntelligenceService(
        assets=assets,
        provider=Mock(),
        provider_name="test-provider",
        model_name="test-model",
    )

    with patch("video_intelligence.extract_video_frames") as extractor:
        with pytest.raises(
            VideoIntelligenceError,
            match="not a video",
        ):
            service.analyze_asset(
                context=Mock(),
                asset_id="asset-1",
                version=1,
                source_bytes=b"test",
            )

        extractor.assert_not_called()
