import httpx
import pytest

from fault_injection import request_with_recovery


@pytest.mark.asyncio
async def test_transient_503_recovers():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(503 if attempts < 3 else 200)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = await request_with_recovery(client, "http://localhost/test")

    assert result.recovered
    assert result.attempts == 3
    assert result.final_status == 200


@pytest.mark.asyncio
async def test_persistent_503_exhausts_retries():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503))
    ) as client:
        result = await request_with_recovery(client, "http://localhost/test")

    assert not result.recovered
    assert result.attempts == 3


@pytest.mark.asyncio
async def test_404_does_not_retry():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(404)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = await request_with_recovery(client, "http://localhost/test")

    assert not result.recovered
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_timeout_recovers():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            raise httpx.ReadTimeout("Injected timeout")

        return httpx.Response(200)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = await request_with_recovery(client, "http://localhost/test")

    assert result.recovered
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_transport_failure_recovers():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            raise httpx.ConnectError("Injected connection failure")

        return httpx.Response(200)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = await request_with_recovery(client, "http://localhost/test")

    assert result.recovered
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_retry_limit_enforced():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200))
    ) as client:
        with pytest.raises(ValueError):
            await request_with_recovery(
                client,
                "http://localhost/test",
                max_attempts=0,
            )
