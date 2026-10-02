import app
import pytest
import tool_service

from tool_service import AI_TOOLS
from fastapi.testclient import TestClient

client = TestClient(app.app)

def test_account_url():
    assert app.ACCOUNT_URL == "https://starmenlearning2026.blob.core.windows.net"


def test_container_name():
    assert app.CONTAINER_NAME == "documents"


def test_blob_name():
    assert app.BLOB_NAME == "hello.txt"

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy"
    }

def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Azure Blob Storage Demo API"
    }

def test_blob_endpoint(monkeypatch):
    class FakeDownloadStream:
        def readall(self):
            return b"Test blob content"

    class FakeBlobClient:
        def download_blob(self):
            return FakeDownloadStream()

    class FakeContainerClient:
        def get_blob_client(self, blob_name):
            assert blob_name == "hello.txt"
            return FakeBlobClient()

    class FakeBlobServiceClient:
        def get_container_client(self, container_name):
            assert container_name == "documents"
            return FakeContainerClient()

    monkeypatch.setattr(
        app,
        "get_blob_service_client",
        lambda: FakeBlobServiceClient()
    )

    response = client.get("/blob")

    assert response.status_code == 200
    assert response.json() == {
        "container": "documents",
        "blob": "hello.txt",
        "content": "Test blob content"
    }

def test_execute_ai_tool_allows_read_blob(monkeypatch):
    monkeypatch.setattr(
        tool_service,
        "read_blob_tool",
        lambda blob_name: "Mock blob content",
    )

    context = tool_service.ToolContext(
        tenant_id="customer-a",
        groups=("platform-engineering",),
        allowed_tools=frozenset({"read_blob"}),
        allowed_blob_prefixes=("customer-a/",),
    )

    result = tool_service.execute_tool(
        "read_blob",
        '{"blob_name":"customer-a/hello.txt"}',
        context,
    )

    assert result == "Mock blob content"

def test_execute_ai_tool_denies_unknown_tool():
    context = tool_service.ToolContext(
        tenant_id="customer-a",
        groups=("platform-engineering",),
        allowed_tools=frozenset({"read_blob"}),
    )

    with pytest.raises(tool_service.ToolDenied):
        tool_service.execute_tool(
            "delete_all_blobs",
            "{}",
            context,
        )

def test_ai_endpoint_tool_call(monkeypatch):
    class FakeUsage:
        input_tokens = 10
        output_tokens = 5
        total_tokens = 15

    class FakeFunctionCall:
        type = "function_call"
        name = "read_blob"
        arguments = '{"blob_name":"customer-a/hello.txt"}'
        call_id = "call-test-123"

    class FakeFirstResponse:
        id = "response-1"
        output = [FakeFunctionCall()]
        usage = FakeUsage()

    class FakeFinalResponse:
        output = []
        output_text = "The file contains: Mock blob content"
        usage = FakeUsage()

    class FakeResponses:
        def __init__(self):
            self.call_count = 0

        def create(self, **kwargs):
            self.call_count += 1

            if self.call_count == 1:
                assert kwargs["model"] == app.AI_DEPLOYMENT
                assert kwargs["input"] == (
                    "Read customer-a/hello.txt and tell me exactly what it contains."
                )
                assert kwargs["tools"] == AI_TOOLS
                return FakeFirstResponse()

            assert kwargs["model"] == app.AI_DEPLOYMENT
            assert kwargs["previous_response_id"] == "response-1"

            tool_outputs = kwargs["input"]

            assert len(tool_outputs) == 1
            assert tool_outputs[0]["type"] == "function_call_output"
            assert tool_outputs[0]["call_id"] == "call-test-123"
            assert tool_outputs[0]["output"] == "Mock blob content"

            return FakeFinalResponse()

    class FakeAIClient:
        def __init__(self):
            self.responses = FakeResponses()

    monkeypatch.setattr(
        app,
        "get_ai_client",
        lambda: FakeAIClient(),
    )

    monkeypatch.setattr(
        tool_service,
        "read_blob_tool",
        lambda blob_name: "Mock blob content",
    )

    response = client.post(
        "/ai/direct",
        json={
            "message": "Read customer-a/hello.txt and tell me exactly what it contains."
        }
    )

    assert response.status_code == 200

    body = response.json()
    print(body)

    assert body["answer"] == "The file contains: Mock blob content"
    assert body["iterations"] == 2
    assert body["tool_calls"] == 1

def test_rag_endpoint(monkeypatch):
    def fake_answer_question(question, auth):
        assert question == "How should an Azure app authenticate?"
        assert auth.tenant_id == "customer-a"
        assert auth.groups == ("platform-engineering",)

        return {
            "answer": "Use managed identity.",
            "sources": ["azure-identity"],
        }

    monkeypatch.setattr(
        app,
        "answer_question",
        fake_answer_question,
    )

    response = client.post(
        "/rag",
        json={"question": "How should an Azure app authenticate?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"]== "Use managed identity."


def test_rag_requires_question():
    response = client.post("/rag", json={})

    assert response.status_code == 422

def test_langchain_endpoint(monkeypatch):
    class FakeMessage:
        content = "Use managed identity."

    monkeypatch.setattr(
        app,
        "run_langchain_agent",
        lambda **kwargs: {
            "messages": [FakeMessage()]
        },
    )

    response = client.post(
        "/ai/langchain",
        json={"message": "How should AKS authenticate?"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["answer"] == "Use managed identity."
    assert body["orchestrator"] == "langchain"

def test_langgraph_endpoint(monkeypatch):
    class FakeMessage:
        content = "Use workload identity."

    monkeypatch.setattr(
        app,
        "run_langgraph_agent",
        lambda **kwargs: {
            "messages": [FakeMessage()]
        },
    )

    response = client.post(
        "/ai/langgraph",
        json={"message": "How should my AKS pod authenticate?"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["answer"] == "Use workload identity."
    assert body["orchestrator"] == "langgraph"
    
def test_conversation_lifecycle(monkeypatch):
    class FakeResult:
        answer = "AKS Workload Identity uses OIDC federation."
        iterations = 1
        tool_calls = 0

    monkeypatch.setattr(
        "app.run_direct_agent",
        lambda *args, **kwargs: FakeResult(),
    )

    create_response = client.post("/conversations")
    assert create_response.status_code == 200

    conversation_id = create_response.json()["conversation_id"]

    message_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "How does AKS Workload Identity work?"},
    )

    assert message_response.status_code == 200

    get_response = client.get(
        f"/conversations/{conversation_id}"
    )

    assert get_response.status_code == 200

    conversation = get_response.json()

    assert len(conversation["messages"]) == 2
    assert conversation["messages"][0]["role"] == "user"
    assert conversation["messages"][1]["role"] == "assistant"
    
def test_unauthorized_conversation_does_not_execute_agent(
    monkeypatch,
):
    called = False

    def fake_agent(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Agent must not execute")

    monkeypatch.setattr(
        "app.run_direct_agent",
        fake_agent,
    )

    # Create conversation owned by the normal test identity.
    response = client.post("/conversations")
    conversation_id = response.json()["conversation_id"]

    from request_context import RequestContext

    monkeypatch.setattr(
        "app.build_request_context",
        lambda: RequestContext(
            tenant_id="customer-b",
            user_id="mallory",
            groups=(),
        ),
    )

    response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Execute something"},
    )

    assert response.status_code == 403
    assert called is False
    
def test_conversation_not_found_returns_404():
    response = client.get(
        "/conversations/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
