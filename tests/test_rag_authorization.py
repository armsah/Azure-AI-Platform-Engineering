from rag_service import (
    AuthorizationContext,
    build_authorization_filter,
    build_context,
)

from rag_service import build_context


def test_build_context_preserves_source_metadata():
    results = [
        {
            "source": "azure-identity",
            "section": "Authentication",
            "content": "Managed identity avoids application credentials.",
        },
        {
            "source": "azure-rbac",
            "section": "Authorization",
            "content": "RBAC controls permitted Azure operations.",
        },
    ]

    context = build_context(results)

    assert "[1]" in context
    assert "Source: azure-identity" in context
    assert "Section: Authentication" in context

    assert "[2]" in context
    assert "Source: azure-rbac" in context

def test_tenant_filter():
    auth = AuthorizationContext(
        tenant_id="customer-a",
    )

    result = build_authorization_filter(auth)

    assert result == "tenant_id eq 'customer-a'"


def test_authorization_filter_contains_tenant_and_groups():
    auth = AuthorizationContext(
        tenant_id="customer-a",
        groups=("platform-engineering", "developers"),
    )

    result = build_authorization_filter(auth)

    assert "tenant_id eq 'customer-a'" in result
    assert "platform-engineering" in result
    assert "developers" in result

def test_authorization_filter_escapes_odata():
    auth = AuthorizationContext(
        tenant_id="customer'a",
        groups=("dev'ops",),
    )

    result = build_authorization_filter(auth)

    assert "customer''a" in result
    assert "dev''ops" in result


def test_odata_values_are_escaped():
    auth = AuthorizationContext(
        tenant_id="customer'a",
    )

    result = build_authorization_filter(auth)

    assert "customer''a" in result
