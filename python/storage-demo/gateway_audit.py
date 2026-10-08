from dataclasses import dataclass
from typing import Callable
from model_registry import ModelDeployment


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

@dataclass(frozen=True)
class ProviderAttempt:
    deployment: str
    outcome: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float

@dataclass(frozen=True)
class GatewayAuditRecord:
    tenant_id: str
    user_id: str
    correlation_id: str | None
    operation: str

    deployment: str | None
    model_calls: int
    fallback_attempts: int

    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float

    latency_ms: float
    outcome: str
    error_category: str | None = None
    
    attempts: tuple[ProviderAttempt, ...] = ()


AuditSink = Callable[[GatewayAuditRecord], None]


def estimate_cost_usd(
    deployment: str,
    usage: TokenUsage,
) -> float:
    """
    Lab pricing model only.

    Production pricing should come from versioned configuration
    rather than being hardcoded into application logic.
    """

    rates = {
        "gpt-fast": (0.0002, 0.0008),
        "gpt-reasoning": (0.001, 0.004),
        "gpt-multimodal": (0.002, 0.006),
    }

    input_rate, output_rate = rates.get(
        deployment,
        (0.0, 0.0),
    )

    return (
        usage.input_tokens / 1000 * input_rate
        + usage.output_tokens / 1000 * output_rate
    )
    
def estimate_deployment_cost_usd(
    deployment: ModelDeployment,
    usage: TokenUsage,
) -> float:
    if usage.input_tokens < 0 or usage.output_tokens < 0:
        raise ValueError("Token usage cannot be negative")

    return (
        usage.input_tokens / 1000 * deployment.input_cost_per_1k
        + usage.output_tokens / 1000 * deployment.output_cost_per_1k
    )