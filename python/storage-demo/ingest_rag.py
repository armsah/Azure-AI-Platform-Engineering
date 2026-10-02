import os

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from openai import OpenAI

documents = [
    {
        "id": "1",
        "content": "Managed identities allow Azure resources to authenticate without storing credentials.",
        "source": "azure-identity",
    },
    {
        "id": "2",
        "content": "Azure Blob Storage stores unstructured object data such as files and images.",
        "source": "azure-storage",
    },
    {
        "id": "3",
        "content": "Kubernetes uses pods as the smallest deployable workload unit.",
        "source": "kubernetes",
    },
    {
        "id": "4",
        "content": "Docker images are immutable templates used to create containers.",
        "source": "docker",
    },
    {
        "id": "5",
        "content": "Azure RBAC determines what actions an identity may perform on Azure resources.",
        "source": "azure-rbac",
    },
]

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://ai.azure.com/.default",
)

openai_client = OpenAI(
    base_url="https://foundry-armen-sweden-2026.openai.azure.com/openai/v1/",
    api_key=token_provider,
)

for document in documents:
    response = openai_client.embeddings.create(
        model="embedding-learning",
        input=document["content"],
    )

    document["contentVector"] = response.data[0].embedding

print("Embedding dimensions:", len(documents[0]["contentVector"]))

search_client = SearchClient(
    endpoint="https://search-armen-learning-2026.search.windows.net",
    index_name="rag-documents",
    credential=AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"]),
)

result = search_client.upload_documents(documents)

for item in result:
    print(item.key, item.succeeded)