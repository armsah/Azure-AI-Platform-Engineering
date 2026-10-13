# B8 — Multi-Cloud, Performance and Cost Engineering

## B8.1 — Portability, drift and preview environments

The application uses containers and Kubernetes deployment manifests, but
Terraform currently uses the AzureRM provider and an Azure Storage backend.

This is **Azure-specific infrastructure**, not verified multi-cloud deployment.
Portability to another cloud requires provider-specific infrastructure,
identity, networking, secrets, storage and managed-service replacements.

Repository drift is checked through release validation and the platform safety
policy. Live infrastructure drift requires an approved, read-only Terraform
plan against the actual environment.

Preview environments are disabled by default. Future previews require:
- Explicit approval and a documented cost estimate.
- Isolated namespaces, identities and credentials.
- A maximum 24-hour lifetime and automatic expiration.
- Deletion verification and an auditable owner.
- No automatic provisioning while AKS remains stopped.

## B8.2 — Performance, capacity and FinOps

The load tester measures success rate, throughput and p50/p95/p99 latency.
HTTP 4xx, HTTP 5xx and transport failures count as failures.

Run only against an explicitly started local application:

    python python/storage-demo/load_test.py --url http://localhost:8000/health

Do not run against remote endpoints without authorization.

Capacity policy validates Helm HPA minimum/maximum replicas, CPU target,
resource requests and resource limits.

Cost guardrails prohibit automatic Azure provisioning and require approval
and a cost estimate before infrastructure changes.

No live capacity benchmark, secondary-cloud deployment, cost forecast,
or cloud drift check has been performed.

### B8.1 offline acceptance evidence

The following read-only tools are implemented:

- `scripts/check_configuration_drift.py`: compares desired and observed
  JSON snapshots; reports missing, unexpected and changed fields.
- `scripts/audit_preview_lifecycle.py`: validates preview inventory
  metadata, detects expired previews and flags retirement reviews.
- Both tools support UTF-8 BOM input and structured JSON output.
- Regression coverage: 18 tests passed locally.

These checks do not provision, modify or delete infrastructure.
Snapshot comparison does not establish live Terraform drift detection.
Preview retirement review does not establish automatic deletion.
Secondary-cloud portability remains unverified.

### B8.2 local acceptance evidence

Local benchmark against a temporary HTTP server bound to
127.0.0.1:8765:

| Metric | Measured result |
| --- | ---: |
| Requests | 100 |
| Successful requests | 100 |
| Failures | 0 |
| Throughput | 307.92 requests/second |
| p50 latency | 10.75 ms |
| p95 latency | 14.49 ms |
| p99 latency | 14.79 ms |
| Concurrency | 5 |
| Benchmark exit code | 0 |

Acceptance thresholds: success rate >= 99.9%, p95 <= 1000 ms.
Both passed against the local test server.

The load tester rejects concurrency above 10 without a separately
approved testing workflow.

Capacity forecasting tests cover traffic growth, HPA maximum capacity,
minimum replica cost, budget comparisons and invalid inputs.

The $0.10 hourly replica cost used in tests is hypothetical, not an
Azure price quotation. Estimates exclude infrastructure overhead.

Local benchmarks do not demonstrate production capacity, real HPA
scaling or multi-cloud performance. Cost comparisons do not enforce
Azure subscription spending limits.
