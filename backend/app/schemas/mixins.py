"""
Reusable schema mixins for common field patterns.

Mixins provide consistent behavior for frequently used field combinations
across multiple schemas. All mixins inherit from BaseSchema to ensure
consistent configuration and serialization.

Traces to: 05-API-Specification §17.4 (timestamp conventions)
See: E2.T9 acceptance criteria
"""

from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class TimestampMixin(BaseSchema):
    """Mixin adding standard created_at and updated_at timestamp fields.

    Both fields are datetime objects serialized to ISO 8601 UTC format
    with camelCase aliases for JSON responses.

    Used by resource schemas that include audit timestamps.

    Example:
        >>> class AssetSchema(TimestampMixin):
        ...     id: UUID
        ...     filename: str
        ...     # Inherits created_at and updated_at
        >>>
        >>> # JSON output will have: createdAt, updatedAt
    """

    created_at: datetime = Field(
        ...,
        alias="createdAt",
        description="Timestamp when the resource was created (UTC)",
    )
    updated_at: datetime = Field(
        ...,
        alias="updatedAt",
        description="Timestamp when the resource was last updated (UTC)",
    )
