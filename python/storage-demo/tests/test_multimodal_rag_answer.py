import hashlib

import pytest

from multimodal_citation_lineage import (
    EvidenceKind,
    MultimodalCitationError,
    create_multimodal_snapshot,
    validate_multimodal_citations,
)

from multimodal_evidence import (
    DescriptionConflict,
    DescriptionIntegrityError,
    DescriptionNotFound,
    ImageDescriptionRegistry,
)

from multimodal_evidence_gate import (
    MultimodalEvidenceGateError,
    VerifiedMultimodalEvidence,
)

from multimodal_rag_answer import (
    MultimodalDraft,
    MultimodalRAGAnswerService,
    MultimodalRAGError,
)

from multimodal_search_index import (
    SearchModality,
)

from request_context import RequestContext

from tenant_boundary import (
    TenantAuthorizationError,
)


DIGEST = hashlib.sha256(
    b"source"
).hexdigest()


def context():
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id="customer-a",
        user_id="alice",
        groups=(),
        roles=("AI.User",),
    )


def evidence(
    *,
    evidence_id="evidence-1",
    modality=SearchModality.IMAGE,
    tenant="customer-a",
    text="Architecture diagram",
):
    return VerifiedMultimodalEvidence(
        evidence_id=evidence_id,
        modality=modality,
        tenant_id=tenant,
        resource_id="resource-1",
        resource_version=1,
        source_sha256=DIGEST,
        text=text,
    )


class FakeRetrieval:
    def __init__(self, hits):
        self.hits = hits

    def search(
        self,
        *,
        context,
        question,
        top_k,
    ):
        return self.hits[:top_k]


class FakeGate:
    def __init__(
        self,
        *,
        accepted=None,
        rejected=None,
        unexpected=None,
    ):
        self.accepted = accepted or {}
        self.rejected = set(rejected or ())
        self.unexpected = unexpected

    def verify(
        self,
        *,
        context,
        hit,
    ):
        if self.unexpected is not None:
            raise self.unexpected

        if hit in self.rejected:
            raise MultimodalEvidenceGateError(
                "Rejected"
            )

        return self.accepted[hit]


class FakeModel:
    def __init__(
        self,
        *,
        answer="The diagram shows an API.",
        citation_mode="valid",
    ):
        self.answer = answer
        self.citation_mode = citation_mode
        self.calls = 0
        self.received_evidence = None

    def generate(
        self,
        *,
        question,
        evidence,
        citation_ids,
    ):
        self.calls += 1
        self.received_evidence = evidence

        if self.citation_mode == "fabricated":
            citations = ("not-a-real-citation",)

        elif self.citation_mode == "missing":
            citations = ()

        elif self.citation_mode == "duplicate":
            citations = (
                citation_ids[0],
                citation_ids[0],
            )

        else:
            citations = (citation_ids[0],)

        return MultimodalDraft(
            answer=self.answer,
            citation_ids=citations,
        )


def make_service(
    *,
    hits=("hit-1",),
    accepted=None,
    rejected=None,
    model=None,
    unexpected=None,
):
    if accepted is None:
        accepted = {
            "hit-1": evidence()
        }

    if model is None:
        model = FakeModel()

    service = MultimodalRAGAnswerService(
        retrieval=FakeRetrieval(hits),
        evidence_gate=FakeGate(
            accepted=accepted,
            rejected=rejected,
            unexpected=unexpected,
        ),
        model=model,
    )

    return service, model


def test_image_citation_kind():
    snapshot = create_multimodal_snapshot(
        tenant_id="customer-a",
        evidence=(evidence(),),
    )

    assert (
        snapshot.citations[0].kind
        == EvidenceKind.IMAGE
    )


def test_text_citation_kind():
    snapshot = create_multimodal_snapshot(
        tenant_id="customer-a",
        evidence=(
            evidence(
                modality=SearchModality.TEXT
            ),
        ),
    )

    assert (
        snapshot.citations[0].kind
        == EvidenceKind.TEXT
    )


def test_deterministic_snapshot():
    items = (evidence(),)

    first = create_multimodal_snapshot(
        tenant_id="customer-a",
        evidence=items,
    )

    second = create_multimodal_snapshot(
        tenant_id="customer-a",
        evidence=items,
    )

    assert first.snapshot_id == second.snapshot_id


def test_cross_tenant_snapshot_rejected():
    with pytest.raises(MultimodalCitationError):
        create_multimodal_snapshot(
            tenant_id="customer-a",
            evidence=(
                evidence(
                    tenant="customer-b"
                ),
            ),
        )


def test_duplicate_evidence_rejected():
    item = evidence()

    with pytest.raises(MultimodalCitationError):
        create_multimodal_snapshot(
            tenant_id="customer-a",
            evidence=(item, item),
        )


def test_empty_snapshot_rejected():
    with pytest.raises(MultimodalCitationError):
        create_multimodal_snapshot(
            tenant_id="customer-a",
            evidence=(),
        )


def test_valid_citation():
    snapshot = create_multimodal_snapshot(
        tenant_id="customer-a",
        evidence=(evidence(),),
    )

    citation_id = snapshot.citations[0].citation_id

    result = validate_multimodal_citations(
        snapshot,
        (citation_id,),
    )

    assert len(result) == 1


