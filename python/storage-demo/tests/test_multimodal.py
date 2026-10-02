import pytest

from multimodal import (
    InputType,
    InvalidMultimodalInput,
    MultimodalInput,
    select_model_for_inputs,
    validate_image,
)
from production_model_router import ModelCapability


def test_valid_image_is_accepted():
    validate_image(
        content_type="image/png",
        size_bytes=1024,
    )


def test_unsupported_image_type_rejected():
    with pytest.raises(InvalidMultimodalInput):
        validate_image(
            content_type="application/exe",
            size_bytes=1024,
        )


def test_oversized_image_rejected():
    with pytest.raises(InvalidMultimodalInput):
        validate_image(
            content_type="image/png",
            size_bytes=20 * 1024 * 1024,
        )


def test_image_request_routes_to_multimodal_model():
    inputs = [
        MultimodalInput(
            type=InputType.TEXT,
            content="Explain this architecture.",
        ),
        MultimodalInput(
            type=InputType.IMAGE,
            content="image-reference",
        ),
    ]

    model = select_model_for_inputs(inputs)

    assert (
        ModelCapability.MULTIMODAL
        in model.capabilities
    )