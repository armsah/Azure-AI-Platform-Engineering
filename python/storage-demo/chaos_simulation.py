from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FaultScenario:
    name: str
    failure_seconds: float
    recovery_seconds: float
    recovered: bool


def evaluate_recovery(
    scenario: FaultScenario,
    maximum_recovery_seconds: float = 30,
) -> bool:
    if scenario.failure_seconds < 0 or scenario.recovery_seconds < 0:
        return False
    return scenario.recovered and scenario.recovery_seconds <= maximum_recovery_seconds


def classify_incident(
    service_unavailable: bool,
    data_loss: bool,
    degraded: bool,
) -> str:
    if data_loss or service_unavailable:
        return "SEV1"
    if degraded:
        return "SEV2"
    return "SEV3"


SCENARIOS = (
    FaultScenario("dependency-timeout", 5, 10, True),
    FaultScenario("transient-http-503", 3, 8, True),
    FaultScenario("worker-restart", 2, 12, True),
    FaultScenario("unrecoverable-dependency", 5, 60, False),
)
