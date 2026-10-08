from dataclasses import dataclass
from typing import Protocol

from rag_retrieval import RetrievalQuery, RetrievedChunk


class QueryEmbeddingProvider(Protocol):
    def embed_query(self, text: str) -> list[float]:
        ...


class AzureSearchClient(Protocol):
    def search(self, **kwargs):
        ...


@dataclass(frozen=True)
class AzureSearchSchema:
    tenant_field: str = "tenant_id"
    document_field: str = "document_id"
    content_field: str = "content"
    vector_field: str = "content_vector"
    source_field: str = "source"


class AzureHybridRetrievalBackend:
    def __init__(
        self,
        *,
        search_client: AzureSearchClient,
        embedding_provider: QueryEmbeddingProvider,
        schema: AzureSearchSchema = AzureSearchSchema(),
        expected_dimensions: int = 1536,
    ):
        if expected_dimensions <= 0:
            raise ValueError("Invalid embedding dimensions")

        self.search_client = search_client
        self.embedding_provider = embedding_provider
        self.schema = schema
        self.expected_dimensions = expected_dimensions

    def search(
        self,
        query: RetrievalQuery,
    ) -> list[RetrievedChunk]:

        if not query.tenant_id or not query.text.strip():
            raise ValueError("Invalid retrieval query")

        if query.top_k < 1 or query.top_k > 20:
            raise ValueError("Invalid top_k")

        vector = self.embedding_provider.embed_query(query.text)

        if len(vector) != self.expected_dimensions:
            raise ValueError("Unexpected embedding dimensions")

        # Escape OData string literals.
        tenant = query.tenant_id.replace("'", "''")

        # Filter is constructed by trusted application code.
        tenant_filter = (
            f"{self.schema.tenant_field} eq '{tenant}'"
        )

        from azure.search.documents.models import VectorizedQuery

        results = self.search_client.search(
            search_text=query.text,
            vector_queries=[
                VectorizedQuery(
                    vector=vector,
                    k_nearest_neighbors=query.top_k,
                    fields=self.schema.vector_field,
                )
            ],
            filter=tenant_filter,
            top=query.top_k,
            select=[
                "id",
                self.schema.tenant_field,
                self.schema.document_field,
                self.schema.content_field,
                self.schema.source_field,
            ],
        )

        retrieved = []

        for item in results:
            if item[self.schema.tenant_field] != query.tenant_id:
                raise ValueError(
                    "Cross-tenant Azure Search result"
                )

            retrieved.append(
                RetrievedChunk(
                    chunk_id=item["id"],
                    tenant_id=item[self.schema.tenant_field],
                    document_id=item[self.schema.document_field],
                    content=item[self.schema.content_field],
                    score=float(
                        item.get("@search.score", 0.0)
                    ),
                    source=item.get(
                        self.schema.source_field,
                        f"document:{item[self.schema.document_field]}",
                    ),
                )
            )

        return retrieved