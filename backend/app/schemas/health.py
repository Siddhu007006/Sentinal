"""
Health check response schema.

Mirrors the HealthStatus schema from backend/openapi.yaml exactly.
Used by the GET /health endpoint.

See: backend/openapi.yaml components/schemas/HealthStatus.
See: 10-Observability-Architecture §7 (health endpoints).
"""

from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class HealthResponse(BaseSchema):
    """Service health status response.

    Matches backend/openapi.yaml components/schemas/HealthStatus.

    Fields:
        status: One of 'ok', 'degraded', 'unavailable'.
        version: Application version string.
        timestamp: Current server time in UTC.
        dependencies: Status of infrastructure dependencies.
                      Not populated in this Epic — belongs to later Epics.
    """

    status: str = Field(..., examples=["ok"])
    version: str = Field(..., examples=["1.0.0"])
    timestamp: datetime
    dependencies: dict[str, str] | None = Field(
        default=None,
        description=(
            "Status of critical infrastructure dependencies. "
            "Populated when infrastructure health checks are implemented."
        ),
    )
