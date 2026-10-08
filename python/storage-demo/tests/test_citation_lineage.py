from dataclasses import replace

import pytest

from citation_lineage import (
    create_evidence_snapshot,
    validate_snapshot_citations,
)
from evidence_eligibility import (
    EligibleEvidence,
    EvidenceEligibilityError,
)
from provenance_answer_service import (
    ProvenanceAnswerService,
    ProvenanceDraft,
)
from request_context import RequestContext


def evidence(
    *,
    evidence_id="chunk-1",
    tenant="customer-a",
    text="The API depends on the database.",
    version=1,
    kind="chunk",
):
    return EligibleEvidence(
        evidence_id=evidence_id,
        kind=kind,
        tenant_id=tenant,
        document_id="doc-1",
        document_version=version,
        source_sha256="a" * 64,
        text=text,
    )


def context():
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id="customer-a",
        user_id="alice",
        groups=(),
        roles=("AI.User",),
    )


def snapshot():
    return create_evidence_snapshot(
        tenant_id="customer-a",
        evidence=(evidence(),),
    )


def test_snapshot_created():
    result = snapshot()

    assert result.tenant_id == "customer-a"
    assert len(result.citations) == 1


def test_snapshot_id_is_deterministic():
    assert (
        snapshot().snapshot_id
        == snapshot().snapshot_id
    )


def test_citation_id_is_deterministic():
    assert (
        snapshot().citations[0].citation_id
        == snapshot().citations[0].citation_id
    )


def test_empty_snapshot_rejected():
    with pytest.raises(EvidenceEligibilityError):
        create_evidence_snapshot(
            tenant_id="customer-a",
            evidence=(),
        )


def test_cross_tenant_snapshot_rejected():
    with pytest.raises(EvidenceEligibilityError):
        create_evidence_snapshot(
            tenant_id="customer-a",
            evidence=(
                evidence(
                    tenant="customer-b"
                ),
            ),
        )


def test_duplicate_evidence_rejected():
    with pytest.raises(EvidenceEligibilityError):
        create_evidence_snapshot(
            tenant_id="customer-a",
            evidence=(
                evidence(),
                evidence(),
            ),
        )


def test_multiple_distinct_evidence_allowed():
    result = create_evidence_snapshot(
        tenant_id="customer-a",
        evidence=(
            evidence(),
            evidence(
                evidence_id="chunk-2"
            ),
        ),
    )

    assert len(result.citations) == 2


def test_known_citation_accepted():
    result = snapshot()

    citations = validate_snapshot_citations(
        snapshot=result,
        citation_ids=(
            result.citations[0].citation_id,
        ),
    )

    assert len(citations) == 1


def test_unknown_citation_rejected():
    with pytest.raises(EvidenceEligibilityError):
        validate_snapshot_citations(
            snapshot=snapshot(),
            citation_ids=("fabricated",),
        )


def test_missing_citation_rejected():
    with pytest.raises(EvidenceEligibilityError):
        validate_snapshot_citations(
            snapshot=snapshot(),
            citation_ids=(),
        )


def test_duplicate_answer_citation_rejected():
    result = snapshot()
    citation_id = result.citations[0].citation_id

    with pytest.raises(EvidenceEligibilityError):
        validate_snapshot_citations(
            snapshot=result,
            citation_ids=(
                citation_id,
                citation_id,
            ),
        )


def test_text_change_changes_snapshot_id():
    first = snapshot()

    second = create_evidence_snapshot(
        tenant_id="customer-a",
        evidence=(
            evidence(
                text="Modified evidence"
            ),
        ),
    )

    assert first.snapshot_id != second.snapshot_id


def test_version_change_changes_citation_id():
    first = snapshot()

    second = create_evidence_snapshot(
        tenant_id="customer-a",
        evidence=(
            evidence(version=2),
        ),
    )

    assert (
        first.citations[0].citation_id
        != second.citations[0].citation_id
    )


def test_source_digest_change_changes_citation_id():
    first = snapshot()

    second = create_evidence_snapshot(
        tenant_id="customer-a",
        evidence=(
            replace(
                evidence(),
                source_sha256="b" * 64,
            ),
        ),
    )

    assert (
        first.citations[0].citation_id
        != second.citations[0].citation_id
    )


class FakeGate:
    def __init__(self, *, reject=False):
        self.reject = reject
        self.calls = 0

    def verify(self, *, context, candidate):
        self.calls += 1

        if self.reject:
            raise EvidenceEligibilityError(
                "Revoked evidence"
            )

        return evidence()


class FakeModel:
    def __init__(self, *, fabricate=False):
        self.calls = 0
        self.fabricate = fabricate

    def generate(
        self,
        *,
        system_instructions,
        user_message,
    ):
        import json

        self.calls += 1

        payload = json.loads(user_message)

        citation_id = payload["evidence"][0][
            "citation_id"
        ]

        if self.fabricate:
            citation_id = "fabricated"

        return ProvenanceDraft(
            answer="The API depends on the database.",
            citation_ids=(citation_id,),
        )


def test_verified_evidence_reaches_model():
    gate = FakeGate()
    model = FakeModel()

    service = ProvenanceAnswerService(
        eligibility_gate=gate,
        model=model,
    )

    result = service.answer(
        context=context(),
        question="What does the API depend on?",
        candidates=(object(),),
    )

    assert model.calls == 1
    assert len(result.citations) == 1


def test_rejected_evidence_never_reaches_model():
    gate = FakeGate(reject=True)
    model = FakeModel()

    service = ProvenanceAnswerService(
        eligibility_gate=gate,
        model=model,
    )

    with pytest.raises(EvidenceEligibilityError):
        service.answer(
            context=context(),
            question="What does the API depend on?",
            candidates=(object(),),
        )

    assert model.calls == 0


def test_fabricated_model_citation_rejected():
    service = ProvenanceAnswerService(
        eligibility_gate=FakeGate(),
        model=FakeModel(fabricate=True),
    )

    with pytest.raises(EvidenceEligibilityError):
        service.answer(
            context=context(),
            question="What does the API depend on?",
            candidates=(object(),),
        )


def test_empty_question_rejected():
    service = ProvenanceAnswerService(
        eligibility_gate=FakeGate(),
        model=FakeModel(),
    )

    with pytest.raises(EvidenceEligibilityError):
        service.answer(
            context=context(),
            question=" ",
            candidates=(object(),),
        )


def test_snapshot_retains_document_version():
    result = snapshot()

    assert result.citations[0].document_version == 1


def test_snapshot_retains_source_digest():
    result = snapshot()

    assert (
        result.citations[0].source_sha256
        == "a" * 64
    )