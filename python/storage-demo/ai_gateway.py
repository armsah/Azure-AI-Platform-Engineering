from dataclasses import dataclass
from typing import Any

from ai_gateway_policy import (
    CapabilityTier,
    GatewayDecision,
    evaluate_gateway_policy,
)
from production_model_router import (
    ModelCapability,
    ModelTarget,
    RoutingRequest,
    select_model,
)
from request_context import RequestContext


@dataclass(frozen=True)
class AIRequest:
    operation: str
    request_context: RequestContext
    input: Any
    correlation_id: str | None = None


@dataclass(frozen=True)
class AIResponse:
    output: Any
    operation: str
    correlation_id: str | None = None

@dataclass(frozen=True)
class GatewayRoute:
    decision: GatewayDecision
    model: ModelTarget

_CAPABILITY_MAP = {
    CapabilityTier.STANDARD: ModelCapability.FAST,
    CapabilityTier.REASONING: ModelCapability.REASONING,
    CapabilityTier.AGENT: ModelCapability.REASONING,
}

class GatewayDenied(Exception):
    pass

class AIGateway:
    def authorize(self, request: AIRequest) -> GatewayDecision:
        return evaluate_gateway_policy(request.operation)
    
    def route(self, request: AIRequest) -> GatewayRoute:
        decision = self.authorize(request)
        
        if not decision.allowed or decision.capability is None:
            raise GatewayDenied(
                f"Operation denied: {decision.reason}"
            )
            
        required_capability = _CAPABILITY_MAP[decision.capability]
        
        model = select_model(
            RoutingRequest(
                required_capability=required_capability,
            )
        )
        
        return GatewayRoute(
            decision=decision,
            model=model,
        )
        
def model_capability_for(decision: GatewayDecision) -> ModelCapability:
    return _CAPABILITY_MAP[decision.capability]                 