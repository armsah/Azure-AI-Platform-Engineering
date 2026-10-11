import pytest

from azure_speech_provider import (
    AzureSpeechProvider,
    AzureSpeechSettings,
)
from voice_pipeline import VoicePipelineError


def make_provider():
    return AzureSpeechProvider(
        AzureSpeechSettings(
            key="test-key",
            region="test-region",
        )
    )


def test_invalid_sample_rate_rejected():
    with pytest.raises(ValueError):
        AzureSpeechProvider(
            AzureSpeechSettings(
                key="test",
                region="test",
                sample_rate_hz=8000,
            )
        )


def test_invalid_timeout_rejected():
    with pytest.raises(ValueError):
        AzureSpeechProvider(
            AzureSpeechSettings(
                key="test",
                region="test",
                timeout_seconds=0,
            )
        )


@pytest.mark.asyncio
async def test_empty_audio_rejected():
    provider = make_provider()

    with pytest.raises(VoicePipelineError):
        await provider.transcribe(b"")


@pytest.mark.asyncio
async def test_incomplete_pcm_sample_rejected():
    provider = make_provider()

    with pytest.raises(VoicePipelineError):
        await provider.transcribe(b"\x01")


@pytest.mark.asyncio
async def test_transcription_uses_provider(monkeypatch):
    provider = make_provider()

    monkeypatch.setattr(
        provider,
        "_recognize_sync",
        lambda audio: "Recognized speech",
    )

    result = await provider.transcribe(b"\x00\x00")

    assert result == "Recognized speech"


@pytest.mark.asyncio
async def test_synthesis_returns_pcm_chunks(monkeypatch):
    provider = make_provider()

    monkeypatch.setattr(
        provider,
        "_synthesize_sync",
        lambda text: b"\x00\x00" * 2000,
    )

    chunks = []

    async for chunk in provider.synthesize("Hello"):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert sum(map(len, chunks)) == 4000


@pytest.mark.asyncio
async def test_empty_synthesis_text_rejected():
    provider = make_provider()

    with pytest.raises(VoicePipelineError):
        async for _ in provider.synthesize(" "):
            pass


def test_missing_configuration_rejected(monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)

    with pytest.raises(VoicePipelineError):
        AzureSpeechSettings.from_environment()
