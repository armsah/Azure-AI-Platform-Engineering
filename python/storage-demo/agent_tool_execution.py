from dataclasses import dataclass
from typing import Callable

from agent_tool_authorization import (
    AgentToolAuthorizer,
    AuthorizedToolCall,
    ToolAuthorizationError,
    ToolProposal,
)
from request_context import RequestContext
from tenant_resource_access import TenantResource


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_name: str
    tenant_id: str
    resource_id: str
    output: str


class AgentToolExecutor:
    def __init__(
        self,
        *,
        authorizer: AgentToolAuthorizer,
        handlers: dict[
            str,
            Callable[[AuthorizedToolCall], str],
        ],
    ):
        self.authorizer = authorizer
        self.handlers = handlers

    def execute(
        self,
        *,
        context: RequestContext,
        proposal: ToolProposal,
        resource: TenantResource,
    ) -> ToolExecutionResult:

        # Authorization must precede handler execution.
        authorized = self.authorizer.authorize(
            context=context,
            proposal=proposal,
            resource=resource,
        )

        handler = self.handlers.get(
            authorized.name
        )

        if handler is None:
            raise ToolAuthorizationError(
                "No trusted handler registered"
            )

        output = handler(authorized)

        if not isinstance(output, str):
            raise ToolAuthorizationError(
                "Tool returned invalid output"
            )

        return ToolExecutionResult(
            tool_name=authorized.name,
            tenant_id=authorized.tenant_id,
            resource_id=authorized.resource_id,
            output=output,
        )