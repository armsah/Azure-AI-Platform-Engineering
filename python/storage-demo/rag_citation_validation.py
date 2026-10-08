from dataclasses import dataclass

from rag_context_selection import SelectedContext
from rag_grounding import GroundedDraft


class CitationValidationError(Exception):
    pass


@dataclass(frozen=True)
class VerifiedCitation:
    citation_id: str
    document_id: str
    source: str


@dataclass(frozen=True)
class VerifiedAnswer:
    answer: str
    citations: tuple[VerifiedCitation, ...]
    grounded: bool


def validate_grounded_answer(
    draft: GroundedDraft,
    context: SelectedContext,
) -> VerifiedAnswer:

    allowed = {
        item.chunk.chunk_id: item.chunk
        for item in context.chunks
    }

    if not draft.answer.strip():
        return VerifiedAnswer(
            answer="Insufficient evidence to answer.",
            citations=(),
            grounded=False,
        )

    if not draft.citation_ids:
        raise CitationValidationError(
            "Answer contains no citations"
        )

    if len(set(draft.citation_ids)) != len(draft.citation_ids):
        raise CitationValidationError(
            "Duplicate citations"
        )

    citations = []

    for citation_id in draft.citation_ids:
        chunk = allowed.get(citation_id)

        if chunk is None:
            raise CitationValidationError(
                "Fabricated or unauthorized citation"
            )

        citations.append(
            VerifiedCitation(
                citation_id=citation_id,
                document_id=chunk.document_id,
                source=chunk.source,
            )
        )

    return VerifiedAnswer(
        answer=draft.answer.strip(),
        citations=tuple(citations),
        grounded=True,
    )