from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Callable

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from voice_pipeline import OfflineSpeechProvider, SpeechProvider
from voice_sessions import VoiceSessionError, VoiceSessionManager
from voice_websocket import authenticate_voice_token


@dataclass
class StreamingVoiceDependencies:
    sessions: VoiceSessionManager
    authenticate: Callable[[str], object]
    provider: SpeechProvider


def create_streaming_voice_app(
    dependencies: StreamingVoiceDependencies | None = None,
) -> FastAPI:
    dependencies = dependencies or StreamingVoiceDependencies(
        sessions=VoiceSessionManager(),
        authenticate=authenticate_voice_token,
        provider=OfflineSpeechProvider(),
    )

    app = FastAPI(title="Azure AI Platform — Streaming Voice")

    @app.websocket("/api/v1/voice/stream")
    async def stream_voice(websocket: WebSocket):
        authorization = websocket.headers.get("authorization", "")
        scheme, separator, token = authorization.partition(" ")

        if not separator or scheme.lower() != "bearer" or not token.strip():
            await websocket.close(code=1008)
            return

        try:
            context = dependencies.authenticate(token.strip())
            tenant_id = context.tenant_id
            user_id = context.user_id

            if not tenant_id or not user_id:
                raise ValueError("Missing authenticated identity")
        except Exception:
            await websocket.close(code=1008)
            return

        try:
            session = dependencies.sessions.create(tenant_id, user_id)
        except VoiceSessionError:
            await websocket.close(code=1013)
            return

        await websocket.accept()

        active_task: asyncio.Task | None = None
        send_lock = asyncio.Lock()
        audio_buffer = bytearray()
        max_turn_bytes = 2 * 1024 * 1024

        async def send_event(payload: dict):
            async with send_lock:
                await websocket.send_json(payload)

        async def send_audio(chunk: bytes):
            async with send_lock:
                await websocket.send_bytes(chunk)

        async def process_turn(audio: bytes, turn_id: int):
            started = time.monotonic()

            try:
                transcript = await dependencies.provider.transcribe(audio)

                transcription_latency = (
                    time.monotonic() - started
                ) * 1000

                # Deterministic response until the AI assistant is integrated.
                response_text = f"You said: {transcript}"

                first_audio_latency = None

                await send_event({
                    "event": "transcription.completed",
                    "turn_id": turn_id,
                    "transcript": transcript,
                    "latency_ms": round(transcription_latency, 2),
                })

                async for chunk in dependencies.provider.synthesize(
                    response_text
                ):
                    if first_audio_latency is None:
                        first_audio_latency = (
                            time.monotonic() - started
                        ) * 1000

                        await send_event({
                            "event": "response.started",
                            "turn_id": turn_id,
                            "first_audio_latency_ms": round(
                                first_audio_latency, 2
                            ),
                        })

                    await send_audio(chunk)

                await send_event({
                    "event": "response.completed",
                    "turn_id": turn_id,
                })

            except asyncio.CancelledError:
                raise
            except Exception:
                await send_event({
                    "event": "error",
                    "code": "processing_failed",
                    "turn_id": turn_id,
                })

        try:
            await send_event({
                "event": "session.started",
                "session_id": session.session_id,
            })

            while True:
                message = await websocket.receive()

                if message["type"] == "websocket.disconnect":
                    break

                frame = message.get("bytes")

                if frame is not None:
                    if active_task is not None and not active_task.done():
                        await send_event({
                            "event": "error",
                            "code": "response_active",
                        })
                        continue

                    if (
                        not frame
                        or len(frame) > dependencies.sessions.max_audio_frame_bytes
                        or len(audio_buffer) + len(frame) > max_turn_bytes
                    ):
                        await websocket.close(code=1009)
                        break

                    dependencies.sessions.receive_audio(
                        session.session_id,
                        tenant_id,
                        user_id,
                        frame,
                    )

                    audio_buffer.extend(frame)
                    continue

                text = message.get("text")

                if text is None:
                    await websocket.close(code=1003)
                    break

                try:
                    command = json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    await websocket.close(code=1003)
                    break

                if not isinstance(command, dict):
                    await websocket.close(code=1003)
                    break

                event = command.get("event")

                if event == "audio.commit":
                    if active_task is not None and not active_task.done():
                        await send_event({
                            "event": "error",
                            "code": "response_active",
                        })
                        continue

                    if not audio_buffer:
                        await send_event({
                            "event": "error",
                            "code": "empty_audio",
                        })
                        continue

                    audio = bytes(audio_buffer)
                    audio_buffer.clear()

                    turn_id = session.turn_id

                    active_task = asyncio.create_task(
                        process_turn(audio, turn_id)
                    )

                elif event == "interrupt":
                    if active_task is not None:
                        active_task.cancel()

                        try:
                            await active_task
                        except asyncio.CancelledError:
                            pass

                        active_task = None

                    audio_buffer.clear()

                    dependencies.sessions.interrupt(
                        session.session_id,
                        tenant_id,
                        user_id,
                    )

                    await send_event({
                        "event": "response.interrupted",
                    })

                elif event == "session.close":
                    await websocket.close(code=1000)
                    break

                else:
                    await send_event({
                        "event": "error",
                        "code": "unknown_command",
                    })

        except WebSocketDisconnect:
            pass

        finally:
            if active_task is not None:
                active_task.cancel()

                try:
                    await active_task
                except asyncio.CancelledError:
                    pass

            dependencies.sessions.close(
                session.session_id,
                tenant_id,
                user_id,
            )

    return app


app = create_streaming_voice_app()
