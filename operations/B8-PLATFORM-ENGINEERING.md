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
