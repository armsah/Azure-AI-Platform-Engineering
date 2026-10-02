from dataclasses import dataclass, field

from rag_service import (
    AuthorizationContext,
    search_authorized_documents,
)

from enum import Enum

class EvidenceAction(str, Enum):
    ANSWER = "answer"
    RETRIEVE_AGAIN = "retrieve_again"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class EvidenceDecision:
    action: EvidenceAction
    reason: str

@dataclass(frozen=True)
class AgenticRagLimits:
    max_retrievals: int = 3


@dataclass
class AgenticRagState:
    original_question: str
    current_query: str
    retrieval_count: int = 0
    query_history: list[str] = field(default_factory=list)
    
def evaluate_evidence(
    results,
    retrieval_count: int,
    max_retrievals: int,
) -> EvidenceDecision:
    if evidence_is_sufficient(results):
        return EvidenceDecision(
            action=EvidenceAction.ANSWER,
            reason="Sufficient relevant evidence found.",
        )

    if retrieval_count >= max_retrievals:
        return EvidenceDecision(
            action=EvidenceAction.ABSTAIN,
            reason="Retrieval budget exhausted.",
        )

    return EvidenceDecision(
        action=EvidenceAction.RETRIEVE_AGAIN,
        reason="Evidence insufficient.",
    )
    
def evidence_is_sufficient(results) -> bool:
    if not results:
        return False

    return any(
        result.rerank_score > 0
        for result in results
    )
    
def reformulate_query(
    original_question: str,
    attempt: int,
) -> str:
    if attempt == 1:
        return f"{original_question} technical documentation"

    return f"{original_question} architecture implementation"

def run_agentic_retrieval(
    question: str,
    auth: AuthorizationContext,
    limits: AgenticRagLimits | None = None,
):
    limits = limits or AgenticRagLimits()

    state = AgenticRagState(
        original_question=question,
        current_query=question,
    )

    results = []

    while state.retrieval_count < limits.max_retrievals:
        state.query_history.append(state.current_query)
        state.retrieval_count += 1

        results = search_authorized_documents(
            query=state.current_query,
            auth=auth,
        )

        decision = evaluate_evidence(
            results,
            retrieval_count=state.retrieval_count,
            max_retrievals=limits.max_retrievals,
        )

        if decision.action == EvidenceAction.ANSWER:
            break

        if decision.action == EvidenceAction.ABSTAIN:
            break


        state.current_query = reformulate_query(
            original_question=question,
            attempt=state.retrieval_count,
        )

    return results, state