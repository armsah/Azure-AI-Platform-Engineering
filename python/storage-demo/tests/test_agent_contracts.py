import pytest
from pydantic import ValidationError

from agent_contracts import AgentContract, AgentOutcome


def test_valid_success_contract():
    contract = AgentContract(
        outcome=AgentOutcome.SUCCESS,
        answer="Workload Identity uses federation.",
        confidence=0.95,
        evidence_ids=["doc-1"],
    )

    assert contract.outcome == AgentOutcome.SUCCESS


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        AgentContract(
            outcome=AgentOutcome.SUCCESS,
            answer="answer",
            confidence=0.9,
            dangerous_override=True,
        )


def test_invalid_confidence_rejected():
    with pytest.raises(ValidationError):
        AgentContract(
            outcome=AgentOutcome.SUCCESS,
            answer="answer",
            confidence=5.0,
        )


def test_delegation_requires_target():
    with pytest.raises(ValidationError):
        AgentContract(
            outcome=AgentOutcome.NEEDS_DELEGATION,
            confidence=0.5,
        )