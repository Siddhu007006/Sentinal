"""
API v1 aggregate router.

Collects all v1 route modules into a single router that is
included by the application factory. New route modules are
added here as they are implemented in later Epics.

See: 06-Repository-Structure §4 (app/api/v1/).
See: 07-Backend-Development-Standards §4 (route organization).
See: backend/openapi.yaml (tags define the route modules).
"""

from fastapi import APIRouter

from app.api.v1.routes import health


api_v1_router = APIRouter()

# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------
# Each include corresponds to one tag group in backend/openapi.yaml.
# Routes are registered in the order they appear in the OpenAPI spec.
#
# Future Epics will add:
#   api_v1_router.include_router(auth.router, prefix="/auth")
#   api_v1_router.include_router(users.router, prefix="/users")
#   api_v1_router.include_router(uploads.router, prefix="/uploads")
#   api_v1_router.include_router(assets.router, prefix="/assets")
#   api_v1_router.include_router(analyzers.router, prefix="/analyzers")
#   api_v1_router.include_router(analyses.router, prefix="/analyses")
#   api_v1_router.include_router(reports.router, prefix="/reports")
#   api_v1_router.include_router(audit_logs.router, prefix="/audit-logs")
# ---------------------------------------------------------------------------

# Health has no prefix — it lives at /health per openapi.yaml
api_v1_router.include_router(health.router)
