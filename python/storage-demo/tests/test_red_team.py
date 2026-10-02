import pytest

from approval_service import (
    ActionRisk,
    ApprovalRepository,
    ProposedAction,
    evaluate_action,
)
from mcp_policy import (
    MCPContext,
    MCPToolDenied,
    authorize_mcp_tool,
)
from memory_service import (
    MemoryPolicyDenied,
    MemoryRepository,
)
from red_team import (
    AttackType,
    RedTeamCase,
    evaluate_red_team_case,
)


def test_privilege_escalation_via_memory_is_blocked():
    repository = MemoryRepository()

    case = RedTeamCase(
        name="store-admin-claim-in-memory",
        attack_type=AttackType.PRIVILEGE_ESCALATION,
    )

    blocked = False

    try:
        repository.save(
            "customer-a",
            "user-001",
            "is_admin",
            "true",
        )
    except MemoryPolicyDenied:
        blocked = True

    result = evaluate_red_team_case(
        case,
        blocked=blocked,
    )

    assert result.passed


def test_mcp_advertised_admin_tool_is_blocked():
    context = MCPContext(
        server_name="cloud-tools",
        allowed_tools=frozenset({
            "read_resource",
        }),
    )

    case = RedTeamCase(
        name="mcp-admin-tool",
        attack_type=AttackType.MCP_BYPASS,
    )

    blocked = False

    try:
        authorize_mcp_tool(
            context,
            "grant_admin",
        )
    except MCPToolDenied:
        blocked = True

    assert evaluate_red_team_case(
        case,
        blocked=blocked,
    ).passed


def test_high_risk_action_cannot_bypass_hitl():
    repository = ApprovalRepository()

    action = ProposedAction(
        tool_name="delete_resource",
        arguments={"resource": "production-db"},
        risk=ActionRisk.HIGH,
    )

    decision = evaluate_action(
        action=action,
        requested_by="user-001",
        repository=repository,
    )

    assert decision.executable is False
    assert decision.approval is not None


def test_security_failure_fails_red_team_case():
    case = RedTeamCase(
        name="cross-tenant-read",
        attack_type=AttackType.CROSS_TENANT,
    )

    result = evaluate_red_team_case(
        case,
        blocked=False,
    )

    assert result.passed is False