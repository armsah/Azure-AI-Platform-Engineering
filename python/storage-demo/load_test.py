from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from dataclasses import asdict, dataclass

import httpx


@dataclass(frozen=True)
class LoadResult:
    requests: int
    successes: int
    failures: int
    duration_seconds: float
    throughput_rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float

    @property
    def success_rate(self) -> float:
        return self.successes / self.requests if self.requests else 0.0


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def summarize(samples: list[tuple[int, float]], duration: float) -> LoadResult:
    if not samples:
        raise ValueError("At least one request is required")
    if duration <= 0:
        raise ValueError("Duration must be positive")

    latencies = [latency * 1000 for _, latency in samples]
    successes = sum(200 <= status < 400 for status, _ in samples)

    return LoadResult(
        requests=len(samples),
        successes=successes,
        failures=len(samples) - successes,
        duration_seconds=duration,
        throughput_rps=len(samples) / duration,
        p50_ms=percentile(latencies, 0.50),
        p95_ms=percentile(latencies, 0.95),
        p99_ms=percentile(latencies, 0.99),
    )


def evaluate(result: LoadResult, min_success: float, max_p95_ms: float) -> bool:
    return result.success_rate >= min_success and result.p95_ms <= max_p95_ms


async def execute(
    url: str,
    requests: int,
    concurrency: int,
    timeout: float,
) -> LoadResult:
    if requests < 1 or concurrency < 1 or timeout <= 0:
        raise ValueError("Invalid load-test parameters")

    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient() as client:
        async def request() -> tuple[int, float]:
            async with semaphore:
                start = time.perf_counter()
                try:
                    response = await client.get(url, timeout=timeout)
                    status = response.status_code
                except httpx.RequestError:
                    status = 0
                return status, time.perf_counter() - start

        start = time.perf_counter()
        samples = await asyncio.gather(*(request() for _ in range(requests)))
        duration = time.perf_counter() - start

    return summarize(samples, duration)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/health")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--min-success", type=float, default=0.999)
    parser.add_argument("--max-p95-ms", type=float, default=1000)
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()

    from urllib.parse import urlparse

    target = urlparse(args.url)
    if (
        target.scheme not in ("http", "https")
        or target.hostname not in ("localhost", "127.0.0.1", "::1")
        and not args.allow_remote
    ):
        parser.error("Remote load testing requires --allow-remote")

    if not 0 <= args.min_success <= 1 or args.max_p95_ms <= 0:
        parser.error("Invalid acceptance thresholds")

    result = asyncio.run(
        execute(args.url, args.requests, args.concurrency, args.timeout)
    )
    print(json.dumps(asdict(result), indent=2))
    return 0 if evaluate(result, args.min_success, args.max_p95_ms) else 1


if __name__ == "__main__":
    raise SystemExit(main())
