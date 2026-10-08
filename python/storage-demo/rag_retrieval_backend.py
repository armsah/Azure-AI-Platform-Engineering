from document_search_index import InMemorySearchIndex
from rag_retrieval import (
    RetrievalQuery,
    RetrievedChunk,
)


class InMemoryRetrievalBackend:
    def __init__(
        self,
        index: InMemorySearchIndex,
    ):
        self.index = index

    def search(
        self,
        query: RetrievalQuery,
    ) -> list[RetrievedChunk]:

        # Tenant restriction is applied before ranking.
        documents = self.index.list_for_tenant(
            query.tenant_id
        )

        terms = set(query.text.lower().split())

        ranked = []

        for document in documents:
            words = set(document.content.lower().split())

            score = float(len(terms & words))

            if score <= 0:
                continue

            ranked.append(
                RetrievedChunk(
                    chunk_id=document.chunk_id,
                    tenant_id=document.tenant_id,
                    document_id=document.document_id,
                    content=document.content,
                    score=score,
                    source=f"document:{document.document_id}",
                )
            )

        ranked.sort(
            key=lambda item: (-item.score, item.chunk_id)
        )

        return ranked[:query.top_k]