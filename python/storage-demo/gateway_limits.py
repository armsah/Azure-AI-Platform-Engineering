from dataclasses import dataclass
from threading import Lock

from ai_gateway_policy import GatewayDecision
from agent_budget import AgentBudget


class GatewayConcurrencyExceeded(Exception):
    pass


@dataclass(frozen=True)
class GatewayLimitPolicy:
    max_concurrent_requests_per_tenant: int = 5


class TenantConcurrencyLimiter:
    def __init__(
        self,
        policy: GatewayLimitPolicy | None = None,
    ):
        self.policy = policy or GatewayLimitPolicy()
        self._active: dict[str, int] = {}
        self._lock = Lock()

    def acquire(self, tenant_id: str) -> None:
        with self._lock:
            current = self._active.get(tenant_id, 0)

            if (
                current
                >= self.policy.max_concurrent_requests_per_tenant
            ):
                raise GatewayConcurrencyExceeded(
                    "Tenant concurrency limit exceeded."
                )

            self._active[tenant_id] = current + 1

    def release(self, tenant_id: str) -> None:
        with self._lock:
            current = self._active.get(tenant_id, 0)

            if current <= 1:
                self._active.pop(tenant_id, None)
            else:
                self._active[tenant_id] = current - 1

    def active_requests(self, tenant_id: str) -> int:
        with self._lock:
            return self._active.get(tenant_id, 0)


def build_agent_budget(
    decision: GatewayDecision,
) -> AgentBudget:
    if not decision.allowed:
        return AgentBudget(
            max_delegations=0,
            max_tool_calls=0,
            max_model_calls=0,
        )

    if not decision.tools_enabled:
        return AgentBudget(
            max_delegations=0,
            max_tool_calls=0,
            max_model_calls=decision.max_iterations,
        )

    return AgentBudget(
        max_delegations=decision.max_iterations,
        max_tool_calls=decision.max_iterations * 2,
        max_model_calls=decision.max_iterations,
    )