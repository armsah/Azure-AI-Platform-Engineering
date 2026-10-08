from dataclasses import dataclass
from enum import Enum


class CloudProvider(str, Enum):
    AZURE = "azure"
    AWS = "aws"
    GCP = "gcp"


class DeploymentHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ModelDeployment:
    deployment_id: str
    provider: CloudProvider
    region: str
    capabilities: frozenset[str]
    health: DeploymentHealth
    priority: int
    estimated_latency_ms: int
    input_cost_per_1k: float
    output_cost_per_1k: float


class ModelRegistry:
    def __init__(self, deployments: tuple[ModelDeployment, ...]):
        ids = [item.deployment_id for item in deployments]

        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate model deployment ID")

        self.deployments = deployments

    def list_deployments(self) -> tuple[ModelDeployment, ...]:
        return self.deployments