def test_fabricated_citation_rejected():
    snapshot = create_multimodal_snapshot(
        tenant_id="customer-a",
        evidence=(evidence(),),
    )

    with pytest.raises(MultimodalCitationError):
        validate_multimodal_citations(
            snapshot,
            ("fake",),
        )


def test_duplicate_citation_rejected():
    snapshot = create_multimodal_snapshot(
        tenant_id="customer-a",
        evidence=(evidence(),),
    )

    citation_id = snapshot.citations[0].citation_id

    with pytest.raises(MultimodalCitationError):
        validate_multimodal_citations(
            snapshot,
            (citation_id, citation_id),
        )


def test_missing_citation_rejected():
    snapshot = create_multimodal_snapshot(
        tenant_id="customer-a",
        evidence=(evidence(),),
    )

    with pytest.raises(MultimodalCitationError):
        validate_multimodal_citations(
            snapshot,
            (),
        )


def test_valid_answer():
    service, model = make_service()

    result = service.answer(
        context=context(),
        question="What does the diagram show?",
    )

    assert result.abstained is False
    assert model.calls == 1
    assert len(result.citations) == 1


def test_empty_retrieval_abstains():
    service, model = make_service(
        hits=()
    )

    result = service.answer(
        context=context(),
        question="Unknown?",
    )

    assert result.abstained is True
    assert model.calls == 0


def test_all_rejected_abstains():
    service, model = make_service(
        rejected={"hit-1"}
    )

    result = service.answer(
        context=context(),
        question="Unknown?",
    )

    assert result.abstained is True
    assert model.calls == 0


def test_mixed_valid_invalid_evidence():
    service, model = make_service(
        hits=("hit-1", "hit-2"),
        accepted={
            "hit-1": evidence(),
        },
        rejected={"hit-2"},
    )

    result = service.answer(
        context=context(),
        question="Explain the diagram",
    )

    assert result.abstained is False
    assert len(model.received_evidence) == 1


def test_rejected_evidence_not_sent_to_model():
    service, model = make_service(
        hits=("hit-1", "hit-2"),
        accepted={
            "hit-1": evidence(),
        },
        rejected={"hit-2"},
    )

    service.answer(
        context=context(),
        question="Explain",
    )

    assert all(
        item.evidence_id != "hit-2"
        for item in model.received_evidence
    )


def test_fabricated_model_citation_rejected():
    model = FakeModel(
        citation_mode="fabricated"
    )

    service, _ = make_service(
        model=model
    )

    with pytest.raises(MultimodalCitationError):
        service.answer(
            context=context(),
            question="Explain",
        )


def test_missing_model_citation_rejected():
    model = FakeModel(
        citation_mode="missing"
    )

    service, _ = make_service(
        model=model
    )

    with pytest.raises(MultimodalCitationError):
        service.answer(
            context=context(),
            question="Explain",
        )


def test_duplicate_model_citation_rejected():
    model = FakeModel(
        citation_mode="duplicate"
    )

    service, _ = make_service(
        model=model
    )

    with pytest.raises(MultimodalCitationError):
        service.answer(
            context=context(),
            question="Explain",
        )


def test_empty_model_answer_rejected():
    model = FakeModel(
        answer=""
    )

    service, _ = make_service(
        model=model
    )

    with pytest.raises(MultimodalRAGError):
        service.answer(
            context=context(),
            question="Explain",
        )


def test_unexpected_programming_error_propagates():
    service, _ = make_service(
        unexpected=RuntimeError(
            "Programming error"
        )
    )

    with pytest.raises(RuntimeError):
        service.answer(
            context=context(),
            question="Explain",
        )


def test_tenant_authorization_error_propagates():
    service, _ = make_service(
        unexpected=TenantAuthorizationError(
            "Tenant denied"
        )
    )

    with pytest.raises(TenantAuthorizationError):
        service.answer(
            context=context(),
            question="Explain",
        )


def test_description_registry_idempotent():
    registry = ImageDescriptionRegistry()

    values = dict(
        tenant_id="customer-a",
        asset_id="image-1",
        asset_version=1,
        source_sha256=DIGEST,
        sanitized_sha256=DIGEST,
        description="An architecture diagram",
        provider="mock",
        model="mock-vision",
    )

    first = registry.register(**values)
    second = registry.register(**values)

    assert first == second


def test_description_conflict_rejected():
    registry = ImageDescriptionRegistry()

    values = dict(
        tenant_id="customer-a",
        asset_id="image-1",
        asset_version=1,
        source_sha256=DIGEST,
        sanitized_sha256=DIGEST,
        description="First description",
        provider="mock",
        model="mock-vision",
    )

    registry.register(**values)

    with pytest.raises(DescriptionConflict):
        registry.register(
            **{
                **values,
                "description": "Changed description",
            }
        )


def test_description_integrity_rejected():
    registry = ImageDescriptionRegistry()

    registry.register(
        tenant_id="customer-a",
        asset_id="image-1",
        asset_version=1,
        source_sha256=DIGEST,
        sanitized_sha256=DIGEST,
        description="Original",
        provider="mock",
        model="mock-vision",
    )

    with pytest.raises(DescriptionIntegrityError):
        registry.verify(
            tenant_id="customer-a",
            asset_id="image-1",
            asset_version=1,
            source_sha256=DIGEST,
            sanitized_sha256=DIGEST,
            description="Tampered",
        )