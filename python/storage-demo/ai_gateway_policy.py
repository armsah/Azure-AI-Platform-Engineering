from dataclasses import dataclass
from enum import Enum


class CapabilityTier(str, Enum):
    STANDARD = "standard"
    REASONING = "reasoning"
    AGENT = "agent"


@dataclass(frozen=True)
class GatewayDecision:
    allowed: bool
    capability: CapabilityTier | None
    max_output_tokens: int
    max_iterations: int
    tools_enabled: bool
    reason: str


_OPERATION_POLICIES: dict[str, GatewayDecision] = {
    "direct.chat": GatewayDecision(
        allowed=True,
        capability=CapabilityTier.STANDARD,
        max_output_tokens=1024,
        max_iterations=1,
        tools_enabled=False,
        reason="Direct chat policy",
    ),
    "document.summarize": GatewayDecision(
        allowed=True,
        capability=CapabilityTier.STANDARD,
        max_output_tokens=1024,
        max_iterations=1,
        tools_enabled=False,
        reason="Document summarization policy",
    ),
    "classification": GatewayDecision(
        allowed=True,
        capability=CapabilityTier.STANDARD,
        max_output_tokens=256,
        max_iterations=1,
        tools_enabled=False,
        reason="Classification policy",
    ),
    "rag.answer": GatewayDecision(
        allowed=True,
        capability=CapabilityTier.REASONING,
        max_output_tokens=2048,
        max_iterations=1,
        tools_enabled=False,
        reason="RAG policy",
    ),
    "agent.execute": GatewayDecision(
        allowed=True,
        capability=CapabilityTier.AGENT,
        max_output_tokens=2048,
        max_iterations=5,
        tools_enabled=True,
        reason="Agent execution policy",
    ),
}


def evaluate_gateway_policy(operation: str) -> GatewayDecision:
    decision = _OPERATION_POLICIES.get(operation)

    if decision is None:
        return GatewayDecision(
            allowed=False,
            capability=None,
            max_output_tokens=0,
            max_iterations=0,
            tools_enabled=False,
            reason="Operation is not allowed",
        )

    return decision