from dataclasses import dataclass

from request_context import RequestContext
from tenant_boundary import TenantAuthorizationError


@dataclass(frozen=True)
class TenantResource:
    resource_id: str
    tenant_id: str
    resource_type: str


class TenantResourceGuard:
    @staticmethod
    def require_access(
        *,
        context: RequestContext,
        resource: TenantResource,
    ) -> None:

        if not resource.resource_id.strip():
            raise TenantAuthorizationError(
                "Missing resource identity"
            )

        if not resource.tenant_id.strip():
            raise TenantAuthorizationError(
                "Missing resource tenant"
            )

        if resource.tenant_id != context.tenant_id:
            raise TenantAuthorizationError(
                "Cross-tenant resource access denied"
            )