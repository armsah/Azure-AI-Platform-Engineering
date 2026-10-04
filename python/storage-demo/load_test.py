import asyncio
import time
import httpx

URL = "http://localhost:8000/trace-demo"
CONCURRENCY = 50
REQUESTS = 100


async def request(client, semaphore):
    async with semaphore:
        start = time.perf_counter()

        try:
            response = await client.get(URL, timeout=10)
            status = response.status_code
        except Exception:
            status = 0

        return status, time.perf_counter() - start


async def main():
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient() as client:
        start = time.perf_counter()

        results = await asyncio.gather(*[
            request(client, semaphore)
            for _ in range(REQUESTS)
        ])

        duration = time.perf_counter() - start

    latencies = sorted(x[1] for x in results)
    successes = sum(1 for status, _ in results if status < 500 and status != 0)

    print(f"requests:    {REQUESTS}")
    print(f"concurrency: {CONCURRENCY}")
    print(f"duration:    {duration:.2f}s")
    print(f"throughput:  {REQUESTS / duration:.2f} req/s")
    print(f"success:     {successes / REQUESTS:.2%}")
    print(f"p50:         {latencies[int(REQUESTS * .50)] * 1000:.1f} ms")
    print(f"p95:         {latencies[int(REQUESTS * .95)] * 1000:.1f} ms")
    print(f"p99:         {latencies[int(REQUESTS * .99)] * 1000:.1f} ms")


asyncio.run(main())