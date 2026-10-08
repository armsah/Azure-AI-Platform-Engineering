import time

from dataclasses import dataclass

from gateway_execution import (
    GatewayExecutionFailed,
    ProviderExecutionError,
    ProviderResult,
    ProviderTimeout,
)
from model_registry import ModelDeployment
from provider_adapters import ModelProvider
from provider_health import ProviderHealthMonitor


@dataclass(frozen=True)
class ResilientExecutionResult:
    result: ProviderResult
    deployment: str
    attempts: int


class ResilientProviderExecutor:
    def __init__(
        self,
        provider: ModelProvider,
        health: ProviderHealthMonitor,
        total_timeout_seconds: float = 10.0,
        max_attempts: int = 2,
    ):
        if total_timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")

        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

        self.provider = provider
        self.health = health
        self.total_timeout_seconds = total_timeout_seconds
        self.max_attempts = max_attempts

    def execute(
        self,
        candidates: list[ModelDeployment],
        prompt: str,
        max_output_tokens: int,
    ) -> ResilientExecutionResult:

        started = time.monotonic()
        attempts = 0

        for deployment in candidates:
            if attempts >= self.max_attempts:
                break

            remaining = (
                self.total_timeout_seconds
                - (time.monotonic() - started)
            )

            if remaining <= 0:
                break

            if not self.health.is_healthy(deployment.deployment_id):
                continue

            attempts += 1
            call_started = time.monotonic()

            try:
                result = self.provider.execute(
                    deployment.deployment_id,
                    prompt,
                    max_output_tokens,
                    timeout_seconds=remaining,
                )

                latency_ms = (
                    time.monotonic() - call_started
                ) * 1000

                self.health.record_success(
                    deployment.deployment_id,
                    latency_ms,
                )

                return ResilientExecutionResult(
                    result=result,
                    deployment=deployment.deployment_id,
                    attempts=attempts,
                )

            except (ProviderTimeout, ProviderExecutionError):
                self.health.record_failure(
                    deployment.deployment_id
                )

        raise GatewayExecutionFailed(
            "All permitted provider attempts failed"
        )