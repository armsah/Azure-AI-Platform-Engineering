# Azure AI Platform Engineering

A production-oriented engineering platform for building, deploying, securing, operating, and evolving enterprise AI workloads on Azure.

This project focuses on the engineering gap between an **AI prototype** and a **production-grade AI platform**: secure access, tenant-isolated knowledge, controlled agent actions, repeatable infrastructure, safe software delivery, observability, resilience, recovery, and operational governance.

> **Core design principle:** LLM output is a proposal, not authority.

---

## Overview

Enterprise AI systems require more than model inference and retrieval.

A production platform must provide:

* Secure identity and access
* Tenant-aware data isolation
* Controlled AI and agent execution
* Reproducible infrastructure
* Immutable software delivery
* Kubernetes orchestration
* GitOps-based deployment
* Software supply-chain security
* Distributed observability
* SLO and reliability engineering
* High availability and disaster recovery
* Capacity and cost management

The objective of this repository is to demonstrate how AI workloads can be deployed and operated using the same engineering controls expected from production cloud services.

---

## Architecture

The platform evolves from a FastAPI-based RAG application into a production-oriented, agentic AI platform running on Kubernetes.

### AI Application Layer

The application starts with a **FastAPI** service exposing AI and Retrieval-Augmented Generation (RAG) APIs.

The core AI stack uses:

* **Azure AI Foundry / Azure OpenAI** — model inference and embeddings
* **Azure AI Search** — keyword, vector, and hybrid retrieval
* **Azure Blob Storage** — source documents and application data
* **FastAPI** — AI and RAG API layer

The architecture supports the progression from traditional RAG toward **agentic RAG and multi-agent workflows**.

---

## Agentic AI and Controlled Execution

Agents can reason, select tools, delegate work, and propose actions. However, model output never directly becomes system authority.

Application and platform policies enforce:

* Tool authorization
* Execution budgets
* Delegation boundaries
* Tenant boundaries
* Human-in-the-loop (HITL) approval
* Controlled side effects
* Auditable execution

This creates a deterministic control plane around probabilistic AI behaviour.

> **LLM output is a proposal, not authority.**

---

## Identity and Security

Identity is based on **Microsoft Entra ID**, Azure RBAC, and workload identity.

The platform avoids embedding Azure credentials inside application workloads.

Security controls include:

* Microsoft Entra ID authentication
* Azure RBAC
* AKS Workload Identity
* Managed identities
* Azure Key Vault
* Private connectivity
* Network isolation
* Least-privilege authorization
* Tenant-aware access controls

The objective is to establish trusted workload identities while minimizing long-lived credentials and secrets.

---

## Containers and Kubernetes

Applications are packaged as containers using **Docker**.

Immutable container images are stored in **Azure Container Registry (ACR)** and deployed to **Azure Kubernetes Service (AKS)**.

The Kubernetes delivery model uses:

* **Docker** — application packaging
* **Azure Container Registry** — immutable image storage
* **AKS** — workload orchestration
* **Helm** — Kubernetes resource packaging
* **Kustomize** — environment-specific configuration
* **Flux** — GitOps reconciliation

Flux continuously reconciles the desired state stored in Git with the state running in Kubernetes.

---

## Infrastructure as Code

The underlying Azure platform is provisioned through Infrastructure as Code.

The repository uses:

* **Terraform**
* **Bicep**

Infrastructure includes:

* Virtual networking
* AKS
* Identity and RBAC
* Azure Container Registry
* Azure Key Vault
* Private connectivity
* AI services
* Storage and supporting Azure resources

Cloud infrastructure is treated as version-controlled, repeatable, and reviewable software.

---

## CI/CD and GitOps

The project demonstrates the same delivery model across multiple CI platforms:

* Jenkins
* GitHub Actions
* Azure DevOps
* GitLab CI/CD

The pipeline follows the general flow:

```text
Code
  │
  ▼
Test
  │
  ▼
Security Scan
  │
  ▼
Build
  │
  ▼
Generate SBOM
  │
  ▼
Sign Artifact
  │
  ▼
Publish Immutable Artifact
  │
  ▼
Update GitOps State
  │
  ▼
Flux Reconciliation
  │
  ▼
AKS
```

A key architectural boundary is:

> **CI builds artifacts. Flux performs deployment.**

CI systems do not directly mutate production Kubernetes resources.

This separates artifact production from deployment ownership and preserves Git as the source of truth for runtime state.

---

## Software Supply-Chain Security

The delivery pipeline applies production-oriented software supply-chain controls.

These include:

* Dependency scanning
* Container scanning
* SBOM generation
* Artifact signing
* Immutable container images
* Versioned deployment configuration
* GitOps promotion
* Traceable releases

The goal is to establish provenance from source code to the artifact running in the cluster.

---

## Observability

The platform uses **OpenTelemetry** to propagate distributed traces across services implemented in:

* Python
* .NET
* Java
* Node.js

The observability stack includes:

| Component     | Purpose                                           |
| ------------- | ------------------------------------------------- |
| OpenTelemetry | Distributed tracing and telemetry instrumentation |
| Prometheus    | Metrics collection and system behaviour           |
| Grafana       | Dashboards and visualization                      |
| Loki          | Centralized log investigation                     |

