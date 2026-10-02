from multi_agent import (
    AgentName,
    AgentRequest,
    route_request,
    run_supervisor,
)


def test_routes_aks_to_kubernetes_agent():
    decision = route_request(
        "Why is my AKS pod failing?"
    )

    assert decision.agent == AgentName.KUBERNETES


def test_routes_security_request():
    decision = route_request(
        "Review this RBAC security configuration"
    )

    assert decision.agent == AgentName.SECURITY


def test_routes_cloud_request():
    decision = route_request(
        "Explain Azure VNet architecture"
    )

    assert decision.agent == AgentName.CLOUD


def test_supervisor_uses_selected_agent():
    response = run_supervisor(
        AgentRequest(
            question="Why is my Kubernetes pod pending?",
            tenant_id="customer-a",
            user_id="user-001",
        )
    )

    assert response.agent == AgentName.KUBERNETES
    
def test_knowledge_agent_cannot_use_kubernetes_capability():
    import pytest

    from multi_agent import (
        AgentCapabilityDenied,
        authorize_agent_capability,
    )

    with pytest.raises(AgentCapabilityDenied):
        authorize_agent_capability(
            AgentName.KNOWLEDGE,
            "get_pods",
        )
        
def test_delegation_preserves_original_identity():
    from multi_agent import (
        DelegationRequest,
        delegate,
    )

    original = AgentRequest(
        question="Investigate the issue",
        tenant_id="customer-a",
        user_id="user-001",
    )

    delegation = DelegationRequest(
        from_agent=AgentName.CLOUD,
        to_agent=AgentName.KUBERNETES,
        question="Check Kubernetes pods",
    )

    result = delegate(
        delegation,
        original_request=original,
    )

    assert result.response.agent == AgentName.KUBERNETES