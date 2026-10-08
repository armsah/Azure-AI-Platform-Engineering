from dataclasses import dataclass

from rag_context_selection import (
    ContextSelectionPolicy,
    SelectedContext,
    select_context,
)
from rag_reranking import rerank_chunks
from rag_retrieval import TenantSafeRetriever
from request_context import RequestContext


@dataclass(frozen=True)
class EvidenceResult:
    context: SelectedContext
    retrieved_count: int


class RAGEvidencePipeline:
    def __init__(
        self,
        retriever: TenantSafeRetriever,
        policy: ContextSelectionPolicy | None = None,
    ):
        self.retriever = retriever
        self.policy = policy or ContextSelectionPolicy()

    def retrieve_evidence(
        self,
        *,
        context: RequestContext,
        question: str,
        top_k: int = 10,
    ) -> EvidenceResult:

        candidates = self.retriever.retrieve(
            context=context,
            question=question,
            top_k=top_k,
        )

        ranked = rerank_chunks(
            question,
            candidates,
        )

        selected = select_context(
            tenant_id=context.tenant_id,
            ranked_chunks=ranked,
            policy=self.policy,
        )

        return EvidenceResult(
            context=selected,
            retrieved_count=len(candidates),
        )