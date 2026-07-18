"""
Logging infrastructure — structured JSON logging with correlation support.

Provides the foundation for Sentinel's observability through structured logging:
- JSON-formatted log output with consistent field schema
- Request ID (correlation ID) support via contextvars (async-safe)
- Sensitive data redaction at the logging layer
- Context propagation for request-scoped data
- Configurable log levels from Settings

This module is the sole point of logging configuration. All application
code (API, Application, Domain, Infrastructure layers) obtains loggers
through get_logger() from this module.

Key components:

logger.py — Logger factory (get_logger, configure_logging) using standard
    Python logging.Logger with filters and formatters.

formatters.py — SentinelJSONFormatter (JSON output) and
    SentinelPlainFormatter (development readable output).

filters.py — SensitiveDataFilter (redacts passwords/tokens via recursive
    field inspection), and ContextFilter (adds request IDs from contextvars).

request_context.py — Async-safe context storage using contextvars (PEP 567):
    set_request_id(), get_request_id(), set_context_value(), get_context_value(),
    clear_request_context().

Usage:

from app.infrastructure.logging import get_logger
from app.infrastructure.logging.request_context import set_request_id

# In a FastAPI route (E2.T1 will integrate this):
set_request_id(request.headers.get("X-Request-ID") or str(uuid4()))
logger = get_logger(__name__)
logger.info("request_received", extra={"fields": {"path": request.url.path}})

# In any layer (request ID automatically included):
logger = get_logger(__name__)
logger.info("upload_completed", extra={"fields": {"upload_id": upload.id}})
# Output: {"timestamp": "2025-01-15T...", "logger": "app.api.routes",
#          "message": "upload_completed", "request_id": "abc-123", "upload_id": "xyz"}

See: 10-Observability-Architecture §4 (logging architecture).
See: 07-Backend-Development-Standards §10 (logging standards).
See: 08-Security-Architecture §10 (sensitive data redaction).
See: 06-Repository-Structure §7 (app/infrastructure/logging).
"""

from app.infrastructure.logging.filters import (
    ContextFilter,
    SensitiveDataFilter,
)
from app.infrastructure.logging.formatters import (
    SentinelJSONFormatter,
    SentinelPlainFormatter,
)
from app.infrastructure.logging.logger import (
    configure_logging,
    get_logger,
)
from app.infrastructure.logging.request_context import (
    clear_request_context,
    get_context_all,
    get_context_value,
    get_request_id,
    set_context_value,
    set_request_id,
)


__all__ = [  # noqa: RUF022
    # Filters
    "ContextFilter",
    "SensitiveDataFilter",
    # Formatters
    "SentinelJSONFormatter",
    "SentinelPlainFormatter",
    # Logger factory
    "configure_logging",
    "get_logger",
    # Context (async-safe via contextvars)
    "clear_request_context",
    "get_context_all",
    "get_context_value",
    "get_request_id",
    "set_context_value",
    "set_request_id",
]
