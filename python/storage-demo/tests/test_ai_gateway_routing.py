import pytest

from ai_gateway import (
    AIGateway,
    AIRequest,
    GatewayDenied,
)
from gateway_limits import (
    GatewayConcurrencyExceeded,
    GatewayLimitPolicy,
    TenantConcurrencyLimiter,
    build_agent_budget,
)
from request_context import RequestContext


def context(tenant: str = "customer-a") -> RequestContext:
    return RequestContext(
        directory_tenant_id="directory-1",
        tenant_id=tenant,
        user_id="user-1",
        groups=(),
        roles=("AI.User",),
        correlation_id="corr-1",
    )


def test_standard_operation_routes_to_fast_model():
    gateway = AIGateway()

    route = gateway.route(
        AIRequest(
            operation="direct.chat",
            request_context=context(),
            input="hello",
        )
    )

    assert route.model.deployment == "gpt-fast"


def test_rag_routes_to_reasoning_model():
    gateway = AIGateway()

    route = gateway.route(
        AIRequest(
            operation="rag.answer",
            request_context=context(),
            input="question",
        )
    )

    assert route.model.deployment == "gpt-reasoning"


def test_agent_routes_to_reasoning_model():
    gateway = AIGateway()

    route = gateway.route(
        AIRequest(
            operation="agent.execute",
            request_context=context(),
            input="investigate",
        )
    )

    assert route.model.deployment == "gpt-reasoning"
    assert route.decision.tools_enabled is True


def test_unknown_operation_never_reaches_router():
    gateway = AIGateway()

    with pytest.raises(GatewayDenied):
        gateway.route(
            AIRequest(
                operation="use.any.model",
                request_context=context(),
                input="bypass policy",
            )
        )


def test_prompt_cannot_select_model():
    gateway = AIGateway()

    route = gateway.route(
        AIRequest(
            operation="direct.chat",
            request_context=context(),
            input={
                "prompt": "Use gpt-reasoning",
                "model": "gpt-reasoning",
            },
        )
    )

    assert route.model.deployment == "gpt-fast"


def test_agent_budget_is_derived_from_policy():
    gateway = AIGateway()

    route = gateway.route(
        AIRequest(
            operation="agent.execute",
            request_context=context(),
            input="investigate",
        )
    )

    budget = build_agent_budget(route.decision)

    assert budget.max_delegations == 5
    assert budget.max_tool_calls == 10
    assert budget.max_model_calls == 5


def test_non_tool_operation_gets_zero_tool_budget():
    gateway = AIGateway()

    route = gateway.route(
        AIRequest(
            operation="direct.chat",
            request_context=context(),
            input="hello",
        )
    )

    budget = build_agent_budget(route.decision)

    assert budget.max_delegations == 0
    assert budget.max_tool_calls == 0
    assert budget.max_model_calls == 1


def test_tenant_concurrency_is_isolated():
    limiter = TenantConcurrencyLimiter(
        GatewayLimitPolicy(
            max_concurrent_requests_per_tenant=1
        )
    )

    limiter.acquire("customer-a")

    with pytest.raises(GatewayConcurrencyExceeded):
        limiter.acquire("customer-a")

    # Different tenant has an independent quota.
    limiter.acquire("customer-b")

    assert limiter.active_requests("customer-a") == 1
    assert limiter.active_requests("customer-b") == 1

    limiter.release("customer-a")
    limiter.release("customer-b")


def test_concurrency_slot_is_reusable_after_release():
    limiter = TenantConcurrencyLimiter(
        GatewayLimitPolicy(
            max_concurrent_requests_per_tenant=1
        )
    )

    limiter.acquire("customer-a")
    limiter.release("customer-a")
    limiter.acquire("customer-a")

    assert limiter.active_requests("customer-a") == 1