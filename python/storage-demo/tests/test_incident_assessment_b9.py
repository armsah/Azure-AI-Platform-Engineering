import pytest

from incident_assessment import assess_incident, assessment_report


BASE = {
    "service_unavailable": False,
    "data_loss": False,
    "degraded": False,
    "rollback_approved": False,
    "logs_preserved": True,
    "metrics_preserved": True,
    "revision_recorded": True,
    "health_restored": True,
    "slo_met": True,
    "data_integrity_verified": True,
}


@pytest.mark.parametrize("changes,expected", [
    ({"service_unavailable": True}, "SEV1"),
    ({"data_loss": True}, "SEV1"),
    ({"degraded": True}, "SEV2"),
    ({}, "SEV3"),
])
def test_incident_severity(changes, expected):
    result = assess_incident(**(BASE | changes))
    assert result.severity == expected


def test_rollback_requires_explicit_approval():
    assert not assess_incident(**BASE).rollback_permitted
    assert assess_incident(
        **(BASE | {"rollback_approved": True})
    ).rollback_permitted


@pytest.mark.parametrize("missing_field,expected", [
    ("logs_preserved", "logs"),
    ("metrics_preserved", "metrics"),
    ("revision_recorded", "deployment_revision"),
])
def test_missing_evidence_blocks_recovery(missing_field, expected):
    result = assess_incident(
        **(BASE | {missing_field: False})
    )
    assert not result.recovery_verified
    assert expected in result.missing_evidence


@pytest.mark.parametrize("field", [
    "health_restored",
    "slo_met",
    "data_integrity_verified",
])
def test_recovery_requires_all_checks(field):
    result = assess_incident(**(BASE | {field: False}))
    assert not result.recovery_verified


def test_verified_recovery():
    result = assess_incident(**BASE)
    assert result.recovery_verified
    assert assessment_report(result)["severity"] == "SEV3"
