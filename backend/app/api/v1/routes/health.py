"""
Health check route.

Implements GET /health as defined in backend/openapi.yaml.
This endpoint is unauthenticated (security: []) and returns
basic liveness information.

See: backend/openapi.yaml paths./health.get
See: 06-Repository-Structure §4 (routes/health.py).
See: 10-Observability-Architecture §7 (health endpoints).
"""

import os
from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas.health import HealthResponse


router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Get service health",
    operation_id="getHealthStatus",
)
async def get_health_status() -> HealthResponse:
    """Return basic service liveness status.

    This endpoint confirms the API process is running and responding.
    Infrastructure dependency checks (database, queue, storage) are
    not implemented here — they belong to later Epics when those
    adapters exist.

    Returns:
        HealthResponse with status 'ok', current version, and timestamp.
    """
    return HealthResponse(
        status="ok",
        version=os.environ.get("APP_VERSION", "0.0.0-dev"),
        timestamp=datetime.now(UTC),
    )
