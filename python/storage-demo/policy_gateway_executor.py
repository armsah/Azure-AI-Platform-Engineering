import time

from dataclasses import dataclass
from typing import Any, Callable

from ai_gateway import (
    AIGateway,
    AIRequest,
    model_capability_for,
)
from circuit_breaker import CircuitBreaker, CircuitOpen
from gateway_execution import (
    GatewayExecutionFailed,
    ProviderExecutionError,
    ProviderResult,
    ProviderTimeout,
    Usage,
)
from model_registry import ModelRegistry
from model_routing_policy import (
    rank_eligible_deployments,
)
from gateway_audit import (
    AuditSink,
    GatewayAuditRecord,
    ProviderAttempt,
    TokenUsage,
    estimate_deployment_cost_usd,
)
from tenant_model_policy import build_routing_policy


@dataclass(frozen=True)
class PolicyExecutionResult:
    output: Any
    deployment: str
    usage: Usage
    token_usage: TokenUsage
    estimated_cost_usd: float


class PolicyGatewayExecutor:
    def __init__(
        self,
        registry: ModelRegistry,
        audit_sink: AuditSink | None = None,
    ):
        self.gateway = AIGateway()
        self.registry = registry
        self.audit_sink = audit_sink
        self.breakers: dict[str, CircuitBreaker] = {}

    def _breaker(self, deployment: str) -> CircuitBreaker:
        if deployment not in self.breakers:
            self.breakers[deployment] = CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=30,
            )
        return self.breakers[deployment]

    def _audit(self, record: GatewayAuditRecord) -> None:
        if self.audit_sink:
            self.audit_sink(record)

    def execute(
        self,
        request: AIRequest,
        provider_call: Callable[
            [str, Any, int],
            ProviderResult,
        ],
    ) -> PolicyExecutionResult:

        started = time.monotonic()

        # Authorize the operation before selecting a deployment.
        decision = self.gateway.authorize(request)

        if not decision.allowed:
            raise PermissionError("Gateway operation denied")

        required_capability = model_capability_for(decision).value

        routing_policy = build_routing_policy(
            request.request_context,
            required_capability,
        )

        candidates = rank_eligible_deployments(
            self.registry,
            routing_policy,
        )

        model_calls = 0
        fallback_attempts = 0
        attempts: list[ProviderAttempt] = []

        for index, deployment in enumerate(candidates):
            breaker = self._breaker(deployment.deployment_id)

            try:
                breaker.allow_request()
            except CircuitOpen:
                continue

            try:
                model_calls += 1

                result = provider_call(
                    deployment.deployment_id,
                    request.input,
                    decision.max_output_tokens,
                )

                breaker.record_success()

                cost = estimate_deployment_cost_usd(
                    deployment,
                    result.usage,
                )
                
                attempts.append(
                   ProviderAttempt(
                       deployment=deployment.deployment_id,
                       outcome="success",
                       input_tokens=result.usage.input_tokens,
                       output_tokens=result.usage.output_tokens,
                       estimated_cost_usd=cost,
                    )
                )
                
                total_cost = sum(
                    attempt.estimated_cost_usd
                    for attempt in attempts
                )

                self._audit(
                    GatewayAuditRecord(
                        tenant_id=request.request_context.tenant_id,
                        user_id=request.request_context.user_id,
                        correlation_id=request.correlation_id,
                        operation=request.operation,
                        deployment=deployment.deployment_id,
                        model_calls=model_calls,
                        fallback_attempts=fallback_attempts,
                        input_tokens=sum(a.input_tokens for a in attempts),
                        output_tokens=sum(a.output_tokens for a in attempts),
                        estimated_cost_usd=total_cost,
                        latency_ms=(
                            time.monotonic() - started
                        ) * 1000,
                        outcome="success",
                        attempts=tuple(attempts),
                    )
                )

                return PolicyExecutionResult(
                    output=result.output,
                    deployment=deployment.deployment_id,
                    usage=Usage(
                        model_calls=model_calls,
                        fallback_attempts=fallback_attempts,
                    ),
                    token_usage=result.usage,
                    estimated_cost_usd=total_cost,
                )

            except (ProviderTimeout, ProviderExecutionError) as exc:
                breaker.record_failure()
                
                attempts.append(
                   ProviderAttempt(
                        deployment=deployment.deployment_id,
                        outcome=type(exc).__name__,
                        input_tokens=0,
                        output_tokens=0,
                        estimated_cost_usd=0.0,
                    )
                )

                if index < len(candidates) - 1:
                    fallback_attempts += 1
                    
        total_cost = sum(
            attempt.estimated_cost_usd
            for attempt in attempts
        )

        self._audit(
            GatewayAuditRecord(
                tenant_id=request.request_context.tenant_id,
                user_id=request.request_context.user_id,
                correlation_id=request.correlation_id,
                operation=request.operation,
                deployment=None,
                model_calls=model_calls,
                fallback_attempts=fallback_attempts,
                input_tokens=sum(a.input_tokens for a in attempts),
                output_tokens=sum(a.output_tokens for a in attempts),
                estimated_cost_usd=total_cost,
                latency_ms=(time.monotonic() - started) * 1000,
                outcome="failure",
                error_category="provider_unavailable",
                attempts=tuple(attempts),
            )
        )

        raise GatewayExecutionFailed(
            "No policy-eligible deployment succeeded"
        )