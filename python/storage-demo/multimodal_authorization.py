from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from multimodal_assets import (
    MultimodalAsset,
    MultimodalAssetRegistry,
)

from request_context import RequestContext

from tenant_boundary import (
    TenantAuthorizationError,
    TenantBoundary,
)


# ============================================================
# Asset authorization grant
# ============================================================

@dataclass(frozen=True)
class AssetGrant:
    tenant_id: str
    asset_id: str
    user_id: str


# ============================================================
# In-memory asset access policy
# ============================================================

class InMemoryAssetAccessPolicy:
    """
    Tenant-scoped, user-specific asset access policy.

    Grants are stored as:

        (tenant_id, asset_id, user_id)

    Default behavior is deny unless an explicit grant exists.

    Supports:
      - Initial grants supplied through the constructor
      - Dynamic grants from trusted ingestion workflows
      - Explicit revocation
      - Thread-safe reads and updates
    """

    def __init__(
        self,
        grants: tuple[AssetGrant, ...] = (),
    ):
        self._lock = RLock()

        self._grants: set[tuple[str, str, str]] = {
            (
                grant.tenant_id,
                grant.asset_id,
                grant.user_id,
            )
            for grant in grants
        }

    def grant(
        self,
        grant: AssetGrant,
    ) -> None:
        """
        Add an explicit asset access grant.

        Intended to be called by trusted application services,
        such as MultimodalUploadWorkflow.

        Do not expose this method directly through an
        unauthenticated or user-controlled API.
        """

        if not isinstance(grant, AssetGrant):
            raise TypeError(
                "Expected an AssetGrant instance"
            )

        if not all(
            (
                grant.tenant_id,
                grant.asset_id,
                grant.user_id,
            )
        ):
            raise ValueError(
                "Asset grant fields must be non-empty"
            )

        with self._lock:
            self._grants.add(
                (
                    grant.tenant_id,
                    grant.asset_id,
                    grant.user_id,
                )
            )

    def revoke(
        self,
        grant: AssetGrant,
    ) -> None:
        """
        Remove an existing asset access grant.

        Revocation is idempotent: removing a nonexistent
        grant does not raise an exception.
        """

        if not isinstance(grant, AssetGrant):
            raise TypeError(
                "Expected an AssetGrant instance"
            )

        with self._lock:
            self._grants.discard(
                (
                    grant.tenant_id,
                    grant.asset_id,
                    grant.user_id,
                )
            )

    def can_read(
        self,
        *,
        context: RequestContext,
        asset_id: str,
    ) -> bool:
        """
        Return True only when the exact tenant, asset,
        and user combination has been granted access.
        """

        key = (
            context.tenant_id,
            asset_id,
            context.user_id,
        )

        with self._lock:
            return key in self._grants


# ============================================================
# Authorized asset service
# ============================================================

class AuthorizedMultimodalAssetService:
    """
    Enforces tenant membership and asset-level access
    before returning or verifying an asset.
    """

    def __init__(
        self,
        *,
        registry: MultimodalAssetRegistry,
        boundary: TenantBoundary,
        access_policy: InMemoryAssetAccessPolicy,
    ):
        self.registry = registry
        self.boundary = boundary
        self.access_policy = access_policy

    def get_asset(
        self,
        *,
        context: RequestContext,
        asset_id: str,
        version: int,
    ) -> MultimodalAsset:

        self.boundary.authorize(
            context=context,
            requested_tenant_id=context.tenant_id,
        )

        if not self.access_policy.can_read(
            context=context,
            asset_id=asset_id,
        ):
            raise TenantAuthorizationError(
                "Asset access denied"
            )

        return self.registry.get(
            tenant_id=context.tenant_id,
            asset_id=asset_id,
            version=version,
        )

    def verify_asset(
        self,
        *,
        context: RequestContext,
        asset_id: str,
        version: int,
        content: bytes,
    ) -> MultimodalAsset:

        self.get_asset(
            context=context,
            asset_id=asset_id,
            version=version,
        )

        return self.registry.verify(
            tenant_id=context.tenant_id,
            asset_id=asset_id,
            version=version,
            content=content,
        )