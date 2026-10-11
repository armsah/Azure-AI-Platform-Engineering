"""Isolated video decoding with bounded IPC and process monitoring."""

from __future__ import annotations

import math
import multiprocessing
import struct
import time
import queue
import threading
from multiprocessing.connection import Connection, wait

from secure_video_processing import (
    VideoFrame,
    VideoLimits,
    VideoSecurityError,
    extract_video_frames,
)


DEFAULT_DECODE_TIMEOUT_SECONDS = 15.0

MAX_IPC_MESSAGE_BYTES = 32 * 1024 * 1024
MAX_JPEG_BYTES = 8 * 1024 * 1024
MAX_IPC_FRAMES = 12
MAX_CONCURRENT_DECODERS = 2
_DECODER_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_DECODERS)

_PROTOCOL_MAGIC = b"VD01"

_STATUS_OK = 0
_STATUS_VALIDATION_ERROR = 1
_STATUS_DECODER_ERROR = 2

_HEADER = struct.Struct("!4sBH")
_FRAME_HEADER = struct.Struct("!dI")


def _encode_response(
    status: str,
    payload: list[VideoFrame] | str,
    *,
    limits: VideoLimits,
) -> bytes:
    """Serialize a decoder response without pickle."""

    status_codes = {
        "ok": _STATUS_OK,
        "validation_error": _STATUS_VALIDATION_ERROR,
        "decoder_error": _STATUS_DECODER_ERROR,
    }

    if status not in status_codes:
        raise VideoSecurityError("Invalid decoder response status")

    status_code = status_codes[status]

    if status == "ok":
        if not isinstance(payload, list):
            raise VideoSecurityError("Invalid decoder output")

        max_frames = min(limits.max_frames, MAX_IPC_FRAMES)

        if not 1 <= len(payload) <= max_frames:
            raise VideoSecurityError("Invalid IPC frame count")

        parts = [
            _HEADER.pack(
                _PROTOCOL_MAGIC,
                status_code,
                len(payload),
            )
        ]

        total_size = _HEADER.size

        for frame in payload:
            if not isinstance(frame, VideoFrame):
                raise VideoSecurityError("Invalid IPC frame")

            timestamp = frame.timestamp_seconds
            jpeg = frame.jpeg_bytes

            if not isinstance(timestamp, (int, float)):
                raise VideoSecurityError("Invalid frame timestamp")

            if not math.isfinite(timestamp):
                raise VideoSecurityError("Invalid frame timestamp")

            if timestamp < 0 or timestamp > limits.max_duration_seconds:
                raise VideoSecurityError("Invalid frame timestamp")

            if not isinstance(jpeg, bytes):
                raise VideoSecurityError("Invalid JPEG payload")

            if not 4 <= len(jpeg) <= MAX_JPEG_BYTES:
                raise VideoSecurityError("Invalid JPEG size")

            if not (
                jpeg.startswith(b"\xff\xd8")
                and jpeg.endswith(b"\xff\xd9")
            ):
                raise VideoSecurityError("Invalid JPEG signature")

            total_size += _FRAME_HEADER.size + len(jpeg)

            if total_size > MAX_IPC_MESSAGE_BYTES:
                raise VideoSecurityError("IPC message exceeds size limit")

            parts.append(
                _FRAME_HEADER.pack(
                    float(timestamp),
                    len(jpeg),
                )
            )
            parts.append(jpeg)

        return b"".join(parts)

    if not isinstance(payload, str):
        raise VideoSecurityError("Invalid decoder error response")

    encoded_message = payload.encode("utf-8")

    if len(encoded_message) > 1024:
        raise VideoSecurityError("IPC error message exceeds size limit")

    return (
        _HEADER.pack(
            _PROTOCOL_MAGIC,
            status_code,
            0,
        )
        + encoded_message
    )


def _decode_response(
    data: bytes,
    *,
    limits: VideoLimits,
) -> tuple[str, list[VideoFrame] | str]:
    """Validate and deserialize a bounded binary decoder response."""

    if len(data) > MAX_IPC_MESSAGE_BYTES:
        raise VideoSecurityError("IPC message exceeds size limit")

    if len(data) < _HEADER.size:
        raise VideoSecurityError("Invalid IPC response")

    magic, status_code, frame_count = _HEADER.unpack_from(data)

    if magic != _PROTOCOL_MAGIC:
        raise VideoSecurityError("Invalid IPC protocol")

    offset = _HEADER.size

    if status_code in (
        _STATUS_VALIDATION_ERROR,
        _STATUS_DECODER_ERROR,
    ):
        if frame_count != 0:
            raise VideoSecurityError("Invalid IPC error response")

        message_bytes = data[offset:]

        if len(message_bytes) > 1024:
            raise VideoSecurityError("IPC error message exceeds size limit")

        try:
            message = message_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise VideoSecurityError("Invalid IPC error message") from None

        if status_code == _STATUS_VALIDATION_ERROR:
            return "validation_error", message

        return "decoder_error", message

    if status_code != _STATUS_OK:
        raise VideoSecurityError("Invalid IPC response status")

    max_frames = min(limits.max_frames, MAX_IPC_FRAMES)

    if not 1 <= frame_count <= max_frames:
        raise VideoSecurityError("Invalid IPC frame count")

    frames: list[VideoFrame] = []

    for _ in range(frame_count):
        if offset + _FRAME_HEADER.size > len(data):
            raise VideoSecurityError("Truncated IPC frame header")

        timestamp, jpeg_size = _FRAME_HEADER.unpack_from(
            data,
            offset,
        )

        offset += _FRAME_HEADER.size

        if not math.isfinite(timestamp):
            raise VideoSecurityError("Invalid frame timestamp")

        if timestamp < 0 or timestamp > limits.max_duration_seconds:
            raise VideoSecurityError("Invalid frame timestamp")

        if not 4 <= jpeg_size <= MAX_JPEG_BYTES:
            raise VideoSecurityError("Invalid JPEG size")

        if offset + jpeg_size > len(data):
            raise VideoSecurityError("Truncated IPC JPEG payload")

        jpeg = data[offset : offset + jpeg_size]
        offset += jpeg_size

        if not (
            jpeg.startswith(b"\xff\xd8")
            and jpeg.endswith(b"\xff\xd9")
        ):
            raise VideoSecurityError("Invalid JPEG signature")

        frames.append(
            VideoFrame(
                timestamp_seconds=timestamp,
                jpeg_bytes=jpeg,
            )
        )

    if offset != len(data):
        raise VideoSecurityError("Unexpected trailing IPC data")

    return "ok", frames


