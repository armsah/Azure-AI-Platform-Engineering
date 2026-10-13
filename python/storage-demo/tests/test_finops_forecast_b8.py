import pytest

from capacity_planning import (
    estimate_capacity,
    estimate_monthly_cost,
    requires_budget_approval,
)


def test_forecast_requires_more_replicas_as_traffic_grows():
    baseline = estimate_capacity(100, 50, 2, 5, 100)
    peak = estimate_capacity(200, 50, 2, 5, 100)

    assert baseline.required_replicas == 2
    assert peak.required_replicas == 4
    assert peak.estimated_cpu_millicores == 400
    assert peak.within_capacity


def test_forecast_rejects_traffic_above_hpa_capacity():
    forecast = estimate_capacity(300, 50, 2, 5, 100)

    assert forecast.required_replicas == 6
    assert forecast.provisioned_replicas == 5
    assert not forecast.within_capacity


def test_forecast_respects_minimum_replica_cost():
    forecast = estimate_capacity(0, 50, 2, 5, 100)
    monthly_cost = estimate_monthly_cost(0.10, forecast.provisioned_replicas)

    assert monthly_cost == 146.00
    assert requires_budget_approval(monthly_cost, 0)


def test_approved_budget_covers_forecast():
    forecast = estimate_capacity(200, 50, 2, 5, 100)
    monthly_cost = estimate_monthly_cost(0.10, forecast.provisioned_replicas)

    assert monthly_cost == 292.00
    assert not requires_budget_approval(monthly_cost, 300)


def test_forecast_exceeding_budget_requires_approval():
    forecast = estimate_capacity(250, 50, 2, 5, 100)
    monthly_cost = estimate_monthly_cost(0.10, forecast.provisioned_replicas)

    assert monthly_cost == 365.00
    assert requires_budget_approval(monthly_cost, 300)


@pytest.mark.parametrize("rps,pod_rps,min_pods,max_pods,cpu", [
    (-1, 50, 2, 5, 100),
    (100, 0, 2, 5, 100),
    (100, 50, 0, 5, 100),
    (100, 50, 6, 5, 100),
    (100, 50, 2, 5, 0),
])
def test_invalid_forecast_inputs_rejected(
    rps, pod_rps, min_pods, max_pods, cpu
):
    with pytest.raises(ValueError):
        estimate_capacity(rps, pod_rps, min_pods, max_pods, cpu)


def test_negative_hourly_cost_rejected():
    with pytest.raises(ValueError):
        estimate_monthly_cost(-0.10, 2)


def test_negative_estimated_spend_rejected():
    with pytest.raises(ValueError):
        requires_budget_approval(-1, 100)
