# ===========================================================================
# Sentinel Backend — Multi-Stage Dockerfile (canonical)
# ===========================================================================
#
# This is the canonical production Dockerfile. The project definition
# (pyproject.toml + uv.lock) lives at the repo root; the app source is
# under backend/app and is installed into the venv as the `app` wheel
# package (no source copy needed in the runtime image).
#
# Build strategy:
#   Stage 1 (builder): resolve dependencies and build the project wheel
#   Stage 2 (runtime): copy only the installed venv
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
# Stage 1: Builder — install dependencies and the application
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Build argument for version tagging
ARG APP_VERSION=0.0.0-dev

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv for fast, reproducible dependency resolution
# (pinned major version for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /build

# Copy only the dependency specification first (layer caching):
# changes to app source do NOT invalidate the dependency layer.
COPY pyproject.toml uv.lock ./

# Install production dependencies into a standalone virtual environment.
# --frozen: fail if the lock file is out of date (reproducibility)
RUN uv venv /opt/venv && \
    UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --no-dev --frozen --no-install-project

# Copy application source and install the project wheel into the venv
COPY backend/app ./backend/app
RUN UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --no-dev --frozen


# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal production image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Labels for container metadata
LABEL org.opencontainers.image.title="sentinel-backend" \
      org.opencontainers.image.description="Sentinel Digital Asset Analysis Platform — Backend" \
      org.opencontainers.image.source="https://github.com/sentinel/sentinel" \
      org.opencontainers.image.version="${APP_VERSION}"

ARG APP_VERSION=0.0.0-dev

# Runtime environment variables
# Source: 07-Backend-Development-Standards §10 (structured logging)
# Source: 08-Security-Architecture §9 (no secrets baked into image)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${APP_VERSION} \
    APP_NAME=sentinel

# Create non-root user
# Source: 08-Security-Architecture §9 (container runs as non-root)
RUN groupadd --gid 1000 sentinel && \
    useradd --uid 1000 --gid sentinel --shell /bin/bash --create-home sentinel

# Copy the installed virtualenv (application included as the app wheel)
COPY --from=builder /opt/venv /opt/venv

WORKDIR /home/sentinel
RUN chown -R sentinel:sentinel /home/sentinel

# Switch to non-root user
USER sentinel

# Expose the API port
# Source: backend/openapi.yaml server URL (localhost:8000)
EXPOSE 8000

# Default command: uvicorn serving the app package from the venv
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
