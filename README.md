# Azure AI Platform Engineering

## What problem is solved?

This project demonstrates how to engineer secure, scalable, and observable AI applications on Azure rather than treating an LLM as an isolated API.

It combines Generative AI with production cloud engineering, addressing RAG, agent execution, tenant isolation, identity, CI/CD, Kubernetes deployment, security, observability, reliability, and cost-aware operation.

## What is the architecture?

The platform is a cloud-native monorepo centered on Azure and Kubernetes.

The Python/FastAPI AI application integrates **Azure AI Foundry/OpenAI, Azure AI Search, Blob Storage, RAG, hybrid retrieval, embeddings, Agentic AI, multi-agent workflows, tool calling, multimodal processing, and HITL controls**.

Infrastructure uses **AKS, Docker, Terraform, Bicep, Helm, Kustomize, Flux GitOps, Azure Container Registry, Key Vault, VNet, Private Endpoints, Entra ID, RBAC, Managed Identity, and Workload Identity**.

Delivery is implemented across **Jenkins, GitHub Actions, Azure DevOps, and GitLab CI/CD**.

Observability uses **OpenTelemetry, Prometheus, Grafana, and Loki**.

## What senior engineering problems were solved?

The project implements production-oriented engineering patterns including:

- Tenant-aware RAG and authorization
- Agentic and multi-agent AI with bounded execution
- Model routing, budgets, circuit breaking, and AI evaluation
- AI red-teaming and controlled tool execution
- Federated CI identity and workload identity
- Infrastructure as Code and GitOps
- DevSecOps, SBOMs, signing, and immutable artifacts
- Kubernetes autoscaling, network policies, and reliability controls
- Distributed tracing across Python, .NET, Java, and Node.js
- SLI/SLO, error budgets, incident analysis, HA/DR, load and capacity testing

A central principle is that **LLM output is a proposal, not authority**. Security and authorization remain deterministic application/platform responsibilities.

## How can I run or inspect the demo?

Clone and test:

```bash
git clone https://github.com/armsah/Azure-AI-Platform-Engineering.git
cd Azure-AI-Platform-Engineering/python/storage-demo
python -m venv .venv
python -m pip install -r requirements.txt
python -m pytest -q
