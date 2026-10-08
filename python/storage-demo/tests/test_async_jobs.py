from dataclasses import replace

import pytest

from async_job_envelope import (
    JobEnvelopeSigner,
    JobSecurityError,
)
from async_job_submission import (
    AsyncJobSubmissionService,
)
from async_job_worker import (
    AsyncJobWorker,
    InMemoryJobLedger,
)
from request_context import RequestContext
from tenant_boundary import (
    InMemoryTenantMembershipStore,
    TenantAuthorizationError,
    TenantBoundary,
    TenantMembership,
)


SECRET = b"development-test-key-32-bytes-minimum!!"


def make_context(
    tenant="customer-a",
    user="user-1",
):
    return RequestContext(
        directory_tenant_id="entra-directory",
        tenant_id=tenant,
        user_id=user,
        groups=(),
        roles=("AI.User",),
    )


def make_boundary(
    memberships=None,
):
    if memberships is None:
        memberships = (
            TenantMembership(
                directory_tenant_id="entra-directory",
                user_id="user-1",
                business_tenant_id="customer-a",
            ),
        )

    return TenantBoundary(
        InMemoryTenantMembershipStore(
            memberships
        )
    )


def make_signer(
    now=1000,
    audience="document-worker",
):
    return JobEnvelopeSigner(
        secret=SECRET,
        audience=audience,
        ttl_seconds=300,
        clock=lambda: now,
    )


def make_envelope(
    signer=None,
):
    signer = signer or make_signer()

    return signer.sign(
        job_id="job-1",
        directory_tenant_id="entra-directory",
        tenant_id="customer-a",
        user_id="user-1",
        operation="document.process",
        resource_id="doc-1",
    )


def make_worker(
    *,
    signer=None,
    boundary=None,
    ledger=None,
    handlers=None,
):
    return AsyncJobWorker(
        signer=signer or make_signer(),
        boundary=boundary or make_boundary(),
        ledger=ledger or InMemoryJobLedger(),
        handlers=handlers or {
            "document.process": lambda ctx, rid: None,
        },
    )


def test_valid_envelope_verifies():
    signer = make_signer()

    signer.verify(
        make_envelope(signer)
    )


def test_tenant_tampering_rejected():
    envelope = make_envelope()

    tampered = replace(
        envelope,
        tenant_id="customer-b",
    )

    with pytest.raises(JobSecurityError):
        make_signer().verify(tampered)


def test_operation_tampering_rejected():
    envelope = make_envelope()

    tampered = replace(
        envelope,
        operation="admin.delete",
    )

    with pytest.raises(JobSecurityError):
        make_signer().verify(tampered)


def test_resource_tampering_rejected():
    envelope = make_envelope()

    tampered = replace(
        envelope,
        resource_id="secret-document",
    )

    with pytest.raises(JobSecurityError):
        make_signer().verify(tampered)


def test_expired_envelope_rejected():
    envelope = make_envelope()

    with pytest.raises(JobSecurityError):
        make_signer(now=1301).verify(envelope)


def test_future_issued_envelope_rejected():
    envelope = make_envelope()

    with pytest.raises(JobSecurityError):
        make_signer(now=999).verify(envelope)


def test_wrong_audience_rejected():
    envelope = make_envelope()

    with pytest.raises(JobSecurityError):
        make_signer(
            audience="admin-worker"
        ).verify(envelope)


def test_invalid_signature_rejected():
    envelope = make_envelope()

    tampered = replace(
        envelope,
        signature="0" * 64,
    )

    with pytest.raises(JobSecurityError):
        make_signer().verify(tampered)


def test_submission_uses_authorized_context():
    submission = AsyncJobSubmissionService(
        boundary=make_boundary(),
        signer=make_signer(),
    )

    envelope = submission.submit(
        context=make_context(),
        requested_tenant_id="customer-a",
        operation="document.process",
        resource_id="doc-1",
    )

    assert envelope.tenant_id == "customer-a"
    assert envelope.user_id == "user-1"


