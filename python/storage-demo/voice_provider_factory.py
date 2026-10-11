from __future__ import annotations

import os

from azure_speech_provider import (
    AzureSpeechProvider,
    AzureSpeechSettings,
)
from voice_pipeline import OfflineSpeechProvider, SpeechProvider


class VoiceConfigurationError(ValueError):
    pass


def create_speech_provider() -> SpeechProvider:
    environment = os.getenv(
        "APP_ENV",
        "development",
    ).strip().lower()

    mode = os.getenv(
        "VOICE_PROVIDER",
        "",
    ).strip().lower()

    if environment not in {
        "development",
        "test",
        "staging",
        "production",
    }:
        raise VoiceConfigurationError(
            f"Unsupported APP_ENV: {environment}"
        )

    if not mode:
        if environment in {"production", "staging"}:
            raise VoiceConfigurationError(
                "VOICE_PROVIDER must be explicitly configured"
            )

        mode = "offline"

    if mode == "offline":
        if environment not in {"development", "test"}:
            raise VoiceConfigurationError(
                "Offline speech is prohibited outside development/test"
            )

        return OfflineSpeechProvider()

    if mode == "azure":
        return AzureSpeechProvider(
            AzureSpeechSettings.from_environment()
        )

    raise VoiceConfigurationError(
        f"Unsupported VOICE_PROVIDER: {mode}"
    )
