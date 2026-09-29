from model_router import get_model_route


def test_known_model_route():
    route = get_model_route("complex")

    assert route.primary
    assert route.fallback


def test_unknown_route_uses_default():
    route = get_model_route("unknown-task")

    assert route == get_model_route("default")