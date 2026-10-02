import pytest

from conversation_service import (
    ConversationAccessDenied,
    ConversationRepository,
)


def test_cross_tenant_conversation_access_denied():
    repository = ConversationRepository()

    conversation = repository.create(
        tenant_id="customer-a",
        user_id="alice",
    )

    with pytest.raises(ConversationAccessDenied):
        repository.get(
            conversation.id,
            tenant_id="customer-b",
            user_id="bob",
        )
        
def test_create_conversation():
    repository = ConversationRepository()

    conversation = repository.create(
        tenant_id="customer-a",
        user_id="alice",
    )

    assert conversation.id
    assert conversation.tenant_id == "customer-a"
    assert conversation.user_id == "alice"
    assert conversation.messages == []
    
def test_owner_can_retrieve_conversation():
    repository = ConversationRepository()

    created = repository.create(
        tenant_id="customer-a",
        user_id="alice",
    )

    retrieved = repository.get(
        created.id,
        tenant_id="customer-a",
        user_id="alice",
    )

    assert retrieved.id == created.id
    
def test_different_user_conversation_access_denied():
    repository = ConversationRepository()

    conversation = repository.create(
        tenant_id="customer-a",
        user_id="alice",
    )

    with pytest.raises(ConversationAccessDenied):
        repository.get(
            conversation.id,
            tenant_id="customer-a",
            user_id="bob",
        )  