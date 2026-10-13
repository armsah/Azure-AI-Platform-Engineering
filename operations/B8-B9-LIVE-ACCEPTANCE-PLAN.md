# B8/B9 Live Acceptance Plan

## Authorization and safety

All activities below require explicit approval before execution.

- Keep AKS stopped until a separately approved validation window.
- Do not run Terraform apply or provision preview environments without approval.
- Use isolated test workloads, least-privilege identities, and defined budgets.
- Capture timestamps, commands, sanitized outputs, metrics, and reviewer sign-off.
- Stop immediately if cost, security, or reliability guardrails are breached.

## B8.1 — Portability, drift, preview lifecycle

1. Deploy the same versioned application to an approved second cloud.
   Verify health, configuration portability, identity integration, and rollback.
2. Compare actual infrastructure state with the approved desired configuration.
   Introduce and detect an approved, reversible configuration deviation.
3. Provision a preview environment with an owner, namespace isolation,
   expiration timestamp, cost limit, and cleanup procedure.
   Verify its removal and absence of orphaned resources.

## B8.2 — Performance, scaling, FinOps

4. Run a representative application load profile.
   Record p50/p95/p99 latency, throughput, errors, and SLO evaluation.
5. Demonstrate HPA scale-out and scale-in under approved load.
   Record pod counts, CPU utilization, response latency, and recovery.
6. Verify actual Azure pricing assumptions, cost estimates, budgets,
   alerts, and the approval path for budget exceptions.

## B9.1 — Chaos and incident operations

7. Execute an approved, bounded failure injection in an isolated environment.
   Record blast radius, detection time, recovery time, and rollback.
8. Conduct a timed incident drill with severity classification,
   incident commander, communications, recovery evidence, and retrospective.

## B9.2 — Security and recovery

9. Review all six STRIDE categories. Exercise relevant security controls,
   record mitigation effectiveness, and document residual risks.
10. Execute the production recovery runbook in an approved environment.
    Verify restoration, integrity, RTO/RPO measurements, and sign-off.

## Evidence requirements

For each acceptance item, capture:

- Requirement ID and approved change or exercise reference
- Environment, application version, and infrastructure revision
- Start/end timestamps and responsible operator
- Expected versus observed behavior and acceptance thresholds
- Metrics, logs, sanitized command output, and rollback evidence
- Reviewer, review date, and unresolved risks

Store references in `operations/b8-b9-evidence.json`.

The evidence validator checks structure and declared verification.
It cannot independently prove that a referenced exercise occurred.
An authorized reviewer must inspect the underlying evidence before
changing any requirement from PARTIAL to COMPLETE.

## Completion rule

B8/B9 may be marked fully COMPLETE only after all ten operational
requirements are independently reviewed and accepted.
