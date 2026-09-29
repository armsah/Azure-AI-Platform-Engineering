import pytest

from eval.run_agent_eval import enforce_quality_gate
from eval.run_agent_eval import evaluate_tool_trajectory


def test_correct_tool_trajectory_passes():
    result = evaluate_tool_trajectory(
        actual_tools=["search_documents", "read_document"],
        expected_tools=["search_documents", "read_document"],
    )

    assert result["passed"] is True


def test_forbidden_tool_fails_security():
    result = evaluate_tool_trajectory(
        actual_tools=["search_documents", "read_blob"],
        forbidden_tools=["read_blob"],
    )

    assert result["security_pass"] is False
    assert result["passed"] is False

def test_wrong_tool_order_fails():
    result = evaluate_tool_trajectory(
        actual_tools=["read_document", "search_documents"],
        expected_tools=["search_documents", "read_document"],
    )

    assert result["expected_tools_pass"] is False
    assert result["passed"] is False

def test_calculate_metrics():
    from eval.run_agent_eval import calculate_metrics

    results = [
        {"passed": True, "security_pass": True},
        {"passed": True, "security_pass": True},
        {"passed": False, "security_pass": True},
    ]

    metrics = calculate_metrics(results)

    assert metrics["pass_rate"] == 2 / 3
    assert metrics["security_pass_rate"] == 1.0


def test_calculate_metrics_empty():
    from eval.run_agent_eval import calculate_metrics

    metrics = calculate_metrics([])

    assert metrics["pass_rate"] == 0.0
    assert metrics["security_pass_rate"] == 0.0

def test_quality_gate_passes():
    enforce_quality_gate(
        {
            "pass_rate": 0.97,
            "security_pass_rate": 1.0,
        }
    )


def test_quality_gate_rejects_low_quality():
    with pytest.raises(RuntimeError):
        enforce_quality_gate(
            {
                "pass_rate": 0.80,
                "security_pass_rate": 1.0,
            }
        )


def test_quality_gate_rejects_security_regression():
    with pytest.raises(RuntimeError):
        enforce_quality_gate(
            {
                "pass_rate": 1.0,
                "security_pass_rate": 0.99,
            }
        )
