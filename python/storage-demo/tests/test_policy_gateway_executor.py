import pytest

from ai_gateway import AIRequest
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
    ModelRegistry,
)

from policy_gateway_executor import PolicyGatewayExecutor
from request_context import RequestContext
from tenant_model_policy import TenantPolicyNotFound


CONTEXT = RequestContext(
    directory_tenant_id="directory-001",
    tenant_id="customer-a",
    user_id="user-001",
    groups=("platform-engineering",),
    roles=("AI.User",),
)


def request():
    return AIRequest(
        operation="rag.answer",
        request_context=CONTEXT,
        input="Explain private networking.",
        correlation_id="corr-a4",
    )


def deployment(name, region, priority):
    return ModelDeployment(
        deployment_id=name,
        provider=CloudProvider.AZURE,
        region=region,
        capabilities=frozenset({"reasoning"}),
        health=DeploymentHealth.HEALTHY,
        priority=priority,
        estimated_latency_ms=100,
        input_cost_per_1k=0.001,
        output_cost_per_1k=0.004,
    )


def policy():
    return ModelRoutingPolicy(
        required_capability="reasoning",
        allowed_regions=frozenset({"swedencentral"}),
        max_input_cost_per_1k=0.01,
        max_output_cost_per_1k=0.03,
        max_estimated_latency_ms=1000,
    )


def provider_success(deployment_id, input_data, max_tokens):
    return ProviderResult(
        output="answer",
        usage=TokenUsage(100, 50),
    )


def test_selects_policy_eligible_primary():
    registry = ModelRegistry((
        deployment("sweden-primary", "swedencentral", 1),
        deployment("us-primary", "eastus", 0),
    ))

    executor = PolicyGatewayExecutor(registry)
    result = executor.execute(request(), provider_success)

    assert result.deployment == "sweden-primary"


def test_fallback_never_crosses_region():
    registry = ModelRegistry((
        deployment("sweden-primary", "swedencentral", 1),
        deployment("sweden-backup", "swedencentral", 2),
        deployment("us-backup", "eastus", 0),
    ))

    calls = []

    def provider(deployment_id, input_data, max_tokens):
        calls.append(deployment_id)

        if deployment_id == "sweden-primary":
            raise ProviderExecutionError("unavailable")

        return ProviderResult(
            output="fallback",
            usage=TokenUsage(100, 50),
        )

    executor = PolicyGatewayExecutor(registry)
    result = executor.execute(request(), provider)

    assert calls == ["sweden-primary", "sweden-backup"]
    assert "us-backup" not in calls
    assert result.deployment == "sweden-backup"

def test_unknown_tenant_policy_fails_closed():
    unknown_context = RequestContext(
        directory_tenant_id="directory-001",
        tenant_id="unknown-tenant",
        user_id="user-001",
        groups=(),
        roles=("AI.User",),
    )

    unknown_request = AIRequest(
        operation="rag.answer",
        request_context=unknown_context,
        input="Explain private networking.",
        correlation_id="unknown-tenant-test",
    )

    registry = ModelRegistry((
        deployment("sweden-primary", "swedencentral", 1),
    ))

    executor = PolicyGatewayExecutor(registry)

    with pytest.raises(TenantPolicyNotFound):
        executor.execute(
            unknown_request,
            provider_success,
        )


def test_all_eligible_models_fail_closed():
    registry = ModelRegistry((
        deployment("sweden-primary", "swedencentral", 1),
        deployment("us-backup", "eastus", 0),
    ))

    calls = []

    def failing_provider(deployment_id, input_data, max_tokens):
        calls.append(deployment_id)
        raise ProviderExecutionError("unavailable")

    executor = PolicyGatewayExecutor(registry)

    with pytest.raises(GatewayExecutionFailed):
        executor.execute(request(), failing_provider)

    assert calls == ["sweden-primary"]