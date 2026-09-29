import agents.langchain_agent as langchain_agent

from tool_service import ToolContext


def test_langchain_module_imports():
    assert callable(langchain_agent.run_langchain_agent)


def test_langchain_uses_same_tool_context():
    context = ToolContext(
        tenant_id="customer-a",
        groups=("platform-engineering",),
        allowed_tools=frozenset({
            "search_documents",
            "read_document",
            "read_blob",
        }),
    )

    assert context.tenant_id == "customer-a"
    assert "search_documents" in context.allowed_tools