def test_submission_rejects_tenant_override():
    submission = AsyncJobSubmissionService(
        boundary=make_boundary(),
        signer=make_signer(),
    )

    with pytest.raises(TenantAuthorizationError):
        submission.submit(
            context=make_context(),
            requested_tenant_id="customer-b",
            operation="document.process",
            resource_id="doc-1",
        )


def test_worker_executes_authorized_job():
    calls = []

    worker = make_worker(
        handlers={
            "document.process": (
                lambda ctx, rid: calls.append(
                    (ctx.tenant_id, rid)
                )
            ),
        }
    )

    result = worker.execute(
        make_envelope()
    )

    assert result.status == "completed"
    assert calls == [
        ("customer-a", "doc-1")
    ]


def test_worker_rechecks_membership():
    worker = make_worker(
        boundary=make_boundary(
            memberships=()
        )
    )

    with pytest.raises(TenantAuthorizationError):
        worker.execute(
            make_envelope()
        )


def test_unknown_operation_rejected():
    envelope = make_signer().sign(
        job_id="job-2",
        directory_tenant_id="entra-directory",
        tenant_id="customer-a",
        user_id="user-1",
        operation="admin.delete",
        resource_id="doc-1",
    )

    worker = make_worker()

    with pytest.raises(JobSecurityError):
        worker.execute(envelope)


def test_duplicate_job_not_reexecuted():
    calls = []

    worker = make_worker(
        handlers={
            "document.process": (
                lambda ctx, rid: calls.append(rid)
            ),
        }
    )

    envelope = make_envelope()

    first = worker.execute(envelope)
    second = worker.execute(envelope)

    assert first.status == "completed"
    assert second.status == "duplicate"
    assert calls == ["doc-1"]


def test_failed_job_can_retry():
    attempts = []

    def handler(ctx, rid):
        attempts.append(rid)

        if len(attempts) == 1:
            raise RuntimeError("Transient failure")

    worker = make_worker(
        handlers={
            "document.process": handler,
        }
    )

    envelope = make_envelope()

    with pytest.raises(RuntimeError):
        worker.execute(envelope)

    result = worker.execute(envelope)

    assert result.status == "completed"
    assert attempts == ["doc-1", "doc-1"]


def test_tenant_scoped_idempotency():
    ledger = InMemoryJobLedger()

    assert ledger.claim(
        tenant_id="customer-a",
        job_id="same-job",
    )

    assert ledger.claim(
        tenant_id="customer-b",
        job_id="same-job",
    )


def test_duplicate_claim_rejected_while_running():
    ledger = InMemoryJobLedger()

    assert ledger.claim(
        tenant_id="customer-a",
        job_id="job-1",
    )

    assert not ledger.claim(
        tenant_id="customer-a",
        job_id="job-1",
    )


def test_released_claim_can_be_retried():
    ledger = InMemoryJobLedger()

    assert ledger.claim(
        tenant_id="customer-a",
        job_id="job-1",
    )

    ledger.release(
        tenant_id="customer-a",
        job_id="job-1",
    )

    assert ledger.claim(
        tenant_id="customer-a",
        job_id="job-1",
    )


def test_completed_job_cannot_be_reclaimed():
    ledger = InMemoryJobLedger()

    assert ledger.claim(
        tenant_id="customer-a",
        job_id="job-1",
    )

    ledger.complete(
        tenant_id="customer-a",
        job_id="job-1",
    )

    assert not ledger.claim(
        tenant_id="customer-a",
        job_id="job-1",
    )


def test_worker_context_has_no_inherited_roles():
    observed = []

    worker = make_worker(
        handlers={
            "document.process": (
                lambda ctx, rid: observed.append(
                    ctx.roles
                )
            ),
        }
    )

    worker.execute(
        make_envelope()
    )

    assert observed == [()]