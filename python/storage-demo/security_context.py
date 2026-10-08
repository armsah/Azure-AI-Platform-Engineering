from request_context import RequestContext
from tool_service import ToolContext


def build_tool_context(context: RequestContext) -> ToolContext:
    allowed_tools: set[str] = set()
    
    # Deterministic application authorization policy.
    if "AI.User" in context.roles:
        allowed_tools.update({
                "search_documents",
                "read_document",
        })

    if "platform-engineering" in context.groups:
        allowed_tools.add("read_blob")
        
    return ToolContext(
        tenant_id=context.tenant_id,
        groups=context.groups,
        allowed_tools=frozenset(allowed_tools),
        allowed_blob_prefixes=(f"{context.tenant_id}/",),
    )
