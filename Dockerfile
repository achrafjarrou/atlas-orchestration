# Multi-stage build: Builder (~800MB) → Runtime (~200MB)
FROM python:3.11-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir poetry==1.8.0
COPY pyproject.toml poetry.lock* ./
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

FROM python:3.11-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY atlas/ ./atlas/
COPY scripts/ ./scripts/
RUN useradd -m -u 1000 atlasuser && chown -R atlasuser:atlasuser /app
USER atlasuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "atlas.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]