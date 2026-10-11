import pytest

from voice_sessions import (
    VoiceSessionError,
    VoiceSessionManager,
    VoiceState,
)


def test_voice_session_lifecycle():
    manager = VoiceSessionManager()
    session = manager.create("tenant-a", "user-a")

    assert session.state == VoiceState.IDLE

    turn_id = manager.receive_audio(
        session.session_id,
        "tenant-a",
        "user-a",
        b"audio-frame",
    )

    assert turn_id == 1
    assert session.state == VoiceState.LISTENING

    latency = manager.begin_response(
        session.session_id,
        "tenant-a",
        "user-a",
    )

    assert latency >= 0
    assert session.state == VoiceState.RESPONDING

    manager.interrupt(
        session.session_id,
        "tenant-a",
        "user-a",
    )

    assert session.state == VoiceState.IDLE

    manager.close(
        session.session_id,
        "tenant-a",
        "user-a",
    )

    with pytest.raises(VoiceSessionError):
        manager.get(session.session_id, "tenant-a", "user-a")


def test_voice_session_tenant_isolation():
    manager = VoiceSessionManager()
    session = manager.create("tenant-a", "user-a")

    with pytest.raises(VoiceSessionError):
        manager.get(session.session_id, "tenant-b", "user-a")

    with pytest.raises(VoiceSessionError):
        manager.get(session.session_id, "tenant-a", "user-b")


def test_voice_frame_size_validation():
    manager = VoiceSessionManager(max_audio_frame_bytes=4)
    session = manager.create("tenant-a", "user-a")

    for audio in (b"", b"12345"):
        with pytest.raises(VoiceSessionError):
            manager.receive_audio(
                session.session_id,
                "tenant-a",
                "user-a",
                audio,
            )


def test_voice_session_capacity():
    manager = VoiceSessionManager(max_sessions=1)
    manager.create("tenant-a", "user-a")

    with pytest.raises(VoiceSessionError):
        manager.create("tenant-a", "user-b")


def test_voice_interruption_starts_new_turn():
    manager = VoiceSessionManager()
    session = manager.create("tenant-a", "user-a")

    first_turn = manager.receive_audio(
        session.session_id, "tenant-a", "user-a", b"first"
    )

    manager.begin_response(
        session.session_id, "tenant-a", "user-a"
    )

    manager.interrupt(
        session.session_id, "tenant-a", "user-a"
    )

    second_turn = manager.receive_audio(
        session.session_id, "tenant-a", "user-a", b"second"
    )

    assert second_turn == first_turn + 1
