from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from uuid import uuid4


class VoiceSessionError(Exception):
    pass


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    RESPONDING = "responding"
    CLOSED = "closed"


@dataclass
class VoiceSession:
    session_id: str
    tenant_id: str
    user_id: str
    state: VoiceState = VoiceState.IDLE
    turn_id: int = 0
    started_at: float = field(default_factory=time.monotonic)
    first_response_latency_ms: float | None = None
    _turn_started_at: float | None = None


class VoiceSessionManager:
    def __init__(
        self,
        max_audio_frame_bytes: int = 64 * 1024,
        max_sessions: int = 100,
    ) -> None:
        if max_audio_frame_bytes <= 0 or max_sessions <= 0:
            raise ValueError("Voice limits must be positive")

        self.max_audio_frame_bytes = max_audio_frame_bytes
        self.max_sessions = max_sessions
        self._sessions: dict[str, VoiceSession] = {}
        self._lock = RLock()

    def create(self, tenant_id: str, user_id: str) -> VoiceSession:
        if not tenant_id or not user_id:
            raise VoiceSessionError("Trusted identity is required")

        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                raise VoiceSessionError("Voice session capacity exceeded")

            session = VoiceSession(
                session_id=uuid4().hex,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            self._sessions[session.session_id] = session
            return session

    def get(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> VoiceSession:
        with self._lock:
            session = self._sessions.get(session_id)

            if (
                session is None
                or session.tenant_id != tenant_id
                or session.user_id != user_id
            ):
                raise VoiceSessionError("Voice session unavailable")

            return session

    def receive_audio(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        audio: bytes,
    ) -> int:
        if not audio or len(audio) > self.max_audio_frame_bytes:
            raise VoiceSessionError("Invalid audio frame size")

        with self._lock:
            session = self.get(session_id, tenant_id, user_id)

            if session.state == VoiceState.CLOSED:
                raise VoiceSessionError("Voice session is closed")

            if session.state != VoiceState.LISTENING:
                session.turn_id += 1
                session._turn_started_at = time.monotonic()
                session.first_response_latency_ms = None

            session.state = VoiceState.LISTENING
            return session.turn_id

    def begin_response(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> float:
        with self._lock:
            session = self.get(session_id, tenant_id, user_id)

            if session.state != VoiceState.LISTENING:
                raise VoiceSessionError("No active audio turn")

            session.state = VoiceState.RESPONDING

            latency_ms = (
                time.monotonic() - session._turn_started_at
            ) * 1000

            session.first_response_latency_ms = latency_ms
            return latency_ms

    def interrupt(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> None:
        with self._lock:
            session = self.get(session_id, tenant_id, user_id)

            if session.state == VoiceState.CLOSED:
                raise VoiceSessionError("Voice session is closed")

            session.state = VoiceState.IDLE
            session._turn_started_at = None

    def close(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> None:
        with self._lock:
            session = self.get(session_id, tenant_id, user_id)
            session.state = VoiceState.CLOSED
            del self._sessions[session_id]
