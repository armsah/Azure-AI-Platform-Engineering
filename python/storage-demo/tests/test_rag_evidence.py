import pytest

from rag_context_selection import (
    ContextSelectionError,
    ContextSelectionPolicy,
    estimate_tokens,
    select_context,
)
from rag_evidence_pipeline import RAGEvidencePipeline
from rag_reranking import (
    RankedChunk,
    rerank_chunks,
)
from rag_retrieval import (
    RetrievedChunk,
    TenantSafeRetriever,
)
from request_context import RequestContext


def make_chunk(
    chunk_id,
    content,
    tenant_id="customer-a",
    score=1.0,
):
    return RetrievedChunk(
        chunk_id=chunk_id,
        tenant_id=tenant_id,
        document_id=f"doc-{chunk_id}",
        content=content,
        score=score,
        source=f"document:{chunk_id}",
    )


def make_context():
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id="customer-a",
        user_id="user-1",
        groups=(),
        roles=("AI.User",),
    )


def test_reranking_prioritizes_query_coverage():
    chunks = [
        make_chunk("a", "Azure platform"),
        make_chunk("b", "Azure Kubernetes platform"),
    ]

    ranked = rerank_chunks(
        "Azure Kubernetes",
        chunks,
    )

    assert ranked[0].chunk.chunk_id == "b"


def test_reranking_is_deterministic():
    chunks = [
        make_chunk("b", "Azure architecture"),
        make_chunk("a", "Azure architecture"),
    ]

    first = rerank_chunks("Azure", chunks)
    second = rerank_chunks("Azure", chunks)

    assert [x.chunk.chunk_id for x in first] == [
        x.chunk.chunk_id for x in second
    ]


def test_low_relevance_is_filtered():
    ranked = rerank_chunks(
        "Azure Kubernetes",
        [
            make_chunk("a", "Unrelated content"),
            make_chunk("b", "Azure Kubernetes platform"),
        ],
    )

    selected = select_context(
        tenant_id="customer-a",
        ranked_chunks=ranked,
        policy=ContextSelectionPolicy(
            min_relevance_score=0.5,
        ),
    )

    assert len(selected.chunks) == 1
    assert selected.chunks[0].chunk.chunk_id == "b"


def test_duplicate_content_is_removed():
    ranked = rerank_chunks(
        "Azure",
        [
            make_chunk("a", "Azure platform"),
            make_chunk("b", "  AZURE   platform  "),
        ],
    )

    selected = select_context(
        tenant_id="customer-a",
        ranked_chunks=ranked,
        policy=ContextSelectionPolicy(),
    )

    assert len(selected.chunks) == 1


def test_context_budget_is_enforced():
    chunks = [
        make_chunk("a", "Azure " * 100),
        make_chunk("b", "Azure " * 100),
    ]

    ranked = rerank_chunks("Azure", chunks)

    selected = select_context(
        tenant_id="customer-a",
        ranked_chunks=ranked,
        policy=ContextSelectionPolicy(
            max_context_tokens=160,
            max_chunks=5,
        ),
    )

    assert selected.estimated_tokens <= 160
    assert len(selected.chunks) == 1


def test_max_chunk_count_is_enforced():
    ranked = rerank_chunks(
        "Azure",
        [
            make_chunk("a", "Azure architecture"),
            make_chunk("b", "Azure networking"),
            make_chunk("c", "Azure security"),
        ],
    )

    selected = select_context(
        tenant_id="customer-a",
        ranked_chunks=ranked,
        policy=ContextSelectionPolicy(
            max_chunks=2,
        ),
    )

    assert len(selected.chunks) == 2


def test_cross_tenant_candidate_is_rejected():
    ranked = [
        RankedChunk(
            chunk=make_chunk(
                "secret",
                "Azure confidential",
                tenant_id="customer-b",
            ),
            relevance_score=1.0,
        )
    ]

    with pytest.raises(ContextSelectionError):
        select_context(
            tenant_id="customer-a",
            ranked_chunks=ranked,
            policy=ContextSelectionPolicy(),
        )


def test_invalid_context_policy_rejected():
    with pytest.raises(ContextSelectionError):
        select_context(
            tenant_id="customer-a",
            ranked_chunks=[],
            policy=ContextSelectionPolicy(
                max_context_tokens=0,
            ),
        )


def test_token_estimate_is_positive():
    assert estimate_tokens("") == 1


def test_evidence_pipeline_end_to_end():
    class FakeBackend:
        def search(self, query):
            return [
                make_chunk(
                    "a",
                    "Azure Kubernetes architecture",
                ),
                make_chunk(
                    "b",
                    "Unrelated material",
                ),
            ]

    retriever = TenantSafeRetriever(
        FakeBackend()
    )

    pipeline = RAGEvidencePipeline(
        retriever=retriever,
        policy=ContextSelectionPolicy(
            min_relevance_score=0.5,
        ),
    )

    result = pipeline.retrieve_evidence(
        context=make_context(),
        question="Azure Kubernetes",
    )

    assert result.retrieved_count == 2
    assert len(result.context.chunks) == 1
    assert (
        result.context.chunks[0].chunk.chunk_id
        == "a"
    )