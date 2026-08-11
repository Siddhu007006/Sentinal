"""
Authentication route handlers.

FastAPI router for authentication endpoints:
- POST /auth/register (public)
- POST /auth/login (public)
- POST /auth/refresh (refresh-token authenticated)
- POST /auth/logout (access-token authenticated)
- GET /auth/me (access-token authenticated)

All endpoints use RFC 7807 Problem Details format for errors.
All endpoints validate request bodies with Pydantic schemas.
All protected endpoints use FastAPI Depends() for declarative auth.

Traces to: Requirement 6 in requirements.md
Traces to: design.md § Auth Flows
Traces to: 07-Backend-Development-Standards §4 (route structure)
Traces to: 05-API-Specification.md §2-3 (endpoint definitions)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.dependencies.auth import get_current_user
from app.application.services.auth_service import (
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
    PasswordTooWeakError,
)
from app.core.dependencies import (
    get_audit_log_repository,
    get_refresh_token_repository,
    get_user_repository,
)
from app.domain.exceptions import TokenAlreadyRotatedError
from app.domain.services.audit_service import AuditService
from app.infrastructure.security.jwt import TokenService
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPairResponse,
    UserResponse,
)


if TYPE_CHECKING:
    from app.domain.repositories.audit_log import AuditLogRepository
    from app.domain.repositories.refresh_token import RefreshTokenRepository
    from app.domain.repositories.user import UserRepository

from app.domain.entities.user import User  # noqa: TC001


router = APIRouter(tags=["auth"])


def _get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),  # noqa: B008
    refresh_token_repo: RefreshTokenRepository = Depends(  # noqa: B008
        get_refresh_token_repository
    ),
    audit_log_repo: AuditLogRepository = Depends(  # noqa: B008
        get_audit_log_repository
    ),
) -> AuthService:
    """Dependency factory that creates AuthService with all dependencies."""
    token_service = TokenService()
    audit_service = AuditService(audit_log_repo)
    return AuthService(
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
        token_service=token_service,
        audit_service=audit_service,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Register a new user with email and password. "
        "Returns the created user profile (without password hash)."
    ),
)
async def register(
    payload: RegisterRequest,
    auth_service: AuthService = Depends(_get_auth_service),  # noqa: B008
) -> UserResponse:
    """
    Register a new user account.

    **Request Body:**
    - `email`: User's email address (must be unique and valid format)
    - `password`: Password (minimum 12 characters)
    - `full_name`: User's full name (optional)

    **Success Response (201 Created):**
    - Returns registered user with id, email, full_name, role
      (defaults to "viewer"), created_at
    - Does NOT include password_hash

    **Error Responses:**
    - 400 Bad Request: Validation error (invalid email, weak password)
    - 409 Conflict: Email already registered

    **Example:**
    ```
    POST /api/v1/auth/register
    Content-Type: application/json

    {
        "email": "alice@sentinel.local",
        "password": "SuperSecureP@ss123",
        "full_name": "Alice Smith"
    }

    Response (201):
    {
        "userId": "550e8400-e29b-41d4-a716-446655440000",
        "email": "alice@sentinel.local",
        "fullName": "Alice Smith",
        "role": "viewer",
        "createdAt": "2024-02-10T08:00:00Z"
    }
    ```
    """
    try:
        user = await auth_service.register(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )

        return UserResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            created_at=user.created_at,
        )

    except DuplicateEmailError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    except PasswordTooWeakError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e


@router.post(
    "/login",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and get tokens",
    description=(
        "Authenticate user with email and password. "
        "Returns access token (15min) and refresh token (30day)."
    ),
)
async def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(_get_auth_service),  # noqa: B008
) -> TokenPairResponse:
    """
    Authenticate user and issue token pair.

    **Request Body:**
    - `email`: User's email address
    - `password`: User's password

    **Success Response (200 OK):**
    - Returns TokenPair with access_token and refresh_token
    - access_token: Short-lived JWT (15 minutes)
    - refresh_token: Long-lived JWT (30 days)

    **Error Responses:**
    - 401 Unauthorized: Invalid credentials

    **Example:**
    ```
    POST /api/v1/auth/login
    Content-Type: application/json

    {
        "email": "alice@sentinel.local",
        "password": "SuperSecureP@ss123"
    }

    Response (200):
    {
        "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```
    """
    try:
        access_token, refresh_token = await auth_service.login(
            email=payload.email,
            password=payload.password,
        )

        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from e


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description=(
        "Exchange valid refresh token for new access and refresh token. "
        "Implements token rotation."
    ),
)
async def refresh(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(_get_auth_service),  # noqa: B008
) -> TokenPairResponse:
    """
    Refresh authentication tokens using a refresh token.

    **Request Body:**
    - `refresh_token`: Valid refresh token from previous login or refresh

    **Success Response (200 OK):**
    - Returns new TokenPair with fresh tokens
    - Old refresh_token is revoked immediately

    **Error Responses:**
    - 401 Unauthorized: Token expired, revoked, or invalid
    - 409 Conflict: Token concurrently rotated by another request
      (retry not recommended)

    **Example:**
    ```
    POST /api/v1/auth/refresh
    Content-Type: application/json

    {
        "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }

    Response (200):
    {
        "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```
    """
    try:
        access_token, refresh_token = await auth_service.refresh(
            refresh_token=payload.refresh_token,
        )

        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    except TokenAlreadyRotatedError as e:
        # Token was concurrently rotated by another request
        # Return 409 Conflict to indicate request conflict (not authentication failure)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Refresh token was concurrently rotated by another request",
        ) from e

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from e


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out user (revoke session)",
    description="Revoke user's refresh token(s) to log out.",
)
async def logout(
    payload: LogoutRequest,
    logout_all: bool = Query(False),
    current_user: User = Depends(get_current_user),  # noqa: B008
    auth_service: AuthService = Depends(_get_auth_service),  # noqa: B008
) -> None:
    """
    Log out authenticated user by revoking refresh token(s).

    **Request Body (optional):**
    - `refresh_token`: Specific token to revoke (for device-specific logout)

    **Query Parameters (optional):**
    - `logout_all`: Set to `true` to log out from all devices

    **Success Response (204 No Content):**
    - Returns empty body on success

    **Error Responses:**
    - 401 Unauthorized: Missing or invalid access token

    **Example:**
    ```
    POST /api/v1/auth/logout
    Authorization: Bearer <access_token>
    Content-Type: application/json

    {
        "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }

    Response: 204 No Content
    ```
    """
    await auth_service.logout(
        user_id=current_user.id,
        user_role=current_user.role,
        refresh_token=payload.refresh_token if payload else None,
        logout_all=logout_all,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user profile",
    description="Return the authenticated user's profile information.",
)
async def get_me(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserResponse:
    """
    Get authenticated user's profile.

    **Request:**
    - No body
    - Requires Bearer token in Authorization header

    **Success Response (200 OK):**
    - Returns user profile with id, email, full_name, role, created_at
    - Does NOT include password_hash

    **Error Responses:**
    - 401 Unauthorized: Missing or invalid access token

    **Example:**
    ```
    GET /api/v1/auth/me
    Authorization: Bearer <access_token>

    Response (200):
    {
        "userId": "550e8400-e29b-41d4-a716-446655440000",
        "email": "alice@sentinel.local",
        "fullName": "Alice Smith",
        "role": "viewer",
        "createdAt": "2024-02-10T08:00:00Z"
    }
    ```
    """
    return UserResponse(
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        created_at=current_user.created_at,
    )
