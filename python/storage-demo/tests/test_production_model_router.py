import pytest

from production_model_router import (
    ModelCapability,
    ModelTarget,
    NoModelAvailable,
    RoutingRequest,
    fallback_models,
    select_model,
)


def test_fast_request_prefers_fast_model():
    selected = select_model(
        RoutingRequest(
            required_capability=ModelCapability.FAST
        )
    )

    assert selected.deployment == "gpt-fast"


def test_reasoning_request_requires_reasoning_capability():
    selected = select_model(
        RoutingRequest(
            required_capability=ModelCapability.REASONING
        )
    )

    assert (
        ModelCapability.REASONING
        in selected.capabilities
    )


def test_unsupported_capability_fails_closed():
    catalog = (
        ModelTarget(
            deployment="fast-only",
            capabilities=frozenset({
                ModelCapability.FAST,
            }),
            priority=1,
        ),
    )

    with pytest.raises(NoModelAvailable):
        select_model(
            RoutingRequest(
                required_capability=ModelCapability.REASONING
            ),
            catalog=catalog,
        )


def test_fallback_preserves_required_capability():
    primary = ModelTarget(
        deployment="reasoning-primary",
        capabilities=frozenset({
            ModelCapability.REASONING,
        }),
        priority=1,
    )

    fallback = ModelTarget(
        deployment="reasoning-secondary",
        capabilities=frozenset({
            ModelCapability.REASONING,
        }),
        priority=2,
    )

    invalid = ModelTarget(
        deployment="fast-only",
        capabilities=frozenset({
            ModelCapability.FAST,
        }),
        priority=3,
    )

    candidates = fallback_models(
        failed_model=primary,
        request=RoutingRequest(
            required_capability=ModelCapability.REASONING
        ),
        catalog=(primary, fallback, invalid),
    )

    assert candidates == [fallback]