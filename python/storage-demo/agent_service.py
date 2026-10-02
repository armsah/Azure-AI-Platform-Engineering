import time

from dataclasses import dataclass, field
from observability import tracer


class AgentLimitExceeded(Exception):
    pass

@dataclass(frozen=True)
class AgentLimits:
    max_iterations: int = 5  # maximum agent loops
    max_tool_calls: int = 8  # maximum tool executions
    timeout_seconds: float = 30.0  # maximum elapsed time
    max_tokens: int = 10_000  # maximum AI tokens used

@dataclass
class AgentState:
    iteration: int = 0
    tool_calls: int = 0
    previous_response_id: str | None = None
    total_tokens: int = 0
    tool_trajectory: list[str] = field(default_factory=list)

@dataclass
class AgentResult:
    answer: str
    iterations: int
    tool_calls: int
    total_tokens: int
    tool_trajectory: list[str]

@dataclass
class ConversationState:
    conversation_id: str
    tenant_id: str
    user_id: str
    messages: list

def run_agent(
    client,
    model: str,
    user_input: str,
    tools: list,
    execute_tool,
    limits: AgentLimits = AgentLimits(),
) -> AgentResult:

    with tracer.start_as_current_span("agent.run") as span:
        # Safe operational metadata
        span.set_attribute("ai.model", model)
        span.set_attribute("ai.max_iterations", limits.max_iterations)
        span.set_attribute("ai.max_tool_calls", limits.max_tool_calls)

        started_at = time.monotonic()
        state = AgentState()

        with tracer.start_as_current_span("model.call") as model_span:
            model_span.set_attribute("ai.model", model)

            response = client.responses.create(
                model=model,
                input=user_input,
                tools=tools,
            )

            add_token_usage(response, state, limits)

            usage = getattr(response, "usage", None)
            if usage is not None:
                model_span.set_attribute(
                    "ai.response_tokens",
                    usage.total_tokens,
                )

        for iteration in range(1, limits.max_iterations + 1):
            state.iteration = iteration

            if time.monotonic() - started_at >= limits.timeout_seconds:
                raise AgentLimitExceeded(
                    "Agent execution timeout exceeded."
                )

            tool_calls = [
                item
                for item in response.output
                if item.type == "function_call"
            ]

            if not tool_calls:
                # Record final operational metrics before returning.
                span.set_attribute("ai.iterations", state.iteration)
                span.set_attribute("ai.tool_calls", state.tool_calls)
                span.set_attribute("ai.total_tokens", state.total_tokens)
                span.set_attribute("ai.outcome", "success")

                return AgentResult(
                    answer=response.output_text,
                    iterations=state.iteration,
                    tool_calls=state.tool_calls,
                    total_tokens=state.total_tokens,
                    tool_trajectory=state.tool_trajectory,
                )

            tool_outputs = []

            for call in tool_calls:
                if state.tool_calls >= limits.max_tool_calls:
                    raise AgentLimitExceeded(
                        "maximum tool-call budget exceeded"
                    )

                with tracer.start_as_current_span("tool.execute") as tool_span:
                    tool_span.set_attribute("tool.name", call.name)

                    result = execute_tool(
                        call.name,
                        call.arguments,
                    )

                state.tool_calls += 1
                state.tool_trajectory.append(call.name)

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": result,
                    }
                )

            state.previous_response_id = response.id

            with tracer.start_as_current_span("model.call") as model_span:
                model_span.set_attribute("ai.model", model)

                response = client.responses.create(
                    model=model,
                    previous_response_id=state.previous_response_id,
                    input=tool_outputs,
                    tools=tools,
                )

                add_token_usage(response, state, limits)

                usage = getattr(response, "usage", None)
                if usage is not None:
                    model_span.set_attribute("ai.response_tokens", usage.total_tokens)

        raise AgentLimitExceeded(
            "maximum agent iterations exceeded"
        )

def add_token_usage(response, state: AgentState, limits: AgentLimits):
    usage = getattr(response, "usage", None)

    if usage is None:
        return

    state.total_tokens += usage.total_tokens

    if state.total_tokens > limits.max_tokens:
        raise AgentLimitExceeded(
            "maximum token budget exceeded"
        )
