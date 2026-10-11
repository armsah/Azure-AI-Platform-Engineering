"""Windows-spawn-compatible regression tests for isolated video decoding."""

import multiprocessing
import struct
import threading
import time
from unittest.mock import patch

import pytest

import video_decoder_worker
from secure_video_processing import VideoFrame, VideoLimits, VideoSecurityError
from video_decoder_worker import extract_video_frames_isolated

VALID_HEADER = b"\x00\x00\x00\x18ftypisomtest-video"


def _worker_that_hangs(content, limits, connection):
    time.sleep(30)


def _worker_that_crashes(content, limits, connection):
    import os
    os._exit(17)


def _worker_that_sends_malformed_message(content, limits, connection):
    connection.send_bytes(b"partial")
    time.sleep(30)


def _worker_that_sends_valid_message(content, limits, connection):
    response = video_decoder_worker._encode_response(
        "ok", [VideoFrame(0.0, b"\xff\xd8test\xff\xd9")], limits=limits
    )
    connection.send_bytes(response)
    time.sleep(30)


def _inject_worker(monkeypatch, worker):
    """Override Process(target=...) without relying on patches crossing spawn."""
    original = multiprocessing.get_context

    class TestContext:
        def __init__(self, real):
            self.real = real

        def Pipe(self, *args, **kwargs):
            return self.real.Pipe(*args, **kwargs)

        def Process(self, *args, **kwargs):
            kwargs["target"] = worker
            return self.real.Process(*args, **kwargs)

    monkeypatch.setattr(
        video_decoder_worker.multiprocessing,
        "get_context",
        lambda method: TestContext(original(method)),
    )


def test_reject_empty_video_without_starting_worker():
    with patch("video_decoder_worker.multiprocessing.get_context") as get_context:
        with pytest.raises(VideoSecurityError, match="Empty video"):
            extract_video_frames_isolated(b"")
        get_context.assert_not_called()


def test_reject_invalid_signature_without_starting_worker():
    with patch("video_decoder_worker.multiprocessing.get_context") as get_context:
        with pytest.raises(VideoSecurityError, match="Invalid MP4"):
            extract_video_frames_isolated(b"not-an-mp4")
        get_context.assert_not_called()


def test_reject_oversized_video_without_starting_worker():
    with patch("video_decoder_worker.multiprocessing.get_context") as get_context:
        with pytest.raises(VideoSecurityError, match="size limit"):
            extract_video_frames_isolated(b"x" * 32, limits=VideoLimits(max_bytes=16))
        get_context.assert_not_called()


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_reject_invalid_timeout(timeout):
    with pytest.raises(ValueError, match="timeout"):
        extract_video_frames_isolated(VALID_HEADER, timeout_seconds=timeout)


def test_isolated_decoder_returns_frames():
    from pathlib import Path
    import tempfile
    import cv2
    import numpy as np

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "sample.mp4"
        writer = cv2.VideoWriter(
            str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (64, 64)
        )
        if not writer.isOpened():
            pytest.skip("MP4 encoder unavailable")
        try:
            for index in range(5):
                frame = np.zeros((64, 64, 3), dtype=np.uint8)
                frame[:, :, 1] = index * 30
                writer.write(frame)
        finally:
            writer.release()
        frames = extract_video_frames_isolated(
            path.read_bytes(),
            limits=VideoLimits(
                max_bytes=1024 * 1024,
                max_duration_seconds=10,
                max_frames=3,
                max_pixels_per_frame=64 * 64,
            ),
            timeout_seconds=15,
        )
    assert len(frames) == 3
    assert all(isinstance(frame, VideoFrame) for frame in frames)


def test_worker_validation_error_is_propagated():
    with pytest.raises(VideoSecurityError):
        extract_video_frames_isolated(VALID_HEADER, timeout_seconds=15)


def test_worker_timeout_terminates_process(monkeypatch):
    _inject_worker(monkeypatch, _worker_that_hangs)
    with pytest.raises(VideoSecurityError, match="time limit"):
        extract_video_frames_isolated(VALID_HEADER, timeout_seconds=0.5)


def test_worker_crash_is_reported(monkeypatch):
    _inject_worker(monkeypatch, _worker_that_crashes)
    with pytest.raises(VideoSecurityError, match="exited unexpectedly"):
        extract_video_frames_isolated(VALID_HEADER, timeout_seconds=5)


