from dataclasses import dataclass

from model_registry import CloudProvider
from model_routing_policy import ModelRoutingPolicy
from request_context import RequestContext


class TenantPolicyNotFound(Exception):
    pass


@dataclass(frozen=True)
class TenantModelPolicy:
    allowed_regions: frozenset[str]
    allowed_providers: frozenset[CloudProvider]
    max_input_cost_per_1k: float
    max_output_cost_per_1k: float
    max_estimated_latency_ms: int


# Development configuration.
# Production: load from a controlled, versioned policy store.
TENANT_POLICIES = {
    "customer-a": TenantModelPolicy(
        allowed_regions=frozenset({"swedencentral"}),
        allowed_providers=frozenset({CloudProvider.AZURE}),
        max_input_cost_per_1k=0.01,
        max_output_cost_per_1k=0.03,
        max_estimated_latency_ms=1000,
    ),
}


def resolve_tenant_model_policy(
    context: RequestContext,
) -> TenantModelPolicy:
    policy = TENANT_POLICIES.get(context.tenant_id)

    if policy is None:
        raise TenantPolicyNotFound(
            "No routing policy configured for tenant"
        )

    return policy


def build_routing_policy(
    context: RequestContext,
    required_capability: str,
) -> ModelRoutingPolicy:
    tenant_policy = resolve_tenant_model_policy(context)

    return ModelRoutingPolicy(
        required_capability=required_capability,
        allowed_regions=tenant_policy.allowed_regions,
        allowed_providers=tenant_policy.allowed_providers,
        max_input_cost_per_1k=tenant_policy.max_input_cost_per_1k,
        max_output_cost_per_1k=tenant_policy.max_output_cost_per_1k,
        max_estimated_latency_ms=tenant_policy.max_estimated_latency_ms,
    )