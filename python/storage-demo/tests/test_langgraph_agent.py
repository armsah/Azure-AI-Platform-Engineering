from langchain_core.messages import AIMessage

from agents.langgraph_agent import build_langgraph_agent
from tool_service import ToolContext


class FakeBoundLLM:
    def __init__(self, responses):
        self.responses = iter(responses)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return next(self.responses)


def make_context():
    return ToolContext(
        tenant_id="customer-a",
        groups=("platform-engineering",),
        allowed_tools=frozenset({
            "search_documents",
            "read_document",
            "read_blob",
        }),
    )

def test_sensitive_tool_requires_approval():
    llm = FakeBoundLLM([
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "update_document",
                    "args": {
                        "document_id": "doc-1",
                        "content": "modified",
                    },
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        )
    ])

    graph = build_langgraph_agent(
        llm=llm,
        context=make_context(),
    )

    result = graph.invoke({
        "messages": [
            {
                "role": "user",
                "content": "Update doc-1",
            }
        ]
    })

    assert result["approval_required"] is True
    assert (
        result["messages"][-1].content
        == "This operation requires explicit human approval before execution."
    )

def test_safe_tool_executes(monkeypatch):
    executed = []

    def fake_execute_tool(name, raw_arguments, context):
        executed.append(name)
        return "authorized search result"

    monkeypatch.setattr(
        "agents.langgraph_agent.execute_tool",
        fake_execute_tool,
    )

    llm = FakeBoundLLM([
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_documents",
                    "args": {"query": "managed identity"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content="Use managed identity.",
        ),
    ])

    graph = build_langgraph_agent(
        llm=llm,
        context=make_context(),
    )

    result = graph.invoke({
        "messages": [
            {
                "role": "user",
                "content": "How should the application authenticate?",
            }
        ]
    })

    assert executed == ["search_documents"]
    assert result["approval_required"] is False
    assert result["messages"][-1].content == "Use managed identity."
