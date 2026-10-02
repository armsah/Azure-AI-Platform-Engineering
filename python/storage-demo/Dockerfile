FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py rag_service.py agent_service.py tool_service.py security_context.py observability.py model_router.py resilience.py ./
COPY agents ./agents

# Create an unprivileged application user
RUN useradd --create-home --uid 10001 appuser

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]