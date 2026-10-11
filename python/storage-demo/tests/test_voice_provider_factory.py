import pytest

from azure_speech_provider import AzureSpeechProvider
from voice_pipeline import OfflineSpeechProvider
from voice_provider_factory import create_speech_provider


def test_default_provider_is_offline(monkeypatch):
    monkeypatch.delenv("VOICE_PROVIDER", raising=False)

    assert isinstance(
        create_speech_provider(),
        OfflineSpeechProvider,
    )


def test_explicit_offline_provider(monkeypatch):
    monkeypatch.setenv("VOICE_PROVIDER", "offline")

    assert isinstance(
        create_speech_provider(),
        OfflineSpeechProvider,
    )


def test_azure_provider_selection(monkeypatch):
    monkeypatch.setenv("VOICE_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")

    assert isinstance(
        create_speech_provider(),
        AzureSpeechProvider,
    )


def test_azure_provider_requires_configuration(monkeypatch):
    monkeypatch.setenv("VOICE_PROVIDER", "azure")
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)

    with pytest.raises(Exception):
        create_speech_provider()


def test_unsupported_provider_rejected(monkeypatch):
    monkeypatch.setenv("VOICE_PROVIDER", "unsupported")

    with pytest.raises(ValueError):
        create_speech_provider()
