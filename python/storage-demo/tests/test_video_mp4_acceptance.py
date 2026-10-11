import cv2
import numpy as np
import pytest

from secure_video_processing import (
    VideoLimits,
    extract_video_frames,
)


def test_real_mp4_frame_extraction(tmp_path):
    video_path = tmp_path / "sample.mp4"

    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        5.0,
        (64, 64),
    )

    if not writer.isOpened():
        pytest.skip("MP4 encoder unavailable")

    try:
        for index in range(10):
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            frame[:, :, 0] = index * 20
            frame[:, :, 1] = 100
            frame[:, :, 2] = 200
            writer.write(frame)
    finally:
        writer.release()

    content = video_path.read_bytes()

    frames = extract_video_frames(
        content,
        limits=VideoLimits(
            max_bytes=1024 * 1024,
            max_duration_seconds=10,
            max_frames=4,
            max_pixels_per_frame=64 * 64,
        ),
    )

    assert len(frames) == 4

    timestamps = [frame.timestamp_seconds for frame in frames]
    assert timestamps == sorted(timestamps)

    for frame in frames:
        decoded = cv2.imdecode(
            np.frombuffer(frame.jpeg_bytes, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )

        assert decoded is not None
        assert decoded.shape[:2] == (64, 64)