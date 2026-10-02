import pytest

from circuit_breaker import (
    CircuitBreaker,
    CircuitOpen,
    CircuitState,
)


def test_circuit_opens_after_failure_threshold():
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout=30,
    )

    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED

    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    with pytest.raises(CircuitOpen):
        breaker.allow_request()


def test_success_resets_failure_count():
    breaker = CircuitBreaker(failure_threshold=3)

    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()

    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_open_circuit_transitions_to_half_open(monkeypatch):
    clock = iter([100.0, 131.0])

    monkeypatch.setattr(
        "circuit_breaker.time.monotonic",
        lambda: next(clock),
    )

    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=30,
    )

    breaker.record_failure()

    breaker.allow_request()

    assert breaker.state == CircuitState.HALF_OPEN


def test_half_open_success_closes_circuit():
    breaker = CircuitBreaker()

    breaker.state = CircuitState.HALF_OPEN
    breaker.failure_count = 3

    breaker.record_success()

    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0