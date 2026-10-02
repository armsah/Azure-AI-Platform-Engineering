from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from httpcore2 import request


class ActionRisk(str, Enum):
    READ_ONLY = "read_only"
    LOW = "low"
    HIGH = "high"


class ApprovalStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ProposedAction:
    tool_name: str
    arguments: dict
    risk: ActionRisk


@dataclass
class ApprovalRequest:
    id: str
    action: ProposedAction
    requested_by: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    
@dataclass(frozen=True)
class ActionDecision:
    executable: bool
    approval: ApprovalRequest | None = None


def evaluate_action(
    action: ProposedAction,
    requested_by: str,
    repository: ApprovalRepository,
) -> ActionDecision:

    if not requires_approval(action):
        return ActionDecision(executable=True)

    approval = repository.create(
        action=action,
        requested_by=requested_by,
    )

    return ActionDecision(
        executable=False,
        approval=approval,
    )
    
class ApprovalRepository:
    def __init__(self):
        self._requests: dict[str, ApprovalRequest] = {}

    def create(
        self,
        action: ProposedAction,
        requested_by: str,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            id=str(uuid4()),
            action=action,
            requested_by=requested_by,
        )

        self._requests[request.id] = request
        return request

    def get(self, approval_id: str) -> ApprovalRequest:
        return self._requests[approval_id]
    
    def approve(self, approval_id: str) -> ApprovalRequest:
        request = self.get(approval_id)
        request.status = ApprovalStatus.APPROVED
        return request

    def reject(self, approval_id: str) -> ApprovalRequest:
        request = self.get(approval_id)
        request.status = ApprovalStatus.REJECTED
        return request
    
def requires_approval(action: ProposedAction) -> bool:
    return action.risk == ActionRisk.HIGH