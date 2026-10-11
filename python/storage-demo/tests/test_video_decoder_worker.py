"""Tests for isolated video decoding."""

import multiprocessing
import time
from unittest.mock import patch

import pytest

from secure_video_processing import (
    VideoFrame,
    VideoLimits,
    VideoSecurityError,
)
from video_decoder_worker import extract_video_frames_isolated


VALID_HEADER = b"\x00\x00\x00\x18ftypisomtest-video"


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
            extract_video_frames_isolated(
                b"x" * 32,
                limits=VideoLimits(max_bytes=16),
            )

        get_context.assert_not_called()


def test_reject_invalid_timeout():
    with pytest.raises(ValueError, match="timeout"):
        extract_video_frames_isolated(
            VALID_HEADER,
            timeout_seconds=0,
        )


def test_isolated_decoder_returns_frames():
    # Run the actual child process; avoid mocking multiprocessing.
    from pathlib import Path
    import tempfile

    import cv2
    import numpy as np

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "sample.mp4"

        writer = cv2.VideoWriter(
            str(path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            5.0,
            (64, 64),
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
    # A syntactically valid header is not a decodable MP4.
    with pytest.raises(VideoSecurityError):
        extract_video_frames_isolated(
            VALID_HEADER,
            timeout_seconds=15,
        )
        
def _worker_that_hangs(content, limits, result_queue):
    time.sleep(30)


def _worker_that_crashes(content, limits, result_queue):
    import os

    os._exit(17)


def test_worker_timeout_terminates_process():
    with patch(
        "video_decoder_worker._decode_worker",
        _worker_that_hangs,
    ):
        with pytest.raises(
            VideoSecurityError,
            match="time limit",
        ):
            extract_video_frames_isolated(
                VALID_HEADER,
                timeout_seconds=0.5,
            )


def test_worker_crash_is_reported():
    with patch(
        "video_decoder_worker._decode_worker",
        _worker_that_crashes,
    ):
        with pytest.raises(
            VideoSecurityError,
            match="exited unexpectedly",
        ):
            extract_video_frames_isolated(
                VALID_HEADER,
                timeout_seconds=1,
            )