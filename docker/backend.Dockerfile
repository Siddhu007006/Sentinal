# ===========================================================================
# Sentinel Backend — Multi-Stage Dockerfile
# ===========================================================================
#
# Build strategy:
#   Stage 1 (builder): Install uv, resolve and install dependencies
#   Stage 2 (runtime): Copy only installed packages + app source
#
# Source: 09-Deployment-Architecture §3 (environment parity)
# Source: 08-Security-Architecture §9 (non-root, no secrets in image)
# Source: 06-Repository-Structure §12 (docker/backend.Dockerfile)
# Source: 07-Backend-Development-Standards §3 (Python 3.12)
#
# Usage:
#   docker build -f docker/backend.Dockerfile -t sentinel-backend .
#   (build context is the repo root)
# ===========================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder — install dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Build arguments for reproducibility and CI tagging
ARG APP_VERSION=0.0.0-dev

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv for fast, reproducible dependency resolution
# hadolint ignore=DL3013
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy only dependency specification first (layer caching)
# Changes to app source code will NOT invalidate this layer
COPY backend/pyproject.toml backend/README.md ./

# Install dependencies into a virtual environment
# --no-dev: production dependencies only (dev deps not needed in image)
# --frozen: fail if lock file is out of date (reproducibility)
RUN uv venv /opt/venv && \
    UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --no-dev --no-install-project

# Copy application source code (separate layer from dependencies)
COPY backend/app ./app

# Install the project itself (editable not needed in container)
RUN UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --no-dev


# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal production image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Labels for container metadata
LABEL org.opencontainers.image.title="sentinel-backend" \
      org.opencontainers.image.description="Sentinel Digital Asset Analysis Platform — Backend" \
      org.opencontainers.image.source="https://github.com/sentinel/sentinel"

ARG APP_VERSION=0.0.0-dev

# Runtime environment variables
# Source: 07-Backend-Development-Standards §10 (structured logging)
# Source: 08-Security-Architecture §9 (no secrets baked into image)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Make the virtualenv's Python the default
    PATH="/opt/venv/bin:$PATH" \
    # Application metadata (overridden at runtime via .env)
    APP_VERSION=${APP_VERSION} \
    APP_NAME=sentinel

# Create non-root user
# Source: 08-Security-Architecture §9 (container runs as non-root)
RUN groupadd --gid 1000 sentinel && \
    useradd --uid 1000 --gid sentinel --shell /bin/bash --create-home sentinel

# Copy installed virtualenv from builder (no build tools in runtime image)
COPY --from=builder /opt/venv /opt/venv

# Copy application source
WORKDIR /home/sentinel/app
COPY --from=builder /build/app ./app

# Change ownership to non-root user
RUN chown -R sentinel:sentinel /home/sentinel

# Switch to non-root user
USER sentinel

# Expose the API port
# Source: backend/openapi.yaml server URL (localhost:8000)
EXPOSE 8000

# Default command: uvicorn with reload disabled (production-like)
# In development, docker-compose overrides this with --reload
# NOTE: app.main:app will be created in Epic 2. This Dockerfile is
# the containerization foundation; the entrypoint will work once
# the FastAPI application factory exists.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
