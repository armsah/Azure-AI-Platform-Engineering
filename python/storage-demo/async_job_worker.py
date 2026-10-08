import threading
from dataclasses import dataclass
from typing import Callable

from async_job_envelope import (
    JobEnvelope,
    JobEnvelopeSigner,
    JobSecurityError,
)
from request_context import RequestContext
from tenant_boundary import (
    TenantAuthorizationError,
    TenantBoundary,
)


@dataclass(frozen=True)
class JobExecutionResult:
    job_id: str
    tenant_id: str
    status: str


class InMemoryJobLedger:
    def __init__(self):
        self._lock = threading.Lock()
        self._completed: set[tuple[str, str]] = set()
        self._in_progress: set[tuple[str, str]] = set()

    def claim(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> bool:
        key = (tenant_id, job_id)

        with self._lock:
            if (
                key in self._completed
                or key in self._in_progress
            ):
                return False

            self._in_progress.add(key)
            return True

    def complete(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> None:
        key = (tenant_id, job_id)

        with self._lock:
            self._in_progress.discard(key)
            self._completed.add(key)

    def release(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> None:
        key = (tenant_id, job_id)

        with self._lock:
            self._in_progress.discard(key)


class AsyncJobWorker:
    def __init__(
        self,
        *,
        signer: JobEnvelopeSigner,
        boundary: TenantBoundary,
        ledger: InMemoryJobLedger,
        handlers: dict[
            str,
            Callable[[RequestContext, str], None],
        ],
    ):
        self.signer = signer
        self.boundary = boundary
        self.ledger = ledger
        self.handlers = handlers

    def execute(
        self,
        envelope: JobEnvelope,
    ) -> JobExecutionResult:

        self.signer.verify(envelope)

        context = RequestContext(
            directory_tenant_id=(
                envelope.directory_tenant_id
            ),
            tenant_id=envelope.tenant_id,
            user_id=envelope.user_id,
            groups=(),
            roles=(),
        )

        self.boundary.authorize(
            context=context,
            requested_tenant_id=envelope.tenant_id,
        )

        handler = self.handlers.get(
            envelope.operation
        )

        if handler is None:
            raise JobSecurityError(
                "Operation is not permitted"
            )

        if not self.ledger.claim(
            tenant_id=envelope.tenant_id,
            job_id=envelope.job_id,
        ):
            return JobExecutionResult(
                job_id=envelope.job_id,
                tenant_id=envelope.tenant_id,
                status="duplicate",
            )

        try:
            handler(
                context,
                envelope.resource_id,
            )
        except Exception:
            self.ledger.release(
                tenant_id=envelope.tenant_id,
                job_id=envelope.job_id,
            )
            raise

        self.ledger.complete(
            tenant_id=envelope.tenant_id,
            job_id=envelope.job_id,
        )

        return JobExecutionResult(
            job_id=envelope.job_id,
            tenant_id=envelope.tenant_id,
            status="completed",
        )