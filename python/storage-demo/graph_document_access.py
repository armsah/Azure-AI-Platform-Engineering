from dataclasses import dataclass
from typing import Protocol

from request_context import RequestContext


class DocumentAccessPolicy(Protocol):
    def can_read(
        self,
        *,
        context: RequestContext,
        document_id: str,
    ) -> bool:
        ...


@dataclass(frozen=True)
class DocumentGrant:
    tenant_id: str
    document_id: str
    user_id: str


class InMemoryDocumentAccessPolicy:
    def __init__(
        self,
        grants: tuple[DocumentGrant, ...] = (),
    ):
        self._grants = frozenset(
            (
                grant.tenant_id,
                grant.document_id,
                grant.user_id,
            )
            for grant in grants
        )

    def can_read(
        self,
        *,
        context: RequestContext,
        document_id: str,
    ) -> bool:
        return (
            context.tenant_id,
            document_id,
            context.user_id,
        ) in self._grants