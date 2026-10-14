# B8/B9 Local Kubernetes Validation Evidence

Date: 2026-10-14
Environment: Docker Desktop + kind
Kubernetes context: kind-b8-b9-local
Namespace: b8-b9-local
Application: storage-demo
Image: storage-demo:b8-b9-local

## B8 — Local Application Availability

Method: 200 sequential HTTP GET requests to /health through kubectl port-forward.

Results:
- Total requests: 200
- HTTP 200 responses: 200
- Failed requests: 0
- Observed success rate: 100%

Scope: Local availability smoke test only.
Not a representative concurrent load or capacity benchmark.

## B9 — Controlled Pod Failure and Recovery

Method: Delete the application pod in the isolated local namespace
and wait for Kubernetes Deployment readiness.

Incident start: 2026-10-14T03:58:45.4333955+03:00
Deployment recovered: 2026-10-14T03:58:57.0805215+03:00

Observed recovery measurement: 11.65 seconds

Original pod:
b8-b9-local-storage-demo-c85fd946b-f7xj9

Replacement pod:
b8-b9-local-storage-demo-c85fd946b-crclj

Post-recovery:
- Deployment ready: 1/1
- Replacement pod: Running, ready 1/1
- Container restarts: 0

Measurement limitation:
RecoverySeconds measures elapsed time between incident initiation
and successful rollout-status completion. It does not measure
end-user downtime or a production recovery-time objective.

## Safety and Acceptance Boundaries

- All Kubernetes actions targeted kind-b8-b9-local.
- Azure AKS remained stopped.
- No Azure deployments were performed.
- No additional Azure consumption was intentionally initiated.
- Application checks were limited to /health.
- Local testing does not satisfy production or second-cloud requirements.
- Original B8/B9 cloud acceptance criteria remain PARTIAL.
