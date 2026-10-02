import pytest

from agent_budget import (
    AgentBudget,
    AgentBudgetExceeded,
)


def test_delegation_budget_is_enforced():
    budget = AgentBudget(max_delegations=2)

    budget.consume_delegation()
    budget.consume_delegation()

    with pytest.raises(AgentBudgetExceeded):
        budget.consume_delegation()


def test_tool_budget_is_enforced():
    budget = AgentBudget(max_tool_calls=1)

    budget.consume_tool_call()

    with pytest.raises(AgentBudgetExceeded):
        budget.consume_tool_call()


def test_model_budget_is_enforced():
    budget = AgentBudget(max_model_calls=1)

    budget.consume_model_call()

    with pytest.raises(AgentBudgetExceeded):
        budget.consume_model_call()
        
def test_nested_agents_share_same_budget():
    budget = AgentBudget(max_delegations=2)

    supervisor_budget = budget
    cloud_agent_budget = budget
    kubernetes_agent_budget = budget

    supervisor_budget.consume_delegation()
    cloud_agent_budget.consume_delegation()

    with pytest.raises(AgentBudgetExceeded):
        kubernetes_agent_budget.consume_delegation()

    assert budget.delegations == 2