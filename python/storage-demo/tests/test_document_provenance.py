from dataclasses import replace

import pytest

from document_provenance import (
    DocumentProvenanceRegistry,
    ProvenanceConflict,
    ProvenanceIntegrityError,
    sha256_bytes,
)
from graph_document_access import (
    DocumentGrant,
    InMemoryDocumentAccessPolicy,
)
from provenance_authorization import (
    AuthorizedProvenanceService,
)
from request_context import RequestContext
from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantAuthorizationError,
    TenantBoundary,
    TenantMembership,
)


def context(
    tenant="customer-a",
    user="alice",
):
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id=tenant,
        user_id=user,
        groups=(),
        roles=("AI.User",),
    )


def registry_with_document():
    registry = DocumentProvenanceRegistry()

    registry.register(
        tenant_id="customer-a",
        document_id="doc-1",
        version=1,
        content=b"Version one",
    )

    return registry


def authorized_service(
    *,
    registry=None,
    grant=True,
):
    if registry is None:
        registry = registry_with_document()

    grants = (
        (
            DocumentGrant(
                tenant_id="customer-a",
                document_id="doc-1",
                user_id="alice",
            ),
        )
        if grant
        else ()
    )

    return AuthorizedProvenanceService(
        registry=registry,
        boundary=TenantBoundary(
            InMemoryTenantMembershipStore(
                (
                    TenantMembership(
                        directory_tenant_id="entra-directory",
                        user_id="alice",
                        business_tenant_id="customer-a",
                    ),
                )
            )
        ),
        document_access=InMemoryDocumentAccessPolicy(
            grants
        ),
    )


def test_sha256_is_deterministic():
    assert sha256_bytes(b"hello") == sha256_bytes(
        b"hello"
    )


def test_registration_records_digest_and_size():
    manifest = registry_with_document().get_manifest(
        tenant_id="customer-a",
        document_id="doc-1",
        version=1,
    )

    assert manifest.content_sha256 == sha256_bytes(
        b"Version one"
    )

    assert manifest.size_bytes == len(
        b"Version one"
    )


def test_registered_version_verifies():
    result = registry_with_document().verify(
        tenant_id="customer-a",
        document_id="doc-1",
        version=1,
        content=b"Version one",
    )

    assert result.is_current


def test_modified_content_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        registry_with_document().verify(
            tenant_id="customer-a",
            document_id="doc-1",
            version=1,
            content=b"Version two",
        )


def test_missing_version_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        registry_with_document().verify(
            tenant_id="customer-a",
            document_id="doc-1",
            version=999,
            content=b"Version one",
        )


def test_duplicate_version_rejected():
    registry = registry_with_document()

    with pytest.raises(ProvenanceConflict):
        registry.register(
            tenant_id="customer-a",
            document_id="doc-1",
            version=1,
            content=b"Different content",
        )


def test_versions_must_increase():
    registry = registry_with_document()

    registry.register(
        tenant_id="customer-a",
        document_id="doc-1",
        version=2,
        content=b"Version two",
    )

    with pytest.raises(ProvenanceConflict):
        registry.register(
            tenant_id="customer-a",
            document_id="doc-1",
            version=1,
            content=b"Version one",
        )


def test_stale_version_rejected_by_default():
    registry = registry_with_document()

    registry.register(
        tenant_id="customer-a",
        document_id="doc-1",
        version=2,
        content=b"Version two",
    )

    with pytest.raises(ProvenanceIntegrityError):
        registry.verify(
            tenant_id="customer-a",
            document_id="doc-1",
            version=1,
            content=b"Version one",
        )


def test_historical_version_can_be_verified():
    registry = registry_with_document()

    registry.register(
        tenant_id="customer-a",
        document_id="doc-1",
        version=2,
        content=b"Version two",
    )

    result = registry.verify(
        tenant_id="customer-a",
        document_id="doc-1",
        version=1,
        content=b"Version one",
        require_current=False,
    )

    assert not result.is_current


def test_revoked_version_rejected():
    registry = registry_with_document()

    registry.revoke(
        tenant_id="customer-a",
        document_id="doc-1",
        version=1,
    )

    with pytest.raises(ProvenanceIntegrityError):
        registry.verify(
            tenant_id="customer-a",
            document_id="doc-1",
            version=1,
            content=b"Version one",
        )


def test_tenant_a_cannot_verify_tenant_b_document():
    registry = registry_with_document()

    with pytest.raises(ProvenanceIntegrityError):
        registry.verify(
            tenant_id="customer-b",
            document_id="doc-1",
            version=1,
            content=b"Version one",
        )


def test_authorized_user_can_verify_document():
    service = authorized_service()

    result = service.verify_document(
        context=context(),
        document_id="doc-1",
        version=1,
        content=b"Version one",
    )

    assert result.manifest.document_id == "doc-1"


def test_missing_document_grant_denied():
    service = authorized_service(
        grant=False
    )

    with pytest.raises(TenantAuthorizationError):
        service.verify_document(
            context=context(),
            document_id="doc-1",
            version=1,
            content=b"Version one",
        )


def test_other_user_denied():
    service = authorized_service()

    with pytest.raises(TenantAuthorizationError):
        service.verify_document(
            context=context(user="mallory"),
            document_id="doc-1",
            version=1,
            content=b"Version one",
        )


def test_cross_tenant_context_denied():
    service = authorized_service()

    with pytest.raises(TenantAuthorizationError):
        service.verify_document(
            context=context(tenant="customer-b"),
            document_id="doc-1",
            version=1,
            content=b"Version one",
        )


def test_authorized_manifest_lookup():
    manifest = authorized_service().get_manifest(
        context=context(),
        document_id="doc-1",
        version=1,
    )

    assert manifest.version == 1
    assert manifest.tenant_id == "customer-a"