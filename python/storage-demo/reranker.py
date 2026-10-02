from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalCandidate:
    id: str
    content: str
    source: str
    section: str = "unknown"
    retrieval_score: float = 0.0


@dataclass(frozen=True)
class RankedCandidate:
    candidate: RetrievalCandidate
    rerank_score: float


class Reranker:
    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        top_k: int = 5,
    ) -> list[RankedCandidate]:
        query_terms = set(query.lower().split())

        ranked = []

        for candidate in candidates:
            content_terms = set(candidate.content.lower().split())

            overlap = len(query_terms & content_terms)

            ranked.append(
                RankedCandidate(
                    candidate=candidate,
                    rerank_score=float(overlap),
                )
            )

        ranked.sort(
            key=lambda item: item.rerank_score,
            reverse=True,
        )

        return ranked[:top_k]