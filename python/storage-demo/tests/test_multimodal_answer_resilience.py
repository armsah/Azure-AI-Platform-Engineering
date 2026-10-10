from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from multimodal_api import require_authenticated_context

from multimodal_offline_environment import (
    create_offline_multimodal_environment,
)

from request_context import RequestContext


DIRECTORY = "directory-1"
TENANT = "tenant-a"
USER = "alice"


def make_client():
    environment = create_offline_multimodal_environment(
        directory_tenant_id=DIRECTORY,
        tenant_id=TENANT,
        user_id=USER,
    )

    context = RequestContext(
        directory_tenant_id=DIRECTORY,
        tenant_id=TENANT,
        user_id=USER,
        groups=(),
        roles=("AI.User",),
    )

    environment.app.dependency_overrides[
        require_authenticated_context
    ] = lambda: context

    return TestClient(environment.app), environment


def test_answer_timeout_returns_503_without_internal_details():
    client, environment = make_client()

    with patch.object(
        environment.answers,
        "answer",
        side_effect=TimeoutError(
            "Model timeout: internal deployment details"
        ),
    ):
        response = client.post(
            "/api/v1/multimodal/answers",
            json={
                "question": "What does the diagram show?",
            },
        )

    assert response.status_code == 503

    assert response.json() == {
        "detail": "Answer generation service is unavailable"
    }

    assert "internal deployment details" not in response.text


def test_answer_connection_failure_returns_503():
    client, environment = make_client()

    with patch.object(
        environment.answers,
        "answer",
        side_effect=ConnectionError(
            "Internal search service connection failed"
        ),
    ):
        response = client.post(
            "/api/v1/multimodal/answers",
            json={
                "question": "Summarize the available evidence",
            },
        )

    assert response.status_code == 503

    assert response.json() == {
        "detail": "Answer generation service is unavailable"
    }

    assert "Internal search service" not in response.text