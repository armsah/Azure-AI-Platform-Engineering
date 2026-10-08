import re
from dataclasses import dataclass

from rag_retrieval import RetrievedChunk


@dataclass(frozen=True)
class RankedChunk:
    chunk: RetrievedChunk
    relevance_score: float


def tokenize(text: str) -> set[str]:
    return set(
        re.findall(r"\b\w+\b", text.casefold())
    )


def rerank_chunks(
    question: str,
    chunks: list[RetrievedChunk],
) -> list[RankedChunk]:

    query_terms = tokenize(question)

    if not query_terms:
        return []

    ranked = []

    for chunk in chunks:
        content_terms = tokenize(chunk.content)

        overlap = len(query_terms & content_terms)

        # Score is normalized to [0, 1].
        relevance = overlap / len(query_terms)

        ranked.append(
            RankedChunk(
                chunk=chunk,
                relevance_score=relevance,
            )
        )

    return sorted(
        ranked,
        key=lambda item: (
            -item.relevance_score,
            -item.chunk.score,
            item.chunk.chunk_id,
        ),
    )