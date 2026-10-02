from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)

SEARCH_ENDPOINT = "https://search-armen-learning-2026.search.windows.net"
INDEX_NAME = "rag-documents"

# Temporary lab authentication.
# We'll replace this with Entra ID/RBAC later.
import os
SEARCH_KEY = os.environ["AZURE_SEARCH_ADMIN_KEY"]

client = SearchIndexClient(
    endpoint=SEARCH_ENDPOINT,
    credential=AzureKeyCredential(SEARCH_KEY),
)

fields = [
    SimpleField(
        name="id",
        type=SearchFieldDataType.String,
        key=True,
    ),
    SearchableField(
        name="content",
        type=SearchFieldDataType.String,
    ),
    SimpleField(
        name="source",
        type=SearchFieldDataType.String,
        filterable=True,
    ),
    SearchField(
        name="contentVector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=1536,
        vector_search_profile_name="rag-vector-profile",
    ),
]

vector_search = VectorSearch(
    algorithms=[
        HnswAlgorithmConfiguration(
            name="rag-hnsw",
        )
    ],
    profiles=[
        VectorSearchProfile(
            name="rag-vector-profile",
            algorithm_configuration_name="rag-hnsw",
        )
    ],
)

index = SearchIndex(
    name=INDEX_NAME,
    fields=fields,
    vector_search=vector_search,
)

client.create_or_update_index(index)

print(f"Created index: {INDEX_NAME}")