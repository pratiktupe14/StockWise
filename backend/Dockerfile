# Multi-stage production Dockerfile for StockWise Backend
FROM python:3.12-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final minimal runtime image
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/stockwise/.local/bin:$PATH \
    PORT=8000

# Install runtime PostgreSQL client library and curl for health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /bin/bash stockwise

# Copy installed python wheels from builder
COPY --from=builder --chown=stockwise:stockwise /root/.local /home/stockwise/.local

# Copy application code and Alembic migrations
COPY --chown=stockwise:stockwise alembic.ini .
COPY --chown=stockwise:stockwise alembic/ alembic/
COPY --chown=stockwise:stockwise app/ app/

USER stockwise

EXPOSE 8000

# Container readiness healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/ready || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
