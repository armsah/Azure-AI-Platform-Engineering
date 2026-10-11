from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from voice_pipeline import OfflineSpeechProvider
from voice_sessions import VoiceSessionManager
from voice_streaming import (
    StreamingVoiceDependencies,
    create_streaming_voice_app,
)


@dataclass
class FakeContext:
    tenant_id: str
    user_id: str


def authenticate(token):
    if token != "valid":
        raise ValueError("Invalid token")

    return FakeContext("tenant-a", "user-a")


@pytest.fixture
def environment():
    sessions = VoiceSessionManager(max_audio_frame_bytes=16)

    app = create_streaming_voice_app(
        StreamingVoiceDependencies(
            sessions=sessions,
            authenticate=authenticate,
            provider=OfflineSpeechProvider(),
        )
    )

    return TestClient(app), sessions


def connect(client, token="valid"):
    return client.websocket_connect(
        "/api/v1/voice/stream",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_streaming_voice_end_to_end(environment):
    client, sessions = environment

    with connect(client) as ws:
        started = ws.receive_json()
        assert started["event"] == "session.started"

        ws.send_bytes(b"audio")
        ws.send_json({"event": "audio.commit"})

        transcript = ws.receive_json()
        assert transcript["event"] == "transcription.completed"
        assert transcript["transcript"] == "offline transcription"

        response = ws.receive_json()
        assert response["event"] == "response.started"
        assert response["first_audio_latency_ms"] >= 0

        audio_chunks = [
            ws.receive_bytes()
            for _ in range(4)
        ]

        assert audio_chunks == [
            b"You",
            b"said:",
            b"offline",
            b"transcription",
        ]

        completed = ws.receive_json()
        assert completed["event"] == "response.completed"

    assert len(sessions._sessions) == 0


def test_streaming_missing_token_rejected(environment):
    client, _ = environment

    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/api/v1/voice/stream"):
            pass

    assert error.value.code == 1008


def test_streaming_invalid_token_rejected(environment):
    client, _ = environment

    with pytest.raises(WebSocketDisconnect) as error:
        with connect(client, "invalid"):
            pass

    assert error.value.code == 1008


def test_streaming_empty_commit(environment):
    client, _ = environment

    with connect(client) as ws:
        ws.receive_json()

        ws.send_json({"event": "audio.commit"})

        error = ws.receive_json()

        assert error == {
            "event": "error",
            "code": "empty_audio",
        }


def test_streaming_oversized_frame(environment):
    client, _ = environment

    with connect(client) as ws:
        ws.receive_json()

        ws.send_bytes(b"x" * 17)

        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()

        assert error.value.code == 1009


def test_streaming_interruption(environment):
    client, _ = environment

    with connect(client) as ws:
        ws.receive_json()

        ws.send_json({"event": "interrupt"})

        interrupted = ws.receive_json()

        assert interrupted["event"] == "response.interrupted"


def test_streaming_session_close(environment):
    client, sessions = environment

    with connect(client) as ws:
        ws.receive_json()

        ws.send_json({"event": "session.close"})

        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()

        assert error.value.code == 1000

    assert len(sessions._sessions) == 0
