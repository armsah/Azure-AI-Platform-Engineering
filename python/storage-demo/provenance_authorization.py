from dataclasses import dataclass

from document_provenance import (
    DocumentProvenanceRegistry,
    DocumentVersionManifest,
    VerifiedDocumentVersion,
)
from graph_document_access import DocumentAccessPolicy
from request_context import RequestContext
from tenant_boundary import (
    TenantAuthorizationError,
    TenantBoundary,
)


@dataclass(frozen=True)
class AuthorizedDocumentVersion:
    tenant_id: str
    document_id: str
    version: int


class AuthorizedProvenanceService:
    def __init__(
        self,
        *,
        registry: DocumentProvenanceRegistry,
        boundary: TenantBoundary,
        document_access: DocumentAccessPolicy,
    ):
        self.registry = registry
        self.boundary = boundary
        self.document_access = document_access

    def _authorize(
        self,
        *,
        context: RequestContext,
        document_id: str,
    ) -> None:

        self.boundary.authorize(
            context=context,
            requested_tenant_id=context.tenant_id,
        )

        if not self.document_access.can_read(
            context=context,
            document_id=document_id,
        ):
            raise TenantAuthorizationError(
                "Document access denied"
            )

    def verify_document(
        self,
        *,
        context: RequestContext,
        document_id: str,
        version: int,
        content: bytes,
        require_current: bool = True,
    ) -> VerifiedDocumentVersion:

        self._authorize(
            context=context,
            document_id=document_id,
        )

        return self.registry.verify(
            tenant_id=context.tenant_id,
            document_id=document_id,
            version=version,
            content=content,
            require_current=require_current,
        )

    def get_manifest(
        self,
        *,
        context: RequestContext,
        document_id: str,
        version: int,
    ) -> DocumentVersionManifest:

        self._authorize(
            context=context,
            document_id=document_id,
        )

        return self.registry.get_manifest(
            tenant_id=context.tenant_id,
            document_id=document_id,
            version=version,
        )