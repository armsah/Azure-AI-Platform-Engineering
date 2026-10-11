import pytest

from azure_speech_provider import AzureSpeechProvider
from voice_pipeline import OfflineSpeechProvider
from voice_provider_factory import (
    VoiceConfigurationError,
    create_speech_provider,
)


@pytest.mark.parametrize(
    "environment",
    ["production", "staging"],
)
def test_production_requires_explicit_provider(
    monkeypatch,
    environment,
):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.delenv("VOICE_PROVIDER", raising=False)

    with pytest.raises(VoiceConfigurationError):
        create_speech_provider()


@pytest.mark.parametrize(
    "environment",
    ["production", "staging"],
)
def test_offline_provider_forbidden_in_production(
    monkeypatch,
    environment,
):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("VOICE_PROVIDER", "offline")

    with pytest.raises(VoiceConfigurationError):
        create_speech_provider()


def test_development_defaults_to_offline(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("VOICE_PROVIDER", raising=False)

    assert isinstance(
        create_speech_provider(),
        OfflineSpeechProvider,
    )


def test_production_azure_provider(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("VOICE_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")

    assert isinstance(
        create_speech_provider(),
        AzureSpeechProvider,
    )


def test_production_azure_requires_credentials(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("VOICE_PROVIDER", "azure")
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)

    with pytest.raises(Exception):
        create_speech_provider()


def test_unknown_environment_rejected(monkeypatch):
    monkeypatch.setenv("APP_ENV", "unknown")

    with pytest.raises(VoiceConfigurationError):
        create_speech_provider()
