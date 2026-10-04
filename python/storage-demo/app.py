import os
import httpx
import logging

from pydantic import BaseModel
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI
from fastapi import FastAPI
from azure.storage.blob import BlobServiceClient
from rag_service import AuthorizationContext, answer_question
from agents.direct_agent import run_direct_agent
from agents.langchain_agent import run_langchain_agent
from agents.langgraph_agent import run_langgraph_agent
from security_context import build_tool_context
from request_context import build_request_context
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from conversation_service import (
    ConversationAccessDenied,
    ConversationNotFound,
    ConversationRepository,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from observability import configure_logging, configure_otel_logging


configure_logging()
configure_otel_logging()
logger = logging.getLogger("storage-demo")

ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "starmenlearning2026")
ACCOUNT_URL = f"https://{ACCOUNT_NAME}.blob.core.windows.net"
CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "documents")
BLOB_NAME = os.getenv("AZURE_STORAGE_BLOB_NAME", "hello.txt")
AI_ENDPOINT = os.getenv(
    "AZURE_AI_ENDPOINT",
    "https://foundry-armen-sweden-2026.openai.azure.com/openai/v1/",
)
AI_DEPLOYMENT = os.getenv(
    "AZURE_AI_DEPLOYMENT",
    "gpt-5-mini-learning",
)

conversation_repository = ConversationRepository()

class RagRequest(BaseModel):
    question: str


class AIRequest(BaseModel):
    message: str
    
class ConversationMessageRequest(BaseModel):
    message: str

app = FastAPI(
    title="Azure Blob Storage Demo",
    version="1.0.0",
)

FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()

def get_authorization_context() -> AuthorizationContext:
    # Learning implementation.
    # Later: derive these values from validated Entra ID token claims.
    return AuthorizationContext(
        tenant_id="customer-a",
        groups=("platform-engineering",),
    )

@app.post("/rag")
def rag(request: RagRequest):
    auth = get_authorization_context()

    return answer_question(
        question=request.question,
        auth=auth,
    )

@app.get("/")
def root():
    return {
        "message": "Azure Blob Storage Demo API"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }

def get_blob_service_client():
    credential = DefaultAzureCredential()

    return BlobServiceClient(
        account_url=ACCOUNT_URL,
        credential=credential
    )

@app.get("/blob")
def get_blob():
    blob_service_client = get_blob_service_client()

    container_client = blob_service_client.get_container_client(
        CONTAINER_NAME
    )

    blob_client = container_client.get_blob_client(
        BLOB_NAME
    )

    download_stream = blob_client.download_blob()
    content = download_stream.readall()

    return {
        "container": CONTAINER_NAME,
        "blob": BLOB_NAME,
        "content": content.decode("utf-8")
    }

def get_ai_client():
    credential = DefaultAzureCredential()

    token_provider = get_bearer_token_provider(
        credential,
        "https://ai.azure.com/.default",
    )

    return OpenAI(
        base_url=AI_ENDPOINT,
        api_key=token_provider,
    )

@app.post("/ai/direct")
def ai(request: AIRequest):
    client = get_ai_client()

    tool_context = build_tool_context()

    result = run_direct_agent(
        client=client,
        model=AI_DEPLOYMENT,
        user_input=request.message,
        context=tool_context,
    )

    return {
        "answer": result.answer,
        "iterations": result.iterations,
        "tool_calls": result.tool_calls,
    }

@app.post("/ai/langchain")
def ai_langchain(request: AIRequest):
    tool_context = build_tool_context()

    result = run_langchain_agent(
        model=AI_DEPLOYMENT,
        user_input=request.message,
        context=tool_context,
        base_url=AI_ENDPOINT,
    )

    messages = result["messages"]
    final_message = messages[-1]

    return {
        "answer": final_message.content,
        "orchestrator": "langchain",
    }

@app.post("/ai/langgraph")
def ai_langgraph(request: AIRequest):
    tool_context = build_tool_context()

    result = run_langgraph_agent(
        model=AI_DEPLOYMENT,
        user_input=request.message,
        context=tool_context,
        base_url=AI_ENDPOINT,
    )

    final_message = result["messages"][-1]

    return {
        "answer": final_message.content,
        "orchestrator": "langgraph",
    }
    
@app.post("/conversations")
def create_conversation():
    context = build_request_context()

    conversation = conversation_repository.create(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
    )

    return {
        "conversation_id": conversation.id,
        "created_at": conversation.created_at,
    }
    
@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    context = build_request_context()

    conversation = conversation_repository.get(
        conversation_id,
        context.tenant_id,
        context.user_id,
    )

    return conversation

@app.post("/conversations/{conversation_id}/messages")
def send_conversation_message(
    conversation_id: str,
    request: ConversationMessageRequest,
):
    context = build_request_context()

    # Authorization happens before agent execution.
    conversation_repository.get(
        conversation_id,
        context.tenant_id,
        context.user_id,
    )

    conversation_repository.add_message(
        conversation_id,
        context.tenant_id,
        context.user_id,
        role="user",
        content=request.message,
    )

    tool_context = build_tool_context()

    result = run_direct_agent(
        request.message,
        tool_context,
    )

    conversation_repository.add_message(
        conversation_id,
        context.tenant_id,
        context.user_id,
        role="assistant",
        content=result.answer,
    )

    return {
        "conversation_id": conversation_id,
        "answer": result.answer,
        "iterations": result.iterations,
        "tool_calls": result.tool_calls,
    }
    
@app.exception_handler(ConversationNotFound)
async def conversation_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Conversation not found"},
    )


@app.exception_handler(ConversationAccessDenied)
async def conversation_access_denied_handler(request, exc):
    return JSONResponse(
        status_code=403,
        content={"detail": "Conversation access denied"},
    )
    

@app.exception_handler(ConversationAccessDenied)
async def conversation_access_denied_handler(request, exc):
    return JSONResponse(
        status_code=403,
        content={"detail": "Conversation access denied"},
    )  
    
DOTNET_API_URL = os.getenv(
    "DOTNET_API_URL",
    "http://localhost:5001",
)

@app.get("/trace-demo")
async def trace_demo():
    logger.info("Calling dotnet-api")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:5001/trace-demo")
            response.raise_for_status()

        return {
            "service": "storage-demo-python",
            "downstream": response.json(),
        }

    except httpx.HTTPError:
        logger.exception(
            "Downstream request failed",
            extra={"dependency": "dotnet-api"},
        )
        raise
    