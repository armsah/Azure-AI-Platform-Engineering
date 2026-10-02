import pytest
import resilience
from resilience import is_retryable_status


def test_transient_failures_are_retryable():
    assert is_retryable_status(429)
    assert is_retryable_status(500)
    assert is_retryable_status(503)


def test_non_transient_failures_are_not_retryable():
    assert not is_retryable_status(400)
    assert not is_retryable_status(401)
    assert not is_retryable_status(403)

def test_backoff_is_exponential_and_capped(monkeypatch):
    monkeypatch.setattr(
        resilience.random,
        "uniform",
        lambda low, high: high,
    )

    assert resilience.calculate_backoff(0) == 0.5
    assert resilience.calculate_backoff(1) == 1.0
    assert resilience.calculate_backoff(2) == 2.0
    assert resilience.calculate_backoff(10) == 8.0

def test_retry_eventually_succeeds():
    attempts = []

    def operation():
        attempts.append(1)

        if len(attempts) < 3:
            raise resilience.RetryableError(503)

        return "success"

    result = resilience.execute_with_retry(
        operation,
        max_retries=2,
        sleep_fn=lambda _: None,
    )

    assert result == "success"
    assert len(attempts) == 3


def test_non_retryable_error_fails_immediately():
    attempts = []

    def operation():
        attempts.append(1)
        raise resilience.RetryableError(403)

    with pytest.raises(resilience.RetryableError):
        resilience.execute_with_retry(
            operation,
            max_retries=3,
            sleep_fn=lambda _: None,
        )

    assert len(attempts) == 1

def test_fallback_used_after_primary_exhausted():
    primary_attempts = []
    fallback_attempts = []

    def primary():
        primary_attempts.append(1)
        raise resilience.RetryableError(503)

    def fallback():
        fallback_attempts.append(1)
        return "fallback-success"

    result = resilience.execute_with_fallback(
        primary,
        fallback,
        max_retries=2,
        sleep_fn=lambda _: None,
    )

    assert result == "fallback-success"
    assert len(primary_attempts) == 3
    assert len(fallback_attempts) == 1

def test_non_retryable_failure_does_not_use_fallback():
    fallback_called = []

    def primary():
        raise resilience.RetryableError(403)

    def fallback():
        fallback_called.append(True)
        return "should-not-run"

    with pytest.raises(resilience.RetryableError):
        resilience.execute_with_fallback(
            primary,
            fallback,
            max_retries=2,
            sleep_fn=lambda _: None,
        )

    assert fallback_called == []
