import pytest

from capacity_planning import (
    estimate_capacity,
    estimate_monthly_cost,
    requires_budget_approval,
)


def test_capacity_within_limits():
    result = estimate_capacity(100, 50, 2, 5, 100)
    assert result.required_replicas == 2
    assert result.within_capacity
    assert result.estimated_cpu_millicores == 200


def test_capacity_exceeds_hpa_maximum():
    result = estimate_capacity(500, 50, 2, 5, 100)
    assert result.required_replicas == 10
    assert result.provisioned_replicas == 5
    assert not result.within_capacity


def test_minimum_replicas_preserved():
    result = estimate_capacity(0, 50, 2, 5, 100)
    assert result.provisioned_replicas == 2


def test_invalid_capacity_inputs_rejected():
    with pytest.raises(ValueError):
        estimate_capacity(100, 0, 2, 5, 100)


def test_monthly_cost_estimation():
    assert estimate_monthly_cost(0.10, 2) == 146.00


def test_unapproved_spending_rejected():
    assert requires_budget_approval(146, 0)


def test_within_approved_budget():
    assert not requires_budget_approval(100, 150)


def test_negative_budget_rejected():
    with pytest.raises(ValueError):
        requires_budget_approval(100, -1)
