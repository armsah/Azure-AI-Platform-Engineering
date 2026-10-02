from dataclasses import dataclass
from enum import Enum


class ModelCapability(str, Enum):
    FAST = "fast"
    REASONING = "reasoning"
    MULTIMODAL = "multimodal"


@dataclass(frozen=True)
class ModelTarget:
    deployment: str
    capabilities: frozenset[ModelCapability]
    priority: int


@dataclass(frozen=True)
class RoutingRequest:
    required_capability: ModelCapability


class NoModelAvailable(Exception):
    pass

MODEL_CATALOG = (
    ModelTarget(
        deployment="gpt-fast",
        capabilities=frozenset({
            ModelCapability.FAST,
        }),
        priority=1,
    ),
    ModelTarget(
        deployment="gpt-reasoning",
        capabilities=frozenset({
            ModelCapability.FAST,
            ModelCapability.REASONING,
        }),
        priority=2,
    ),
    ModelTarget(
        deployment="gpt-multimodal",
        capabilities=frozenset({
            ModelCapability.FAST,
            ModelCapability.MULTIMODAL,
        }),
        priority=3,
    ),
)

def select_model(
    request: RoutingRequest,
    catalog=MODEL_CATALOG,
) -> ModelTarget:
    candidates = [
        model
        for model in catalog
        if request.required_capability
        in model.capabilities
    ]

    if not candidates:
        raise NoModelAvailable(
            f"No model supports "
            f"{request.required_capability.value}"
        )

    return min(
        candidates,
        key=lambda model: model.priority,
    )
    
def fallback_models(
    failed_model: ModelTarget,
    request: RoutingRequest,
    catalog=MODEL_CATALOG,
) -> list[ModelTarget]:

    return sorted(
        [
            model
            for model in catalog
            if model.deployment != failed_model.deployment
            and request.required_capability
            in model.capabilities
        ],
        key=lambda model: model.priority,
    )