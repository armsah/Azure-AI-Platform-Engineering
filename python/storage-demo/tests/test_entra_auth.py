import time
import app
import jwt
import pytest
import entra_auth

from cryptography.hazmat.primitives.asymmetric import rsa
from tenant_resolver import TenantResolutionError
from fastapi.testclient import TestClient



TENANT_ID = "11111111-1111-1111-1111-111111111111"
CLIENT_ID = "22222222-2222-2222-2222-222222222222"
USER_ID = "33333333-3333-3333-3333-333333333333"

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
def configure_auth(monkeypatch):
    monkeypatch.setattr(entra_auth, "TENANT_ID", TENANT_ID)
    monkeypatch.setattr(entra_auth, "API_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(
        entra_auth,
        "get_jwks_client",
        lambda: FakeJwksClient(),
    )


def make_token(**overrides):
    now = int(time.time())

    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        "aud": CLIENT_ID,
        "iat": now,
        "exp": now + 300,
        "tid": TENANT_ID,
        "oid": USER_ID,
        "groups": ["platform-engineering"],
        "roles": ["AI.User"],
        "scp": "access_as_user",
    }

    claims.update(overrides)

    return jwt.encode(
        claims,
        PRIVATE_KEY,
        algorithm="RS256",
    )


def test_valid_token():
    claims = entra_auth.validate_access_token(make_token())

    assert claims["tid"] == TENANT_ID
    assert claims["oid"] == USER_ID


def test_expired_token_rejected():
    token = make_token(exp=int(time.time()) - 60)

    with pytest.raises(jwt.ExpiredSignatureError):
        entra_auth.validate_access_token(token)


def test_wrong_audience_rejected():
    token = make_token(aud="wrong-api")

    with pytest.raises(jwt.InvalidAudienceError):
        entra_auth.validate_access_token(token)


def test_wrong_issuer_rejected():
    token = make_token(
        iss="https://login.microsoftonline.com/attacker/v2.0"
    )

    with pytest.raises(jwt.InvalidIssuerError):
        entra_auth.validate_access_token(token)


def test_forged_signature_rejected():
    attacker_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    now = int(time.time())

    token = jwt.encode(
        {
            "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            "aud": CLIENT_ID,
            "iat": now,
            "exp": now + 300,
            "tid": TENANT_ID,
            "oid": USER_ID,
        },
        attacker_key,
        algorithm="RS256",
    )

    with pytest.raises(jwt.InvalidSignatureError):
        entra_auth.validate_access_token(token)


def test_claims_become_request_context(monkeypatch):
    monkeypatch.setattr(
        entra_auth,
        "resolve_application_tenant",
        lambda directory_tenant_id, user_id: "customer-a",
    )
        
    claims = entra_auth.validate_access_token(make_token())

    context = entra_auth.claims_to_request_context(claims)

    assert context.directory_tenant_id == TENANT_ID
    assert context.tenant_id == "customer-a"
    assert context.user_id == USER_ID
    assert context.groups == ("platform-engineering",)
    assert context.roles == ("AI.User",)
    
def test_valid_user_without_membership_gets_403(monkeypatch):
    def deny_membership(directory_tenant_id, user_id):
        raise TenantResolutionError(
            "User has no application tenant membership"
        )

    monkeypatch.setattr(
        entra_auth,
        "resolve_application_tenant",
        deny_membership,
    )

    token = make_token()
    
    previous_override = app.app.dependency_overrides.pop(
        entra_auth.get_request_context,
        None,
    )
    
    try:

        client = TestClient(app.app)

        response = client.post(
            "/rag",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "question": "test",
            },
        )

        assert response.status_code == 403
        
    finally:
        if previous_override is not None:
            app.app.dependency_overrides[
                entra_auth.get_request_context
            ] = previous_override
            
def test_delegated_token_with_required_scope_is_allowed():
    entra_auth.authorize_api_token({
        "scp": entra_auth.EXPECTED_DELEGATED_SCOPE,
    })


def test_delegated_token_without_required_scope_is_denied():
    with pytest.raises(entra_auth.TokenAuthorizationError):
        entra_auth.authorize_api_token({
            "scp": "Some.Other.Scope",
        })


def test_application_token_with_required_role_is_allowed():
    entra_auth.authorize_api_token({
        "roles": [entra_auth.EXPECTED_APPLICATION_ROLE],
    })


def test_application_token_without_required_role_is_denied():
    with pytest.raises(entra_auth.TokenAuthorizationError):
        entra_auth.authorize_api_token({
            "roles": ["Some.Other.Role"],
        })


def test_token_without_scope_or_role_is_denied():
    with pytest.raises(entra_auth.TokenAuthorizationError):
        entra_auth.authorize_api_token({})
        
def test_group_overage_does_not_trust_groups(monkeypatch):
    monkeypatch.setattr(
        "entra_auth.resolve_application_tenant",
        lambda directory_tenant_id, user_id: "customer-a",
    )

    claims = {
        "tid": "directory-tenant",
        "oid": "user-001",
        "groups": ["platform-engineering"],
        "hasgroups": True,
    }

    context = entra_auth.claims_to_request_context(claims)

    assert context.groups == ()