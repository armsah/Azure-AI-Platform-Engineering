from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRoute:
    primary: str
    fallback: str | None = None


ROUTES = {
    "default": ModelRoute(
        primary="gpt-5-mini-learning",
    ),
    "complex": ModelRoute(
        primary="gpt-5-mini-learning",
        fallback="gpt-5-mini-learning",
    ),
}


def get_model_route(task_type: str) -> ModelRoute:
    return ROUTES.get(task_type, ROUTES["default"])