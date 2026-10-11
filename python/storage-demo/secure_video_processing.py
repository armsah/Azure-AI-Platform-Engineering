"""Bounded MP4 frame extraction for video intelligence."""

from dataclasses import dataclass
from pathlib import Path
import tempfile

import cv2


class VideoSecurityError(ValueError):
    """Video input failed validation."""


@dataclass(frozen=True)
class VideoLimits:
    max_bytes: int = 25 * 1024 * 1024
    max_duration_seconds: float = 120.0
    max_frames: int = 12
    max_pixels_per_frame: int = 1920 * 1080


@dataclass(frozen=True)
class VideoFrame:
    timestamp_seconds: float
    jpeg_bytes: bytes


def extract_video_frames(
    content: bytes,
    *,
    limits: VideoLimits = VideoLimits(),
) -> list[VideoFrame]:
    """Extract a bounded set of timestamped JPEG frames."""

    if not content:
        raise VideoSecurityError("Empty video")

    if len(content) > limits.max_bytes:
        raise VideoSecurityError("Video exceeds size limit")

    # ISO Base Media File Format: MP4 typically contains an ftyp box.
    if len(content) < 12 or content[4:8] != b"ftyp":
        raise VideoSecurityError("Invalid MP4 signature")

    if limits.max_frames < 1:
        raise VideoSecurityError("Invalid frame limit")

    with tempfile.TemporaryDirectory(prefix="video-") as directory:
        path = Path(directory) / "input.mp4"
        path.write_bytes(content)

        capture = cv2.VideoCapture(str(path))

        try:
            if not capture.isOpened():
                raise VideoSecurityError("Unable to decode video")

            fps = capture.get(cv2.CAP_PROP_FPS)
            frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)

            if fps <= 0 or frame_count <= 0:
                raise VideoSecurityError("Invalid video metadata")

            duration = frame_count / fps

            if duration > limits.max_duration_seconds:
                raise VideoSecurityError("Video exceeds duration limit")

            interval = max(1, int(frame_count // limits.max_frames))
            frames: list[VideoFrame] = []

            for index in range(0, int(frame_count), interval):
                if len(frames) >= limits.max_frames:
                    break

                capture.set(cv2.CAP_PROP_POS_FRAMES, index)
                success, frame = capture.read()

                if not success:
                    raise VideoSecurityError("Video frame decoding failed")

                height, width = frame.shape[:2]

                if width * height > limits.max_pixels_per_frame:
                    raise VideoSecurityError("Video frame exceeds pixel limit")

                success, encoded = cv2.imencode(".jpg", frame)

                if not success:
                    raise VideoSecurityError("Frame encoding failed")

                frames.append(
                    VideoFrame(
                        timestamp_seconds=index / fps,
                        jpeg_bytes=encoded.tobytes(),
                    )
                )

            if not frames:
                raise VideoSecurityError("No video frames extracted")

            return frames

        finally:
            capture.release()