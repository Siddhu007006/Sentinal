"""
Rate limiting middleware for API request throttling.

Implements per-IP rate limiting using Redis as the backing store.
Tracks requests per minute and returns 429 Too Many Requests when limits are
exceeded.

**Window Algorithm**: Fixed 60-second window (NOT sliding window).
Each IP gets a separate Redis key per minute bucket. The counter expires after
60 seconds. Different minute buckets (e.g., :12345600 vs :12345661) are
independent counters.

**Atomicity**: Redis INCR is atomic. TTL is set only on first increment.
Race condition between INCR returning 1 and EXPIRE is acceptable because:
- EXPIRE is idempotent (setting on an already-expiring key just updates TTL)
- Both requests increment the same counter either way
- Worst case: counter lives slightly longer than 60s (still acceptable)

**Trust Model for X-Forwarded-For**:
This middleware trusts the X-Forwarded-For header ONLY when deployed behind
a trusted proxy (load balancer, reverse proxy). The assumption is that:
1. The proxy is configured to append X-Forwarded-For headers
2. Untrusted clients cannot inject X-Forwarded-For headers directly
3. The application is deployed such that client requests ALWAYS come through the proxy

If deployed without a trusted proxy, clients can spoof X-Forwarded-For headers
and bypass rate limiting. Review deployment configuration before enabling.

See: docs/22-Engineering-Backlog.md E2.T7
See: 08-Security-Architecture §7 (rate limiting)
See: backend/openapi.yaml 429 TooManyRequests response
"""

import logging
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

import redis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.settings import RateLimitSettings


logger = logging.getLogger(__name__)

