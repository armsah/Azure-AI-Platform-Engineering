import math

def ndcg_at_k(
    retrieved_ids: list[str],
    relevance: dict[str, int],
    k: int,
) -> float:
    def dcg(ids: list[str]) -> float:
        score = 0.0

        for rank, item_id in enumerate(ids[:k], start=1):
            rel = relevance.get(item_id, 0)

            score += (2**rel - 1) / math.log2(rank + 1)

        return score

    actual = dcg(retrieved_ids)

    ideal_ids = sorted(
        relevance,
        key=relevance.get,
        reverse=True,
    )

    ideal = dcg(ideal_ids)

    return actual / ideal if ideal else 0.0

def recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    if not relevant_ids:
        return 0.0

    retrieved = set(retrieved_ids[:k])

    return len(retrieved & relevant_ids) / len(relevant_ids)


def precision_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    if k <= 0:
        return 0.0

    retrieved = retrieved_ids[:k]

    relevant_count = sum(
        item in relevant_ids for item in retrieved
    )

    return relevant_count / k


def reciprocal_rank(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> float:
    for rank, item in enumerate(retrieved_ids, start=1):
        if item in relevant_ids:
            return 1.0 / rank

    return 0.0