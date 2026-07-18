"""
Base schema for all Pydantic models.

Centralizes configuration, serialization, and validation behavior for all
API schemas. Every schema in app/schemas/ should inherit from BaseSchema
to ensure consistent behavior across:
- Field naming (snake_case in Python, camelCase in JSON)
- Datetime serialization (ISO 8601 UTC)
- UUID serialization (string)
- Input parsing (both snake_case and camelCase accepted)

Traces to: 07-Backend-Development-Standards §9 (API schemas)
Traces to: 05-API-Specification §17.4 (timestamp conventions)
See: E2.T9 acceptance criteria
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


class BaseSchema(BaseModel):
    """Base schema for all API models.

    Centralizes Pydantic configuration for:
    - populate_by_name: Accepts both snake_case (Python) and
      camelCase (JSON) in requests
    - from_attributes: Allows construction from ORM models
    - Datetime serialization: ISO 8601 UTC format with microseconds

    All API schemas should inherit from this base to ensure consistent
    configuration and serialization behavior.

    Example:
        >>> from app.schemas.base import BaseSchema
        >>> from pydantic import Field
        >>> from uuid import UUID
        >>>
        >>> class MySchema(BaseSchema):
        ...     my_id: UUID
        ...     created_at: datetime
        ...
        >>> # Both snake_case and camelCase work in requests
        >>> data1 = MySchema.model_validate({"my_id": "...", "created_at": "..."})
        >>> data2 = MySchema.model_validate({"myId": "...", "createdAt": "..."})
    """

    model_config = ConfigDict(
        populate_by_name=True,  # Accept both snake_case and camelCase in input
        from_attributes=True,  # Allow construction from ORM models (obj.field syntax)
    )

    @field_serializer("*", mode="wrap")
    def serialize_datetime_fields(
        self,
        value: Any,  # noqa: ANN401
        handler: Any,  # noqa: ANN401
        info: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        """Serialize datetime fields to ISO 8601 UTC format.

        Format: YYYY-MM-DDTHH:mm:ss.ffffffZ (microseconds + Z suffix)

        Ensures:
        - Timezone-aware datetimes are converted to UTC
        - Naive datetimes assumed to be UTC
        - Microsecond precision preserved
        - Always suffixed with Z (UTC indicator)

        Args:
            value: Field value to serialize
            handler: Pydantic field serializer handler
            info: Serialization context

        Returns:
            Serialized value (formatted datetime for datetime
            fields, original for others)
        """
        # Only handle datetime fields
        if not isinstance(value, datetime):
            return handler(value)

        if value is None:
            return None

        # Ensure timezone-aware (convert to UTC if needed)
        if value.tzinfo is None:
            # Naive datetime assumed to be UTC
            value = value.replace(tzinfo=UTC)
        else:
            # Convert to UTC if in different timezone
            value = value.astimezone(UTC)

        # Format as ISO 8601 with microseconds and Z suffix
        return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
