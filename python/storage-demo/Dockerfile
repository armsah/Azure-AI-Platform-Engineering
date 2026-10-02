FROM python:3.14-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.14-slim AS runtime

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY app.py rag_service.py agent_service.py tool_service.py security_context.py observability.py model_router.py resilience.py conversation_service.py reranker.py agentic_rag.py multi_agent.py approval_service.py mcp_policy.py agent_contracts.py agent_budget.py circuit_breaker.py production_model_router.py memory_service.py multimodal.py multi_agent_eval.py red_team.py ./
COPY agents ./agents

RUN useradd --create-home --uid 10001 appuser

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]