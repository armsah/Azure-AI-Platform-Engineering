from dataclasses import dataclass

from model_registry import (
    DeploymentHealth,
    ModelDeployment,
    ModelRegistry,
    CloudProvider
)


class NoEligibleDeployment(Exception):
    pass


@dataclass(frozen=True)
class ModelRoutingPolicy:
    required_capability: str
    allowed_regions: frozenset[str]
    max_input_cost_per_1k: float
    max_output_cost_per_1k: float
    max_estimated_latency_ms: int
    allowed_providers: frozenset[CloudProvider] = frozenset({
        CloudProvider.AZURE,
    })


def eligible_deployments(
    registry: ModelRegistry,
    policy: ModelRoutingPolicy,
) -> list[ModelDeployment]:

    return [
        deployment
        for deployment in registry.list_deployments()
        if policy.required_capability in deployment.capabilities
        and deployment.region in policy.allowed_regions
        and deployment.health != DeploymentHealth.UNAVAILABLE
        and deployment.input_cost_per_1k
        <= policy.max_input_cost_per_1k
        and deployment.output_cost_per_1k
        <= policy.max_output_cost_per_1k
        and deployment.estimated_latency_ms
        <= policy.max_estimated_latency_ms
        and deployment.provider in policy.allowed_providers
    ]


def select_deployment(
    registry: ModelRegistry,
    policy: ModelRoutingPolicy,
) -> ModelDeployment:

    candidates = rank_eligible_deployments(
        registry, 
        policy,
    )

    if not candidates:
        raise NoEligibleDeployment(
            "No deployment satisfies routing policy"
        )

    return candidates[0]

    
def rank_eligible_deployments(
    registry: ModelRegistry,
    policy: ModelRoutingPolicy,
) -> list[ModelDeployment]:

    candidates = eligible_deployments(registry, policy)

    health_rank = {
        DeploymentHealth.HEALTHY: 0,
        DeploymentHealth.DEGRADED: 1,
        DeploymentHealth.UNAVAILABLE: 2,
    }

    return sorted(
        candidates,
        key=lambda deployment: (
            health_rank[deployment.health],
            deployment.priority,
            deployment.estimated_latency_ms,
            deployment.input_cost_per_1k,
            deployment.deployment_id,
        ),
    )