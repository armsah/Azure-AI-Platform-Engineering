import pytest

from request_context import RequestContext
from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantAuthorizationError,
    TenantBoundary,
    TenantMembership,
)
from tenant_request_service import TenantRequestService
from tenant_resource_access import (
    TenantResource,
    TenantResourceGuard,
)


def make_context(
    tenant_id="customer-a",
    user_id="user-1",
    directory_tenant_id="entra-directory",
):
    return RequestContext(
        directory_tenant_id=directory_tenant_id,
        tenant_id=tenant_id,
        user_id=user_id,
        groups=(),
        roles=("AI.User",),
    )


def make_boundary():
    return TenantBoundary(
        InMemoryTenantMembershipStore(
            (
                TenantMembership(
                    directory_tenant_id="entra-directory",
                    user_id="user-1",
                    business_tenant_id="customer-a",
                ),
            )
        )
    )


def test_valid_membership_authorized():
    context = make_context()

    result = make_boundary().authorize(
        context=context,
        requested_tenant_id="customer-a",
    )

    assert result is context


def test_requested_tenant_override_rejected():
    with pytest.raises(TenantAuthorizationError):
        make_boundary().authorize(
            context=make_context(),
            requested_tenant_id="customer-b",
        )


def test_missing_membership_rejected():
    with pytest.raises(TenantAuthorizationError):
        make_boundary().authorize(
            context=make_context(
                user_id="unknown-user"
            ),
            requested_tenant_id="customer-a",
        )


def test_directory_tenant_is_part_of_membership():
    with pytest.raises(TenantAuthorizationError):
        make_boundary().authorize(
            context=make_context(
                directory_tenant_id="other-directory"
            ),
            requested_tenant_id="customer-a",
        )


def test_empty_requested_tenant_rejected():
    with pytest.raises(TenantAuthorizationError):
        make_boundary().authorize(
            context=make_context(),
            requested_tenant_id="",
        )


def test_same_tenant_resource_allowed():
    TenantResourceGuard.require_access(
        context=make_context(),
        resource=TenantResource(
            resource_id="doc-1",
            tenant_id="customer-a",
            resource_type="document",
        ),
    )


def test_cross_tenant_resource_rejected():
    with pytest.raises(TenantAuthorizationError):
        TenantResourceGuard.require_access(
            context=make_context(),
            resource=TenantResource(
                resource_id="doc-secret",
                tenant_id="customer-b",
                resource_type="document",
            ),
        )


def test_missing_resource_identity_rejected():
    with pytest.raises(TenantAuthorizationError):
        TenantResourceGuard.require_access(
            context=make_context(),
            resource=TenantResource(
                resource_id="",
                tenant_id="customer-a",
                resource_type="document",
            ),
        )


def test_end_to_end_authorized_resource():
    service = TenantRequestService(
        boundary=make_boundary()
    )

    result = service.access_resource(
        context=make_context(),
        requested_tenant_id="customer-a",
        resource=TenantResource(
            resource_id="doc-1",
            tenant_id="customer-a",
            resource_type="document",
        ),
    )

    assert result.tenant_id == "customer-a"
    assert result.resource_id == "doc-1"


def test_end_to_end_cross_tenant_denied():
    service = TenantRequestService(
        boundary=make_boundary()
    )

    with pytest.raises(TenantAuthorizationError):
        service.access_resource(
            context=make_context(),
            requested_tenant_id="customer-a",
            resource=TenantResource(
                resource_id="doc-secret",
                tenant_id="customer-b",
                resource_type="document",
            ),
        )


def test_end_to_end_unverified_membership_denied():
    service = TenantRequestService(
        boundary=make_boundary()
    )

    with pytest.raises(TenantAuthorizationError):
        service.access_resource(
            context=make_context(
                user_id="unknown-user"
            ),
            requested_tenant_id="customer-a",
            resource=TenantResource(
                resource_id="doc-1",
                tenant_id="customer-a",
                resource_type="document",
            ),
        )


def test_membership_is_tenant_specific():
    boundary = make_boundary()

    with pytest.raises(TenantAuthorizationError):
        boundary.authorize(
            context=make_context(
                tenant_id="customer-b"
            ),
            requested_tenant_id="customer-b",
        )