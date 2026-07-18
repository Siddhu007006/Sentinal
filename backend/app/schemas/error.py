"""
Error response schemas.

Mirrors the Error and ErrorDetail schemas from backend/openapi.yaml exactly.
Used by centralized exception handlers to produce consistent error envelopes.

See: 07-Backend-Development-Standards §9 (error response consistency).
See: backend/openapi.yaml components/schemas/Error.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class ErrorDetail(BaseSchema):
    """Individual field-level validation error.

    Matches backend/openapi.yaml components/schemas/ErrorDetail.
    """

    field: str | None = Field(default=None, examples=["email"])
    issue: str | None = Field(default=None, examples=["must be a valid email address"])


class ErrorBody(BaseSchema):
    """Inner error object containing code, message, and optional details.

    Matches the nested 'error' object within the Error schema.
    """

    code: str = Field(..., examples=["validation_error"])
    message: str = Field(..., examples=["One or more fields failed validation."])
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseSchema):
    """Standardized error envelope returned by all error responses.

    Every error response from the API uses this exact shape, regardless
    of which layer originated the error. This is enforced by centralized
    exception handlers, not by individual route handlers.

    Matches backend/openapi.yaml components/schemas/Error exactly:
    - error: {code, message, details?}
    - requestId: UUID
    - timestamp: datetime
    """

    error: ErrorBody
    request_id: UUID = Field(
        ..., alias="requestId", examples=["5b6c7d8e-9f01-4a2b-8c3d-4e5f60718293"]
    )
    timestamp: datetime = Field(..., examples=["2024-02-10T08:00:00Z"])
