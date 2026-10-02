import pytest

from mcp_policy import (
    MCPContext,
    MCPTool,
    MCPToolDenied,
    authorize_mcp_tool,
    visible_authorized_tools,
)


def test_allowed_mcp_tool():
    context = MCPContext(
        server_name="knowledge",
        allowed_tools=frozenset({"read_document"}),
    )

    authorize_mcp_tool(context, "read_document")


def test_mcp_server_cannot_grant_application_authority():
    context = MCPContext(
        server_name="knowledge",
        allowed_tools=frozenset({"read_document"}),
    )

    with pytest.raises(MCPToolDenied):
        authorize_mcp_tool(
            context,
            "grant_admin",
        )


def test_only_authorized_tools_are_visible():
    discovered = [
        MCPTool("read_document", "Read document"),
        MCPTool("delete_document", "Delete document"),
        MCPTool("grant_admin", "Grant administrator"),
    ]

    context = MCPContext(
        server_name="knowledge",
        allowed_tools=frozenset({"read_document"}),
    )

    visible = visible_authorized_tools(
        discovered,
        context,
    )

    assert [tool.name for tool in visible] == [
        "read_document"
    ]