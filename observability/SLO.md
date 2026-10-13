# Storage Demo Service-Level Objectives

## Scope
HTTP requests served by the Storage Demo FastAPI application.

## Availability SLO
- Target: 99.9% successful HTTP requests over a rolling 30-day window.
- Indicator: proportion of requests returning a status below 500.
- Error budget: 0.1% of requests.
- Prometheus metric: `storage_demo_http_requests_total`.

## Latency SLO
- Target: 95% of HTTP requests complete within 1 second over 30 days.
- Indicator: request-duration histogram.
- Prometheus metric: `storage_demo_http_request_duration_seconds`.

## Alerting
- High error rate: greater than 5% HTTP 5xx responses over 5 minutes, sustained for 10 minutes.
- High latency: p95 greater than 1 second over 5 minutes, sustained for 10 minutes.
- Alerts are configuration examples; no monitoring stack is deployed.

## Limitations
- These are initial engineering targets, not measured production achievements.
- Metrics are process-local; multi-worker aggregation requires a supported deployment configuration.
- No Prometheus scrape configuration or Alertmanager deployment is included.
