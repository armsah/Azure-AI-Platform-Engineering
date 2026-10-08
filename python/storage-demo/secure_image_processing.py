import hashlib
import io
import warnings
from dataclasses import dataclass

from PIL import (
    Image,
    ImageOps,
    UnidentifiedImageError,
)


class ImageSecurityError(Exception):
    pass


MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_WIDTH = 8192
MAX_IMAGE_HEIGHT = 8192
MAX_IMAGE_PIXELS = 20_000_000
MAX_NORMALIZED_BYTES = 30 * 1024 * 1024


CONTENT_TYPE_FORMATS = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/webp": "WEBP",
}


@dataclass(frozen=True)
class SanitizedImage:
    content: bytes
    content_type: str
    width: int
    height: int
    source_sha256: str
    sanitized_sha256: str
    original_format: str


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_signature(
    *,
    content_type: str,
    content: bytes,
) -> None:

    if content_type == "image/png":
        valid = content.startswith(
            b"\x89PNG\r\n\x1a\n"
        )

    elif content_type == "image/jpeg":
        valid = content.startswith(
            b"\xff\xd8\xff"
        )

    elif content_type == "image/webp":
        valid = (
            len(content) >= 12
            and content[:4] == b"RIFF"
            and content[8:12] == b"WEBP"
        )

    else:
        raise ImageSecurityError(
            "Unsupported image content type"
        )

    if not valid:
        raise ImageSecurityError(
            "Image signature does not match MIME type"
        )


def sanitize_image(
    *,
    content_type: str,
    content: bytes,
) -> SanitizedImage:

    if not isinstance(content, bytes):
        raise ImageSecurityError(
            "Image content must be bytes"
        )

    if not content:
        raise ImageSecurityError(
            "Empty image"
        )

    if len(content) > MAX_IMAGE_BYTES:
        raise ImageSecurityError(
            "Image exceeds byte limit"
        )

    _validate_signature(
        content_type=content_type,
        content=content,
    )

    expected_format = CONTENT_TYPE_FORMATS[
        content_type
    ]

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(
                io.BytesIO(content)
            ) as image:

                if image.format != expected_format:
                    raise ImageSecurityError(
                        "Decoded format does not match MIME"
                    )

                width, height = image.size
                
                oriented = ImageOps.exif_transpose(
                    image
                )
                
                oriented_width, oriented_height = (
                    oriented.size
                )

                if (
                    width <= 0
                    or height <= 0
                    or width > MAX_IMAGE_WIDTH
                    or height > MAX_IMAGE_HEIGHT
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise ImageSecurityError(
                        "Image dimensions exceed limits"
                    )

                # Decode before passing the image onward.
                image.load()

                # Apply EXIF orientation and create
                # a fresh pixel-only representation.
                oriented = ImageOps.exif_transpose(
                    image
                )

                try:
                    normalized = oriented.convert(
                        "RGB"
                    )

                    try:
                        output = io.BytesIO()

                        # Do not copy EXIF, ICC profiles,
                        # comments, or other metadata.
                        normalized.save(
                            output,
                            format="PNG",
                            optimize=False,
                        )

                        sanitized = output.getvalue()

                    finally:
                        normalized.close()

                finally:
                    oriented.close()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ImageSecurityError(
            "Image decoding failed security validation"
        ) from exc

    if len(sanitized) > MAX_NORMALIZED_BYTES:
        raise ImageSecurityError(
            "Normalized image exceeds output limit"
        )

    return SanitizedImage(
        content=sanitized,
        content_type="image/png",
        width=oriented_width,
        height=oriented_height,
        source_sha256=sha256_bytes(content),
        sanitized_sha256=sha256_bytes(
            sanitized
        ),
        original_format=expected_format,
    )