def test_worker_crash_is_detected_before_timeout(monkeypatch):
    _inject_worker(monkeypatch, _worker_that_crashes)
    started = time.monotonic()
    with pytest.raises(VideoSecurityError, match="exited unexpectedly"):
        extract_video_frames_isolated(VALID_HEADER, timeout_seconds=10)
    assert time.monotonic() - started < 5


def test_worker_ipc_uses_bounded_binary_receive():
    assert video_decoder_worker.MAX_IPC_MESSAGE_BYTES > 0
    assert hasattr(video_decoder_worker, "_recv_bytes_with_deadline")


def test_worker_ipc_rejects_oversized_message():
    with pytest.raises(VideoSecurityError, match="IPC|size|large"):
        video_decoder_worker._decode_response(
            b"x" * (video_decoder_worker.MAX_IPC_MESSAGE_BYTES + 1),
            limits=VideoLimits(),
        )


def test_worker_ipc_rejects_malformed_message():
    with pytest.raises(VideoSecurityError):
        video_decoder_worker._decode_response(
            b"not-a-valid-worker-response", limits=VideoLimits()
        )


def test_worker_ipc_encoder_rejects_nonfinite_timestamp():
    with pytest.raises(VideoSecurityError, match="Invalid frame timestamp"):
        video_decoder_worker._encode_response(
            "ok", [VideoFrame(float("nan"), b"\xff\xd8test\xff\xd9")],
            limits=VideoLimits(),
        )


def test_worker_ipc_decoder_rejects_nonfinite_timestamp():
    payload = (
        struct.pack("!4sBH", b"VD01", 0, 1)
        + struct.pack("!dI", float("nan"), 8)
        + b"\xff\xd8test\xff\xd9"
    )
    with pytest.raises(VideoSecurityError, match="Invalid frame timestamp"):
        video_decoder_worker._decode_response(payload, limits=VideoLimits())


def test_malformed_ipc_message_is_rejected(monkeypatch):
    _inject_worker(monkeypatch, _worker_that_sends_malformed_message)
    started = time.monotonic()
    with pytest.raises(VideoSecurityError, match="IPC"):
        extract_video_frames_isolated(VALID_HEADER, timeout_seconds=5)
    assert time.monotonic() - started < 5


def test_valid_ipc_message_is_accepted(monkeypatch):
    _inject_worker(monkeypatch, _worker_that_sends_valid_message)
    frames = extract_video_frames_isolated(VALID_HEADER, timeout_seconds=5)
    assert len(frames) == 1
    assert frames[0].timestamp_seconds == 0.0


def test_concurrency_admission_rejects_when_full(monkeypatch):
    _inject_worker(monkeypatch, _worker_that_hangs)
    # Deterministic saturation without starting multiple Windows processes.
    acquired = []
    try:
        for _ in range(video_decoder_worker.MAX_CONCURRENT_DECODERS):
            assert video_decoder_worker._DECODER_SLOTS.acquire(blocking=False)
            acquired.append(True)
        with pytest.raises(VideoSecurityError, match="concurrency limit"):
            extract_video_frames_isolated(VALID_HEADER, timeout_seconds=0.5)
    finally:
        for _ in acquired:
            video_decoder_worker._DECODER_SLOTS.release()


def test_concurrency_slot_released_after_timeout(monkeypatch):
    _inject_worker(monkeypatch, _worker_that_hangs)
    with pytest.raises(VideoSecurityError, match="time limit"):
        extract_video_frames_isolated(VALID_HEADER, timeout_seconds=0.5)
    assert video_decoder_worker._DECODER_SLOTS.acquire(blocking=False)
    video_decoder_worker._DECODER_SLOTS.release()


def test_deadline_reader_does_not_block_caller():
    class StalledConnection:
        def recv_bytes(self, *, maxlength):
            time.sleep(2)
            return b"late"

    started = time.monotonic()
    with pytest.raises(VideoSecurityError, match="time limit"):
        video_decoder_worker._recv_bytes_with_deadline(
            StalledConnection(), maxlength=1024,
            deadline=time.monotonic() + 0.05,
        )
    assert time.monotonic() - started < 1
