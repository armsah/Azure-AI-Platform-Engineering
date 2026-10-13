# B9 — Chaos Engineering, Incident Response and Operations

## B9.1 — Failure injection and incident response

Offline simulations cover:
- Dependency timeout.
- Transient HTTP 503.
- Worker restart.
- Unrecoverable dependency.

These are deterministic recovery-policy simulations, not real failures
in a running Kubernetes cluster.

Incident classification:
- SEV1: service unavailable or confirmed data loss.
- SEV2: degraded service.
- SEV3: minor impact without service degradation.

Incident procedure:
1. Declare severity, incident commander, timestamp and affected services.
2. Preserve logs, traces, metrics and deployment revision.
3. Stop unsafe automation; do not start AKS without authorization.
4. Check error rate, p95 latency, saturation and dependency health.
5. Apply an approved rollback or mitigation.
6. Verify recovery against SLOs and record the recovery timeline.
7. Complete a blameless post-incident review with corrective actions.

## B9.2 — Threat modeling and runbooks

STRIDE assessment:

| Threat | Example | Required mitigation |
| --- | --- | --- |
| Spoofing | Forged service identity | Workload identity and authentication |
| Tampering | Modified image digest | Immutable digests and release validation |
| Repudiation | Unattributed changes | Git PR audit trail and structured logs |
| Information disclosure | Secret exposure | Key Vault, RBAC and redaction |
| Denial of service | Request overload | Rate limiting, HPA and resource limits |
| Elevation of privilege | Overprivileged workload | Least privilege and namespace isolation |

Recovery procedure:
1. Identify the last known-good Git revision and image digest.
2. Verify incident scope and authorization.
3. Prepare a reviewed rollback PR.
4. Run Jenkins with VALIDATION_ONLY=true.
5. Obtain explicit authorization before any live deployment.
6. Verify health, metrics, error budget and data integrity.
7. Document evidence, recovery time and remaining risks.

Refer to release/RECOVERY-RUNBOOK.md and observability/RUNBOOK.md.

Live chaos experiments, production recovery and threat-control effectiveness
remain unverified while the cluster is stopped.

### B9 offline incident acceptance

The incident assessment module implements deterministic checks for:

- SEV1/SEV2/SEV3 classification.
- Explicit rollback authorization.
- Preservation of logs, metrics and deployment revision.
- Recovery health, SLO and data-integrity verification.
- Structured assessment reports.

Existing offline fault-injection tests cover dependency failures,
timeouts, retry behavior and simulated recovery.

These checks do not execute a live chaos experiment, perform a
production rollback or establish actual incident recovery times.
