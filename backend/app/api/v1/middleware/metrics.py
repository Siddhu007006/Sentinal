"""Prometheus metrics middleware.

Instrument HTTP requests with Prometheus metrics:
- Request count by method, endpoint, status code
- Request latency by method, endpoint

Source: 10-Observability-Architecture §5 (Metrics Collection)
Source: 22-Engineering-Backlog E11.T1 (Metrics Collection)
"""

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import http_request_duration_seconds, http_requests_total


# Paths to exclude from metrics instrumentation
_EXCLUDED_PATHS = {"/metrics", "/health", "/api/v1/health"}


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to instrument HTTP requests with Prometheus metrics."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and record metrics."""
        start_time = time.time()

        # Process the request
        response = await call_next(request)

        # Skip instrumentation for health check and metrics endpoints
        if request.url.path in _EXCLUDED_PATHS:
            return response

        # Calculate duration
        duration = time.time() - start_time

        # Get route pattern if available, otherwise use path
        route_pattern = request.scope.get("route", request.url.path)
        if hasattr(route_pattern, "path"):
            endpoint = route_pattern.path
        else:
            endpoint = request.url.path

        # Record metrics
        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=response.status_code,
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)

        return response