def _decode_worker(
    content: bytes,
    limits: VideoLimits,
    result_connection: Connection,
) -> None:
    """Decode video in a child process and return a binary response."""

    try:
        try:
            frames = extract_video_frames(
                content,
                limits=limits,
            )

            response = _encode_response(
                "ok",
                frames,
                limits=limits,
            )

        except VideoSecurityError as exc:
            response = _encode_response(
                "validation_error",
                str(exc),
                limits=limits,
            )

        except Exception:
            response = _encode_response(
                "decoder_error",
                "Video decoding failed",
                limits=limits,
            )

        result_connection.send_bytes(response)

    finally:
        result_connection.close()

def _recv_bytes_with_deadline(
    connection: Connection,
    *,
    maxlength: int,
    deadline: float,
) -> bytes:
    """Receive an IPC message without blocking the caller past its deadline."""

    result_queue: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

    def receive() -> None:
        try:
            data = connection.recv_bytes(maxlength=maxlength)
            result_queue.put_nowait(("ok", data))
        except (EOFError, OSError, ValueError) as exc:
            result_queue.put_nowait(("error", exc))

    remaining = deadline - time.monotonic()

    if remaining <= 0:
        raise VideoSecurityError("Video decoding exceeded time limit")

    reader = threading.Thread(
        target=receive,
        daemon=True,
        name="video-ipc-reader",
    )
    reader.start()

    try:
        status, result = result_queue.get(timeout=remaining)
    except queue.Empty:
        raise VideoSecurityError(
            "Video decoding exceeded time limit"
        ) from None

    if status == "error":
        if isinstance(result, EOFError):
            raise VideoSecurityError(
                "Video decoder process exited unexpectedly"
            ) from None

        raise VideoSecurityError(
            "Invalid or oversized IPC response"
        ) from None

    if not isinstance(result, bytes):
        raise VideoSecurityError("Invalid IPC response")

    return result


def extract_video_frames_isolated(
    content: bytes,
    *,
    limits: VideoLimits = VideoLimits(),
    timeout_seconds: float = DEFAULT_DECODE_TIMEOUT_SECONDS,
) -> list[VideoFrame]:
    """Decode video in a subprocess with bounded IPC and crash detection."""

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("Decoder timeout must be positive and finite")

    if not content:
        raise VideoSecurityError("Empty video")

    if len(content) > limits.max_bytes:
        raise VideoSecurityError("Video exceeds size limit")

    if len(content) < 12 or content[4:8] != b"ftyp":
        raise VideoSecurityError("Invalid MP4 signature")

    if limits.max_frames < 1:
        raise VideoSecurityError("Invalid frame limit")

    if not _DECODER_SLOTS.acquire(blocking=False):
        raise VideoSecurityError("Video decoder concurrency limit reached")

    try:
        return _extract_with_slot(content, limits=limits, timeout_seconds=timeout_seconds)
    finally:
        _DECODER_SLOTS.release()


def _extract_with_slot(
    content: bytes, *, limits: VideoLimits, timeout_seconds: float
) -> list[VideoFrame]:
    """Launch and supervise one admitted decoder."""
    deadline = time.monotonic() + timeout_seconds
    ctx = multiprocessing.get_context("spawn")

    parent_connection, child_connection = ctx.Pipe(duplex=False)

    process = ctx.Process(
        target=_decode_worker,
        args=(content, limits, child_connection),
        daemon=True,
    )

    try:
        process.start()
        child_connection.close()

        while True:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                raise VideoSecurityError(
                    "Video decoding exceeded time limit"
                )

            ready = wait(
                [parent_connection, process.sentinel],
                timeout=remaining,
            )

            if parent_connection in ready:
                data = _recv_bytes_with_deadline(
                    parent_connection,
                    maxlength=MAX_IPC_MESSAGE_BYTES,
                    deadline=deadline,
                )

                status, payload = _decode_response(
                    data,
                    limits=limits,
                )

                if status == "validation_error":
                    raise VideoSecurityError(payload)

                if status == "decoder_error":
                    raise VideoSecurityError(
                        "Video decoding failed"
                    )

                if status != "ok":
                    raise VideoSecurityError(
                        "Invalid decoder worker response"
                    )

                return payload

            if process.sentinel in ready:
                raise VideoSecurityError(
                    "Video decoder process exited unexpectedly"
                )

    finally:
        # Stop the producer before closing the pipe; unblock any reader thread.
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=0.5)
            if process.is_alive():
                process.kill()
                process.join(timeout=0.5)
        parent_connection.close()
        child_connection.close()