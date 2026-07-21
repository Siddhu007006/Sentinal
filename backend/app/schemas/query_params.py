"""
Query parameter schemas for list endpoints.

Provides validation and parsing for sort and filter parameters used
in query strings (e.g., ?sort=createdAt:desc&filter=status:active).

Traces to: 05-API-Specification §4 (query parameters)
See: E2.T9 acceptance criteria
"""

from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema


class SortParam(BaseSchema):
    """Sort parameter schema for list endpoints.

    Represents a single sort specification in format: field:direction.

    Fields:
        field: Field name to sort by (e.g., createdAt, filename)
        direction: Sort direction (asc for ascending, desc for descending)

    Example:
        >>> sort = SortParam(field="createdAt", direction="desc")
        >>> # Represents: sort=createdAt:desc in query string
    """

    field: str = Field(
        ...,
        min_length=1,
        description="Field name to sort by",
    )
    direction: Literal["asc", "desc"] = Field(
        default="asc",
        description="Sort direction (asc or desc)",
    )

    @classmethod
    def from_string(cls, sort_string: str) -> SortParam:
        """Parse sort parameter from query string format.

        Format: field:direction (e.g., createdAt:desc)

        Args:
            sort_string: Sort specification string

        Returns:
            SortParam instance

        Raises:
            ValueError: If format is invalid

        Example:
            >>> sort = SortParam.from_string("createdAt:desc")
            >>> sort.field
            'createdAt'
            >>> sort.direction
            'desc'
        """
        if ":" not in sort_string:
            # Default to ascending if direction not specified
            return cls(field=sort_string, direction="asc")

        field, direction = sort_string.split(":", 1)
        return cls(field=field.strip(), direction=direction.strip())  # type: ignore

    def to_string(self) -> str:
        """Serialize sort parameter to query string format.

        Returns:
            Sort specification string (e.g., createdAt:desc)
        """
        return f"{self.field}:{self.direction}"


class FilterParam(BaseSchema):
    """Filter parameter schema for list endpoints.

    Represents a single filter condition. The specific filter types
    depend on the resource being filtered (e.g., status, createdAfter).

    Fields:
        field: Field name to filter by
        operator: Comparison operator (eq for equals, gte for >=, etc.)
        value: Filter value

    Example:
        >>> filter_param = FilterParam(field="status", operator="eq", value="active")
        >>> # Represents: filter=status:eq:active in query string
    """

    field: str = Field(
        ...,
        min_length=1,
        description="Field name to filter by",
    )
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "contains"] = Field(
        default="eq",
        description="Comparison operator",
    )
    value: str = Field(
        ...,
        min_length=1,
        description="Filter value",
    )

    @classmethod
    def from_string(cls, filter_string: str) -> FilterParam:
        """Parse filter parameter from query string format.

        Format: field:operator:value or field:value (defaults operator to eq)
        Examples: status:eq:active, created_after:gte:2025-01-01

        Args:
            filter_string: Filter specification string

        Returns:
            FilterParam instance

        Raises:
            ValueError: If format is invalid
        """
        parts = filter_string.split(":", 2)

        if len(parts) == 2:
            # Format: field:value (operator defaults to eq)
            field, value = parts
            return cls(field=field.strip(), operator="eq", value=value.strip())
        elif len(parts) == 3:
            # Format: field:operator:value
            field, operator, value = parts
            return cls(
                field=field.strip(),
                operator=operator.strip(),  # type: ignore
                value=value.strip(),
            )
        else:
            raise ValueError(
                f"Invalid filter format: {filter_string}. "
                "Expected field:value or field:operator:value"
            )

    def to_string(self) -> str:
        """Serialize filter parameter to query string format.

        Returns:
            Filter specification string (e.g., status:eq:active)
        """
        return f"{self.field}:{self.operator}:{self.value}"
