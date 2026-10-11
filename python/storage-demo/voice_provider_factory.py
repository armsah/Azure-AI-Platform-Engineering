from __future__ import annotations

import os

from azure_speech_provider import (
    AzureSpeechProvider,
    AzureSpeechSettings,
)
from voice_pipeline import OfflineSpeechProvider, SpeechProvider


def create_speech_provider() -> SpeechProvider:
    mode = os.getenv("VOICE_PROVIDER", "offline").strip().lower()

    if mode == "offline":
        return OfflineSpeechProvider()

    if mode == "azure":
        return AzureSpeechProvider(
            AzureSpeechSettings.from_environment()
        )

    raise ValueError(f"Unsupported VOICE_PROVIDER: {mode}")
