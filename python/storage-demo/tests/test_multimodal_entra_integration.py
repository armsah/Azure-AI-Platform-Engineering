from __future__ import annotations

import time

import jwt
import pytest

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

import entra_auth

from multimodal_api import (
    MultimodalAPIDependencies,
    create_multimodal_app,
)

from multimodal_offline_environment import (
    create_offline_multimodal_environment,
)

from tenant_resolver import TenantResolutionError


DIRECTORY = "11111111-1111-1111-1111-111111111111"
CLIENT_ID = "22222222-2222-2222-2222-222222222222"
USER = "33333333-3333-3333-3333-333333333333"
BUSINESS_TENANT = "customer-a"


PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

PUBLIC_KEY = PRIVATE_KEY.public_key()


class FakeSigningKey:
    key = PUBLIC_KEY


class FakeJwksClient:
    def get_signing_key_from_jwt(self, token):
        return FakeSigningKey()


@pytest.fixture(autouse=True)
def configure_entra(monkeypatch):
    monkeypatch.setattr(
        entra_auth,
        "TENANT_ID",
        DIRECTORY,
    )

    monkeypatch.setattr(
        entra_auth,
        "API_CLIENT_ID",
        CLIENT_ID,
    )

    monkeypatch.setattr(
        entra_auth,
        "get_jwks_client",
        lambda: FakeJwksClient(),
    )

    # Test-only identity-to-tenant mapping.
    # Reject any identity other than the configured test user.
    def resolve_test_tenant(directory_tenant_id, user_id):
        if (
            directory_tenant_id != DIRECTORY
            or user_id != USER
        ):
            raise TenantResolutionError(
                "No application tenant membership"
            )

        return BUSINESS_TENANT

    monkeypatch.setattr(
        entra_auth,
        "resolve_application_tenant",
        resolve_test_tenant,
    )


def make_token(**overrides):
    now = int(time.time())

    claims = {
        "iss": (
            f"https://login.microsoftonline.com/"
            f"{DIRECTORY}/v2.0"
        ),
        "aud": CLIENT_ID,
        "iat": now,
        "exp": now + 300,
        "tid": DIRECTORY,
        "oid": USER,
        "scp": "access_as_user",
        "roles": ["AI.User"],
    }

    claims.update(overrides)

    return jwt.encode(
        claims,
        PRIVATE_KEY,
        algorithm="RS256",
    )


def make_client():
    environment = create_offline_multimodal_environment(
        directory_tenant_id=DIRECTORY,
        tenant_id=BUSINESS_TENANT,
        user_id=USER,
    )

    workflow = environment.upload_workflow

    dependencies = MultimodalAPIDependencies(
        boundary=workflow.boundary,
        assets=environment.assets,
        answers=environment.answers,
        upload_workflow=workflow,
    )

    app = create_multimodal_app(
        dependencies,
        enable_entra_auth=True,
    )

    return TestClient(app)


def post_answer(client, token=None):
    headers = {}

    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

    return client.post(
        "/api/v1/multimodal/answers",
        headers=headers,
        json={
            "question": "Describe the architecture",
        },
    )


def test_missing_token_returns_401():
    client = make_client()

    response = post_answer(client)

    assert response.status_code == 401


def test_malformed_token_returns_401():
    client = make_client()

    response = post_answer(
        client,
        "not-a-valid-jwt",
    )

    assert response.status_code == 401


def test_expired_token_returns_401():
    client = make_client()

    response = post_answer(
        client,
        make_token(
            exp=int(time.time()) - 60,
        ),
    )

    assert response.status_code == 401


def test_wrong_audience_returns_401():
    client = make_client()

    response = post_answer(
        client,
        make_token(
            aud="attacker-api",
        ),
    )

    assert response.status_code == 401


def test_wrong_issuer_returns_401():
    client = make_client()

    response = post_answer(
        client,
        make_token(
            iss=(
                "https://login.microsoftonline.com/"
                "attacker/v2.0"
            ),
        ),
    )

    assert response.status_code == 401


def test_missing_api_permission_returns_403():
    client = make_client()

    response = post_answer(
        client,
        make_token(
            scp="unauthorized.scope",
        ),
    )

    assert response.status_code == 403


def test_missing_tenant_membership_returns_403(
    monkeypatch,
):
    client = make_client()

    def deny_membership(directory_tenant_id, user_id):
        raise TenantResolutionError(
            "No application tenant membership"
        )

    monkeypatch.setattr(
        entra_auth,
        "resolve_application_tenant",
        deny_membership,
    )

    response = post_answer(
        client,
        make_token(),
    )

    assert response.status_code == 403


def test_different_user_cannot_access_business_tenant():
    client = make_client()

    response = post_answer(
        client,
        make_token(
            oid="44444444-4444-4444-4444-444444444444",
        ),
    )

    assert response.status_code == 403


def test_authenticated_request_reaches_answer_service():
    client = make_client()

    response = post_answer(
        client,
        make_token(),
    )

    assert response.status_code == 200

def test_token_from_other_directory_returns_401():
    client = make_client()

    other_directory = (
        "55555555-5555-5555-5555-555555555555"
    )

    token = make_token(
        tid=other_directory,
        iss=(
            "https://login.microsoftonline.com/"
            f"{other_directory}/v2.0"
        ),
    )

    response = post_answer(client, token)

    assert response.status_code == 401

def test_forged_signature_returns_401():
    client = make_client()

    attacker_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    now = int(time.time())

    claims = {
        "iss": (
            f"https://login.microsoftonline.com/"
            f"{DIRECTORY}/v2.0"
        ),
        "aud": CLIENT_ID,
        "iat": now,
        "exp": now + 300,
        "tid": DIRECTORY,
        "oid": USER,
        "scp": "access_as_user",
    }

    forged_token = jwt.encode(
        claims,
        attacker_key,
        algorithm="RS256",
    )

    response = post_answer(
        client,
        forged_token,
    )

    assert response.status_code == 401

def test_resolved_unauthorized_business_tenant_returns_403(
    monkeypatch,
):
    client = make_client()

    monkeypatch.setattr(
        entra_auth,
        "resolve_application_tenant",
        lambda directory_tenant_id, user_id: (
            "customer-attacker"
        ),
    )

    response = post_answer(
        client,
        make_token(),
    )

    assert response.status_code == 403
