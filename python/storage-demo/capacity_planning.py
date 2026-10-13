from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class CapacityEstimate:
    required_replicas: int
    provisioned_replicas: int
    estimated_cpu_millicores: int
    within_capacity: bool


def estimate_capacity(
    requests_per_second: float,
    requests_per_second_per_pod: float,
    min_replicas: int,
    max_replicas: int,
    cpu_request_millicores: int,
) -> CapacityEstimate:
    if requests_per_second < 0:
        raise ValueError("Request rate cannot be negative")
    if requests_per_second_per_pod <= 0:
        raise ValueError("Pod throughput must be positive")
    if not 0 < min_replicas <= max_replicas:
        raise ValueError("Invalid replica limits")
    if cpu_request_millicores <= 0:
        raise ValueError("CPU request must be positive")

    required = max(
        min_replicas,
        ceil(requests_per_second / requests_per_second_per_pod),
    )

    provisioned = min(required, max_replicas)

    return CapacityEstimate(
        required_replicas=required,
        provisioned_replicas=provisioned,
        estimated_cpu_millicores=provisioned * cpu_request_millicores,
        within_capacity=required <= max_replicas,
    )


def estimate_monthly_cost(
    hourly_cost_per_replica: float,
    replicas: int,
    hours_per_month: float = 730,
) -> float:
    if hourly_cost_per_replica < 0 or replicas < 0 or hours_per_month < 0:
        raise ValueError("Cost inputs cannot be negative")

    return round(hourly_cost_per_replica * replicas * hours_per_month, 2)


def requires_budget_approval(
    estimated_monthly_cost: float,
    approved_budget: float,
) -> bool:
    if estimated_monthly_cost < 0 or approved_budget < 0:
        raise ValueError("Budget inputs cannot be negative")

    return estimated_monthly_cost > approved_budget
