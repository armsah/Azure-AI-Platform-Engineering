from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from entra_auth import (
    claims_to_request_context,
    validate_access_token,
)
from voice_sessions import (
    VoiceSessionError,
    VoiceSessionManager,
)


@dataclass
class VoiceTransportDependencies:
    sessions: VoiceSessionManager
    authenticate: Callable[[str], object]


def authenticate_voice_token(token: str):
    claims = validate_access_token(token)
    return claims_to_request_context(claims)


def create_voice_app(
    dependencies: VoiceTransportDependencies | None = None,
) -> FastAPI:
    app = FastAPI(title="Azure AI Platform — Voice Transport")

    dependencies = dependencies or VoiceTransportDependencies(
        sessions=VoiceSessionManager(),
        authenticate=authenticate_voice_token,
    )

    @app.websocket("/api/v1/voice/ws")
    async def voice_websocket(websocket: WebSocket):
        authorization = websocket.headers.get("authorization", "")

        scheme, separator, token = authorization.partition(" ")

        if (
            not separator
            or scheme.lower() != "bearer"
            or not token.strip()
        ):
            await websocket.close(code=1008)
            return

        try:
            context = dependencies.authenticate(token.strip())

            tenant_id = context.tenant_id
            user_id = context.user_id

            if not tenant_id or not user_id:
                raise ValueError("Incomplete authenticated identity")

        except Exception:
            await websocket.close(code=1008)
            return

        # This standalone transport requires an authenticated identity.
        # A browser-compatible ticket exchange will be added separately.
        try:
            session = dependencies.sessions.create(
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except VoiceSessionError:
            await websocket.close(code=1013)
            return

        await websocket.accept()

        try:
            await websocket.send_json({
                "event": "session.started",
                "session_id": session.session_id,
            })

            while True:
                message = await websocket.receive()

                if message["type"] == "websocket.disconnect":
                    break

                audio = message.get("bytes")
                text = message.get("text")

                if audio is not None:
                    try:
                        turn_id = dependencies.sessions.receive_audio(
                            session.session_id,
                            tenant_id,
                            user_id,
                            audio,
                        )
                    except VoiceSessionError:
                        await websocket.close(code=1009)
                        break

                    await websocket.send_json({
                        "event": "audio.received",
                        "turn_id": turn_id,
                        "bytes_received": len(audio),
                    })
                    continue

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

                if command.get("event") == "response.begin":
                    try:
                        latency = dependencies.sessions.begin_response(
                            session.session_id,
                            tenant_id,
                            user_id,
                        )
                    except VoiceSessionError:
                        await websocket.send_json({
                            "event": "error",
                            "code": "invalid_state",
                        })
                        continue

                    await websocket.send_json({
                        "event": "response.started",
                        "latency_ms": round(latency, 2),
                    })

                elif command.get("event") == "interrupt":
                    dependencies.sessions.interrupt(
                        session.session_id,
                        tenant_id,
                        user_id,
                    )

                    await websocket.send_json({
                        "event": "response.interrupted",
                    })

                elif command.get("event") == "session.close":
                    await websocket.close(code=1000)
                    break

                else:
                    await websocket.send_json({
                        "event": "error",
                        "code": "unknown_command",
                    })

        except WebSocketDisconnect:
            pass

        finally:
            try:
                dependencies.sessions.close(
                    session.session_id,
                    tenant_id,
                    user_id,
                )
            except VoiceSessionError:
                pass

    return app


app = create_voice_app()
