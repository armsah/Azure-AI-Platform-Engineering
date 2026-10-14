# B8/B9 Acceptance Matrix

This document distinguishes offline verification from operational
evidence. No live Azure deployment is authorized by these checks.

| Requirement | Offline evidence | Remaining acceptance | Status |
| --- | --- | --- | --- |
| B8.1 Multi-cloud portability | Container/Helm configuration and portability checks | Deploy and validate on an approved second cloud | PARTIAL |
| B8.1 Configuration drift | Snapshot comparison CLI and mutation tests | Approved infrastructure-state drift detection | PARTIAL |
| B8.1 Preview environments | Preview metadata and expiry audit | Provision, isolate, expire and retire an approved preview | PARTIAL |
| B8.2 Load testing | Local HTTP benchmark and acceptance tests | Representative application and workload benchmark | PARTIAL |
| B8.2 Capacity/autoscaling | Replica forecasts and static HPA checks | Observe scaling and recovery under approved load | PARTIAL |
| B8.2 FinOps | Budget comparison and cost-model tests | Verified Azure pricing, budget alerts and enforcement | PARTIAL |
| B9.1 Failure injection | HTTP fault simulation and recovery tests | Approved controlled failure exercise | PARTIAL |
| B9.1 Incident response | Severity, rollback and recovery assessment tests | Timed response drill with evidence | PARTIAL |
| B9.2 Threat modeling | STRIDE completeness and security configuration checks | Verify mitigation effectiveness and residual risks | PARTIAL |
| B9.2 Production runbooks | Documented incident and recovery procedures | Execute and review recovery runbook | PARTIAL |

Completion requires evidence for every outstanding acceptance item.
Passing offline tests does not change a requirement to COMPLETE.

## Local Kubernetes Validation — 2026-10-14

Local evidence: [B8/B9 Kubernetes validation](B8-B9-LOCAL-KUBERNETES-EVIDENCE.md)

The following exercises passed on Docker Desktop + kind:

| Module | Exercise | Observed result |
| --- | --- | --- |
| B8.2 | Sequential HTTP health availability | 200/200 successful responses (100%) |
| B9.1 | Controlled application pod deletion | Replacement pod created automatically |
| B9.1 | Deployment readiness recovery | 11.65 seconds; replacement ready 1/1 |

These results demonstrate local application availability and Kubernetes
self-healing. They do not establish representative concurrent load capacity,
production recovery objectives, second-cloud portability, or live incident
response readiness.

**Acceptance boundary:** All ten original cloud/production acceptance
criteria remain PARTIAL until their specific requirements are verified.
