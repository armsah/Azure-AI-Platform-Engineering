import random
import time

class RetryableError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}")

def is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599

def calculate_backoff(
    attempt: int,
    base_seconds: float = 0.5,
    max_seconds: float = 8.0,
) -> float:
    exponential = base_seconds * (2 ** attempt)
    capped = min(exponential, max_seconds)

    # Full jitter: random delay between 0 and capped delay.
    return random.uniform(0, capped)

def execute_with_retry(
    operation,
    max_retries: int = 2,
    sleep_fn=time.sleep,
):
    for attempt in range(max_retries + 1):
        try:
            return operation()

        except RetryableError as exc:
            if not is_retryable_status(exc.status_code):
                raise

            if attempt >= max_retries:
                raise

            delay = calculate_backoff(attempt)
            sleep_fn(delay)

def execute_with_fallback(
    primary_operation,
    fallback_operation=None,
    max_retries: int = 2,
    sleep_fn=time.sleep,
):
    try:
        return execute_with_retry(
            primary_operation,
            max_retries=max_retries,
            sleep_fn=sleep_fn,
        )
    except RetryableError as exc:
        if not is_retryable_status(exc.status_code):
            raise

        if fallback_operation is None:
            raise

        return execute_with_retry(
            fallback_operation,
            max_retries=max_retries,
            sleep_fn=sleep_fn,
        )
