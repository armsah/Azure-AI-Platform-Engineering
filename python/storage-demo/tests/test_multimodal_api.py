import io
from dataclasses import dataclass
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from multimodal_api import (
    MultimodalAPIDependencies,
    create_multimodal_app,
    require_authenticated_context,
)

from multimodal_assets import (
    MAX_ASSET_BYTES,
    MultimodalAssetRegistry,
)

from request_context import RequestContext

from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantBoundary,
    TenantMembership,
)


DIRECTORY = "directory-1"
TENANT = "tenant-a"
USER = "alice"


def context(
    *,
    tenant=TENANT,
    user=USER,
):
    return RequestContext(
        directory_tenant_id=DIRECTORY,
        tenant_id=tenant,
        user_id=user,
        groups=(),
        roles=("AI.User",),
    )


def png_bytes():
    image = Image.new(
        "RGB",
        (20, 20),
        color=(10, 20, 30),
    )

    output = io.BytesIO()

    image.save(
        output,
        format="PNG",
    )

    return output.getvalue()


def make_client(
    *,
    authenticated=True,
    user=USER,
    tenant=TENANT,
):
    memberships = InMemoryTenantMembershipStore(
        (
            TenantMembership(
                directory_tenant_id=DIRECTORY,
                user_id=USER,
                business_tenant_id=TENANT,
            ),
        )
    )

    boundary = TenantBoundary(memberships)

    assets = MultimodalAssetRegistry()

    answers = Mock()

    app = create_multimodal_app(
        MultimodalAPIDependencies(
            boundary=boundary,
            assets=assets,
            answers=answers,
        )
    )

    if authenticated:
        app.dependency_overrides[
            require_authenticated_context
        ] = lambda: context(
            tenant=tenant,
            user=user,
        )

    return TestClient(app), assets, answers


def upload(
    client,
    content,
    *,
    filename="diagram.png",
    content_type="image/png",
):
    return client.post(
        "/api/v1/multimodal/images",
        files={
            "file": (
                filename,
                content,
                content_type,
            )
        },
    )


def test_health():
    client, _, _ = make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_requires_authentication():
    client, _, _ = make_client(
        authenticated=False
    )

    response = upload(
        client,
        png_bytes(),
    )

    assert response.status_code == 401


def test_answer_requires_authentication():
    client, _, _ = make_client(
        authenticated=False
    )

    response = client.post(
        "/api/v1/multimodal/answers",
        json={"question": "Explain the diagram"},
    )

    assert response.status_code == 401


def test_valid_image_upload():
    client, assets, _ = make_client()

    response = upload(
        client,
        png_bytes(),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["version"] == 1
    assert body["content_type"] == "image/png"
    assert len(body["source_sha256"]) == 64
    assert len(body["sanitized_sha256"]) == 64

    stored = assets.get(
        tenant_id=TENANT,
        asset_id=body["asset_id"],
        version=1,
    )

    assert stored.asset_id == body["asset_id"]


def test_reject_unsupported_content_type():
    client, _, _ = make_client()

    response = upload(
        client,
        b"test",
        content_type="text/plain",
    )

    assert response.status_code == 415


def test_reject_empty_image():
    client, _, _ = make_client()

    response = upload(
        client,
        b"",
    )

    assert response.status_code == 400


def test_reject_invalid_png():
    client, _, _ = make_client()

    response = upload(
        client,
        b"not-a-png",
    )

    assert response.status_code == 422


def test_reject_oversized_image():
    client, _, _ = make_client()

    response = upload(
        client,
        b"x" * (MAX_ASSET_BYTES + 1),
    )

    assert response.status_code == 413


def test_reject_unknown_user():
    client, _, _ = make_client(
        user="mallory",
    )

    response = upload(
        client,
        png_bytes(),
    )

    assert response.status_code == 403


def test_reject_unauthorized_tenant():
    client, _, _ = make_client(
        tenant="tenant-b",
    )

    response = upload(
        client,
        png_bytes(),
    )

    assert response.status_code == 403


def test_answer_question_validation():
    client, _, _ = make_client()

    response = client.post(
        "/api/v1/multimodal/answers",
        json={
            "question": "",
        },
    )

    assert response.status_code == 422


def test_answer_top_k_validation():
    client, _, _ = make_client()

    response = client.post(
        "/api/v1/multimodal/answers",
        json={
            "question": "Explain",
            "top_k": 100,
        },
    )

    assert response.status_code == 422


def test_answer_abstention():
    client, _, answers = make_client()

    answers.answer.return_value = Mock(
        answer="I do not have verified evidence.",
        snapshot_id=None,
        citations=(),
        abstained=True,
    )

    response = client.post(
        "/api/v1/multimodal/answers",
        json={
            "question": "Unknown architecture?",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["abstained"] is True
    assert body["citations"] == []


def test_answer_uses_authenticated_tenant():
    client, _, answers = make_client()

    answers.answer.return_value = Mock(
        answer="No verified evidence.",
        snapshot_id=None,
        citations=(),
        abstained=True,
    )

    response = client.post(
        "/api/v1/multimodal/answers",
        json={
            "question": "Explain",
            "top_k": 3,
        },
    )

    assert response.status_code == 200

    kwargs = answers.answer.call_args.kwargs

    assert kwargs["context"].tenant_id == TENANT
    assert kwargs["context"].user_id == USER
    assert kwargs["top_k"] == 3


def test_answer_unknown_user_rejected_before_model():
    client, _, answers = make_client(
        user="mallory"
    )

    response = client.post(
        "/api/v1/multimodal/answers",
        json={
            "question": "Explain",
        },
    )

    assert response.status_code == 403

    answers.answer.assert_not_called()


def test_answer_cross_tenant_rejected_before_model():
    client, _, answers = make_client(
        tenant="tenant-b"
    )

    response = client.post(
        "/api/v1/multimodal/answers",
        json={
            "question": "Explain",
        },
    )

    assert response.status_code == 403

    answers.answer.assert_not_called()