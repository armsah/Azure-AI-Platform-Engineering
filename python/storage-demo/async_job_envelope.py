import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any


class JobSecurityError(Exception):
    pass


@dataclass(frozen=True)
class JobEnvelope:
    version: int
    job_id: str
    directory_tenant_id: str
    tenant_id: str
    user_id: str
    operation: str
    resource_id: str
    issued_at: int
    expires_at: int
    audience: str
    nonce: str
    signature: str


def _payload(envelope: JobEnvelope) -> dict[str, Any]:
    return {
        "version": envelope.version,
        "job_id": envelope.job_id,
        "directory_tenant_id": envelope.directory_tenant_id,
        "tenant_id": envelope.tenant_id,
        "user_id": envelope.user_id,
        "operation": envelope.operation,
        "resource_id": envelope.resource_id,
        "issued_at": envelope.issued_at,
        "expires_at": envelope.expires_at,
        "audience": envelope.audience,
        "nonce": envelope.nonce,
    }


def _canonical_bytes(envelope: JobEnvelope) -> bytes:
    return json.dumps(
        _payload(envelope),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


class JobEnvelopeSigner:
    def __init__(
        self,
        *,
        secret: bytes,
        audience: str,
        ttl_seconds: int = 300,
        clock=None,
    ):
        if len(secret) < 32:
            raise ValueError(
                "Signing secret must contain at least 32 bytes"
            )

        if not audience.strip():
            raise ValueError("Audience is required")

        if ttl_seconds <= 0:
            raise ValueError("TTL must be positive")

        self._secret = secret
        self.audience = audience
        self.ttl_seconds = ttl_seconds
        self.clock = clock or time.time

    def sign(
        self,
        *,
        job_id: str,
        directory_tenant_id: str,
        tenant_id: str,
        user_id: str,
        operation: str,
        resource_id: str,
    ) -> JobEnvelope:

        fields = (
            job_id,
            directory_tenant_id,
            tenant_id,
            user_id,
            operation,
            resource_id,
        )

        if any(not value.strip() for value in fields):
            raise JobSecurityError(
                "Required job identity or operation is missing"
            )

        now = int(self.clock())

        unsigned = JobEnvelope(
            version=1,
            job_id=job_id,
            directory_tenant_id=directory_tenant_id,
            tenant_id=tenant_id,
            user_id=user_id,
            operation=operation,
            resource_id=resource_id,
            issued_at=now,
            expires_at=now + self.ttl_seconds,
            audience=self.audience,
            nonce=secrets.token_hex(16),
            signature="",
        )

        signature = hmac.new(
            self._secret,
            _canonical_bytes(unsigned),
            hashlib.sha256,
        ).hexdigest()

        return JobEnvelope(
            **{
                **_payload(unsigned),
                "signature": signature,
            }
        )

    def verify(self, envelope: JobEnvelope) -> None:
        if envelope.version != 1:
            raise JobSecurityError(
                "Unsupported job envelope version"
            )

        if envelope.audience != self.audience:
            raise JobSecurityError(
                "Incorrect worker audience"
            )

        now = int(self.clock())

        if envelope.issued_at > now:
            raise JobSecurityError(
                "Job issued in the future"
            )

        if envelope.expires_at <= now:
            raise JobSecurityError(
                "Job envelope expired"
            )

        if (
            envelope.expires_at - envelope.issued_at
            > self.ttl_seconds
        ):
            raise JobSecurityError(
                "Job lifetime exceeds policy"
            )

        if any(
            not value.strip()
            for value in (
                envelope.job_id,
                envelope.directory_tenant_id,
                envelope.tenant_id,
                envelope.user_id,
                envelope.operation,
                envelope.resource_id,
                envelope.nonce,
            )
        ):
            raise JobSecurityError(
                "Missing required job fields"
            )

        expected = hmac.new(
            self._secret,
            _canonical_bytes(envelope),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            expected,
            envelope.signature,
        ):
            raise JobSecurityError(
                "Invalid job signature"
            )