import time

from fastapi import Request
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUESTS = Counter(
    "storage_demo_http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status"],
)

LATENCY = Histogram(
    "storage_demo_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
)


def install_metrics(app):
    @app.middleware("http")
    async def collect_metrics(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            route_name = getattr(route, "path", "unmatched")
            REQUESTS.labels(request.method, route_name, str(status)).inc()
            LATENCY.labels(request.method, route_name).observe(
                time.perf_counter() - start
            )

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
