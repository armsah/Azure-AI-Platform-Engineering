"""Isolated video decoding with a bounded execution timeout."""

from __future__ import annotations

import multiprocessing
import queue
from typing import Any

from secure_video_processing import (
    VideoFrame,
    VideoLimits,
    VideoSecurityError,
    extract_video_frames,
)


DEFAULT_DECODE_TIMEOUT_SECONDS = 15.0


def _decode_worker(
    content: bytes,
    limits: VideoLimits,
    result_queue: Any,
) -> None:
    """Execute untrusted video decoding in a child process."""

    try:
        frames = extract_video_frames(
            content,
            limits=limits,
        )

        result_queue.put(
            ("ok", frames)
        )

    except VideoSecurityError as exc:
        result_queue.put(
            ("validation_error", str(exc))
        )

    except Exception:
        # Avoid exposing internal decoder exceptions to API clients.
        result_queue.put(
            ("decoder_error", "Video decoding failed")
        )


def extract_video_frames_isolated(
    content: bytes,
    *,
    limits: VideoLimits = VideoLimits(),
    timeout_seconds: float = DEFAULT_DECODE_TIMEOUT_SECONDS,
) -> list[VideoFrame]:
    """Decode video in a separate process and enforce a deadline."""

    if timeout_seconds <= 0:
        raise ValueError("Decoder timeout must be positive")

    # Cheap validation before allocating a worker process.
    if not content:
        raise VideoSecurityError("Empty video")

    if len(content) > limits.max_bytes:
        raise VideoSecurityError("Video exceeds size limit")

    if len(content) < 12 or content[4:8] != b"ftyp":
        raise VideoSecurityError("Invalid MP4 signature")

    if limits.max_frames < 1:
        raise VideoSecurityError("Invalid frame limit")

    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue(maxsize=1)

    process = ctx.Process(
        target=_decode_worker,
        args=(content, limits, result_queue),
        daemon=True,
    )

    try:
        process.start()

        try:
            status, payload = result_queue.get(
                timeout=timeout_seconds
            )

        except queue.Empty:
            if process.is_alive():
                raise VideoSecurityError(
                    "Video decoding exceeded time limit"
                )

            raise VideoSecurityError(
                "Video decoder process exited unexpectedly"
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

        if not isinstance(payload, list):
            raise VideoSecurityError(
                "Invalid decoder output"
            )

        return payload

    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()

            process.join(timeout=2.0)

            if process.is_alive():
                process.kill()
                process.join(timeout=2.0)

        result_queue.close()
        result_queue.join_thread()