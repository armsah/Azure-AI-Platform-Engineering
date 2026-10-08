from dataclasses import dataclass
from typing import Any, Mapping

from graph_document_access import DocumentAccessPolicy
from request_context import RequestContext
from tenant_boundary import (
    TenantAuthorizationError,
    TenantBoundary,
)
from tenant_resource_access import (
    TenantResource,
    TenantResourceGuard,
)


class ToolAuthorizationError(Exception):
    pass


@dataclass(frozen=True)
class ToolProposal:
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    required_roles: frozenset[str]
    resource_type: str
    allowed_arguments: frozenset[str]
    required_arguments: frozenset[str]
    requires_document_acl: bool = False


@dataclass(frozen=True)
class AuthorizedToolCall:
    name: str
    tenant_id: str
    user_id: str
    resource_id: str
    resource_type: str


class AgentToolAuthorizer:
    def __init__(
        self,
        *,
        boundary: TenantBoundary,
        document_access: DocumentAccessPolicy,
        policies: tuple[ToolPolicy, ...],
    ):
        self.boundary = boundary
        self.document_access = document_access

        names = [policy.name for policy in policies]

        if len(names) != len(set(names)):
            raise ValueError("Duplicate tool policies")

        self.policies = {
            policy.name: policy
            for policy in policies
        }

    def authorize(
        self,
        *,
        context: RequestContext,
        proposal: ToolProposal,
        resource: TenantResource,
    ) -> AuthorizedToolCall:

        policy = self.policies.get(proposal.name)

        if policy is None:
            raise ToolAuthorizationError(
                "Tool is not allowed"
            )

        if not isinstance(proposal.arguments, dict):
            raise ToolAuthorizationError(
                "Tool arguments must be a JSON object"
            )

        supplied = frozenset(proposal.arguments)

        if not supplied.issubset(
            policy.allowed_arguments
        ):
            raise ToolAuthorizationError(
                "Unexpected tool arguments"
            )

        if not policy.required_arguments.issubset(
            supplied
        ):
            raise ToolAuthorizationError(
                "Missing required tool arguments"
            )

        resource_id = proposal.arguments.get(
            "resource_id"
        )

        if (
            not isinstance(resource_id, str)
            or not resource_id.strip()
        ):
            raise ToolAuthorizationError(
                "Invalid resource ID"
            )

        if resource_id != resource.resource_id:
            raise ToolAuthorizationError(
                "Resource ID mismatch"
            )

        if resource.resource_type != policy.resource_type:
            raise ToolAuthorizationError(
                "Incorrect resource type"
            )

        if not policy.required_roles.issubset(
            frozenset(context.roles)
        ):
            raise ToolAuthorizationError(
                "Insufficient role permissions"
            )

        # Do not derive tenant identity from model arguments.
        if "tenant_id" in proposal.arguments:
            raise ToolAuthorizationError(
                "Model cannot select tenant"
            )

        try:
            authorized_context = self.boundary.authorize(
                context=context,
                requested_tenant_id=context.tenant_id,
            )

            TenantResourceGuard.require_access(
                context=authorized_context,
                resource=resource,
            )
        except TenantAuthorizationError as exc:
            raise ToolAuthorizationError(
                "Tenant authorization denied"
            ) from exc

        if policy.requires_document_acl:
            if not self.document_access.can_read(
                context=authorized_context,
                document_id=resource.resource_id,
            ):
                raise ToolAuthorizationError(
                    "Document access denied"
                )

        return AuthorizedToolCall(
            name=proposal.name,
            tenant_id=authorized_context.tenant_id,
            user_id=authorized_context.user_id,
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
        )