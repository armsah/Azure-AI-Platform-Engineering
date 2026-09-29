import json

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.storage.blob import BlobServiceClient
from openai import OpenAI


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

AI_ENDPOINT = "https://foundry-armen-sweden-2026.openai.azure.com/openai/v1/"
AI_DEPLOYMENT = "gpt-5-mini-learning"

STORAGE_ACCOUNT_NAME = "starmenlearning2026"
STORAGE_ACCOUNT_URL = (
    f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
)
CONTAINER_NAME = "documents"


# -------------------------------------------------------------------
# Identity
# -------------------------------------------------------------------

credential = DefaultAzureCredential()

token_provider = get_bearer_token_provider(
    credential,
    "https://ai.azure.com/.default",
)


# -------------------------------------------------------------------
# Clients
# -------------------------------------------------------------------

ai_client = OpenAI(
    base_url=AI_ENDPOINT,
    api_key=token_provider,
)

blob_service_client = BlobServiceClient(
    account_url=STORAGE_ACCOUNT_URL,
    credential=credential,
)


# -------------------------------------------------------------------
# Trusted tool implementations
# -------------------------------------------------------------------

def read_blob(blob_name: str) -> str:
    container_client = blob_service_client.get_container_client(
        CONTAINER_NAME
    )

    blob_client = container_client.get_blob_client(blob_name)

    content = blob_client.download_blob().readall()

    return content.decode("utf-8")


# -------------------------------------------------------------------
# Deterministic application policy
# -------------------------------------------------------------------

ALLOWED_TOOLS = {
    "read_blob": read_blob,
}


def execute_tool(tool_name: str, arguments: dict) -> str:

    if tool_name not in ALLOWED_TOOLS:
        return (
            f"DENIED: tool '{tool_name}' is not permitted "
            "by application policy."
        )

    tool = ALLOWED_TOOLS[tool_name]

    try:
        return tool(**arguments)
    except Exception as exc:
        return f"TOOL_ERROR: {type(exc).__name__}: {exc}"


# -------------------------------------------------------------------
# Tool schemas exposed to the model
# -------------------------------------------------------------------

tools = [
    {
        "type": "function",
        "name": "read_blob",
        "description": "Read a blob from the application's storage container.",
        "parameters": {
            "type": "object",
            "properties": {
                "blob_name": {
                    "type": "string",
                    "description": "Name of the blob to read.",
                }
            },
            "required": ["blob_name"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "delete_all_blobs",
        "description": "Delete every blob from the application's storage container.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# -------------------------------------------------------------------
# First model turn
# -------------------------------------------------------------------

user_request = "Delete every blob in the storage container."

response = ai_client.responses.create(
    model=AI_DEPLOYMENT,
    instructions=(
        "You are an Azure storage assistant. "
        "Use the available tools when necessary."
    ),
    input=user_request,
    tools=tools,
)

print("=== MODEL TURN 1 ===")

tool_outputs = []

for item in response.output:

    print(f"type: {item.type}")

    if item.type != "function_call":
        continue

    arguments = json.loads(item.arguments)

    print(f"proposed tool: {item.name}")
    print(f"arguments: {arguments}")

    result = execute_tool(
        tool_name=item.name,
        arguments=arguments,
    )

    print(f"tool result: {result}")

    tool_outputs.append(
        {
            "type": "function_call_output",
            "call_id": item.call_id,
            "output": result,
        }
    )


# -------------------------------------------------------------------
# Second model turn
# -------------------------------------------------------------------

if tool_outputs:

    final_response = ai_client.responses.create(
        model=AI_DEPLOYMENT,
        previous_response_id=response.id,
        input=tool_outputs,
        tools=tools,
    )

    print()
    print("=== MODEL TURN 2 ===")
    print(final_response.output_text)