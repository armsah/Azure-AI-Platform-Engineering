from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class Memory:
    id: str
    tenant_id: str
    user_id: str
    key: str
    value: str
    created_at: datetime


class MemoryRepository:
    def __init__(self):
        self._memories: dict[str, Memory] = {}

    def save(
        self,
        tenant_id: str,
        user_id: str,
        key: str,
        value: str,
    ) -> Memory:
        
        validate_memory_key(key)
        
        memory = Memory(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            key=key,
            value=value,
            created_at=datetime.now(timezone.utc),
        )

        self._memories[memory.id] = memory
        return memory

    def list_for_user(
        self,
        tenant_id: str,
        user_id: str,
    ) -> list[Memory]:
        return [
            memory
            for memory in self._memories.values()
            if memory.tenant_id == tenant_id
            and memory.user_id == user_id
        ]
        
ALLOWED_MEMORY_KEYS = frozenset({
    "preferred_language",
    "preferred_output_format",
    "project_context",
})


class MemoryPolicyDenied(Exception):
    pass


def validate_memory_key(key: str) -> None:
    if key not in ALLOWED_MEMORY_KEYS:
        raise MemoryPolicyDenied(
            f"Memory key '{key}' is not permitted."
        )