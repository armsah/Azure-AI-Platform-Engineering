import os

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import OpenAI
from dataclasses import dataclass
from observability import tracer


SEARCH_ENDPOINT = os.getenv(
    "AZURE_SEARCH_ENDPOINT",
    "https://search-armen-learning-2026.search.windows.net",
)
SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "rag-documents")

FOUNDRY_ENDPOINT = os.getenv(
    "AZURE_AI_ENDPOINT",
    "https://foundry-armen-sweden-2026.openai.azure.com/openai/v1/",
)

EMBEDDING_DEPLOYMENT = os.getenv(
    "AZURE_AI_EMBEDDING_DEPLOYMENT",
    "embedding-learning",
)

CHAT_DEPLOYMENT = os.getenv(
    "AZURE_AI_DEPLOYMENT",
    "gpt-5-mini-learning",
)

@dataclass(frozen=True)
class AuthorizationContext:
    tenant_id: str
    groups: tuple[str, ...] = ()

def escape_odata(value: str) -> str:
    return value.replace("'", "''")

def build_authorization_filter(auth: AuthorizationContext) -> str:
    tenant = escape_odata(auth.tenant_id)

    filters = [f"tenant_id eq '{tenant}'"]

    if auth.groups:
        group_filter = " or ".join(
            f"access_groups/any(g: g eq '{escape_odata(group)}')"
            for group in auth.groups
        )

        filters.append(f"({group_filter})")

    return " and ".join(filters)


def create_openai_client():
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://ai.azure.com/.default",
    )

    return OpenAI(
        base_url=FOUNDRY_ENDPOINT,
        api_key=token_provider,
    )


def create_search_client():
    return SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=SEARCH_INDEX,
        credential=DefaultAzureCredential(),
    )

def retrieve_documents(
    question: str,
    query_vector: list[float],
    top_k: int = 5,
    filter_expression: str | None = None,
):
    search_client = create_search_client()

    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=top_k,
        fields="contentVector",
    )

    with tracer.start_as_current_span("rag.retrieve") as span:
        # Safe metadata only
        span.set_attribute("rag.top_k", top_k)
        span.set_attribute(
            "rag.has_authorization_filter",
            filter_expression is not None,
        )

        results =  list(
            search_client.search(
                search_text=question,
                vector_queries=[vector_query],
                filter=filter_expression,
                top=top_k,
            )
        )

        span.set_attribute("rag.result_count", len(results))

        return results

def search_authorized_documents(
    query: str,
    auth: AuthorizationContext,
    top_k: int = 5,
):
    openai_client = create_openai_client()

    query_vector = openai_client.embeddings.create(
        model=EMBEDDING_DEPLOYMENT,
        input=query,
    ).data[0].embedding

    return retrieve_documents(
        question=query,
        query_vector=query_vector,
        top_k=top_k,
        filter_expression=build_authorization_filter(auth),
    )

def read_authorized_document(
    document_id: str,
    auth: AuthorizationContext,
):
    search_client = create_search_client()

    document_filter = (
        f"id eq '{escape_odata(document_id)}' and "
        f"({build_authorization_filter(auth)})"
    )

    results = list(
        search_client.search(
            search_text="*",
            filter=document_filter,
            top=1,
        )
    )

    if not results:
        return None

    return results[0]

def build_context(results) -> str:
    blocks = []

    for index, result in enumerate(results, start=1):
        source = result["source"]
        section = result.get("section", "unknown")
        content = result["content"]

        blocks.append(
            f"[{index}]\n"
            f"Source: {source}\n"
            f"Section: {section}\n"
            f"Content: {content}"
        )

    return "\n\n".join(blocks)


def answer_question(
    question: str,
    auth: AuthorizationContext,
    top_k: int = 2,
):
    openai_client = create_openai_client()

    results = search_authorized_documents(
        query=question,
        auth=auth,
        top_k=top_k,
    )

    context = build_context(results)

    prompt = f"""
Answer the question using only the supplied context.

Rules:
- Do not use information outside the evidence.
- If the evidence is insufficient, say you don't know.
- Cite supporting evidence using [1], [2], etc.
- Do not invent citations.

Evidence:
{context}

Question:
{question}
"""

    response = openai_client.responses.create(
        model=CHAT_DEPLOYMENT,
        input=prompt,
    )

    return {
        "answer": response.output_text,
        "sources": [result["source"] for result in results],
    }
