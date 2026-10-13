# Release rollback and disaster recovery

## Safety boundary

AKS `aks-armen-learning-2026` in `rg-terraform-learning` is intentionally
stopped. Do not start it, provision Azure resources, or trigger deployment
pipelines without explicit authorization.

## Release readiness

Run `python scripts/validate_release.py` from the repository root.
This checks repository-defined release contracts, environment settings,
image digests, and staging-to-production promotion consistency.

This is **offline desired-state validation**, not live Kubernetes drift
detection. No cluster, Flux controller, registry, or Azure API is queried.

## Failed release: containment

1. Stop further promotion and record the failing commit, image digest,
   affected environment, and Jenkins build.
2. Inspect `/health`, `/metrics`, structured application logs, and trace IDs
   if the application is running.
3. Identify the last known-good GitOps commit and its immutable image digest.
4. Open a reviewed pull request restoring the last known-good digest in
   the affected environment's `values-patch.yaml`. Preserve environment
   replica and autoscaling settings.
5. Run the complete offline validation suite and Jenkins
   `VALIDATION_ONLY=true` before approving the rollback.
6. **Only with explicit authorization and a running cluster**, allow the
   existing GitOps controller to reconcile the approved rollback.
7. Verify health, latency, error rate, and workload readiness before
   resuming promotion.

## Disaster recovery

1. Preserve evidence: Git commit, Jenkins logs, GitOps manifests,
   image digest, and any available monitoring data.
2. Establish the recovery target and assess dependencies, credentials,
   container registry availability, and data backup requirements.
3. Restore infrastructure and application state only through an approved
   recovery procedure. This repository does not demonstrate backup
   restoration, RPO/RTO compliance, or live failover.
4. Reconcile reviewed GitOps desired state only after infrastructure
   recovery is authorized.
5. Verify application endpoints, security controls, and data integrity.

## Drift response

Offline validation failures indicate disagreement among repository files
or the release policy. Fix the discrepancy in a reviewed PR.
Actual cluster drift requires a separate authorized live inspection.
