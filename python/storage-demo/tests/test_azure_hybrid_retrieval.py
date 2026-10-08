import pytest

from azure_hybrid_retrieval import AzureHybridRetrievalBackend
from rag_retrieval import RetrievalQuery


class FakeEmbeddings:
    def embed_query(self, text):
        return [0.1, 0.2, 0.3]


class FakeSearchClient:
    def __init__(self, results=None):
        self.results = results or []
        self.last_call = None

    def search(self, **kwargs):
        self.last_call = kwargs
        return self.results


def make_query(tenant_id="customer-a"):
    return RetrievalQuery(
        tenant_id=tenant_id,
        user_id="user-1",
        text="Azure architecture",
        top_k=5,
    )


def make_backend(client):
    return AzureHybridRetrievalBackend(
        search_client=client,
        embedding_provider=FakeEmbeddings(),
        expected_dimensions=3,
    )


def test_hybrid_search_uses_tenant_filter():
    client = FakeSearchClient()
    backend = make_backend(client)

    backend.search(make_query())

    assert client.last_call["filter"] == (
        "tenant_id eq 'customer-a'"
    )
    assert client.last_call["search_text"] == "Azure architecture"
    assert len(client.last_call["vector_queries"]) == 1


def test_odata_tenant_value_is_escaped():
    client = FakeSearchClient()
    backend = make_backend(client)

    backend.search(make_query("customer'o"))

    assert client.last_call["filter"] == (
        "tenant_id eq 'customer''o'"
    )


def test_valid_result_maps_to_retrieved_chunk():
    client = FakeSearchClient([
        {
            "id": "chunk-1",
            "tenant_id": "customer-a",
            "document_id": "doc-1",
            "content": "Azure architecture",
            "@search.score": 2.5,
        }
    ])

    results = make_backend(client).search(make_query())

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-1"
    assert results[0].score == 2.5


def test_cross_tenant_result_rejected():
    client = FakeSearchClient([
        {
            "id": "secret",
            "tenant_id": "customer-b",
            "document_id": "doc-secret",
            "content": "confidential",
        }
    ])

    with pytest.raises(ValueError):
        make_backend(client).search(make_query())


def test_wrong_embedding_dimensions_rejected():
    class WrongEmbeddings:
        def embed_query(self, text):
            return [0.1]

    backend = AzureHybridRetrievalBackend(
        search_client=FakeSearchClient(),
        embedding_provider=WrongEmbeddings(),
        expected_dimensions=3,
    )

    with pytest.raises(ValueError):
        backend.search(make_query())


def test_invalid_top_k_rejected():
    client = FakeSearchClient()
    backend = make_backend(client)

    query = RetrievalQuery(
        tenant_id="customer-a",
        user_id="user-1",
        text="Azure",
        top_k=100,
    )

    with pytest.raises(ValueError):
        backend.search(query)

    assert client.last_call is None