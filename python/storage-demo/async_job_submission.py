import uuid

from async_job_envelope import (
    JobEnvelope,
    JobEnvelopeSigner,
)
from request_context import RequestContext
from tenant_boundary import TenantBoundary


class AsyncJobSubmissionService:
    def __init__(
        self,
        *,
        boundary: TenantBoundary,
        signer: JobEnvelopeSigner,
    ):
        self.boundary = boundary
        self.signer = signer

    def submit(
        self,
        *,
        context: RequestContext,
        requested_tenant_id: str,
        operation: str,
        resource_id: str,
    ) -> JobEnvelope:

        authorized = self.boundary.authorize(
            context=context,
            requested_tenant_id=requested_tenant_id,
        )

        return self.signer.sign(
            job_id=str(uuid.uuid4()),
            directory_tenant_id=(
                authorized.directory_tenant_id
            ),
            tenant_id=authorized.tenant_id,
            user_id=authorized.user_id,
            operation=operation,
            resource_id=resource_id,
        )