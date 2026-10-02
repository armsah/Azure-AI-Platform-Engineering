from dataclasses import dataclass
from enum import Enum
from typing import Callable
from observability import traced_operation


class AgentName(str, Enum):
    KNOWLEDGE = "knowledge"
    CLOUD = "cloud"
    KUBERNETES = "kubernetes"
    SECURITY = "security"
    
AGENT_CAPABILITIES: dict[AgentName, frozenset[str]] = {
    AgentName.KNOWLEDGE: frozenset({
        "search_documents",
        "read_document",
    }),
    AgentName.CLOUD: frozenset({
        "read_cloud_resource",
        "get_cloud_health",
    }),
    AgentName.KUBERNETES: frozenset({
        "get_pods",
        "get_events",
        "get_logs",
    }),
    AgentName.SECURITY: frozenset({
        "read_security_findings",
        "analyze_rbac",
    }),
}


@dataclass(frozen=True)
class AgentRequest:
    question: str
    tenant_id: str
    user_id: str


@dataclass(frozen=True)
class AgentResponse:
    agent: AgentName
    answer: str


@dataclass(frozen=True)
class RoutingDecision:
    agent: AgentName
    reason: str
    
@dataclass(frozen=True)
class DelegationRequest:
    from_agent: AgentName
    to_agent: AgentName
    question: str


@dataclass(frozen=True)
class DelegationResult:
    from_agent: AgentName
    response: AgentResponse
    
AgentHandler = Callable[[AgentRequest], AgentResponse]
    
def route_request(question: str) -> RoutingDecision:
    text = question.lower()

    if any(word in text for word in ("kubernetes", "aks", "pod", "helm")):
        return RoutingDecision(
            agent=AgentName.KUBERNETES,
            reason="Kubernetes-related request.",
        )

    if any(word in text for word in ("security", "rbac", "vulnerability")):
        return RoutingDecision(
            agent=AgentName.SECURITY,
            reason="Security-related request.",
        )

    if any(word in text for word in ("azure", "storage", "vnet")):
        return RoutingDecision(
            agent=AgentName.CLOUD,
            reason="Cloud-related request.",
        )

    return RoutingDecision(
        agent=AgentName.KNOWLEDGE,
        reason="General knowledge request.",
    )
    

def knowledge_agent(request: AgentRequest) -> AgentResponse:
    return AgentResponse(
        agent=AgentName.KNOWLEDGE,
        answer=f"Knowledge analysis: {request.question}",
    )


def cloud_agent(request: AgentRequest) -> AgentResponse:
    return AgentResponse(
        agent=AgentName.CLOUD,
        answer=f"Cloud analysis: {request.question}",
    )


def kubernetes_agent(request: AgentRequest) -> AgentResponse:
    return AgentResponse(
        agent=AgentName.KUBERNETES,
        answer=f"Kubernetes analysis: {request.question}",
    )


def security_agent(request: AgentRequest) -> AgentResponse:
    return AgentResponse(
        agent=AgentName.SECURITY,
        answer=f"Security analysis: {request.question}",
    )

AGENT_REGISTRY = {
    AgentName.KNOWLEDGE: knowledge_agent,
    AgentName.CLOUD: cloud_agent,
    AgentName.KUBERNETES: kubernetes_agent,
    AgentName.SECURITY: security_agent,
}

def run_supervisor(request: AgentRequest) -> AgentResponse:
     with traced_operation(
        "supervisor.route",
        **{
            "agent.tenant_id": request.tenant_id,
        },
    ) as span:
        decision = route_request(request.question)

        span.set_attribute(
            "agent.selected",
            decision.agent.value,
        )

        handler = AGENT_REGISTRY[decision.agent]

        return handler(request)

def delegate(
    request: DelegationRequest,
    original_request: AgentRequest,
) -> DelegationResult:

    with traced_operation(
        "agent.delegate",
        **{
            "agent.from": request.from_agent.value,
            "agent.to": request.to_agent.value,
        },
    ):
        handler = AGENT_REGISTRY.get(request.to_agent)

        if handler is None:
            raise ValueError(
                f"Agent '{request.to_agent}' is not registered."
            )

        delegated_request = AgentRequest(
            question=request.question,
            tenant_id=original_request.tenant_id,
            user_id=original_request.user_id,
        )

        response = handler(delegated_request)

        return DelegationResult(
            from_agent=request.from_agent,
            response=response,
        )
    
class AgentCapabilityDenied(Exception):
    pass


def authorize_agent_capability(
    agent: AgentName,
    capability: str,
) -> None:
    allowed = AGENT_CAPABILITIES.get(
        agent,
        frozenset(),
    )

    if capability not in allowed:
        raise AgentCapabilityDenied(
            f"Agent '{agent.value}' cannot use "
            f"capability '{capability}'."
        )