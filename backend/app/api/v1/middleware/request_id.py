"""
Request ID middleware.

Generates or propagates the X-Request-ID header on every request,
ensuring every log entry and error response can be correlated to
a specific request.

See: 07-Backend-Development-Standards §4 (middleware — request ID).
See: 08-Security-Architecture §7 (X-Request-ID for forensic tracing).
See: 10-Observability-Architecture §4 (correlation IDs).
"""

import time
import uuid

from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

from app.infrastructure.logging import get_logger, set_request_id


REQUEST_ID_HEADER = "X-Request-ID"

logger = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that ensures every request has an X-Request-ID.

    If the client supplies an X-Request-ID header, it is preserved.
    If not, a new UUIDv4 is generated. The ID is attached to the
    request state (for downstream access) and included in the response.

    This provides the correlation ID foundation required by:
    - Structured logging (Doc 07 §10)
    - Error responses (requestId field in Error schema)
    - Audit trails (Doc 08 §10)
    - Distributed tracing (Doc 10 §6)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Extract or generate request ID and propagate it."""
        request_id = request.headers.get(REQUEST_ID_HEADER)
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store on request state for access by route handlers,
        # exception handlers, and logging
        request.state.request_id = request_id

        # Store in contextvars for automatic inclusion in all logs
        set_request_id(request_id)

        # Log request start
        start_time = time.perf_counter()
        logger.info(
            "request_started",
            extra={
                "fields": {
                    "method": request.method,
                    "path": str(request.url.path),
                    "query": str(request.url.query) if request.url.query else None,
                }
            },
        )

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id

        # Log request completion with duration
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "request_completed",
            extra={
                "fields": {
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            },
        )

        return response
