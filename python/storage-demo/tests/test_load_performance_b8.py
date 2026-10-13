import asyncio

import pytest

from load_test import evaluate, execute, percentile, summarize


def test_percentile_nearest_rank():
    assert percentile([10, 20, 30, 40, 50], 0.95) == 50


def test_success_rate_and_latency():
    result = summarize(
        [(200, 0.010), (201, 0.020), (503, 0.030)],
        duration=1.0,
    )
    assert result.requests == 3
    assert result.successes == 2
    assert result.failures == 1
    assert result.throughput_rps == 3
    assert result.p95_ms == 30
    assert not evaluate(result, 0.999, 1000)


def test_acceptance_thresholds_pass():
    result = summarize([(200, 0.010)] * 100, duration=2.0)
    assert result.success_rate == 1.0
    assert result.throughput_rps == 50
    assert evaluate(result, 0.999, 1000)


def test_latency_threshold_fails():
    result = summarize([(200, 1.5)], duration=2.0)
    assert not evaluate(result, 0.999, 1000)


@pytest.mark.parametrize("requests,concurrency,timeout", [
    (0, 1, 1),
    (1, 0, 1),
    (1, 1, 0),
    (1, 11, 1),
])
def test_unsafe_load_parameters_rejected(requests, concurrency, timeout):
    with pytest.raises(ValueError):
        asyncio.run(
            execute(
                "http://127.0.0.1:8000/health",
                requests,
                concurrency,
                timeout,
            )
        )
