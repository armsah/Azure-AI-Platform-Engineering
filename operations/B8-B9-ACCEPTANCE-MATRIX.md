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
