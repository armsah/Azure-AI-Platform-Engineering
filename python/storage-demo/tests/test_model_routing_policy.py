import pytest

from model_registry import (
    CloudProvider,
    DeploymentHealth,
    ModelDeployment,
    ModelRegistry,
)
from model_routing_policy import (
    ModelRoutingPolicy,
    NoEligibleDeployment,
    select_deployment,
)


def deployment(
    name,
    region,
    health=DeploymentHealth.HEALTHY,
    priority=1,
    latency=100,
    input_cost=0.001,
    output_cost=0.004,
):
    return ModelDeployment(
        deployment_id=name,
        provider=CloudProvider.AZURE,
        region=region,
        capabilities=frozenset({"reasoning"}),
        health=health,
        priority=priority,
        estimated_latency_ms=latency,
        input_cost_per_1k=input_cost,
        output_cost_per_1k=output_cost,
    )


def policy(regions=frozenset({"swedencentral"})):
    return ModelRoutingPolicy(
        required_capability="reasoning",
        allowed_regions=regions,
        max_input_cost_per_1k=0.01,
        max_output_cost_per_1k=0.03,
        max_estimated_latency_ms=1000,
    )


def test_selects_healthy_deployment():
    registry = ModelRegistry((
        deployment(
            "degraded",
            "swedencentral",
            health=DeploymentHealth.DEGRADED,
            priority=1,
        ),
        deployment(
            "healthy",
            "swedencentral",
            priority=2,
        ),
    ))

    assert select_deployment(
        registry, policy()
    ).deployment_id == "healthy"


def test_residency_blocks_other_region():
    registry = ModelRegistry((
        deployment("us-model", "eastus"),
    ))

    with pytest.raises(NoEligibleDeployment):
        select_deployment(registry, policy())


def test_cost_ceiling_blocks_expensive_model():
    registry = ModelRegistry((
        deployment(
            "expensive",
            "swedencentral",
            input_cost=0.05,
        ),
    ))

    with pytest.raises(NoEligibleDeployment):
        select_deployment(registry, policy())


def test_latency_ceiling_blocks_slow_model():
    registry = ModelRegistry((
        deployment(
            "slow",
            "swedencentral",
            latency=5000,
        ),
    ))

    with pytest.raises(NoEligibleDeployment):
        select_deployment(registry, policy())


def test_unavailable_model_is_excluded():
    registry = ModelRegistry((
        deployment(
            "offline",
            "swedencentral",
            health=DeploymentHealth.UNAVAILABLE,
        ),
    ))

    with pytest.raises(NoEligibleDeployment):
        select_deployment(registry, policy())


def test_duplicate_deployment_rejected():
    item = deployment("duplicate", "swedencentral")

    with pytest.raises(ValueError):
        ModelRegistry((item, item))