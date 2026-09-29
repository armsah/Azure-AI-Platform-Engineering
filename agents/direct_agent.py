from agent_service import AgentLimits, AgentResult, run_agent
from tool_service import AI_TOOLS, ToolContext, execute_tool


def run_direct_agent(
    client,
    model: str,
    user_input: str,
    context: ToolContext,
    limits: AgentLimits = AgentLimits(),
) -> AgentResult:
    return run_agent(
        client=client,
        model=model,
        user_input=user_input,
        tools=AI_TOOLS,
        execute_tool=lambda name, arguments: execute_tool(
            name,
            arguments,
            context,
        ),
        limits=limits,
    )