These signals support:

* Distributed tracing
* Failure propagation analysis
* Latency analysis
* Capacity planning
* SLO measurement
* Error-budget tracking
* Incident investigation
* Reliability engineering

---

## Senior Engineering Problems Addressed

The project focuses on engineering boundaries that become critical when AI systems move beyond prototypes.

### AI and RAG

* Tenant-aware retrieval
* Vector and hybrid search
* Retrieval authorization
* Agentic RAG
* Multi-agent orchestration
* Bounded agent execution

### Security

* Deterministic authorization around probabilistic AI
* Federated workload identity
* Least-privilege access
* Secret reduction
* Private connectivity
* Tenant isolation

### Platform Engineering

* Infrastructure as Code
* Kubernetes workload design
* Helm packaging
* Environment overlays
* GitOps reconciliation
* Kubernetes scaling

### Software Delivery

* CI/CD separation of responsibilities
* Immutable releases
* Artifact signing
* SBOM generation
* Software supply-chain security
* GitOps promotion

### Reliability Engineering

* Distributed tracing
* Failure propagation
* SLO and error-budget design
* Load and capacity analysis
* High availability
* Disaster recovery

### Operations and Cost

* Observability
* Incident analysis
* Capacity planning
* FinOps
* Production governance

---

## Repository Philosophy

The architecture is built around several engineering principles:

1. **LLM output is a proposal, not authority.**
2. **Identity replaces embedded credentials.**
3. **Authorization is deterministic even when AI behaviour is probabilistic.**
4. **Agents operate within explicit execution boundaries.**
5. **Infrastructure is reproducible and version controlled.**
6. **Artifacts are immutable and traceable.**
7. **CI builds; GitOps deploys.**
8. **Production systems must be observable by design.**
9. **Reliability and recovery are architectural requirements, not operational afterthoughts.**
10. **Cloud-specific dependencies should remain behind well-defined platform boundaries.**

---

## Run the Demo

Clone the repository:

```bash
git clone https://github.com/armsah/Azure-AI-Platform-Engineering.git
cd Azure-AI-Platform-Engineering
```

Run the Python storage demo:

```bash
cd python/storage-demo

python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app:app --reload
```

The FastAPI application will then be available through the local Uvicorn development server.

---

## Technology Stack

| Area           | Technologies                                            |
| -------------- | ------------------------------------------------------- |
| AI / LLM       | Azure AI Foundry, Azure OpenAI                          |
| Retrieval      | Azure AI Search                                         |
| Storage        | Azure Blob Storage                                      |
| API            | FastAPI                                                 |
| Identity       | Microsoft Entra ID, Managed Identity, Workload Identity |
| Secrets        | Azure Key Vault                                         |
| Containers     | Docker                                                  |
| Registry       | Azure Container Registry                                |
| Kubernetes     | Azure Kubernetes Service                                |
| Packaging      | Helm                                                    |
| Configuration  | Kustomize                                               |
| GitOps         | Flux                                                    |
| Infrastructure | Terraform, Bicep                                        |
| CI/CD          | Jenkins, GitHub Actions, Azure DevOps, GitLab           |
| Observability  | OpenTelemetry, Prometheus, Grafana, Loki                |
| Languages      | Python, .NET, Java, Node.js                             |

---

## Future Improvements

The next stage extends the existing platform into a more integrated production AI product.

Planned areas include:

* Authenticated frontend
* Centralized AI Gateway
* Stronger tenant controls
* GraphRAG
* Real MCP server/client communication
* Durable agent workflows
* Event-driven agent execution
* Data Loss Prevention (DLP)
* AI governance
* AIOps
* Controlled automated remediation
* Progressive delivery
* Multi-region recovery
* End-to-end production acceptance testing

---

## Multi-Cloud Direction

The architecture is intentionally designed to reduce Azure-specific coupling.

Portable components include:

* Kubernetes workloads
* Container images
* Helm charts
* Application APIs and contracts
* OpenTelemetry instrumentation
* Core application logic

Cloud-specific infrastructure and managed-service integrations are isolated behind Infrastructure as Code and platform boundaries.

The next multi-cloud stage validates the same workload model across:

```text
Azure AKS
   │
   ├────────► AWS EKS
   │
   └────────► Google GKE
```

This involves mapping Azure-specific capabilities to equivalent AWS and Google Cloud services across:

* Identity
* Container registries
* Kubernetes
* Networking
* Secrets management
* AI/model services
* Search and retrieval
* Storage and data services
* Observability

The objective is to validate portability **without redesigning the application core**.

---

## Engineering Goal

This repository is not intended to demonstrate only how to call an LLM API.

It demonstrates how to engineer the surrounding platform required to make AI systems **secure, deployable, observable, recoverable, governed, and operable in production**.

The progression is:

```text
AI Prototype
     │
     ▼
RAG Application
     │
     ▼
Secure AI Service
     │
     ▼
Agentic AI
     │
     ▼
Containerized Platform
     │
     ▼
Kubernetes + GitOps
     │
     ▼
Observable & Reliable Platform
     │
     ▼
Production AI Engineering
     │
     ▼
Multi-Cloud AI Platform
```

---

## License

See the repository license for usage and distribution terms.
