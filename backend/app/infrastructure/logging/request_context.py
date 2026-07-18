"""
Request context management for correlation IDs and async-aware context.

Provides async-safe storage for request-scoped data (request IDs,
user identifiers, etc.) that can be accessed from any layer without
being passed as parameters.

Uses Python's contextvars module (PEP 567) for proper async context
isolation. Each async task (request) gets its own context, even when
running on the same OS thread, which is essential for FastAPI and
ASGI applications.

See: 10-Observability-Architecture §4 (context propagation).
See: 07-Backend-Development-Standards §10 (correlation IDs).
"""

import uuid
from contextvars import ContextVar
from typing import Any


# ContextVar for storing the request ID per async context
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# ContextVar for arbitrary context data (None by default, initialized on first set)
_context_data_var: ContextVar[dict[str, Any] | None] = ContextVar(
    "context_data", default=None
)


def set_request_id(request_id: str) -> None:
    """Set the request ID (correlation ID) for this request context.

    Args:
        request_id: The correlation ID to use for all logs in this request.

    See: 10-Observability-Architecture §4 (correlation IDs).
    """
    _request_id_var.set(request_id)


def get_request_id() -> str:
    """Get the request ID (correlation ID) from context.

    Returns the X-Request-ID if set, or generates a new UUIDv4 if not.
    This uses contextvars, so each async task has its own value.

    Returns:
        The correlation ID for this request context.

    Example:
        request_id = get_request_id()  # Auto-generates if not set
        logger.info("event", extra={"request_id": request_id})

    See: 10-Observability-Architecture §4 (correlation IDs).
    """
    request_id = _request_id_var.get()
    if not request_id:
        request_id = str(uuid.uuid4())
        _request_id_var.set(request_id)
    return request_id


def set_context_value(key: str, value: object) -> None:
    """Set an arbitrary value in the request context.

    Args:
        key: The key to store under.
        value: The value to store.

    Example:
        set_context_value("user_id", current_user.id)
        user_id = get_context_value("user_id")
    """
    data = _context_data_var.get() or {}
    data[key] = value
    _context_data_var.set(data)


def get_context_value(key: str, default: object = None) -> object:
    """Get a value from the request context.

    Args:
        key: The key to retrieve.
        default: Default value if key is not present.

    Returns:
        The stored value, or default if not present.
    """
    data = _context_data_var.get()
    if data is None:
        return default
    return data.get(key, default)


def get_context_all() -> dict[str, object]:
    """Get a copy of all context data.

    Returns:
        A dictionary of all context data, or empty dict if no context set.
    """
    data = _context_data_var.get()
    return data.copy() if data is not None else {}


def clear_request_context() -> None:
    """Clear the request context for the current async task.

    Called at the end of request processing (e.g., in middleware) to
    clean up context. Unlike thread-local storage, contextvars are
    automatically garbage-collected when the async task completes,
    so this is mainly for explicit cleanup if needed.

    In practice, this is often optional with contextvars, but provided
    for consistency and explicit lifecycle management.
    """
    _request_id_var.set(None)
    _context_data_var.set({})
