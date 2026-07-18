"""
Pagination schemas for list endpoints.

Provides generic PaginatedResponse for wrapping list results with
pagination metadata (page, pageSize, total, totalPages).

Traces to: 05-API-Specification §4 (pagination)
See: E2.T9 acceptance criteria
"""

from typing import Generic, TypeVar

from pydantic import Field

from app.schemas.base import BaseSchema


T = TypeVar("T")


class PaginatedResponse(BaseSchema, Generic[T]):  # noqa: UP046
    """Generic paginated response wrapper.

    Wraps a list of items with pagination metadata. Used by all list
    endpoints to provide consistent pagination information.

    Type Parameters:
        T: The schema type of individual items in the list

    Fields:
        items: List of items for the current page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        pageSize: Number of items per page
        totalPages: Total number of pages

    Example:
        >>> from typing import Generic, TypeVar
        >>> from uuid import UUID
        >>> from app.schemas.pagination import PaginatedResponse
        >>>
        >>> class AssetSchema(BaseSchema):
        ...     id: UUID
        ...     filename: str
        >>>
        >>> # Create response
        >>> response = PaginatedResponse[AssetSchema](
        ...     items=[asset1, asset2],
        ...     total=150,
        ...     page=1,
        ...     pageSize=10,
        ...     totalPages=15,
        ... )
        >>>
        >>> # JSON output: items, total, page, pageSize, totalPages
    """

    items: list[T] = Field(
        ...,
        description="Items for the current page",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of items across all pages",
    )
    page: int = Field(
        ...,
        alias="page",
        ge=1,
        description="Current page number (1-indexed)",
    )
    page_size: int = Field(
        ...,
        alias="pageSize",
        ge=1,
        description="Number of items per page",
    )
    total_pages: int = Field(
        ...,
        alias="totalPages",
        ge=0,
        description="Total number of pages",
    )

