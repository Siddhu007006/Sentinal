"""
Authentication request and response schemas.

Pydantic models for API contracts for authentication endpoints:
- RegisterRequest, UserResponse (for POST /auth/register)
- LoginRequest, TokenPairResponse (for POST /auth/login)
- RefreshTokenRequest, TokenPairResponse (for POST /auth/refresh)
- LogoutRequest (for POST /auth/logout)

Traces to: Requirement 6 in requirements.md
Traces to: 07-Backend-Development-Standards §4 (Pydantic schemas)
Traces to: backend/openapi.yaml (exact response schemas)
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from pydantic import Field

from app.schemas.base import BaseSchema


class RegisterRequest(BaseSchema):
    """Request body for POST /auth/register.

    User registration with email, password, and optional full name.
    """

    email: str = Field(
        ...,
        examples=["alice@sentinel.local"],
        description="User's email address",
    )
    password: str = Field(
        ...,
        min_length=12,
        examples=["SuperSecureP@ss123"],
        description="Password must be at least 12 characters",
    )
    full_name: str | None = Field(
        None,
        examples=["Alice Smith"],
        description="User's full name (optional)",
    )


class UserResponse(BaseSchema):
    """User profile response.

    Returned by POST /auth/register, GET /auth/me, GET /users/{userId}.
    Does NOT include password_hash or any secrets.
    """

    user_id: UUID = Field(
        ...,
        alias="userId",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    email: str = Field(..., examples=["alice@sentinel.local"])
    full_name: str | None = Field(
        None,
        alias="fullName",
        examples=["Alice Smith"],
    )
    role: str = Field(
        ...,
        examples=["viewer"],
        description="One of: admin, analyst, viewer",
    )
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        examples=["2024-02-10T08:00:00Z"],
    )


class LoginRequest(BaseSchema):
    """Request body for POST /auth/login.

    User authentication with email and password.
    """

    email: str = Field(..., examples=["alice@sentinel.local"])
    password: str = Field(..., examples=["SuperSecureP@ss123"])


class TokenPairResponse(BaseSchema):
    """Response body for POST /auth/login and POST /auth/refresh.

    Contains access token (short-lived) and refresh token (long-lived).
    """

    access_token: str = Field(
        ...,
        alias="accessToken",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJleHAiOjE3MDc1MzA0MDB9"
        ],
        description="Short-lived JWT access token (15 minutes)",
    )
    refresh_token: str = Field(
        ...,
        alias="refreshToken",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJleHAiOjE3MDc1MzA0MDB9"
        ],
        description="Long-lived JWT refresh token (30 days)",
    )


class RefreshTokenRequest(BaseSchema):
    """Request body for POST /auth/refresh.

    Contains the refresh token needed to obtain new access and refresh tokens.
    """

    refresh_token: str = Field(
        ...,
        alias="refreshToken",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJleHAiOjE3MDc1MzA0MDB9"
        ],
        description="Refresh token from previous login or refresh",
    )


class LogoutRequest(BaseSchema):
    """Request body for POST /auth/logout.

    Optional refresh token for device-specific logout.
    If not provided, must use query param ?logout_all=true for logout all.
    """

    refresh_token: str | None = Field(
        None,
        alias="refreshToken",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJleHAiOjE3MDc1MzA0MDB9"
        ],
        description="Refresh token to revoke (for device-specific logout)",
    )


class PaginationInfo(BaseSchema):
    """Pagination metadata for list responses.

    Includes pagination information: total count, limit, and offset.
    Used by paginated endpoints like GET /users.
    """

    total: int = Field(
        ...,
        examples=[100],
        description="Total number of items (across all pages)",
    )
    limit: int = Field(
        ...,
        examples=[50],
        description="Maximum items per page",
    )
    offset: int = Field(
        ...,
        examples=[0],
        description="Number of items skipped (pagination offset)",
    )


class UserListResponse(BaseSchema):
    """Response body for GET /users (admin-only, paginated).

    Contains paginated list of users with pagination metadata.
    """

    items: list[UserResponse] = Field(
        ...,
        description="List of users on this page",
    )
    pagination_info: PaginationInfo = Field(
        ...,
        description="Pagination metadata",
    )
