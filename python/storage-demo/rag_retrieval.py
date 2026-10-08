from dataclasses import dataclass
from typing import Protocol

from request_context import RequestContext


class RetrievalError(Exception):
    pass


@dataclass(frozen=True)
class RetrievalQuery:
    tenant_id: str
    user_id: str
    text: str
    top_k: int


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    tenant_id: str
    document_id: str
    content: str
    score: float
    source: str


class RetrievalBackend(Protocol):
    def search(
        self,
        query: RetrievalQuery,
    ) -> list[RetrievedChunk]:
        ...


class TenantSafeRetriever:
    def __init__(
        self,
        backend: RetrievalBackend,
        max_top_k: int = 20,
    ):
        if max_top_k < 1:
            raise ValueError("max_top_k must be positive")

        self.backend = backend
        self.max_top_k = max_top_k

    def retrieve(
        self,
        context: RequestContext,
        question: str,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:

        if not question.strip():
            raise RetrievalError("Question cannot be empty")

        if top_k < 1 or top_k > self.max_top_k:
            raise RetrievalError("Invalid top_k")

        # Tenant identity comes from trusted server context.
        query = RetrievalQuery(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            text=question,
            top_k=top_k,
        )

        results = self.backend.search(query)

        # Defense in depth: reject incorrect backend results.
        if any(
            chunk.tenant_id != context.tenant_id
            for chunk in results
        ):
            raise RetrievalError(
                "Cross-tenant retrieval result detected"
            )

        return results[:top_k]