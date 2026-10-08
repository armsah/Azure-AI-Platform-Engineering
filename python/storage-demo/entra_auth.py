import os
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from request_context import RequestContext
from tenant_resolver import (
    TenantResolutionError,
    resolve_application_tenant,
)


TENANT_ID = os.getenv("ENTRA_TENANT_ID", "")
API_CLIENT_ID = os.getenv("ENTRA_API_CLIENT_ID", "")
EXPECTED_DELEGATED_SCOPE = os.getenv(
    "ENTRA_API_SCOPE",
    "access_as_user",
)

EXPECTED_APPLICATION_ROLE = os.getenv(
    "ENTRA_API_ROLE",
    "AI.Access",
)

class TokenAuthorizationError(Exception):
    pass


def authorize_api_token(claims: dict) -> None:
    scopes = set(str(claims.get("scp", "")).split())

    raw_roles = claims.get("roles", [])
    roles = set(raw_roles) if isinstance(raw_roles, list) else set()

    # Delegated user token
    if scopes:
        if EXPECTED_DELEGATED_SCOPE not in scopes:
            raise TokenAuthorizationError(
                "Required delegated API scope is missing"
            )
        return

    # Application/service-principal token
    if roles:
        if EXPECTED_APPLICATION_ROLE not in roles:
            raise TokenAuthorizationError(
                "Required application role is missing"
            )
        return

    raise TokenAuthorizationError(
        "Token contains no authorized API permission"
    )

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_jwks_client() -> PyJWKClient:
    if not TENANT_ID:
        raise RuntimeError("ENTRA_TENANT_ID is not configured")

    return PyJWKClient(
        f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
    )


def validate_access_token(token: str) -> dict:
    if not TENANT_ID or not API_CLIENT_ID:
        raise RuntimeError("Entra authentication is not configured")

    signing_key = get_jwks_client().get_signing_key_from_jwt(token)

    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=API_CLIENT_ID,
        issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        options={
            "require": ["exp", "iat", "tid"],
        },
    )

def token_has_group_overage(claims: dict) -> bool:
    return (
        claims.get("hasgroups") is True
        or "groups" in claims.get("_claim_names", {})
    )


def claims_to_request_context(claims: dict) -> RequestContext:
    directory_tenant_id = claims["tid"]
    user_id = claims.get("oid") or claims.get("sub")
    
    if not user_id:
        raise ValueError("Required identity claims are missing")

    tenant_id = resolve_application_tenant(
        directory_tenant_id,
        user_id,
    )

    if not tenant_id or not user_id:
        raise ValueError("Required identity claims are missing")
    
    if token_has_group_overage(claims):
        groups = ()
    else:
        raw_groups = claims.get("groups", [])
        groups = (
            tuple(raw_groups)
            if isinstance(raw_groups, list)
            else ()
        )
        
    raw_roles = claims.get("roles", [])
    roles = (
        tuple(raw_roles)
        if isinstance(raw_roles, list)
        else ()
    )

    return RequestContext(
        directory_tenant_id=directory_tenant_id,
        tenant_id=tenant_id,
        user_id=user_id,
        groups=groups,
        roles=roles,
    )


def get_request_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> RequestContext:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token")

    claims = validate_access_token(credentials.credentials)

    try:
        authorize_api_token(claims)
    except TokenAuthorizationError as exc:
        raise HTTPException(
            status_code=403,
            detail="Insufficient API permission",
        ) from exc

    try:
        return claims_to_request_context(claims)
    except TenantResolutionError as exc:
        raise HTTPException(
            status_code=403,
            detail="No application tenant membership",
        ) from exc