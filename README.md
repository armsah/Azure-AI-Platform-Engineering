# Azure AI Platform Engineering

## What problem is solved?

This project demonstrates how to engineer secure, scalable and observable enterprise AI applications instead of treating an LLM as an isolated API.

It combines Generative AI with production cloud engineering: RAG, agents, tenant isolation, identity, Kubernetes, CI/CD, security, observability, reliability and cost-aware operation.

## What is the architecture?

The platform is a cloud-native monorepo centered on **Azure and Kubernetes**, while applying cloud-portable architecture patterns.

The AI layer uses **FastAPI, Azure AI Foundry/OpenAI, Azure AI Search, embeddings, hybrid RAG, reranking, Agentic AI, multi-agent workflows, tool calling, multimodal AI, structured outputs, HITL, evaluation and red-teaming**.

The platform uses **AKS, Docker, Terraform, Bicep, Helm, Kustomize, Flux GitOps, ACR, Key Vault, Entra ID, RBAC and Workload Identity**.

CI/CD spans **Jenkins, GitHub Actions, Azure DevOps and GitLab CI/CD**. Observability uses **OpenTelemetry, Prometheus, Grafana and Loki**.

Multi-cloud engineering includes portable Kubernetes/application patterns and architecture mappings for **Azure, AWS and GCP**, including AKS/EKS/GKE and cloud-neutral Terraform concepts.

## What senior engineering problems were solved?

Key engineering areas include tenant-aware RAG, bounded agent execution, multi-agent delegation, model routing, distributed budgets, circuit breaking, AI evaluation, red-teaming, federated identity, DevSecOps, SBOM/signing, immutable releases, GitOps, autoscaling, network security, distributed tracing, SLI/SLOs, HA/DR, incident analysis, load testing and FinOps.

A core principle is: **LLM output is a proposal, not authority.**

## How can I run or inspect the demo?

```bash
git clone https://github.com/armsah/Azure-AI-Platform-Engineering.git
cd Azure-AI-Platform-Engineering/python/storage-demo
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app:app --reload
