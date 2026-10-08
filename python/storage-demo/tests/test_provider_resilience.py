import pytest

from gateway_audit import TokenUsage
from gateway_execution import (
    GatewayExecutionFailed,
    ProviderExecutionError,
    ProviderResult,
)
from model_registry import (
    CloudProvider,
    DeploymentHealth,
    ModelDeployment,
)
from provider_health import ProviderHealthMonitor
from resilient_provider import ResilientProviderExecutor


def deployment(name):
    return ModelDeployment(
        deployment_id=name,
        provider=CloudProvider.AZURE,
        region="swedencentral",
        capabilities=frozenset({"reasoning"}),
        health=DeploymentHealth.HEALTHY,
        priority=1,
        estimated_latency_ms=100,
        input_cost_per_1k=0.001,
        output_cost_per_1k=0.004,
    )


class FakeProvider:
    def __init__(self, failures=None):
        self.failures = set(failures or [])
        self.calls = []

    def execute(
        self,
        deployment,
        prompt,
        max_output_tokens,
        timeout_seconds,
    ):
        self.calls.append(deployment)

        if deployment in self.failures:
            raise ProviderExecutionError("simulated failure")

        return ProviderResult(
            output="successful response",
            usage=TokenUsage(100, 50),
        )


def test_primary_succeeds():
    provider = FakeProvider()
    health = ProviderHealthMonitor()

    executor = ResilientProviderExecutor(provider, health)

    result = executor.execute(
        [deployment("primary")],
        "Explain RAG",
        1024,
    )

    assert result.deployment == "primary"
    assert result.attempts == 1


def test_fallback_to_second_eligible_model():
    provider = FakeProvider(failures={"primary"})
    health = ProviderHealthMonitor()

    executor = ResilientProviderExecutor(provider, health)

    result = executor.execute(
        [deployment("primary"), deployment("backup")],
        "Explain RAG",
        1024,
    )

    assert provider.calls == ["primary", "backup"]
    assert result.deployment == "backup"
    assert result.attempts == 2


def test_max_attempts_enforced():
    provider = FakeProvider(
        failures={"one", "two", "three"}
    )
    health = ProviderHealthMonitor()

    executor = ResilientProviderExecutor(
        provider,
        health,
        max_attempts=2,
    )

    with pytest.raises(GatewayExecutionFailed):
        executor.execute(
            [
                deployment("one"),
                deployment("two"),
                deployment("three"),
            ],
            "Explain RAG",
            1024,
        )

    assert provider.calls == ["one", "two"]


def test_unhealthy_provider_skipped():
    provider = FakeProvider()
    health = ProviderHealthMonitor()

    for _ in range(5):
        health.record_failure("primary")

    executor = ResilientProviderExecutor(provider, health)

    result = executor.execute(
        [deployment("primary"), deployment("backup")],
        "Explain RAG",
        1024,
    )

    assert provider.calls == ["backup"]
    assert result.deployment == "backup"


def test_failure_rate_monitor():
    health = ProviderHealthMonitor()

    for _ in range(4):
        health.record_failure("primary")

    health.record_success("primary", 100)

    assert health.failure_rate("primary") == 0.8
    assert not health.is_healthy("primary")


def test_invalid_execution_budget():
    provider = FakeProvider()
    health = ProviderHealthMonitor()

    with pytest.raises(ValueError):
        ResilientProviderExecutor(
            provider,
            health,
            max_attempts=0,
        )