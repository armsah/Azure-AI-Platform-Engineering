from dataclasses import dataclass
from enum import Enum
from production_model_router import (
    ModelCapability,
    RoutingRequest,
    select_model,
)


class InputType(str, Enum):
    TEXT = "text"
    IMAGE = "image"


@dataclass(frozen=True)
class MultimodalInput:
    type: InputType
    content: str


class InvalidMultimodalInput(Exception):
    pass


MAX_IMAGE_BYTES = 10 * 1024 * 1024


def validate_image(
    content_type: str,
    size_bytes: int,
) -> None:
    allowed_types = {
        "image/png",
        "image/jpeg",
        "image/webp",
    }

    if content_type not in allowed_types:
        raise InvalidMultimodalInput(
            f"Unsupported image type: {content_type}"
        )

    if size_bytes > MAX_IMAGE_BYTES:
        raise InvalidMultimodalInput(
            "Image exceeds maximum allowed size."
        )
        
def select_model_for_inputs(
    inputs: list[MultimodalInput],
):
    contains_image = any(
        item.type == InputType.IMAGE
        for item in inputs
    )

    capability = (
        ModelCapability.MULTIMODAL
        if contains_image
        else ModelCapability.FAST
    )

    return select_model(
        RoutingRequest(
            required_capability=capability
        )
    )