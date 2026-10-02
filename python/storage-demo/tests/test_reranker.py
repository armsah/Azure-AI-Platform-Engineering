from reranker import RetrievalCandidate, Reranker


def test_reranker_places_more_relevant_candidate_first():
    candidates = [
        RetrievalCandidate(
            id="1",
            content="Docker containers package applications",
            source="docker.md",
            retrieval_score=0.90,
        ),
        RetrievalCandidate(
            id="2",
            content="AKS workload identity uses OIDC federation",
            source="aks.md",
            retrieval_score=0.70,
        ),
    ]

    result = Reranker().rerank(
        query="AKS workload identity OIDC",
        candidates=candidates,
        top_k=1,
    )

    assert len(result) == 1
    assert result[0].candidate.id == "2"