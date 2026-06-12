FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium --with-deps

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# ── API target ───────────────────────────────────────────────────────────────
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--loop", "uvloop"]

# ── Worker target ─────────────────────────────────────────────────────────────
FROM base AS worker
CMD ["celery", "-A", "src.workers.celery_app", "worker", \
     "--loglevel=info", "--concurrency=4", \
     "--queues=${WORKER_QUEUE:-ingest,pipeline}"]
