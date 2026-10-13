from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class IncidentAssessment:
    severity: str
    rollback_permitted: bool
    recovery_verified: bool
    missing_evidence: tuple[str, ...]


def assess_incident(
    *,
    service_unavailable: bool,
    data_loss: bool,
    degraded: bool,
    rollback_approved: bool,
    logs_preserved: bool,
    metrics_preserved: bool,
    revision_recorded: bool,
    health_restored: bool,
    slo_met: bool,
    data_integrity_verified: bool,
) -> IncidentAssessment:
    if service_unavailable or data_loss:
        severity = "SEV1"
    elif degraded:
        severity = "SEV2"
    else:
        severity = "SEV3"

    missing = []

    if not logs_preserved:
        missing.append("logs")
    if not metrics_preserved:
        missing.append("metrics")
    if not revision_recorded:
        missing.append("deployment_revision")

    recovery_verified = (
        health_restored
        and slo_met
        and data_integrity_verified
        and not missing
    )

    return IncidentAssessment(
        severity=severity,
        rollback_permitted=rollback_approved,
        recovery_verified=recovery_verified,
        missing_evidence=tuple(missing),
    )


def assessment_report(assessment: IncidentAssessment) -> dict:
    return asdict(assessment)
