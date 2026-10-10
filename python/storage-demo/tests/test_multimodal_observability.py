from __future__ import annotations

import logging
from uuid import UUID
from unittest.mock import patch

import pytest

from fastapi.testclient import TestClient

from multimodal_api import (
    MultimodalAPIDependencies,
    create_multimodal_app,
    require_authenticated_context,
)

from multimodal_offline_environment import (
    create_offline_multimodal_environment,
)


def make_app():
    environment = create_offline_multimodal_environment(
        directory_tenant_id="directory-1",
        tenant_id="tenant-a",
        user_id="alice",
    )

    dependencies = MultimodalAPIDependencies(
        boundary=environment.upload_workflow.boundary,
        assets=environment.assets,
        answers=environment.answers,
        upload_workflow=environment.upload_workflow,
    )

    return create_multimodal_app(
        dependencies,
        enable_entra_auth=False,
    )


def test_health_response_has_valid_request_id():
    client = TestClient(make_app())

    response = client.get("/health")

    assert response.status_code == 200

    request_id = response.headers["X-Request-ID"]

    assert str(UUID(request_id)) == request_id


def test_each_request_receives_unique_request_id():
    client = TestClient(make_app())

    first = client.get("/health")
    second = client.get("/health")

    assert first.headers["X-Request-ID"] != (
        second.headers["X-Request-ID"]
    )


def test_authentication_failure_has_request_id():
    app = make_app()

    assert (
        require_authenticated_context
        not in app.dependency_overrides
    )

    client = TestClient(app)

    response = client.post(
        "/api/v1/multimodal/answers",
        json={
            "question": "What does the diagram show?",
        },
    )

    assert response.status_code == 401

    assert response.headers["X-Request-ID"]


def test_request_completion_log_contains_correlation_fields(caplog):
    client = TestClient(make_app())

    with caplog.at_level(
        logging.INFO,
        logger="multimodal.api",
    ):
        response = client.get("/health")

    matching_records = [
        record
        for record in caplog.records
        if record.name == "multimodal.api"
        and record.getMessage() == "multimodal_request_completed"
    ]

    assert matching_records

    record = matching_records[-1]

    assert record.request_id == response.headers["X-Request-ID"]
    assert record.http_method == "GET"
    assert record.http_path == "/health"
    assert record.http_status_code == 200
    
def test_unexpected_error_log_does_not_expose_exception_details(
    caplog,
):
    app = make_app()

    @app.get("/test-unexpected-failure")
    def unexpected_failure():
        raise RuntimeError(
            "SECRET_INTERNAL_DATABASE_CONNECTION_STRING"
        )

    client = TestClient(app)

    with caplog.at_level(
        logging.ERROR,
        logger="multimodal.api",
    ):
        with pytest.raises(
            RuntimeError,
            match="SECRET_INTERNAL_DATABASE_CONNECTION_STRING",
        ):
            client.get("/test-unexpected-failure")

    matching_records = [
        record
        for record in caplog.records
        if record.name == "multimodal.api"
        and record.getMessage() == "multimodal_request_failed"
    ]

    assert len(matching_records) == 1

    record = matching_records[0]

    assert record.failure_category == "unexpected_error"
    assert record.request_id
    assert record.http_method == "GET"
    assert record.http_path == "/test-unexpected-failure"

    assert record.exc_info is None

    assert (
        "SECRET_INTERNAL_DATABASE_CONNECTION_STRING"
        not in record.getMessage()
    )