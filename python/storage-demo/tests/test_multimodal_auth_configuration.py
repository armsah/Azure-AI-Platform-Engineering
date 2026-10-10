from __future__ import annotations

from fastapi.testclient import TestClient

from multimodal_api import (
    MultimodalAPIDependencies,
    create_multimodal_app,
    require_authenticated_context,
)

from multimodal_offline_environment import (
    create_offline_multimodal_environment,
)

from entra_auth import get_request_context


DIRECTORY = "directory-1"
TENANT = "tenant-a"
USER = "alice"


def make_dependencies():
    environment = create_offline_multimodal_environment(
        directory_tenant_id=DIRECTORY,
        tenant_id=TENANT,
        user_id=USER,
    )

    return MultimodalAPIDependencies(
        boundary=environment.upload_workflow.boundary,
        assets=environment.assets,
        answers=environment.answers,
        upload_workflow=environment.upload_workflow,
    )


def test_entra_disabled_preserves_fail_closed_authentication():
    app = create_multimodal_app(
        make_dependencies(),
        enable_entra_auth=False,
    )

    assert (
        require_authenticated_context
        not in app.dependency_overrides
    )

    client = TestClient(app)

    response = client.post(
        "/api/v1/multimodal/answers",
        json={
            "question": "Describe the diagram",
        },
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        "Authentication is not configured"
    )


def test_entra_enabled_installs_verified_authentication():
    app = create_multimodal_app(
        make_dependencies(),
        enable_entra_auth=True,
    )

    assert (
        app.dependency_overrides[
            require_authenticated_context
        ]
        is get_request_context
    )
    