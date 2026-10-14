# B10 — Production Launch and Architecture Defense

## Completion scope

B10 implementation is under local validation. Production release
authorization and live recovery acceptance remain pending.

## Architecture

- Infrastructure: Azure Bicep and Terraform modules.
- Application: Python API packaged as a container.
- Deployment: Helm, Kubernetes and GitOps manifests.
- Release management: immutable image digests and environment-specific
  configuration validated by `scripts/validate_release.py`.
- Security: non-root containers, Kubernetes security controls,
  identity configuration, and repository security tests.
- Operations: health checks, observability runbooks, incident response,
  and documented rollback procedures.

These are repository-defined capabilities. This document does not
establish that they are all active in a production environment.

## Architecture decisions and trade-offs

| Decision | Benefit | Limitation |
| --- | --- | --- |
| GitOps desired state | Reviewable configuration changes | Requires a healthy controller and cluster |
| Immutable image digests | Reproducible release references | Does not establish image security |
| Separate environment overlays | Environment-specific configuration | Configuration drift remains possible |
| Kubernetes probes | Detect unhealthy containers | Do not prove end-to-end service availability |
| Offline release validation | Safe, repeatable CI checks | Cannot verify live production behavior |
| Local kind recovery drills | Exercise pod replacement | Cannot prove production RTO or RPO |

## Release decision

Run `python scripts/validate_release.py` and
`python scripts/validate_b10.py`.

The B10 validator must return `NO-GO` while required production
evidence remains pending. A local validation pass does not authorize
deployment.

## Recovery strategy

Follow `release/RECOVERY-RUNBOOK.md`.

A production rollback requires explicit authorization, reviewed
GitOps changes, and post-recovery verification.

Local pod-replacement evidence is documented in
`operations/B8-B9-LOCAL-KUBERNETES-EVIDENCE.md`.

## Outstanding production acceptance

- Approved production go/no-go review.
- Verified deployment and post-deployment health evidence.
- Security review with accountable approval.
- Demonstrated rollback or recovery in an approved environment.
- Verified backup restoration and applicable RPO/RTO targets.
- Architecture review with recorded decisions and residual risks.

## Safety boundary

AKS `aks-armen-learning-2026` remains stopped.

Do not start AKS, provision Azure resources, apply Terraform,
trigger cloud deployment, or promote GitOps changes without explicit
authorization.
