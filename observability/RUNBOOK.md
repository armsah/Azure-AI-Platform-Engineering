# Storage Demo Observability Runbook

## Health checks
- `GET /health`: application health endpoint.
- `GET /metrics`: Prometheus metrics endpoint.
- JSON logs contain timestamp, level, logger, message, trace ID and span ID.
- OpenTelemetry provides FastAPI and HTTPX tracing.

## High error rate
1. Inspect `storage_demo_http_requests_total` by route and status.
2. Identify affected routes and inspect correlated application logs.
3. Check downstream Azure service errors and credential failures.
4. Escalate if the error budget is being consumed.

## High latency
1. Inspect `storage_demo_http_request_duration_seconds_bucket`.
2. Identify slow routes and examine correlated traces.
3. Check downstream dependencies and resource saturation.
4. Escalate if the latency SLO is breached.

## Safe recovery
- Do not start AKS or create Azure resources without authorization.
- Use offline tests and Helm validation while AKS is stopped.
- Follow the established GitOps PR workflow for deployment changes.
- Avoid modifying production state during investigation without approval.

## Validation
Run from `python/storage-demo`:

`python -m pytest -q`

The alerts are not active until an authorized Prometheus-compatible
monitoring system loads `observability/alerts.yaml`.
