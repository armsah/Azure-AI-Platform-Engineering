import hashlib
import re
from dataclasses import dataclass

from rag_reranking import RankedChunk


class ContextSelectionError(Exception):
    pass


@dataclass(frozen=True)
class ContextSelectionPolicy:
    max_context_tokens: int = 1500
    max_chunks: int = 5
    min_relevance_score: float = 0.25


@dataclass(frozen=True)
class SelectedContext:
    chunks: tuple[RankedChunk, ...]
    estimated_tokens: int


def estimate_tokens(text: str) -> int:
    # Approximation only, not model-tokenizer accounting.
    return max(1, (len(text) + 3) // 4)


def normalize_content(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        text.casefold(),
    ).strip()


def select_context(
    *,
    tenant_id: str,
    ranked_chunks: list[RankedChunk],
    policy: ContextSelectionPolicy,
) -> SelectedContext:

    if not tenant_id:
        raise ContextSelectionError(
            "Tenant is required"
        )

    if policy.max_context_tokens <= 0:
        raise ContextSelectionError(
            "Token budget must be positive"
        )

    if policy.max_chunks <= 0:
        raise ContextSelectionError(
            "Maximum chunk count must be positive"
        )

    if not 0.0 <= policy.min_relevance_score <= 1.0:
        raise ContextSelectionError(
            "Invalid relevance threshold"
        )

    # Validate ALL candidates before selecting any.
    if any(
        item.chunk.tenant_id != tenant_id
        for item in ranked_chunks
    ):
        raise ContextSelectionError(
            "Cross-tenant context candidate detected"
        )

    selected = []
    seen_hashes = set()
    total_tokens = 0

    for item in ranked_chunks:
        if len(selected) >= policy.max_chunks:
            break

        if item.relevance_score < policy.min_relevance_score:
            continue

        normalized = normalize_content(
            item.chunk.content
        )

        if not normalized:
            continue

        content_hash = hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

        if content_hash in seen_hashes:
            continue

        tokens = estimate_tokens(
            item.chunk.content
        )

        if total_tokens + tokens > policy.max_context_tokens:
            continue

        seen_hashes.add(content_hash)
        selected.append(item)
        total_tokens += tokens

    return SelectedContext(
        chunks=tuple(selected),
        estimated_tokens=total_tokens,
    )