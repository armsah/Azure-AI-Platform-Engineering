import importlib.util
from pathlib import Path

import pytest
import yaml

from chaos_simulation import (
    SCENARIOS,
    FaultScenario,
    classify_incident,
    evaluate_recovery,
)
from load_test import evaluate, percentile, summarize


ROOT = Path(__file__).resolve().parents[3]


def platform_validator():
    path = ROOT / "scripts" / "validate_platform_safety.py"
    spec = importlib.util.spec_from_file_location("platform_validator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_platform_safety_policy():
    assert platform_validator().validate() == []


def test_platform_cost_protection():
    policy = yaml.safe_load(
        (ROOT / "platform/safety-policy.yaml").read_text(encoding="utf-8")
    )["spec"]
    assert policy["finops"]["maximumUnapprovedMonthlyCostUsd"] == 0
    assert policy["finops"]["allowAutomaticAzureProvisioning"] is False
    assert policy["chaos"]["liveFaultInjectionEnabled"] is False


def test_percentile_nearest_rank():
    assert percentile([10, 20, 30, 40], 0.95) == 40


def test_http_4xx_is_failure():
    result = summarize([(200, 0.1), (404, 0.2), (503, 0.3), (0, 0.4)], 1)
    assert result.successes == 1
    assert result.failures == 3
    assert result.success_rate == 0.25


def test_performance_acceptance_passes():
    result = summarize([(200, 0.1)] * 100, 2)
    assert evaluate(result, 0.999, 1000)


def test_performance_acceptance_rejects_errors():
    result = summarize([(200, 0.1), (500, 0.1)], 1)
    assert not evaluate(result, 0.999, 1000)


def test_performance_acceptance_rejects_latency():
    result = summarize([(200, 2.0)] * 10, 3)
    assert not evaluate(result, 0.999, 1000)


def test_empty_load_results_rejected():
    with pytest.raises(ValueError):
        summarize([], 1)


def test_offline_recovery_scenarios():
    assert all(evaluate_recovery(s) for s in SCENARIOS[:3])
    assert not evaluate_recovery(SCENARIOS[3])


def test_recovery_rejects_negative_duration():
    assert not evaluate_recovery(FaultScenario("invalid", -1, 1, True))


def test_incident_severity():
    assert classify_incident(True, False, False) == "SEV1"
    assert classify_incident(False, True, False) == "SEV1"
    assert classify_incident(False, False, True) == "SEV2"
    assert classify_incident(False, False, False) == "SEV3"


def test_operations_documentation():
    b8 = (ROOT / "operations/B8-PLATFORM-ENGINEERING.md").read_text(
        encoding="utf-8"
    )
    b9 = (ROOT / "operations/B9-INCIDENT-OPERATIONS.md").read_text(
        encoding="utf-8"
    )
    assert "multi-cloud" in b8.lower()
    assert "STRIDE" in b9
    assert "VALIDATION_ONLY=true" in b9
