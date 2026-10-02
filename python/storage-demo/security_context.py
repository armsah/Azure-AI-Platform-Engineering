from tool_service import ToolContext


def build_tool_context() -> ToolContext:
    # Temporary development identity.
    # Later this comes from validated Entra JWT claims.
    return ToolContext(
        tenant_id="customer-a",
        groups=("platform-engineering",),
        allowed_tools=frozenset({
            "search_documents",
            "read_document",
            "read_blob",
        }),
        allowed_blob_prefixes=("customer-a/",),
    )