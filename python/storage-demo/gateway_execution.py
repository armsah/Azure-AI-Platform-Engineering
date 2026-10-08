import time

from dataclasses import dataclass
from typing import Callable, Any

from ai_gateway import (
    AIGateway,
    AIRequest,
    model_capability_for,
)
from circuit_breaker import CircuitBreaker, CircuitOpen
from production_model_router import (
    RoutingRequest,
    fallback_models,
)
from gateway_audit import (
    AuditSink,
    GatewayAuditRecord,
    TokenUsage,
    estimate_cost_usd,
)

class ProviderTimeout(Exception):
    pass


class ProviderExecutionError(Exception):
    pass


class GatewayExecutionFailed(Exception):
    pass


@dataclass(frozen=True)
class Usage:
    model_calls: int = 0
    fallback_attempts: int = 0

@dataclass(frozen=True)
class ProviderResult:
    output: Any
    usage: TokenUsage

@dataclass(frozen=True)
class ExecutionResult:
    output: Any
    deployment: str
    usage: Usage
    token_usage: TokenUsage
    estimated_cost_usd: float


class GatewayExecutor:
    def __init__(
        self, 
        gateway: AIGateway | None = None,
        audit_sink: AuditSink | None = None,
    ):        
        self.gateway = gateway or AIGateway()
        self.audit_sink = audit_sink
        self.breakers: dict[str, CircuitBreaker] = {}
        
    def _audit(self, record: GatewayAuditRecord) -> None:
        if self.audit_sink is not None:
            self.audit_sink(record)

    def _breaker(self, deployment: str) -> CircuitBreaker:
        if deployment not in self.breakers:
            self.breakers[deployment] = CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=30,
            )
        return self.breakers[deployment]

    def execute(
        self,
        request: AIRequest,
        provider_call: Callable[[str, Any, int], ProviderResult],
    ) -> ExecutionResult:

        started = time.monotonic()
        
        route = self.gateway.route(request)
        
        routing_request =RoutingRequest(
            required_capability=model_capability_for(route.decision)
            )

        candidates = [
            route.model,
            *fallback_models(
                route.model,
                routing_request,
            ),
        ]

        model_calls = 0
        fallback_attempts = 0

        for index, model in enumerate(candidates):
            breaker = self._breaker(model.deployment)

            try:
                breaker.allow_request()
            except CircuitOpen:
                continue

            try:
                model_calls += 1

                provider_result = provider_call(
                    model.deployment,
                    request.input,
                    route.decision.max_output_tokens,
                )

                breaker.record_success()
                
                latency_ms = (
                    time.monotonic() - started
                ) * 1000
                
                cost = estimate_cost_usd(
                    model.deployment,
                    provider_result.usage,
                )
                
                self._audit(
                    GatewayAuditRecord(
                        tenant_id=request.request_context.tenant_id,
                        user_id=request.request_context.user_id,
                        correlation_id=request.correlation_id,
                        operation=request.operation,
                        deployment=model.deployment,
                        model_calls=model_calls,
                        fallback_attempts=fallback_attempts,
                        input_tokens=provider_result.usage.input_tokens,
                        output_tokens=provider_result.usage.output_tokens,
                        estimated_cost_usd=cost,
                        latency_ms=latency_ms,
                        outcome="success",
                    )
                )

                return ExecutionResult(
                    output=provider_result.output,
                    deployment=model.deployment,
                    usage=Usage(
                        model_calls=model_calls,
                        fallback_attempts=fallback_attempts,
                    ),
                    token_usage=provider_result.usage,
                    estimated_cost_usd=cost,
                )

            except (ProviderTimeout, ProviderExecutionError):
                breaker.record_failure()

                if index < len(candidates) - 1:
                    fallback_attempts += 1

        self._audit(
            GatewayAuditRecord(
                tenant_id=request.request_context.tenant_id,
                user_id=request.request_context.user_id,
                correlation_id=request.correlation_id,
                operation=request.operation,
                deployment=None,
                model_calls=model_calls,
                fallback_attempts=fallback_attempts,
                input_tokens=0,
                output_tokens=0,
                estimated_cost_usd=0.0,
                latency_ms=(time.monotonic() - started) * 1000,
                outcome="failure",
                error_category="provider_unavailable",
            )
        )

        raise GatewayExecutionFailed(
            f"No model successfully executed operation {request.operation}"
        )
