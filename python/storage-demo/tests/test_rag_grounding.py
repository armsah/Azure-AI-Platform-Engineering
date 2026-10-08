import json

import pytest

from rag_answer_service import RAGAnswerService
from rag_citation_validation import (
    CitationValidationError,
    validate_grounded_answer,
)
from rag_context_selection import (
    ContextSelectionPolicy,
    SelectedContext,
)
from rag_evidence_pipeline import RAGEvidencePipeline
from rag_grounding import (
    GroundedDraft,
    SYSTEM_INSTRUCTIONS,
    build_evidence_message,
)
from rag_reranking import RankedChunk
from rag_retrieval import (
    RetrievedChunk,
    TenantSafeRetriever,
)
from request_context import RequestContext


def make_context():
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id="customer-a",
        user_id="user-1",
        groups=(),
        roles=("AI.User",),
    )


def make_chunk(
    chunk_id="chunk-1",
    content="Azure Kubernetes Service runs containers.",
):
    return RetrievedChunk(
        chunk_id=chunk_id,
        tenant_id="customer-a",
        document_id="doc-1",
        content=content,
        score=1.0,
        source="document:doc-1",
    )


def make_selected_context():
    return SelectedContext(
        chunks=(
            RankedChunk(
                chunk=make_chunk(),
                relevance_score=1.0,
            ),
        ),
        estimated_tokens=20,
    )


class FakeModel:
    def __init__(self, draft):
        self.draft = draft
        self.calls = 0

    def generate(self, *, system_instructions, user_message):
        self.calls += 1
        return self.draft


def make_service(model, chunks=None):
    class FakeBackend:
        def search(self, query):
            return chunks if chunks is not None else [make_chunk()]

    return RAGAnswerService(
        evidence_pipeline=RAGEvidencePipeline(
            retriever=TenantSafeRetriever(FakeBackend()),
            policy=ContextSelectionPolicy(
                min_relevance_score=0.25,
            ),
        ),
        model=model,
    )


def test_evidence_message_contains_valid_citation_id():
    message = build_evidence_message(
        "What runs containers?",
        make_selected_context(),
    )

    parsed = json.loads(message)

    assert parsed["evidence"][0]["citation_id"] == "chunk-1"


def test_system_instructions_treat_evidence_as_untrusted():
    assert "untrusted" in SYSTEM_INSTRUCTIONS.lower()


def test_valid_citation_is_accepted():
    result = validate_grounded_answer(
        GroundedDraft(
            answer="AKS runs containers.",
            citation_ids=("chunk-1",),
        ),
        make_selected_context(),
    )

    assert result.grounded
    assert result.citations[0].document_id == "doc-1"


def test_fabricated_citation_is_rejected():
    with pytest.raises(CitationValidationError):
        validate_grounded_answer(
            GroundedDraft(
                answer="Fabricated answer.",
                citation_ids=("nonexistent-chunk",),
            ),
            make_selected_context(),
        )


def test_answer_without_citations_is_rejected():
    with pytest.raises(CitationValidationError):
        validate_grounded_answer(
            GroundedDraft(
                answer="Unsupported answer.",
                citation_ids=(),
            ),
            make_selected_context(),
        )


def test_empty_answer_returns_refusal():
    result = validate_grounded_answer(
        GroundedDraft(
            answer="",
            citation_ids=(),
        ),
        make_selected_context(),
    )

    assert not result.grounded
    assert result.citations == ()


def test_service_returns_grounded_answer():
    model = FakeModel(
        GroundedDraft(
            answer="AKS runs containers.",
            citation_ids=("chunk-1",),
        )
    )

    result = make_service(model).answer(
        context=make_context(),
        question="What runs containers?",
    )

    assert result.grounded
    assert result.answer == "AKS runs containers."
    assert len(result.citations) == 1


def test_no_evidence_skips_model_call():
    model = FakeModel(
        GroundedDraft(
            answer="Should not be generated.",
            citation_ids=("chunk-1",),
        )
    )

    service = make_service(
        model,
        chunks=[],
    )

    result = service.answer(
        context=make_context(),
        question="Unknown information?",
    )

    assert not result.grounded
    assert model.calls == 0