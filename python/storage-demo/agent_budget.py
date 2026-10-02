from dataclasses import dataclass


class AgentBudgetExceeded(Exception):
    pass


@dataclass
class AgentBudget:
    max_delegations: int = 5
    max_tool_calls: int = 10
    max_model_calls: int = 10

    delegations: int = 0
    tool_calls: int = 0
    model_calls: int = 0

    def consume_delegation(self) -> None:
        if self.delegations >= self.max_delegations:
            raise AgentBudgetExceeded(
                "Delegation budget exhausted."
            )

        self.delegations += 1

    def consume_tool_call(self) -> None:
        if self.tool_calls >= self.max_tool_calls:
            raise AgentBudgetExceeded(
                "Tool-call budget exhausted."
            )

        self.tool_calls += 1

    def consume_model_call(self) -> None:
        if self.model_calls >= self.max_model_calls:
            raise AgentBudgetExceeded(
                "Model-call budget exhausted."
            )

        self.model_calls += 1