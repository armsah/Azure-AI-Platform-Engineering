from agent_tool_authorization import ToolPolicy


DEFAULT_TOOL_POLICIES = (
    ToolPolicy(
        name="document.read",
        required_roles=frozenset({"AI.User"}),
        resource_type="document",
        allowed_arguments=frozenset({"resource_id"}),
        required_arguments=frozenset({"resource_id"}),
        requires_document_acl=True,
    ),
    ToolPolicy(
        name="document.reindex",
        required_roles=frozenset({"Document.Admin"}),
        resource_type="document",
        allowed_arguments=frozenset({"resource_id"}),
        required_arguments=frozenset({"resource_id"}),
        requires_document_acl=False,
    ),
    ToolPolicy(
        name="graph.inspect",
        required_roles=frozenset({"AI.User"}),
        resource_type="knowledge_graph",
        allowed_arguments=frozenset({"resource_id"}),
        required_arguments=frozenset({"resource_id"}),
        requires_document_acl=False,
    ),
)