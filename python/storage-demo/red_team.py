from dataclasses import dataclass
from enum import Enum


class AttackType(str, Enum):
    PROMPT_INJECTION = "prompt_injection"
    CROSS_TENANT = "cross_tenant"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    HITL_BYPASS = "hitl_bypass"
    MCP_BYPASS = "mcp_bypass"


@dataclass(frozen=True)
class RedTeamCase:
    name: str
    attack_type: AttackType
    expected_blocked: bool = True


@dataclass(frozen=True)
class RedTeamResult:
    case: RedTeamCase
    blocked: bool

    @property
    def passed(self) -> bool:
        return self.blocked == self.case.expected_blocked


def evaluate_red_team_case(
    case: RedTeamCase,
    *,
    blocked: bool,
) -> RedTeamResult:
    return RedTeamResult(
        case=case,
        blocked=blocked,
    )