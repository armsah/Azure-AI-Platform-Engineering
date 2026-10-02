import os

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import OpenAI

query = "How can an Azure application authenticate without keeping a password?"

openai_client = OpenAI(
    base_url="https://foundry-armen-sweden-2026.openai.azure.com/openai/v1/",
    api_key=get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://ai.azure.com/.default",
    ),
)

search_client = SearchClient(
    endpoint="https://search-armen-learning-2026.search.windows.net",
    index_name="rag-documents",
    credential=AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"]),
)

# Generate query embedding
query_vector = openai_client.embeddings.create(
    model="embedding-learning",
    input=query,
).data[0].embedding

vector_query = VectorizedQuery(
    vector=query_vector,
    k_nearest_neighbors=3,
    fields="contentVector",
)

print("\nKEYWORD")
results = search_client.search(
    search_text=query,
    top=3,
)

for result in results:
    print(round(result["@search.score"], 4), result["content"])

print("\nVECTOR")
results = search_client.search(
    search_text=None,
    vector_queries=[vector_query],
    top=3,
)

for result in results:
    print(round(result["@search.score"], 4), result["content"])

print("\nHYBRID")
results = search_client.search(
    search_text=query,
    vector_queries=[vector_query],
    top=3,
)

for result in results:
    print(round(result["@search.score"], 4), result["content"])

results = search_client.search(
    search_text=query,
    vector_queries=[vector_query],
    top=2,
)

retrieved = list(results)

context = "\n".join(
    result["content"]
    for result in retrieved
)

prompt = f"""
Answer the question using only the supplied context.
If the context does not contain the answer, say you don't know.

Context:
{context}

Question:
{query}
"""

response = openai_client.responses.create(
    model="gpt-5-mini-learning",
    input=prompt,
)

print("\nRAG ANSWER")
print(response.output_text)

print("\nSOURCES")
for result in retrieved:
    print("-", result["source"])