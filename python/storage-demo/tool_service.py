import json
import os

from dataclasses import dataclass
from typing import Callable

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rag_service import ( AuthorizationContext, read_authorized_document, search_authorized_documents,)

ACCOUNT_NAME = os.getenv(
    "AZURE_STORAGE_ACCOUNT_NAME",
    "starmenlearning2026",
)
ACCOUNT_URL = f"https://{ACCOUNT_NAME}.blob.core.windows.net"

CONTAINER_NAME = os.getenv(
    "AZURE_STORAGE_CONTAINER_NAME",
    "documents",
)

AI_TOOLS = [
    {
        "type": "function",
        "name": "search_documents",
        "description": "Search authorized documents relevant to a question.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_document",
        "description": "Read an authorized document by document ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string"},
            },
            "required": ["document_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_blob",
        "description": "Read a blob from the application's storage container.",
        "parameters": {
            "type": "object",
            "properties": {
                "blob_name": {"type": "string"},
            },
            "required": ["blob_name"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

# Custom exceptions
class ToolDenied(Exception):
    pass


class ToolNotFound(Exception):
    pass

# Tool argument models
class SearchDocumentsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)


class ReadDocumentArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, max_length=200)

class ReadBlobArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blob_name: str = Field(min_length=1, max_length=200)

# Tool execution context
@dataclass(frozen=True)
class ToolContext:
    tenant_id: str
    groups: tuple[str, ...]
    allowed_tools: frozenset[str]
    allowed_blob_prefixes: tuple[str, ...] = ()

# Tool definitions
ToolHandler = Callable[[dict, ToolContext], str]

@dataclass(frozen=True)
class ToolDefinition:
    handler: ToolHandler
    arguments_model: type[BaseModel]

# Tool implementations
def search_documents(args: dict, context: ToolContext) -> str:
    auth = AuthorizationContext(
        tenant_id=context.tenant_id,
        groups=context.groups,
    )

    results = search_authorized_documents(
        query=args["query"],
        auth=auth,
        top_k=5,
    )

    documents = [
        {
            "id": result["id"],
            "source": result["source"],
            "section": result.get("section", "unknown"),
            "content": result["content"],
        }
        for result in results
    ]

    return json.dumps({"documents": documents})


def read_document(args: dict, context: ToolContext) -> str:
    auth = AuthorizationContext(
        tenant_id=context.tenant_id,
        groups=context.groups,
    )

    result = read_authorized_document(
        document_id=args["document_id"],
        auth=auth,
    )

    if result is None:
        return json.dumps({"document": None})

    return json.dumps({
        "document": {
            "id": result["id"],
            "source": result["source"],
            "section": result.get("section", "unknown"),
            "content": result["content"],
        }
    })

def read_blob(args: dict, context: ToolContext) -> str:
    blob_name = args["blob_name"]

    if not any(
        blob_name.startswith(prefix)
        for prefix in context.allowed_blob_prefixes
    ):
        raise ToolDenied(
            f"Access to blob '{blob_name}' is not permitted."
        )

    return read_blob_tool(args["blob_name"])

def read_blob_tool(blob_name: str) -> str:
    blob_service_client = get_blob_service_client()

    container_client = blob_service_client.get_container_client(
        CONTAINER_NAME
    )

    blob_client = container_client.get_blob_client(blob_name)

    return blob_client.download_blob().readall().decode("utf-8")

# Executable tool registry
TOOL_REGISTRY = {
    "search_documents": ToolDefinition(
        handler=search_documents,
        arguments_model=SearchDocumentsArguments,
    ),
    "read_document": ToolDefinition(
        handler=read_document,
        arguments_model=ReadDocumentArguments,
    ),
    "read_blob": ToolDefinition(
        handler=read_blob,
        arguments_model=ReadBlobArguments,
    ),
}

# Controlled tool executor
def execute_tool(
    name: str,
    raw_arguments: str,
    context: ToolContext,
) -> str:

    # Authorization check
    if name not in context.allowed_tools:
        raise ToolDenied(
            f"tool '{name}' is not permitted"
        )

    # Registry check
    definition = TOOL_REGISTRY.get(name)

    if definition is None:
        raise ToolNotFound(
            f"tool '{name}' is not registered"
        )

    # Parse and validate model-provided arguments
    try:
        raw = json.loads(raw_arguments)
        validated = definition.arguments_model.model_validate(raw)

    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(
            f"invalid arguments for tool '{name}'"
        ) from exc

    # Execute the controlled application function
    return definition.handler(
        validated.model_dump(),
        context,
    )
