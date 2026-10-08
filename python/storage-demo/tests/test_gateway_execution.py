import pytest

from ai_gateway import AIRequest
from gateway_audit import TokenUsage
from gateway_execution import (
    GatewayExecutor,
    GatewayExecutionFailed,
    ProviderExecutionError,
    ProviderTimeout,
    ProviderResult,
)
from request_context import RequestContext


TEST_CONTEXT = RequestContext(
    directory_tenant_id="directory-001",
    tenant_id="customer-a",
    user_id="user-001",
    groups=("platform-engineering",),
    roles=("AI.User",),
)


def make_request(operation: str = "direct.chat") -> AIRequest:
    return AIRequest(
        operation=operation,
        request_context=TEST_CONTEXT,
        input="Explain Kubernetes.",
        correlation_id="test-correlation-id",
    )


def test_primary_model_success():
    executor = GatewayExecutor()
    calls = []

    def provider_call(deployment, input_data, max_output_tokens):
        calls.append(deployment)
        return ProviderResult(
            output="success",
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
            )
        )

    result = executor.execute(
        make_request(),
        provider_call,
    )

    assert result.output == "success"
    assert result.deployment == "gpt-fast"
    assert result.usage.model_calls == 1
    assert result.usage.fallback_attempts == 0
    assert calls == ["gpt-fast"]


def test_provider_failure_uses_fallback():
    executor = GatewayExecutor()
    calls = []

    def provider_call(deployment, input_data, max_output_tokens):
        calls.append(deployment)

        if deployment == "gpt-fast":
            raise ProviderExecutionError("primary unavailable")

        return ProviderResult(
            output="fallback-success",
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
            )
        )

    result = executor.execute(
        make_request(),
        provider_call,
    )

    assert result.output == "fallback-success"
    assert result.deployment == "gpt-reasoning"
    assert result.usage.model_calls == 2
    assert result.usage.fallback_attempts == 1
    assert calls == ["gpt-fast", "gpt-reasoning"]


def test_timeout_uses_fallback():
    executor = GatewayExecutor()
    calls = []

    def provider_call(deployment, input_data, max_output_tokens):
        calls.append(deployment)

        if deployment == "gpt-fast":
            raise ProviderTimeout("provider timed out")

        return ProviderResult(
            output="fallback-after-timeout",
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
            )
        )

    result = executor.execute(
        make_request(),
        provider_call,
    )

    assert result.output == "fallback-after-timeout"
    assert result.deployment == "gpt-reasoning"
    assert result.usage.model_calls == 2
    assert result.usage.fallback_attempts == 1
    assert calls == ["gpt-fast", "gpt-reasoning"]


def test_open_circuit_skips_model():
    executor = GatewayExecutor()

    primary_breaker = executor._breaker("gpt-fast")

    for _ in range(3):
        primary_breaker.record_failure()

    calls = []

    def provider_call(deployment, input_data, max_output_tokens):
        calls.append(deployment)
        return ProviderResult(
            output="fallback-success",
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
            )
        )

    result = executor.execute(
        make_request(),
        provider_call,
    )

    assert "gpt-fast" not in calls
    assert calls == ["gpt-reasoning"]
    assert result.deployment == "gpt-reasoning"
    assert result.output == "fallback-success"

    # Circuit-skipped deployments are not provider calls.
    assert result.usage.model_calls == 1


def test_all_models_fail_closed():
    executor = GatewayExecutor()
    calls = []

    def provider_call(deployment, input_data, max_output_tokens):
        calls.append(deployment)
        raise ProviderExecutionError("provider unavailable")

    with pytest.raises(GatewayExecutionFailed):
        executor.execute(
            make_request(),
            provider_call,
        )

    assert len(calls) >= 1