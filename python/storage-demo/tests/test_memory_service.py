import pytest

from memory_service import (
    MemoryPolicyDenied,
    MemoryRepository,
)


def test_memory_is_scoped_to_tenant_and_user():
    repository = MemoryRepository()

    repository.save(
        "customer-a",
        "user-001",
        "preferred_language",
        "Python",
    )

    repository.save(
        "customer-a",
        "user-002",
        "preferred_language",
        "Java",
    )

    memories = repository.list_for_user(
        "customer-a",
        "user-001",
    )

    assert len(memories) == 1
    assert memories[0].value == "Python"


def test_cross_tenant_memory_is_not_returned():
    repository = MemoryRepository()

    repository.save(
        "customer-a",
        "user-001",
        "project_context",
        "AKS platform",
    )

    memories = repository.list_for_user(
        "customer-b",
        "user-001",
    )

    assert memories == []


def test_security_attributes_cannot_be_stored_as_memory():
    repository = MemoryRepository()

    with pytest.raises(MemoryPolicyDenied):
        repository.save(
            "customer-a",
            "user-001",
            "is_admin",
            "true",
        )