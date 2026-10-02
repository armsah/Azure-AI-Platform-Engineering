from dataclasses import dataclass


class MCPToolDenied(Exception):
    pass


@dataclass(frozen=True)
class MCPContext:
    server_name: str
    allowed_tools: frozenset[str]


def authorize_mcp_tool(
    context: MCPContext,
    tool_name: str,
) -> None:
    if tool_name not in context.allowed_tools:
        raise MCPToolDenied(
            f"MCP tool '{tool_name}' is not permitted "
            f"for server '{context.server_name}'."
        )
        
@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str


def visible_authorized_tools(
    discovered_tools: list[MCPTool],
    context: MCPContext,
) -> list[MCPTool]:
    return [
        tool
        for tool in discovered_tools
        if tool.name in context.allowed_tools
    ]