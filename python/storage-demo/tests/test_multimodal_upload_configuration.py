from __future__ import annotations
import logging

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from multimodal_api import (
    MultimodalAPIDependencies,
    create_multimodal_app,
    require_authenticated_context,
)

from multimodal_offline_environment import (
    create_offline_multimodal_environment,
)

from request_context import RequestContext
from unittest.mock import patch

from multimodal_upload_workflow import (
    MultimodalRollbackError,
    MultimodalUploadError,
)


DIRECTORY = "directory-1"
TENANT = "tenant-a"
USER = "alice"


def make_png() -> bytes:
    buffer = BytesIO()

    image = Image.new(
        "RGB",
        (32, 32),
        color="blue",
    )

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def test_missing_upload_workflow_fails_closed():
    environment = create_offline_multimodal_environment(
        directory_tenant_id=DIRECTORY,
        tenant_id=TENANT,
        user_id=USER,
    )

    dependencies = MultimodalAPIDependencies(
        boundary=environment.upload_workflow.boundary,
        assets=environment.assets,
        answers=environment.answers,
        upload_workflow=None,
    )

    app = create_multimodal_app(
        dependencies,
        enable_entra_auth=False,
    )

    context = RequestContext(
        directory_tenant_id=DIRECTORY,
        tenant_id=TENANT,
        user_id=USER,
        groups=(),
        roles=("AI.User",),
    )

    app.dependency_overrides[
        require_authenticated_context
    ] = lambda: context

    client = TestClient(app)

    response = client.post(
        "/api/v1/multimodal/images",
        files={
            "file": (
                "diagram.png",
                make_png(),
                "image/png",
            ),
        },
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "Image ingestion service is unavailable"
    )

    assert len(environment.assets._assets) == 0
    assert len(environment.index._documents) == 0
    assert len(environment.descriptions._records) == 0
    assert len(environment.image_sources._items) == 0

def test_ingestion_failure_returns_503_without_internal_details():
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

    client = TestClient(environment.app)

    with patch.object(
        environment.upload_workflow,
        "upload",
        side_effect=MultimodalUploadError(
            "Internal indexing failure: sensitive diagnostics"
        ),
    ):
        response = client.post(
            "/api/v1/multimodal/images",
            files={
                "file": (
                    "diagram.png",
                    make_png(),
                    "image/png",
                ),
            },
        )

    assert response.status_code == 503

    assert response.json() == {
        "detail": "Image ingestion service is unavailable"
    }

    assert "sensitive diagnostics" not in response.text

def test_vision_provider_timeout_returns_503_without_details():
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

    client = TestClient(environment.app)

    with patch.object(
        environment.upload_workflow.vision_provider,
        "describe",
        side_effect=TimeoutError(
            "Vision provider timeout: internal endpoint details"
        ),
    ):
        response = client.post(
            "/api/v1/multimodal/images",
            files={
                "file": (
                    "diagram.png",
                    make_png(),
                    "image/png",
                ),
            },
        )

    assert response.status_code == 503

    assert response.json() == {
        "detail": "Image ingestion service is unavailable"
    }

    assert "internal endpoint details" not in response.text

    # Provider failure occurs before the commit phase.
    # No asset, evidence, description, or index should be written.
    assert len(environment.assets._assets) == 0
    assert len(environment.index._documents) == 0
    assert len(environment.descriptions._records) == 0
    assert len(environment.image_sources._items) == 0

def test_incomplete_rollback_is_logged_without_exposing_details(
    caplog,
):
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

    client = TestClient(environment.app)

    with patch.object(
        environment.upload_workflow,
        "upload",
        side_effect=MultimodalRollbackError(
            "Image ingestion failed and cleanup was incomplete: "
            "internal storage diagnostics"
        ),
    ):
        with caplog.at_level(
            logging.ERROR,
            logger="multimodal.api",
        ):
            response = client.post(
                "/api/v1/multimodal/images",
                files={
                    "file": (
                        "diagram.png",
                        make_png(),
                        "image/png",
                    ),
                },
            )

    assert response.status_code == 503

    assert response.json() == {
        "detail": "Image ingestion service is unavailable"
    }

    assert "internal storage diagnostics" not in response.text

    matching_records = [
        record
        for record in caplog.records
        if record.name == "multimodal.api"
        and record.getMessage() == "multimodal_ingestion_failed"
    ]

    assert len(matching_records) == 1

    record = matching_records[0]

    assert record.failure_category == "rollback_incomplete"
    assert record.rollback_incomplete is True

    assert record.request_id == response.headers["X-Request-ID"]

    assert "internal storage diagnostics" not in (
        record.getMessage()
    )
