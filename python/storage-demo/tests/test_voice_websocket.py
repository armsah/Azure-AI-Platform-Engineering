from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from voice_sessions import VoiceSessionManager
from voice_websocket import (
    VoiceTransportDependencies,
    create_voice_app,
)


@dataclass
class FakeContext:
    tenant_id: str
    user_id: str


def authenticate(token: str):
    if token == "valid-token-a":
        return FakeContext("tenant-a", "user-a")

    if token == "valid-token-b":
        return FakeContext("tenant-b", "user-b")

    raise ValueError("Invalid token")


@pytest.fixture
def environment():
    sessions = VoiceSessionManager(max_audio_frame_bytes=16)

    app = create_voice_app(
        VoiceTransportDependencies(
            sessions=sessions,
            authenticate=authenticate,
        )
    )

    return TestClient(app), sessions


def connect(client, token):
    return client.websocket_connect(
        "/api/v1/voice/ws",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_authenticated_voice_session(environment):
    client, sessions = environment

    with connect(client, "valid-token-a") as ws:
        started = ws.receive_json()

        assert started["event"] == "session.started"
        assert started["session_id"]

        assert len(sessions._sessions) == 1

    assert len(sessions._sessions) == 0


def test_missing_token_rejected(environment):
    client, _ = environment

    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/api/v1/voice/ws"):
            pass

    assert error.value.code == 1008


def test_invalid_token_rejected(environment):
    client, _ = environment

    with pytest.raises(WebSocketDisconnect) as error:
        with connect(client, "invalid-token"):
            pass

    assert error.value.code == 1008


def test_audio_frame_and_response_lifecycle(environment):
    client, _ = environment

    with connect(client, "valid-token-a") as ws:
        ws.receive_json()

        ws.send_bytes(b"audio")

        received = ws.receive_json()

        assert received["event"] == "audio.received"
        assert received["turn_id"] == 1
        assert received["bytes_received"] == 5

        ws.send_json({"event": "response.begin"})

        response = ws.receive_json()

        assert response["event"] == "response.started"
        assert response["latency_ms"] >= 0

        ws.send_json({"event": "interrupt"})

        interrupted = ws.receive_json()

        assert interrupted["event"] == "response.interrupted"

        ws.send_bytes(b"next")

        next_turn = ws.receive_json()

        assert next_turn["turn_id"] == 2


def test_oversized_audio_rejected(environment):
    client, sessions = environment

    with connect(client, "valid-token-a") as ws:
        ws.receive_json()

        ws.send_bytes(b"x" * 17)

        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()

        assert error.value.code == 1009

    assert len(sessions._sessions) == 0


def test_invalid_command_rejected(environment):
    client, _ = environment

    with connect(client, "valid-token-a") as ws:
        ws.receive_json()

        ws.send_text("not-json")

        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()

        assert error.value.code == 1003


def test_cross_tenant_sessions_are_distinct(environment):
    client, sessions = environment

    with connect(client, "valid-token-a") as first:
        first_started = first.receive_json()

        with connect(client, "valid-token-b") as second:
            second_started = second.receive_json()

            assert (
                first_started["session_id"]
                != second_started["session_id"]
            )

            assert len(sessions._sessions) == 2

    assert len(sessions._sessions) == 0


def test_session_close_command(environment):
    client, sessions = environment

    with connect(client, "valid-token-a") as ws:
        ws.receive_json()

        ws.send_json({"event": "session.close"})

        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()

        assert error.value.code == 1000

    assert len(sessions._sessions) == 0
