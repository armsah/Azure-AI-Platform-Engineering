from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import partial

from voice_pipeline import VoicePipelineError


@dataclass(frozen=True)
class AzureSpeechSettings:
    key: str
    region: str
    recognition_language: str = "en-US"
    voice_name: str = "en-US-JennyNeural"
    sample_rate_hz: int = 16000
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> "AzureSpeechSettings":
        key = os.getenv("AZURE_SPEECH_KEY", "")
        region = os.getenv("AZURE_SPEECH_REGION", "")

        if not key or not region:
            raise VoicePipelineError(
                "AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are required"
            )

        return cls(key=key, region=region)


class AzureSpeechProvider:
    """
    Azure Speech adapter.

    Input: raw mono 16-bit PCM at 16 kHz.
    Output: raw mono 16-bit PCM at 16 kHz.

    This adapter is not a fully streaming STT implementation:
    transcription begins after the client commits its audio turn.
    """

    def __init__(self, settings: AzureSpeechSettings):
        if settings.sample_rate_hz != 16000:
            raise ValueError("Only 16 kHz PCM is supported")

        if settings.timeout_seconds <= 0:
            raise ValueError("Speech timeout must be positive")

        self.settings = settings

    def _speech_sdk(self):
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as exc:
            raise VoicePipelineError(
                "Azure Speech SDK is not installed"
            ) from exc

        return speechsdk

    def _recognize_sync(self, audio: bytes) -> str:
        speechsdk = self._speech_sdk()

        config = speechsdk.SpeechConfig(
            subscription=self.settings.key,
            region=self.settings.region,
        )
        config.speech_recognition_language = (
            self.settings.recognition_language
        )

        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=16000,
            bits_per_sample=16,
            channels=1,
        )

        stream = speechsdk.audio.PushAudioInputStream(
            stream_format=audio_format
        )

        stream.write(audio)
        stream.close()

        audio_config = speechsdk.audio.AudioConfig(stream=stream)

        recognizer = speechsdk.SpeechRecognizer(
            speech_config=config,
            audio_config=audio_config,
        )

        result = recognizer.recognize_once_async().get()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text

        if result.reason == speechsdk.ResultReason.NoMatch:
            raise VoicePipelineError("Speech could not be recognized")

        raise VoicePipelineError("Azure speech recognition failed")

    def _synthesize_sync(self, text: str) -> bytes:
        speechsdk = self._speech_sdk()

        config = speechsdk.SpeechConfig(
            subscription=self.settings.key,
            region=self.settings.region,
        )

        config.speech_synthesis_voice_name = (
            self.settings.voice_name
        )

        config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat
            .Raw16Khz16BitMonoPcm
        )

        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=config,
            audio_config=None,
        )

        result = synthesizer.speak_text_async(text).get()

        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            raise VoicePipelineError("Azure speech synthesis failed")

        return result.audio_data

    async def transcribe(self, audio: bytes) -> str:
        if not audio or len(audio) % 2:
            raise VoicePipelineError(
                "Audio must contain complete 16-bit PCM samples"
            )

        return await asyncio.wait_for(
            asyncio.to_thread(self._recognize_sync, audio),
            timeout=self.settings.timeout_seconds,
        )

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        if not text.strip():
            raise VoicePipelineError("Text is required")

        audio = await asyncio.wait_for(
            asyncio.to_thread(self._synthesize_sync, text),
            timeout=self.settings.timeout_seconds,
        )

        chunk_bytes = 3200

        for offset in range(0, len(audio), chunk_bytes):
            await asyncio.sleep(0)
            yield audio[offset:offset + chunk_bytes]
