from dataclasses import replace

import pytest

from chunk_provenance import (
    create_extraction_manifest,
)
from document_provenance import (
    DocumentProvenanceRegistry,
    ProvenanceConflict,
    ProvenanceIntegrityError,
)
from graph_document_access import (
    DocumentGrant,
    InMemoryDocumentAccessPolicy,
)
from graph_provenance_evidence import (
    GraphEvidenceCandidate,
    VerifiedGraphEvidenceService,
)
from graph_relationship_provenance import (
    GraphRelationshipProvenanceRegistry,
    create_relationship_provenance,
)
from graph_relationship_verifier import (
    GraphRelationshipVerifier,
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


SOURCE = b"Payment API depends on Customer Database."
TEXT = SOURCE.decode("utf-8")

EVIDENCE_START = 0
EVIDENCE_END = len(TEXT)


def make_context(
    *,
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


def make_fixture(
    *,
    grant=True,
    revoke_relationship=False,
    revoke_document=False,
    current_version=1,
):
    document_registry = DocumentProvenanceRegistry()

    manifest = document_registry.register(
        tenant_id="customer-a",
        document_id="doc-1",
        version=1,
        content=SOURCE,
    )

    if current_version == 2:
        document_registry.register(
            tenant_id="customer-a",
            document_id="doc-1",
            version=2,
            content=b"Updated document",
        )

    if revoke_document:
        document_registry.revoke(
            tenant_id="customer-a",
            document_id="doc-1",
            version=1,
        )

    extraction = create_extraction_manifest(
        document_manifest=manifest,
        extracted_text=TEXT,
        extraction_version="extractor-v1",
    )

    relationship = create_relationship_provenance(
        extraction=extraction,
        extracted_text=TEXT,
        source_entity_id="payment-api",
        target_entity_id="customer-db",
        relationship_type="depends_on",
        evidence_start_char=EVIDENCE_START,
        evidence_end_char=EVIDENCE_END,
    )

    relationship_registry = (
        GraphRelationshipProvenanceRegistry()
    )

    relationship_registry.register(
        relationship
    )

    if revoke_relationship:
        relationship_registry.revoke(
            tenant_id="customer-a",
            relationship_id=relationship.relationship_id,
        )

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

    provenance_service = AuthorizedProvenanceService(
        registry=document_registry,
        boundary=TenantBoundary(
            InMemoryTenantMembershipStore(
                (
                    TenantMembership(
                        directory_tenant_id=(
                            "entra-directory"
                        ),
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

    verifier = GraphRelationshipVerifier(
        registry=relationship_registry,
        provenance_service=provenance_service,
    )

    return {
        "document_registry": document_registry,
        "relationship_registry": relationship_registry,
        "manifest": manifest,
        "extraction": extraction,
        "relationship": relationship,
        "verifier": verifier,
    }


def verify(
    fixture,
    *,
    context=None,
    relationship=None,
    extraction=None,
    source_bytes=SOURCE,
    extracted_text=TEXT,
    require_current=True,
):
    if context is None:
        context = make_context()

    if relationship is None:
        relationship = fixture["relationship"]

    if extraction is None:
        extraction = fixture["extraction"]

    return fixture["verifier"].verify(
        context=context,
        relationship=relationship,
        extraction=extraction,
        source_bytes=source_bytes,
        extracted_text=extracted_text,
        require_current=require_current,
    )


def test_valid_relationship_verifies():
    result = verify(make_fixture())

    assert result.relationship_type == "depends_on"
    assert result.evidence_text == TEXT


def test_relationship_identity_is_deterministic():
    fixture = make_fixture()

    duplicate = create_relationship_provenance(
        extraction=fixture["extraction"],
        extracted_text=TEXT,
        source_entity_id="payment-api",
        target_entity_id="customer-db",
        relationship_type="depends_on",
        evidence_start_char=0,
        evidence_end_char=len(TEXT),
    )

    assert duplicate == fixture["relationship"]


def test_duplicate_relationship_registration_rejected():
    fixture = make_fixture()

    with pytest.raises(ProvenanceConflict):
        fixture["relationship_registry"].register(
            fixture["relationship"]
        )


def test_modified_relationship_type_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["relationship"],
        relationship_type="owns",
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            relationship=forged,
        )


def test_modified_source_entity_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["relationship"],
        source_entity_id="attacker",
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            relationship=forged,
        )


def test_modified_target_entity_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["relationship"],
        target_entity_id="secret-db",
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            relationship=forged,
        )


def test_modified_relationship_id_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["relationship"],
        relationship_id="forged",
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            relationship=forged,
        )


def test_modified_evidence_digest_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["relationship"],
        evidence_sha256="0" * 64,
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            relationship=forged,
        )


def test_modified_evidence_span_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["relationship"],
        evidence_end_char=7,
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            relationship=forged,
        )


def test_modified_source_bytes_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        verify(
            make_fixture(),
            source_bytes=b"Forged source document",
        )


def test_modified_extracted_text_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        verify(
            make_fixture(),
            extracted_text="Payment API owns Customer Database.",
        )


def test_document_version_mismatch_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["relationship"],
        document_version=2,
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            relationship=forged,
        )


def test_cross_tenant_relationship_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["relationship"],
        tenant_id="customer-b",
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            relationship=forged,
        )


def test_missing_document_grant_rejected():
    with pytest.raises(TenantAuthorizationError):
        verify(
            make_fixture(grant=False)
        )


def test_other_user_rejected():
    with pytest.raises(TenantAuthorizationError):
        verify(
            make_fixture(),
            context=make_context(
                user="mallory"
            ),
        )


def test_revoked_relationship_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        verify(
            make_fixture(
                revoke_relationship=True
            )
        )


def test_revoked_document_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        verify(
            make_fixture(
                revoke_document=True
            )
        )


def test_stale_document_version_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        verify(
            make_fixture(
                current_version=2
            )
        )


def test_historical_verification_is_explicit():
    result = verify(
        make_fixture(
            current_version=2
        ),
        require_current=False,
    )

    assert result.document_version == 1


def test_graph_evidence_adapter_returns_verified_span():
    fixture = make_fixture()

    adapter = VerifiedGraphEvidenceService(
        verifier=fixture["verifier"]
    )

    result = adapter.verify_candidate(
        context=make_context(),
        candidate=GraphEvidenceCandidate(
            relationship=fixture["relationship"],
            extraction=fixture["extraction"],
            source_bytes=SOURCE,
            extracted_text=TEXT,
        ),
    )

    assert result.statement == (
        "payment-api depends_on customer-db"
    )

    assert result.evidence_text == TEXT
    assert result.document_version == 1