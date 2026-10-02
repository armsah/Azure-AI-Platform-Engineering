import pytest
import agent_service

from agent_service import (AgentLimitExceeded, AgentLimits, run_agent,)
from tool_service import ToolContext, ToolDenied, execute_tool


def test_agent_returns_without_tool_call():
    class FakeResponse:
        id = "response-1"
        output = []
        output_text = "Direct answer"

    class FakeResponses:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        responses = FakeResponses()

    executed = []

    result = run_agent(
        client=FakeClient(),
        model="test-model",
        user_input="Hello",
        tools=[],
        execute_tool=lambda name, args: executed.append(name),
        limits=AgentLimits(),
    )

    assert result.answer == "Direct answer"
    assert result.iterations == 1
    assert result.tool_calls == 0
    assert executed == []


def test_agent_executes_multiple_tool_rounds():
    class FakeFunctionCall:
        type = "function_call"

        def __init__(self, name, arguments, call_id):
            self.name = name
            self.arguments = arguments
            self.call_id = call_id

    class FakeResponse:
        def __init__(self, response_id, output, output_text=""):
            self.id = response_id
            self.output = output
            self.output_text = output_text

    responses = [
        FakeResponse(
            "response-1",
            [
                FakeFunctionCall(
                    "search_documents",
                    '{"query":"managed identity"}',
                    "call-1",
                )
            ],
        ),
        FakeResponse(
            "response-2",
            [
                FakeFunctionCall(
                    "read_document",
                    '{"document_id":"doc-123"}',
                    "call-2",
                )
            ],
        ),
        FakeResponse(
            "response-3",
            [],
            "Managed identity provides passwordless authentication.",
        ),
    ]

    class FakeResponses:
        def __init__(self):
            self.index = 0

        def create(self, **kwargs):
            response = responses[self.index]
            self.index += 1
            return response

    class FakeClient:
        def __init__(self):
            self.responses = FakeResponses()

    executed = []

    def fake_execute_tool(name, arguments):
        executed.append(name)

        if name == "search_documents":
            return "doc-123"

        if name == "read_document":
            return "Managed identity provides passwordless authentication."

        raise AssertionError(f"Unexpected tool: {name}")

    result = run_agent(
        client=FakeClient(),
        model="test-model",
        user_input="How should my Azure app authenticate?",
        tools=[],
        execute_tool=fake_execute_tool,
    )

    assert result.answer == (
        "Managed identity provides passwordless authentication."
    )
    assert result.iterations == 3
    assert result.tool_calls == 2

    assert executed == [
        "search_documents",
        "read_document",
    ]

def test_agent_cannot_execute_unauthorized_tool():
    class FakeFunctionCall:
        type = "function_call"
        name = "delete_all_blobs"
        arguments = "{}"
        call_id = "call-dangerous"

    class FakeResponse:
        id = "response-1"
        output = [FakeFunctionCall()]
        output_text = ""

    class FakeResponses:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        responses = FakeResponses()

    context = ToolContext(
        tenant_id="customer-a",
        groups=("platform-engineering",),
        allowed_tools=frozenset({
            "search_documents",
            "read_document",
            "read_blob",
        }),
    )

    with pytest.raises(ToolDenied):
        run_agent(
            client=FakeClient(),
            model="test-model",
            user_input="Delete everything",
            tools=[],
            execute_tool=lambda name, arguments: execute_tool(
                name,
                arguments,
                context,
            ),
        )

def test_agent_stops_infinite_tool_loop():
    class FakeFunctionCall:
        type = "function_call"
        name = "search_documents"
        arguments = '{"query":"keep searching"}'
        call_id = "call-loop"

    class FakeResponse:
        id = "response-loop"
        output = [FakeFunctionCall()]
        output_text = ""

    class FakeResponses:
        def create(self, **kwargs):
            # Model never gives a final answer.
            # It always requests another tool.
            return FakeResponse()

    class FakeClient:
        responses = FakeResponses()

    executed = []

    with pytest.raises(AgentLimitExceeded):
        run_agent(
            client=FakeClient(),
            model="test-model",
            user_input="Search forever",
            tools=[],
            execute_tool=lambda name, arguments: executed.append(name) or "result",
            limits=AgentLimits(
                max_iterations=2,
                max_tool_calls=2,
            ),
        )

def test_agent_stops_when_timeout_exceeded(monkeypatch):
    class FakeFunctionCall:
        type = "function_call"
        name = "search_documents"
        arguments = '{"query":"test"}'
        call_id = "call-1"

    class FakeResponse:
        id = "response-1"
        output = [FakeFunctionCall()]
        output_text = ""

    class FakeResponses:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        responses = FakeResponses()

    # First call = start time.
    # Second call = beginning of first iteration.
    times = iter([100.0, 131.0])

    monkeypatch.setattr(
        agent_service.time,
        "monotonic",
        lambda: next(times),
    )

    with pytest.raises(
        AgentLimitExceeded,
        match="Agent execution timeout exceeded",
    ):
        run_agent(
            client=FakeClient(),
            model="test-model",
            user_input="Test timeout",
            tools=[],
            execute_tool=lambda name, arguments: "result",
            limits=AgentLimits(
                timeout_seconds=30.0,
            ),
        )

def test_agent_stops_when_token_budget_exceeded():
    class FakeUsage:
        total_tokens = 120

    class FakeResponse:
        id = "response-1"
        output = []
        output_text = "This should not be returned."
        usage = FakeUsage()

    class FakeResponses:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        responses = FakeResponses()

    with pytest.raises(
        AgentLimitExceeded,
        match="maximum token budget exceeded",
    ):
        run_agent(
            client=FakeClient(),
            model="test-model",
            user_input="Expensive request",
            tools=[],
            execute_tool=lambda name, arguments: "result",
            limits=AgentLimits(
                max_tokens=100,
            ),
        )

def test_tool_failure_propagates():
    class FakeFunctionCall:
        type = "function_call"
        name = "search_documents"
        arguments = '{"query":"azure"}'
        call_id = "call-1"

    class FakeResponse:
        id = "response-1"
        output = [FakeFunctionCall()]
        output_text = ""

    class FakeResponses:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        responses = FakeResponses()

    def failing_tool(name, arguments):
        raise RuntimeError("Search unavailable")

    with pytest.raises(
        RuntimeError,
        match="Search unavailable",
    ):
        run_agent(
            client=FakeClient(),
            model="test-model",
            user_input="Find Azure documentation",
            tools=[],
            execute_tool=failing_tool,
        )
