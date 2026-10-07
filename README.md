# Azure AI Platform Engineering

## What problem is solved?

This project builds a production-oriented platform for enterprise AI workloads. It addresses the gap between an AI prototype and an operational system: secure access, tenant-isolated knowledge, controlled agent actions, repeatable infrastructure, safe software delivery, observability, resilience and recovery.

The objective is to make AI workloads deployable and operable using the same engineering controls expected from production cloud services.

## What is the architecture?

The project starts with a **FastAPI application** exposing AI and RAG APIs. Azure AI Foundry/OpenAI provides model inference and embeddings, while **Azure AI Search** implements keyword, vector and hybrid retrieval. Blob Storage provides source data.

The application evolves into **agentic RAG and multi-agent workflows**. Agents can reason and propose actions, but application policies control tool authorization, execution budgets, delegation and HITL approval. Entra ID, RBAC and Workload Identity establish trusted identities without embedding Azure credentials in workloads.

The application is containerized with **Docker**, stored as immutable images in **Azure Container Registry**, and deployed to **AKS**. Helm packages Kubernetes resources, Kustomize represents environment differences, and Flux continuously reconciles Git with the cluster.

**Terraform and Bicep** provision the underlying cloud platform: networking, AKS, identity, private connectivity, Key Vault and supporting Azure resources.

Jenkins, GitHub Actions, Azure DevOps and GitLab validate the same delivery model: test → security scan → build → SBOM/sign → immutable artifact → GitOps promotion. CI builds artifacts; **Flux performs deployment**, preventing CI from directly mutating production.

Finally, **OpenTelemetry** propagates traces across Python, .NET, Java and Node.js services. Prometheus measures system behaviour, Grafana visualizes it, and Loki supports log investigation. These signals feed SLO, capacity, incident and reliability analysis.

## What senior engineering problems were solved?

The project addresses boundaries that become critical beyond prototypes: tenant-aware retrieval, deterministic authorization around probabilistic AI, bounded agent execution, federated identity, supply-chain security, immutable releases, GitOps ownership, Kubernetes scaling, distributed tracing, failure propagation, SLO/error-budget design, load/capacity analysis, HA/DR and FinOps.

A central design rule is: **LLM output is a proposal, not authority.**

## How can I run or inspect the demo?

```bash
git clone https://github.com/armsah/Azure-AI-Platform-Engineering.git
cd Azure-AI-Platform-Engineering/python/storage-demo

python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app:app --reload

## Future improvements

The project extends the existing platform into an integrated production product: authenticated frontend, centralized AI Gateway, stronger tenant controls, GraphRAG, real MCP server/client communication, durable and event-driven agent workflows, DLP/governance, AIOps, controlled remediation, progressive delivery, multi-region recovery and end-to-end production acceptance.

The architecture is also designed to reduce Azure-specific coupling. Kubernetes workloads, containers, Helm, OpenTelemetry and application contracts remain portable, while cloud-specific infrastructure is isolated behind IaC and platform boundaries.

The next multi-cloud stage validates the same workload model across AKS, AWS EKS and Google GKE, mapping Azure-specific identity, registry, networking, secrets, AI and data services to AWS/GCP equivalents without redesigning the application core.
