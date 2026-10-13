from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class RecoveryResult:
    attempts: int
    recovered: bool
    final_status: int


async def request_with_recovery(
    client: httpx.AsyncClient,
    url: str,
    max_attempts: int = 3,
) -> RecoveryResult:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    retryable = {429, 500, 502, 503, 504}

    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.get(url)
            status = response.status_code
        except (httpx.TimeoutException, httpx.TransportError):
            status = 0

        if 200 <= status < 400:
            return RecoveryResult(attempt, True, status)

        if status not in retryable and status != 0:
            return RecoveryResult(attempt, False, status)

        if attempt < max_attempts:
            await asyncio.sleep(0)

    return RecoveryResult(max_attempts, False, status)
