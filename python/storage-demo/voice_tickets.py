from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass


class VoiceTicketError(Exception):
    pass


@dataclass(frozen=True)
class VoiceTicketIdentity:
    tenant_id: str
    user_id: str


class VoiceTicketStore:
    def __init__(
        self,
        ttl_seconds: float = 30.0,
        max_tickets: int = 1000,
    ):
        if ttl_seconds <= 0:
            raise ValueError("Ticket TTL must be positive")

        if max_tickets <= 0:
            raise ValueError("Ticket capacity must be positive")

        self.ttl_seconds = ttl_seconds
        self.max_tickets = max_tickets
        self._tickets = {}
        self._lock = threading.Lock()

    def issue(
        self,
        tenant_id: str,
        user_id: str,
    ) -> str:
        if not tenant_id or not user_id:
            raise VoiceTicketError("Authenticated identity required")

        now = time.monotonic()

        with self._lock:
            self._purge_expired(now)

            if len(self._tickets) >= self.max_tickets:
                raise VoiceTicketError("Ticket capacity exceeded")

            ticket = secrets.token_urlsafe(32)

            self._tickets[ticket] = (
                VoiceTicketIdentity(tenant_id, user_id),
                now + self.ttl_seconds,
            )

            return ticket

    def consume(self, ticket: str) -> VoiceTicketIdentity:
        if not ticket:
            raise VoiceTicketError("Missing ticket")

        now = time.monotonic()

        with self._lock:
            entry = self._tickets.pop(ticket, None)

        if entry is None:
            raise VoiceTicketError("Invalid or already used ticket")

        identity, expires_at = entry

        if now >= expires_at:
            raise VoiceTicketError("Expired ticket")

        return identity

    def _purge_expired(self, now: float) -> None:
        expired = [
            ticket
            for ticket, (_, expires_at) in self._tickets.items()
            if now >= expires_at
        ]

        for ticket in expired:
            del self._tickets[ticket]
