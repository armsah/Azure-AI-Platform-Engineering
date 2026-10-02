from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentOutcome(str, Enum):
    SUCCESS = "success"
    NEEDS_DELEGATION = "needs_delegation"
    NEEDS_APPROVAL = "needs_approval"
    ABSTAIN = "abstain"


class AgentContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: AgentOutcome
    answer: str | None = None
    delegate_to: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = []
    
    @model_validator(mode="after")
    def validate_outcome(self):
        if (
            self.outcome == AgentOutcome.NEEDS_DELEGATION
            and not self.delegate_to
        ):
            raise ValueError(
                "delegate_to required for delegation"
            )

        if (
            self.outcome == AgentOutcome.SUCCESS
            and not self.answer
        ):
            raise ValueError(
                "answer required for success"
            )

        return self    