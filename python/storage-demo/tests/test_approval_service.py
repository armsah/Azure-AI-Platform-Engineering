from approval_service import (
    ActionRisk,
    ApprovalRepository,
    ApprovalStatus,
    ProposedAction,
    evaluate_action,
)


def test_read_only_action_executes_without_approval():
    repository = ApprovalRepository()

    action = ProposedAction(
        tool_name="get_pods",
        arguments={},
        risk=ActionRisk.READ_ONLY,
    )

    decision = evaluate_action(
        action,
        requested_by="user-001",
        repository=repository,
    )

    assert decision.executable is True
    assert decision.approval is None


def test_high_risk_action_becomes_pending():
    repository = ApprovalRepository()

    action = ProposedAction(
        tool_name="delete_resource",
        arguments={"resource_id": "resource-123"},
        risk=ActionRisk.HIGH,
    )

    decision = evaluate_action(
        action,
        requested_by="user-001",
        repository=repository,
    )

    assert decision.executable is False
    assert decision.approval is not None
    assert decision.approval.status == ApprovalStatus.PENDING


def test_human_can_approve_pending_action():
    repository = ApprovalRepository()

    action = ProposedAction(
        tool_name="change_rbac",
        arguments={"role": "Reader"},
        risk=ActionRisk.HIGH,
    )

    decision = evaluate_action(
        action,
        requested_by="user-001",
        repository=repository,
    )

    approved = repository.approve(
        decision.approval.id
    )

    assert approved.status == ApprovalStatus.APPROVED