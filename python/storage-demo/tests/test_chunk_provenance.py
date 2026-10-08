from dataclasses import replace

import pytest

from chunk_provenance import (
    create_chunk_provenance,
    create_extraction_manifest,
)
from chunk_provenance_verifier import (
    ChunkProvenanceVerifier,
)
from document_provenance import (
    DocumentProvenanceRegistry,
    ProvenanceIntegrityError,
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
from verified_rag_evidence import (
    CandidateChunk,
    VerifiedRAGEvidenceService,
)


SOURCE = b"API depends on Database."
TEXT = "API depends on Database."


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
    revoked=False,
    current_version=1,
):
    registry = DocumentProvenanceRegistry()

    manifest = registry.register(
        tenant_id="customer-a",
        document_id="doc-1",
        version=1,
        content=SOURCE,
    )

    if current_version == 2:
        registry.register(
            tenant_id="customer-a",
            document_id="doc-1",
            version=2,
            content=b"Updated document",
        )

    if revoked:
        registry.revoke(
            tenant_id="customer-a",
            document_id="doc-1",
            version=1,
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

    service = AuthorizedProvenanceService(
        registry=registry,
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

    extraction = create_extraction_manifest(
        document_manifest=manifest,
        extracted_text=TEXT,
        extraction_version="extractor-v1",
    )

    chunk = create_chunk_provenance(
        extraction=extraction,
        extracted_text=TEXT,
        chunk_index=0,
        start_char=0,
        end_char=3,
    )

    verifier = ChunkProvenanceVerifier(
        provenance_service=service
    )

    return {
        "registry": registry,
        "manifest": manifest,
        "extraction": extraction,
        "chunk": chunk,
        "verifier": verifier,
    }


def verify(
    fixture,
    *,
    context=None,
    source_bytes=SOURCE,
    extracted_text=TEXT,
    extraction=None,
    chunk=None,
    chunk_text="API",
    require_current=True,
):
    if context is None:
        context = make_context()

    if extraction is None:
        extraction = fixture["extraction"]

    if chunk is None:
        chunk = fixture["chunk"]

    return fixture["verifier"].verify(
        context=context,
        source_bytes=source_bytes,
        extracted_text=extracted_text,
        extraction=extraction,
        chunk=chunk,
        chunk_text=chunk_text,
        require_current=require_current,
    )


def test_valid_chunk_verifies():
    result = verify(make_fixture())

    assert result.text == "API"
    assert result.start_char == 0
    assert result.end_char == 3


def test_chunk_has_deterministic_identity():
    fixture = make_fixture()

    second = create_chunk_provenance(
        extraction=fixture["extraction"],
        extracted_text=TEXT,
        chunk_index=0,
        start_char=0,
        end_char=3,
    )

    assert second == fixture["chunk"]


def test_modified_chunk_text_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        verify(
            make_fixture(),
            chunk_text="BAD",
        )


def test_modified_source_bytes_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        verify(
            make_fixture(),
            source_bytes=b"Modified source",
        )


def test_modified_extraction_text_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        verify(
            make_fixture(),
            extracted_text="API changed on Database.",
        )


def test_modified_chunk_digest_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["chunk"],
        chunk_sha256="0" * 64,
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            chunk=forged,
        )


def test_modified_chunk_id_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["chunk"],
        chunk_id="forged",
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            chunk=forged,
        )


def test_modified_start_offset_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["chunk"],
        start_char=1,
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            chunk=forged,
        )


def test_modified_end_offset_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["chunk"],
        end_char=4,
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            chunk=forged,
        )


def test_modified_chunk_index_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["chunk"],
        chunk_index=99,
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            chunk=forged,
        )


def test_extraction_version_mismatch_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["chunk"],
        extraction_version="extractor-v2",
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            chunk=forged,
        )


def test_extraction_digest_mismatch_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["extraction"],
        extracted_text_sha256="0" * 64,
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            extraction=forged,
        )


def test_document_version_mismatch_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["chunk"],
        document_version=2,
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            chunk=forged,
        )


def test_cross_tenant_chunk_rejected():
    fixture = make_fixture()

    forged = replace(
        fixture["chunk"],
        tenant_id="customer-b",
    )

    with pytest.raises(ProvenanceIntegrityError):
        verify(
            fixture,
            chunk=forged,
        )


def test_missing_document_acl_rejected():
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


def test_revoked_source_version_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        verify(
            make_fixture(revoked=True)
        )


def test_stale_source_version_rejected():
    with pytest.raises(ProvenanceIntegrityError):
        verify(
            make_fixture(current_version=2)
        )


def test_historical_verification_is_explicit():
    result = verify(
        make_fixture(current_version=2),
        require_current=False,
    )

    assert result.document_version == 1


def test_verified_rag_adapter_accepts_valid_chunk():
    fixture = make_fixture()

    adapter = VerifiedRAGEvidenceService(
        verifier=fixture["verifier"]
    )

    result = adapter.verify_candidate(
        context=make_context(),
        source_bytes=SOURCE,
        extracted_text=TEXT,
        candidate=CandidateChunk(
            extraction=fixture["extraction"],
            provenance=fixture["chunk"],
            text="API",
        ),
    )

    assert result.text == "API"