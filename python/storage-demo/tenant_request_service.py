from dataclasses import dataclass

from request_context import RequestContext
from tenant_boundary import TenantBoundary
from tenant_resource_access import (
    TenantResource,
    TenantResourceGuard,
)


@dataclass(frozen=True)
class AuthorizedResourceResult:
    tenant_id: str
    resource_id: str
    resource_type: str


class TenantRequestService:
    def __init__(
        self,
        *,
        boundary: TenantBoundary,
    ):
        self.boundary = boundary
        self.resource_guard = TenantResourceGuard()

    def access_resource(
        self,
        *,
        context: RequestContext,
        requested_tenant_id: str,
        resource: TenantResource,
    ) -> AuthorizedResourceResult:

        authorized_context = self.boundary.authorize(
            context=context,
            requested_tenant_id=requested_tenant_id,
        )

        self.resource_guard.require_access(
            context=authorized_context,
            resource=resource,
        )

        return AuthorizedResourceResult(
            tenant_id=authorized_context.tenant_id,
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
        )