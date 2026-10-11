import asyncio

import pytest

from voice_pipeline import (
    OfflineSpeechProvider,
    VoicePipeline,
    VoicePipelineError,
)


@pytest.mark.asyncio
async def test_offline_transcription():
    provider = OfflineSpeechProvider()

    assert (
        await provider.transcribe(b"audio")
        == "offline transcription"
    )


@pytest.mark.asyncio
async def test_empty_audio_rejected():
    provider = OfflineSpeechProvider()

    with pytest.raises(VoicePipelineError):
        await provider.transcribe(b"")


@pytest.mark.asyncio
async def test_voice_pipeline_generates_audio():
    pipeline = VoicePipeline(OfflineSpeechProvider())

    result, chunks = await pipeline.run(
        b"audio",
        "Hello from Azure",
    )

    assert result.transcript == "offline transcription"
    assert result.response_text == "Hello from Azure"
    assert chunks == [b"Hello", b"from", b"Azure"]
    assert result.transcription_latency_ms >= 0
    assert result.first_audio_latency_ms is not None


@pytest.mark.asyncio
async def test_pre_cancelled_pipeline():
    pipeline = VoicePipeline(OfflineSpeechProvider())
    cancel = asyncio.Event()
    cancel.set()

    with pytest.raises(asyncio.CancelledError):
        await pipeline.run(
            b"audio",
            "response",
            cancel,
        )


@pytest.mark.asyncio
async def test_cancellation_during_synthesis():
    cancel = asyncio.Event()

    class CancellingProvider(OfflineSpeechProvider):
        async def synthesize(self, text):
            yield b"first"
            cancel.set()
            yield b"second"

    pipeline = VoicePipeline(CancellingProvider())

    with pytest.raises(asyncio.CancelledError):
        await pipeline.run(
            b"audio",
            "response",
            cancel,
        )
