from multi_agent_eval import (
    AgentTrajectory,
    EvaluationExpectation,
    evaluate_trajectory,
)


def test_valid_agent_trajectory_passes():
    trajectory = AgentTrajectory(
        selected_agent="kubernetes",
        delegations=("knowledge",),
        tool_calls=("get_pods", "get_events"),
    )

    expected = EvaluationExpectation(
        expected_agent="kubernetes",
        allowed_tools=frozenset({
            "get_pods",
            "get_events",
        }),
    )

    result = evaluate_trajectory(
        trajectory,
        expected,
    )

    assert result.passed is True


def test_unauthorized_tool_fails_evaluation():
    trajectory = AgentTrajectory(
        selected_agent="knowledge",
        tool_calls=("delete_resource",),
    )

    expected = EvaluationExpectation(
        expected_agent="knowledge",
        allowed_tools=frozenset({
            "search_documents",
            "read_document",
        }),
    )

    result = evaluate_trajectory(
        trajectory,
        expected,
    )

    assert result.tools_authorized is False
    assert result.passed is False


def test_wrong_agent_fails_routing_evaluation():
    trajectory = AgentTrajectory(
        selected_agent="cloud",
    )

    expected = EvaluationExpectation(
        expected_agent="security",
        allowed_tools=frozenset(),
    )

    result = evaluate_trajectory(
        trajectory,
        expected,
    )

    assert result.routing_correct is False
    assert result.passed is False


def test_excessive_delegation_fails():
    trajectory = AgentTrajectory(
        selected_agent="cloud",
        delegations=(
            "kubernetes",
            "knowledge",
            "security",
        ),
    )

    expected = EvaluationExpectation(
        expected_agent="cloud",
        allowed_tools=frozenset(),
        max_delegations=2,
    )

    result = evaluate_trajectory(
        trajectory,
        expected,
    )

    assert result.delegation_within_budget is False
    assert result.passed is False