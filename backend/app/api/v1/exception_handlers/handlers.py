"""
Centralized exception handlers.

Translates Python exceptions into the standardized Error envelope
defined in backend/openapi.yaml. Every error response from the API
passes through these handlers, ensuring consistent shape.

See: 07-Backend-Development-Standards §4 (exception handling).
See: 07-Backend-Development-Standards §9 (error response consistency).
See: 06-Repository-Structure §4 (exception_handlers/).
See: backend/openapi.yaml components/schemas/Error.
"""

import uuid
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.schemas.error import ErrorBody, ErrorDetail, ErrorResponse


def _get_request_id(request: Request) -> str:
    """Extract request ID from request state, falling back to a new UUID.

    The RequestIdMiddleware should have already set this, but we
    handle the edge case defensively.
    """
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def _build_error_response(
    request: Request,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> dict[str, object]:
    """Construct the standard Error envelope as a serializable dict."""
    response = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details),
        request_id=uuid.UUID(_get_request_id(request)),
        timestamp=datetime.now(UTC),
    )
    return response.model_dump(mode="json", by_alias=True)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle Starlette/FastAPI HTTP exceptions.

    Converts framework-raised HTTPExceptions (404, 405, etc.) into
    the standardized Error envelope. This ensures even framework-level
    errors (like method not allowed) use the same response shape as
    application-level errors.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_response(
            request=request,
            code=_status_to_code(exc.status_code),
            message=str(exc.detail) if exc.detail else "An error occurred.",
        ),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors.

    Converts FastAPI's RequestValidationError (raised when request
    body/query/path fails schema validation) into the Error envelope
    with field-level detail.

    See: 07-Backend-Development-Standards §4 (validation via Pydantic).
    """
    details = [
        ErrorDetail(
            field=".".join(str(loc) for loc in err.get("loc", [])),
            issue=err.get("msg", "Validation error."),
        )
        for err in exc.errors()
    ]

    return JSONResponse(
        status_code=422,
        content=_build_error_response(
            request=request,
            code="validation_error",
            message="One or more fields failed validation.",
            details=details,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions.

    Returns a generic 500 Internal Server Error without leaking
    internal details to the caller. The full exception is intended
    to be logged at ERROR level by the logging infrastructure
    (implemented in a later Epic).

    See: 07-Backend-Development-Standards §9 (catch-all handler).
    See: 08-Security-Architecture §7 (no stack traces to clients).
    """
    return JSONResponse(
        status_code=500,
        content=_build_error_response(
            request=request,
            code="internal_server_error",
            message="An unexpected error occurred.",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized exception handlers on the FastAPI app.

    Called during application factory setup. Order matters:
    1. Specific framework exceptions first (validation, HTTP)
    2. Generic catch-all last

    This function is the single point of registration — exception
    handlers are never added ad hoc by individual routes.
    """
    app.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)


def _status_to_code(status_code: int) -> str:
    """Map HTTP status codes to human-readable error codes.

    These codes appear in the Error envelope's 'code' field and
    are meant for programmatic consumption by API clients.
    """
    code_map: dict[int, str] = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        413: "payload_too_large",
        415: "unsupported_media_type",
        422: "validation_error",
        429: "rate_limit_exceeded",
        500: "internal_server_error",
        503: "service_unavailable",
    }
    return code_map.get(status_code, f"error_{status_code}")
