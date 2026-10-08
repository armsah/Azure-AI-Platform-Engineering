from dataclasses import dataclass
from typing import Protocol

from request_context import RequestContext


class TenantAuthorizationError(Exception):
    pass


class TenantMembershipStore(Protocol):
    def is_member(
        self,
        *,
        directory_tenant_id: str,
        user_id: str,
        business_tenant_id: str,
    ) -> bool:
        ...


@dataclass(frozen=True)
class TenantMembership:
    directory_tenant_id: str
    user_id: str
    business_tenant_id: str


class InMemoryTenantMembershipStore:
    def __init__(
        self,
        memberships: tuple[TenantMembership, ...] = (),
    ):
        self._memberships = frozenset(
            (
                item.directory_tenant_id,
                item.user_id,
                item.business_tenant_id,
            )
            for item in memberships
        )

    def is_member(
        self,
        *,
        directory_tenant_id: str,
        user_id: str,
        business_tenant_id: str,
    ) -> bool:
        return (
            directory_tenant_id,
            user_id,
            business_tenant_id,
        ) in self._memberships


class TenantBoundary:
    def __init__(
        self,
        memberships: TenantMembershipStore,
    ):
        self.memberships = memberships

    def authorize(
        self,
        *,
        context: RequestContext,
        requested_tenant_id: str,
    ) -> RequestContext:

        if not requested_tenant_id.strip():
            raise TenantAuthorizationError(
                "Missing business tenant"
            )

        if not context.directory_tenant_id.strip():
            raise TenantAuthorizationError(
                "Missing directory tenant"
            )

        if not context.user_id.strip():
            raise TenantAuthorizationError(
                "Missing user identity"
            )

        if requested_tenant_id != context.tenant_id:
            raise TenantAuthorizationError(
                "Request tenant does not match "
                "trusted context"
            )

        if not self.memberships.is_member(
            directory_tenant_id=context.directory_tenant_id,
            user_id=context.user_id,
            business_tenant_id=context.tenant_id,
        ):
            raise TenantAuthorizationError(
                "User is not a member of "
                "the requested business tenant"
            )

        return context