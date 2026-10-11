from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import AsyncIterator, Protocol


class VoicePipelineError(Exception):
    pass


class SpeechProvider(Protocol):
    async def transcribe(self, audio: bytes) -> str:
        ...

    def synthesize(self, text: str) -> AsyncIterator[bytes]:
        ...


@dataclass(frozen=True)
class VoiceResult:
    transcript: str
    response_text: str
    transcription_latency_ms: float
    first_audio_latency_ms: float | None


class OfflineSpeechProvider:
    """Deterministic test provider; not real speech recognition."""

    async def transcribe(self, audio: bytes) -> str:
        if not audio:
            raise VoicePipelineError("Audio is required")

        return "offline transcription"

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        for word in text.split():
            await asyncio.sleep(0)
            yield word.encode("utf-8")


class VoicePipeline:
    def __init__(self, provider: SpeechProvider):
        self.provider = provider

    async def run(
        self,
        audio: bytes,
        response_text: str,
        cancel: asyncio.Event | None = None,
    ) -> tuple[VoiceResult, list[bytes]]:
        cancel = cancel or asyncio.Event()

        if cancel.is_set():
            raise asyncio.CancelledError()

        started = time.monotonic()

        transcript = await self.provider.transcribe(audio)

        transcription_latency = (
            time.monotonic() - started
        ) * 1000

        if cancel.is_set():
            raise asyncio.CancelledError()

        output: list[bytes] = []
        first_audio_latency = None

        async for chunk in self.provider.synthesize(response_text):
            if cancel.is_set():
                raise asyncio.CancelledError()

            if first_audio_latency is None:
                first_audio_latency = (
                    time.monotonic() - started
                ) * 1000

            output.append(chunk)

        return (
            VoiceResult(
                transcript=transcript,
                response_text=response_text,
                transcription_latency_ms=transcription_latency,
                first_audio_latency_ms=first_audio_latency,
            ),
            output,
        )
