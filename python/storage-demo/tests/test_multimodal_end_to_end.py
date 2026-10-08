import io

import pytest

from fastapi.testclient import TestClient
from PIL import Image

from multimodal_api import (
    require_authenticated_context,
)

from multimodal_offline_environment import (
    create_offline_multimodal_environment,
)

from request_context import RequestContext


# ============================================================
# Test identities
# ============================================================

DIRECTORY = "directory-1"
TENANT = "tenant-a"
USER = "alice"


# ============================================================
# Helpers
# ============================================================

def context(
    *,
    tenant=TENANT,
    user=USER,
):
    """
    Construct a deterministic test identity.

    This context is injected through FastAPI dependency
    overrides. Production authentication must use the
    existing verified Entra JWT authentication mechanism.
    """
    return RequestContext(
        directory_tenant_id=DIRECTORY,
        tenant_id=tenant,
        user_id=user,
        groups=(),
        roles=("AI.User",),
    )


def make_png():
    """
    Generate a valid PNG image in memory.

    No filesystem access or external services are required.
    """
    image = Image.new(
        "RGB",
        (32, 32),
        color=(20, 80, 160),
    )

    output = io.BytesIO()

    image.save(
        output,
        format="PNG",
    )

    return output.getvalue()


def make_environment(
    *,
    identity=None,
):
    """
    Create the complete offline multimodal environment.

    Real components:
      - TenantBoundary
      - MultimodalAssetRegistry
      - Secure image processing
      - ImageDescriptionRegistry
      - MultimodalIndexingService
      - MultimodalRetrievalService
      - MultimodalEvidenceGate
      - MultimodalRAGAnswerService

    Offline substitutes:
      - Vision provider
      - Embedding provider
      - Answer model
    """
    environment = create_offline_multimodal_environment(
        directory_tenant_id=DIRECTORY,
        tenant_id=TENANT,
        user_id=USER,
    )

    if identity is not None:
        environment.app.dependency_overrides[
            require_authenticated_context
        ] = lambda: identity

    return environment, TestClient(environment.app)


def upload(client, content=None):
    """
    Upload an image through the real FastAPI endpoint.
    """
    return client.post(
        "/api/v1/multimodal/images",
        files={
            "file": (
                "diagram.png",
                content if content is not None else make_png(),
                "image/png",
            )
        },
    )


def ask(client):
    """
    Ask a question through the real FastAPI endpoint.
    """
    return client.post(
        "/api/v1/multimodal/answers",
        json={
            "question": "Explain the architecture diagram",
            "top_k": 5,
        },
    )


# ============================================================
# Test 1 — Complete image-to-answer workflow
# ============================================================

def test_complete_image_to_cited_answer():
    environment, client = make_environment(
        identity=context(),
    )

    uploaded = upload(client)

    assert uploaded.status_code == 201

    upload_result = uploaded.json()

    asset_id = upload_result["asset_id"]

    assert upload_result["description"]
    assert upload_result["search_id"]

    answered = ask(client)

    assert answered.status_code == 200

    result = answered.json()

    assert result["abstained"] is False
    assert result["snapshot_id"] is not None
    assert len(result["citations"]) == 1

    citation = result["citations"][0]

    assert citation["modality"] == "image"
    assert citation["resource_id"] == asset_id
    assert citation["resource_version"] == 1
    assert citation["citation_id"]
    assert citation["evidence_id"]


# ============================================================
# Test 2 — No indexed evidence means abstention
# ============================================================

def test_unindexed_environment_abstains():
    _, client = make_environment(
        identity=context(),
    )

    answered = ask(client)

    assert answered.status_code == 200

    result = answered.json()

    assert result["abstained"] is True
    assert result["snapshot_id"] is None
    assert result["citations"] == []


# ============================================================
# Test 3 — Upload requires authentication
# ============================================================

def test_upload_requires_authentication():
    _, client = make_environment()

    response = upload(client)

    assert response.status_code == 401


# ============================================================
# Test 4 — Answer requires authentication
# ============================================================

def test_answer_requires_authentication():
    _, client = make_environment()

    response = ask(client)

    assert response.status_code == 401


# ============================================================
# Test 5 — Cross-tenant upload rejected
# ============================================================

def test_cross_tenant_upload_rejected():
    _, client = make_environment(
        identity=context(
            tenant="tenant-b",
        ),
    )

    response = upload(client)

    assert response.status_code == 403


# ============================================================
# Test 6 — Cross-tenant answer rejected
# ============================================================

def test_cross_tenant_answer_rejected():
    _, client = make_environment(
        identity=context(
            tenant="tenant-b",
        ),
    )

    response = ask(client)

    assert response.status_code == 403


# ============================================================
# Test 7 — Unknown user cannot upload
# ============================================================

def test_unknown_user_upload_rejected():
    _, client = make_environment(
        identity=context(
            user="mallory",
        ),
    )

    response = upload(client)

    assert response.status_code == 403


# ============================================================
# Test 8 — Unknown user cannot query
# ============================================================

def test_unknown_user_answer_rejected():
    _, client = make_environment(
        identity=context(
            user="mallory",
        ),
    )

    response = ask(client)

    assert response.status_code == 403


# ============================================================
# Test 9 — Invalid image must not become searchable
# ============================================================

def test_invalid_image_not_indexed():
    environment, client = make_environment(
        identity=context(),
    )

    response = upload(
        client,
        content=b"invalid image bytes",
    )

    assert response.status_code == 422

    answered = ask(client)

    assert answered.status_code == 200
    assert answered.json()["abstained"] is True


# ============================================================
# Test 10 — Description provenance is registered
# ============================================================

def test_description_registered_with_provenance():
    environment, client = make_environment(
        identity=context(),
    )

    uploaded = upload(client)

    assert uploaded.status_code == 201

    upload_result = uploaded.json()

    asset_id = upload_result["asset_id"]

    record = environment.descriptions.get(
        tenant_id=TENANT,
        asset_id=asset_id,
        asset_version=1,
    )

    assert (
        record.source_sha256
        == upload_result["source_sha256"]
    )

    assert (
        record.sanitized_sha256
        == upload_result["sanitized_sha256"]
    )

    assert record.description


# ============================================================
# Test 11 — Tampered source must not produce citations
# ============================================================

def test_tampered_source_causes_abstention():
    environment, client = make_environment(
        identity=context(),
    )

    uploaded = upload(client)

    assert uploaded.status_code == 201

    asset_id = uploaded.json()["asset_id"]

    # Deliberately overwrite the test source store.
    # This simulates source corruption after indexing.
    environment.image_sources.put(
        tenant_id=TENANT,
        asset_id=asset_id,
        asset_version=1,
        content=b"tampered bytes",
    )

    answered = ask(client)

    assert answered.status_code == 200

    result = answered.json()

    assert result["abstained"] is True
    assert result["citations"] == []
    assert result["snapshot_id"] is None


# ============================================================
# Test 12 — Each upload receives a unique asset identity
# ============================================================

def test_multiple_images_have_distinct_assets():
    _, client = make_environment(
        identity=context(),
    )

    first = upload(client)
    second = upload(client)

    assert first.status_code == 201
    assert second.status_code == 201

    first_asset_id = first.json()["asset_id"]
    second_asset_id = second.json()["asset_id"]

    assert first_asset_id != second_asset_id

    assert first.json()["search_id"]
    assert second.json()["search_id"]