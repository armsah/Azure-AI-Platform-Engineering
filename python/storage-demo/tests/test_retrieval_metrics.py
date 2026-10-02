from retrieval_metrics import (
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k():
    result = recall_at_k(
        ["a", "b", "c"],
        {"b", "d"},
        k=3,
    )

    assert result == 0.5


def test_precision_at_k():
    result = precision_at_k(
        ["a", "b", "c"],
        {"b"},
        k=3,
    )

    assert result == 1 / 3


def test_reciprocal_rank():
    result = reciprocal_rank(
        ["a", "b", "c"],
        {"b"},
    )

    assert result == 0.5
    
def test_ndcg_prefers_better_ranking():
    relevance = {
        "a": 3,
        "b": 2,
        "c": 0,
    }

    good = ndcg_at_k(
        ["a", "b", "c"],
        relevance,
        k=3,
    )

    bad = ndcg_at_k(
        ["c", "b", "a"],
        relevance,
        k=3,
    )

    assert good == 1.0
    assert good > bad