import pytest

from document_search_index import (
    InMemorySearchIndex,
    SearchDocument,
)
from rag_retrieval import (
    RetrievalError,
    RetrievedChunk,
    TenantSafeRetriever,
)
from rag_retrieval_backend import InMemoryRetrievalBackend
from request_context import RequestContext


def make_context(tenant_id):
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id=tenant_id,
        user_id="user-1",
        groups=(),
        roles=("AI.User",),
    )


def make_document(
    tenant_id,
    chunk_id,
    content,
):
    return SearchDocument(
        chunk_id=chunk_id,
        tenant_id=tenant_id,
        document_id=f"doc-{chunk_id}",
        content_hash="hash",
        chunk_index=0,
        content=content,
        vector=(0.1, 0.2, 0.3),
    )


def test_retrieval_is_tenant_scoped():
    index = InMemorySearchIndex()

    index.upsert([
        make_document(
            "customer-a",
            "a-1",
            "Azure platform architecture",
        ),
        make_document(
            "customer-b",
            "b-1",
            "Azure confidential architecture",
        ),
    ])

    retriever = TenantSafeRetriever(
        InMemoryRetrievalBackend(index)
    )

    results = retriever.retrieve(
        make_context("customer-a"),
        "Azure architecture",
    )

    assert len(results) == 1
    assert results[0].tenant_id == "customer-a"
    assert results[0].chunk_id == "a-1"


def test_cross_tenant_backend_result_rejected():
    class MaliciousBackend:
        def search(self, query):
            return [
                RetrievedChunk(
                    chunk_id="secret",
                    tenant_id="customer-b",
                    document_id="private-doc",
                    content="secret information",
                    score=1.0,
                    source="private",
                )
            ]

    retriever = TenantSafeRetriever(
        MaliciousBackend()
    )

    with pytest.raises(RetrievalError):
        retriever.retrieve(
            make_context("customer-a"),
            "secret",
        )


def test_empty_question_rejected():
    retriever = TenantSafeRetriever(
        InMemoryRetrievalBackend(
            InMemorySearchIndex()
        )
    )

    with pytest.raises(RetrievalError):
        retriever.retrieve(
            make_context("customer-a"),
            " ",
        )


def test_invalid_top_k_rejected():
    retriever = TenantSafeRetriever(
        InMemoryRetrievalBackend(
            InMemorySearchIndex()
        )
    )

    with pytest.raises(RetrievalError):
        retriever.retrieve(
            make_context("customer-a"),
            "Azure",
            top_k=100,
        )


def test_retrieval_orders_by_relevance():
    index = InMemorySearchIndex()

    index.upsert([
        make_document(
            "customer-a",
            "a-1",
            "Azure architecture",
        ),
        make_document(
            "customer-a",
            "a-2",
            "Azure Kubernetes architecture",
        ),
    ])

    retriever = TenantSafeRetriever(
        InMemoryRetrievalBackend(index)
    )

    results = retriever.retrieve(
        make_context("customer-a"),
        "Azure Kubernetes",
    )

    assert results[0].chunk_id == "a-2"


def test_tenant_is_not_taken_from_question():
    index = InMemorySearchIndex()

    index.upsert([
        make_document(
            "customer-a",
            "a-1",
            "Azure platform",
        ),
        make_document(
            "customer-b",
            "b-1",
            "Azure platform confidential",
        ),
    ])

    retriever = TenantSafeRetriever(
        InMemoryRetrievalBackend(index)
    )

    results = retriever.retrieve(
        make_context("customer-a"),
        "customer-b Azure platform",
    )

    assert all(
        result.tenant_id == "customer-a"
        for result in results
    )