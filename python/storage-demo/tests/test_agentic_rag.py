from agentic_rag import (
    AgenticRagLimits,
    run_agentic_retrieval,
)
from reranker import RetrievalCandidate, RankedCandidate
from rag_service import AuthorizationContext


def test_agentic_rag_respects_retrieval_budget(monkeypatch):
    calls = []

    def fake_search(query, auth):
        calls.append((query, auth))
        return []

    monkeypatch.setattr(
        "agentic_rag.search_authorized_documents",
        fake_search,
    )

    auth = AuthorizationContext(
        tenant_id="customer-a",
        groups=("platform-engineering",),
    )

    results, state = run_agentic_retrieval(
        question="How does workload identity work?",
        auth=auth,
        limits=AgenticRagLimits(max_retrievals=3),
    )

    assert results == []
    assert state.retrieval_count == 3
    assert len(calls) == 3

    # Critical security invariant:
    assert all(call_auth is auth for _, call_auth in calls)
    
def make_ranked_result(score: float = 3.0):
    return RankedCandidate(
        candidate=RetrievalCandidate(
            id="doc-1",
            content="Workload Identity uses OIDC federation.",
            source="aks.md",
            section="Identity",
            retrieval_score=0.8,
        ),
        rerank_score=score,
    )


def test_sufficient_evidence_stops_after_one_retrieval(monkeypatch):
    calls = []

    def fake_search(query, auth):
        calls.append(query)
        return [make_ranked_result()]

    monkeypatch.setattr(
        "agentic_rag.search_authorized_documents",
        fake_search,
    )
    
    auth = AuthorizationContext(
        tenant_id="customer-a",
        groups=("platform-engineering",),
    )

    results, state = run_agentic_retrieval(
        question="How does workload identity work?",
        auth=auth,
    )

    assert len(results) == 1
    assert state.retrieval_count == 1
    assert len(calls) == 1
    
def test_agentic_rag_reformulates_when_evidence_insufficient(
    monkeypatch,
):
    calls = []

    def fake_search(query, auth):
        calls.append(query)

        if len(calls) == 1:
            return []

        return [make_ranked_result()]

    monkeypatch.setattr(
        "agentic_rag.search_authorized_documents",
        fake_search,
    )
    
    auth = AuthorizationContext(
        tenant_id="customer-a",
        groups=("platform-engineering",),
    )

    results, state = run_agentic_retrieval(
        question="Explain AKS identity",
        auth=auth,
    )

    assert len(results) == 1
    assert state.retrieval_count == 2
    assert len(state.query_history) == 2

    assert state.query_history[0] == "Explain AKS identity"
    assert state.query_history[1] != state.query_history[0]