# Paths excluded from rate limiting (health checks, docs, etc.)
DEFAULT_EXCLUDE_PATHS = [
    "/api/v1/health",
    "/api/v1/docs",
    "/api/v1/redoc",
    "/api/v1/openapi.json",
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis counters.

    Implements per-IP rate limiting with configurable limits for:
    - Authenticated requests
    - Unauthenticated requests

    **Window Algorithm**: Fixed 60-second window (NOT sliding).
    Each IP has a Redis key per minute bucket (based on Unix timestamp / 60).
    When the minute bucket changes, a new counter starts (old one expires
    automatically).

    **Atomicity Notes**:
    - INCR: Atomic by Redis design
    - EXPIRE: Called only when INCR returns 1 (first increment)
    - Race: Between INCR==1 and EXPIRE is acceptable because EXPIRE is idempotent

    See: 08-Security-Architecture §7 (rate limiting requirements)
    See: E2.T7 acceptance criteria
    """

    def __init__(
        self,
        app: ASGIApp,
        settings: RateLimitSettings,
        redis_url: str | None = None,
    ) -> None:
        """Initialize rate limiting middleware.

        Args:
            app: FastAPI/Starlette application
            settings: Rate limit configuration (authenticated/unauthenticated limits)
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
        """
        super().__init__(app)
        self.settings = settings
        self.redis_url = redis_url or os.environ.get(
            "REDIS_URL",
            "redis://localhost:6379/0",
        )
        self.exclude_paths = DEFAULT_EXCLUDE_PATHS
        self._redis_error_logged = False  # Track if we've logged Redis errors

        # Initialize Redis connection
        try:
            self.redis: Any = redis.from_url(self.redis_url, decode_responses=True)  # type: ignore
            # Test connection
            self.redis.ping()
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis at startup: {e}", exc_info=True)
            self.redis = None

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Handle rate limiting for incoming requests.

        Args:
            request: Incoming HTTP request
            call_next: Callable to invoke next middleware/handler

        Returns:
            Response (429 if rate limited, or next handler's response)
        """
        # Skip rate limiting for excluded paths
        logger.warning(f"RATE LIMIT PATH: {request.url.path}")
        if self._should_exclude_path(request.url.path):
            response = await call_next(request)
            return response

        # Get client identifier (IP address)
        client_ip = self._get_client_ip(request)
        if not client_ip:
            # If we can't identify the client, skip rate limiting (fail-open)
            response = await call_next(request)
            return response

        # Determine if request is from authenticated user
        is_authenticated = (
            hasattr(request.state, "user") and request.state.user is not None
        )

        # Get configured limit
        limit = (
            self.settings.authenticated_requests_per_minute
            if is_authenticated
            else self.settings.unauthenticated_requests_per_minute
        )

        # Create Redis counter key (IP-based, per-minute window)
        counter_key = f"rate_limit:{client_ip}:{self._get_minute_bucket()}"

        try:
            if self.redis is None:
                # Redis not available, fail-open
                response = await call_next(request)
                return response

            # Increment counter in Redis (atomic operation)
            current_count = self.redis.incr(counter_key)

            # Set expiration on first increment (60-second window)
            # Race condition here is acceptable: EXPIRE is idempotent
            if current_count == 1:
                self.redis.expire(counter_key, 60)

            # Check if limit exceeded
            if current_count > limit:
                return self._create_rate_limit_response(request)

            # Request is within limit, proceed
            response = await call_next(request)
            return response

        except redis.ConnectionError:
            # If Redis is unavailable, fail-open (allow request)
            # Log the error once to avoid flooding logs during outages
            if not self._redis_error_logged:
                logger.warning(
                    "Rate limiting disabled: Redis connection failed. "
                    "Requests will not be rate-limited until Redis is available."
                )
                self._redis_error_logged = True

            response = await call_next(request)
            return response
        except redis.RedisError as e:
            # Other Redis errors: also fail-open
            logger.error(
                f"Rate limiting error: {e}",
                extra={"request_id": getattr(request.state, "request_id", "unknown")},
            )
            response = await call_next(request)
            return response

    def _get_client_ip(self, request: Request) -> str | None:
        """Extract client IP from request.

        **Trust Model**: Checks X-Forwarded-For header ONLY if deployed behind
        a trusted proxy. If X-Forwarded-For header is not trusted in your
        deployment, comment out the X-Forwarded-For check and use only
        request.client.host.

        Checks X-Forwarded-For header first (for proxied requests),
        then falls back to request.client.host.

        Args:
            request: Incoming HTTP request

        Returns:
            Client IP address, or None if unable to determine
        """
        # TRUST MODEL: Only trust X-Forwarded-For if behind a trusted proxy
        # In a direct connection scenario (no proxy), clients can spoof this header
        # See deployment documentation for when to enable/disable X-Forwarded-For
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take first IP (client IP) from comma-separated list
            # Format: client, proxy1, proxy2
            return forwarded_for.split(",")[0].strip()

        # Fall back to request.client.host (direct connection IP)
        if request.client:
            return request.client.host

        return None

    def _get_minute_bucket(self) -> str:
        """Get current minute bucket for rate limit window.

        **Algorithm**: Fixed 60-second window (NOT sliding window).
        Each minute bucket (Unix timestamp / 60) gets its own counter.
        When the timestamp moves to the next 60-second interval, a new counter starts.

        Example:
        - Timestamp 1234567890 (2009-02-13 23:31:30 UTC) → bucket 20576131
        - Timestamp 1234567920 (2009-02-13 23:32:00 UTC) → bucket 20576132 (new!)

        Returns:
            String representing current minute bucket
        """
        # Return minute-based bucket (dividing current timestamp by 60)
        # This creates a new counter every 60 seconds
        return str(int(time.time()) // 60)

    def _should_exclude_path(self, path: str) -> bool:
        """Check if path should be excluded from rate limiting.

        Args:
            path: Request path

        Returns:
            True if path should be excluded, False otherwise
        """
        for exclude_prefix in self.exclude_paths:
            if path.startswith(exclude_prefix):
                return True
        return False

    def _create_rate_limit_response(self, request: Request) -> Response:
        """Create a 429 Too Many Requests response.

        Args:
            request: Incoming HTTP request (for request_id)

        Returns:
            JSONResponse with 429 status and Retry-After header
        """
        # Get request ID from middleware context for correlation
        # RequestIdMiddleware (E2.T4) executes BEFORE this middleware in the stack
        # because it was registered AFTER in the middleware chain.
        # So request.state.request_id should be available.
        request_id = getattr(request.state, "request_id", "unknown")

        # Create error response body (matching RFC 7807 error envelope)
        error_body: dict[str, Any] = {
            "error": {
                "code": "rate_limited",
                "message": "Too many requests. Please retry later.",
                "details": [],
            },
            "requestId": str(request_id),
            "timestamp": self._get_iso_timestamp(),
        }

        # Create response with 429 status
        response = JSONResponse(
            status_code=429,
            content=error_body,
        )

        # Add Retry-After header (RFC 7231)
        # Specifies number of seconds to wait before retrying
        response.headers["Retry-After"] = "60"

        return response

    @staticmethod
    def _get_iso_timestamp() -> str:
        """Get current timestamp in ISO 8601 UTC format.

        Returns:
            ISO 8601 formatted timestamp (e.g., "2025-01-28T10:15:30.123456Z")
        """
        from datetime import UTC, datetime

        return datetime.now(UTC).isoformat(timespec="microseconds")
