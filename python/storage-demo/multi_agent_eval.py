from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTrajectory:
    selected_agent: str
    delegations: tuple[str, ...] = ()
    tool_calls: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationExpectation:
    expected_agent: str
    allowed_tools: frozenset[str]
    max_delegations: int = 3
    max_tool_calls: int = 5


@dataclass(frozen=True)
class EvaluationResult:
    routing_correct: bool
    tools_authorized: bool
    delegation_within_budget: bool
    tool_calls_within_budget: bool

    @property
    def passed(self) -> bool:
        return all((
            self.routing_correct,
            self.tools_authorized,
            self.delegation_within_budget,
            self.tool_calls_within_budget,
        ))
        
def evaluate_trajectory(
    trajectory: AgentTrajectory,
    expected: EvaluationExpectation,
) -> EvaluationResult:

    return EvaluationResult(
        routing_correct=(
            trajectory.selected_agent
            == expected.expected_agent
        ),
        tools_authorized=all(
            tool in expected.allowed_tools
            for tool in trajectory.tool_calls
        ),
        delegation_within_budget=(
            len(trajectory.delegations)
            <= expected.max_delegations
        ),
        tool_calls_within_budget=(
            len(trajectory.tool_calls)
            <= expected.max_tool_calls
        ),
    )