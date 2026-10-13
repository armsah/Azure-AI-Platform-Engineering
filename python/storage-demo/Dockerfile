FROM python:3.14-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir \
    -r requirements.txt \
    "msgpack>=1.2.1" \
    "setuptools>=78.1.1" \
    "urllib3>=2.8.0"


FROM python:3.14-slim AS runtime

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip uninstall -y pip \
    && rm -rf /usr/local/lib/python3.14/ensurepip

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
RUN /opt/venv/bin/pip uninstall -y pip setuptools

ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=10001:10001 *.py ./
COPY agents ./agents

RUN useradd --create-home --uid 10001 appuser

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]