from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class Message:
    role: str
    content: str
    created_at: datetime


@dataclass
class Conversation:
    id: str
    tenant_id: str
    user_id: str
    created_at: datetime
    messages: list[Message] = field(default_factory=list)


class ConversationNotFound(Exception):
    pass


class ConversationAccessDenied(Exception):
    pass


class ConversationRepository:
    def __init__(self):
        self._conversations: dict[str, Conversation] = {}

    def create(self, tenant_id: str, user_id: str) -> Conversation:
        conversation = Conversation(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
        )

        self._conversations[conversation.id] = conversation
        return conversation

    def get(
        self,
        conversation_id: str,
        tenant_id: str,
        user_id: str,
    ) -> Conversation:
        conversation = self._conversations.get(conversation_id)

        if conversation is None:
            raise ConversationNotFound(conversation_id)

        if (
            conversation.tenant_id != tenant_id
            or conversation.user_id != user_id
        ):
            raise ConversationAccessDenied(conversation_id)

        return conversation

    def add_message(
        self,
        conversation_id: str,
        tenant_id: str,
        user_id: str,
        role: str,
        content: str,
    ) -> Message:
        conversation = self.get(
            conversation_id,
            tenant_id,
            user_id,
        )

        message = Message(
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
        )

        conversation.messages.append(message)
        return message