"""
User management route handlers.

FastAPI router for user management endpoints:
- GET /users (admin-only, paginated list)
- GET /users/{userId} (admin or user, 404 on forbidden for enumeration
  prevention)
- PATCH /users/{userId} (admin or user, role changes admin-only)
- DELETE /users/{userId} (admin-only soft-delete)

All endpoints use RFC 7807 Problem Details format for errors.
All endpoints validate request bodies with Pydantic schemas.
All protected endpoints use FastAPI Depends() for declarative auth.

Traces to: Requirement 5 in requirements.md
Traces to: design.md § User Management
Traces to: 07-Backend-Development-Standards §4 (route structure)
Traces to: 05-API-Specification.md §2-3 (endpoint definitions)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  # Runtime import: FastAPI resolves path param

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.dependencies.auth import get_current_user, require_role
from app.application.services.user_service import (
    RoleChangeForbiddenError,
    UserNotFoundError,
    UserService,
)
from app.core.dependencies import (
    get_audit_log_repository,
    get_refresh_token_repository,
    get_user_repository,
)
from app.domain.entities.user import User  # noqa: TC001
from app.domain.services.audit_service import AuditService
from app.schemas.auth import (
    PaginationInfo,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)


if TYPE_CHECKING:
    from app.domain.repositories.audit_log import AuditLogRepository
    from app.domain.repositories.refresh_token import RefreshTokenRepository
    from app.domain.repositories.user import UserRepository


router = APIRouter(tags=["users"])


def _get_user_service(
    user_repo: UserRepository = Depends(get_user_repository),  # noqa: B008
    refresh_token_repo: RefreshTokenRepository = Depends(  # noqa: B008
        get_refresh_token_repository
    ),
    audit_log_repo: AuditLogRepository = Depends(  # noqa: B008
        get_audit_log_repository
    ),
) -> UserService:
    """Dependency factory that creates UserService with all dependencies."""
    return UserService(
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
        audit_service=AuditService(audit_log_repo),
    )


@router.get(
    "",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all users (admin-only)",
    description="Return paginated list of all users. Admin-only endpoint.",
)
async def list_users(
    limit: int = Query(
        50,
        ge=1,
        le=100,
        description="Number of users to return per page (default 50, max 100)",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of users to skip (pagination offset, default 0)",
    ),
    current_user: User = Depends(get_current_user),  # noqa: B008
    _: User = Depends(require_role("admin")),  # noqa: B008
    user_repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> UserListResponse:
    """
    List all users with pagination (admin-only endpoint).

    **Query Parameters:**
    - `limit`: Maximum users per page (default 50, min 1, max 100)
    - `offset`: Number of users to skip (default 0)

    **Success Response (200 OK):**
    - Returns paginated list of users with pagination metadata
    - Excludes soft-deleted users (deleted_at IS NOT NULL)
    - Excludes inactive users (is_active=False)

    **Error Responses:**
    - 401 Unauthorized: Missing or invalid access token
    - 403 Forbidden: User is not admin

    **Example:**
    ```
    GET /api/v1/users?limit=10&offset=0
    Authorization: Bearer <admin_access_token>

    Response (200):
    {
        "items": [
            {
                "userId": "550e8400-e29b-41d4-a716-446655440000",
                "email": "alice@sentinel.local",
                "fullName": "Alice Smith",
                "role": "analyst",
                "createdAt": "2024-02-10T08:00:00Z"
            },
            {
                "userId": "660e8400-e29b-41d4-a716-446655440001",
                "email": "bob@sentinel.local",
                "fullName": "Bob Johnson",
                "role": "viewer",
                "createdAt": "2024-02-11T09:30:00Z"
            }
        ],
        "paginationInfo": {
            "total": 42,
            "limit": 10,
            "offset": 0
        }
    }
    ```
    """
    # Query users from repository with pagination
    # list_active_users filters out is_active=False and deleted_at IS NOT NULL
    users, total = await user_repo.list_active_users(
        skip=offset,
        limit=limit,
        sort_by="created_at",
        sort_order="desc",
    )

    # Build response with items and pagination info
    user_responses = [
        UserResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            created_at=user.created_at,
        )
        for user in users
    ]

    pagination = PaginationInfo(
        total=total,
        limit=limit,
        offset=offset,
    )

    return UserListResponse(
        items=user_responses,
        pagination_info=pagination,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user profile (admin or user themself)",
    description=(
        "Return user profile. Admin can view any user. "
        "Non-admin users can only view their own profile. "
        "Non-owner non-admin → 404 Not Found (prevents enumeration)."
    ),
)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),  # noqa: B008
    user_repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> UserResponse:
    """
    Get user profile by ID.

    **Authorization Rules:**
    - Admin users can view any user profile
    - Non-admin users can only view their own profile
    - Non-owner non-admin users get 404 Not Found (prevents user enumeration)

    **Path Parameters:**
    - `user_id`: UUID of the user to retrieve

    **Success Response (200 OK):**
    - Returns user profile: userId, email, fullName, role, createdAt
    - Excludes password_hash and other secrets

    **Error Responses:**
    - 401 Unauthorized: Missing or invalid access token
    - 404 Not Found: User not found OR requesting user has no permission to access
      (404 used for both "not found" and "forbidden" to prevent enumeration)

    **Security Notes:**
    - Returns 404 instead of 403 to prevent user enumeration attacks
    - Soft-deleted users (deleted_at IS NOT NULL) return 404
    - Inactive users (is_active=False) return 404
    - Non-admin non-owner access returns 404 (not 403)

    **Example:**
    ```
    GET /api/v1/users/550e8400-e29b-41d4-a716-446655440000
    Authorization: Bearer <access_token>

    Response (200):
    {
        "userId": "550e8400-e29b-41d4-a716-446655440000",
        "email": "alice@sentinel.local",
        "fullName": "Alice Smith",
        "role": "analyst",
        "createdAt": "2024-02-10T08:00:00Z"
    }

    Response (404):
    {
        "type": "about:blank",
        "status": 404,
        "title": "Not Found",
        "detail": "User not found"
    }
    ```
    """
    # Try to get the user from repository
    try:
        user = await user_repo.get_by_id(user_id)
    except Exception as exc:
        # User not found, soft-deleted, or inactive
        # Return 404 for enumeration prevention
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc

    # Authorization check: only admin or the user themself can access
    # Both conditions must be checked:
    # 1. current_user.role == "admin" → admin can access any user
    # 2. current_user.id == user_id → user can access their own profile
    is_admin = current_user.role.value == "admin"
    is_owner = current_user.id == user_id

    if not (is_admin or is_owner):
        # Non-owner non-admin user trying to access another user's profile
        # Return 404 (not 403) to prevent enumeration
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Build and return the response
    return UserResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        created_at=user.created_at,
    )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user profile (admin or user themself)",
    description=(
        "Update a user's profile. Owner can change profile fields; "
        "role changes are admin-only. Non-admin attempting a role change "
        "gets 403 Forbidden. Non-owner non-admin gets 404 Not Found "
        "(prevents enumeration)."
    ),
)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    user_service: UserService = Depends(_get_user_service),  # noqa: B008
) -> UserResponse:
    """
    Update a user's profile and/or role.

    **Authorization Rules:**
    - Admin can update any user (including roles)
    - Non-admin can update only their own profile fields
    - Non-admin attempting a role change → 403 Forbidden
    - Non-owner non-admin → 404 Not Found (prevents enumeration)

    **Request Body (partial update):**
    - `fullName`: New full name (optional)
    - `role`: New role, admin-only (optional)

    **Success Response (200 OK):**
    - Returns updated user profile

    **Error Responses:**
    - 401 Unauthorized: Missing or invalid access token
    - 403 Forbidden: Non-admin attempting a role change
    - 404 Not Found: User not found OR no permission to access

    **Audit:**
    - Role changes create an audit log entry with old and new role
    """
    try:
        updated = await user_service.update_user(
            actor=current_user,
            user_id=user_id,
            full_name=payload.full_name,
            role=payload.role,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    except RoleChangeForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can change user roles",
        ) from exc

    return UserResponse(
        user_id=updated.id,
        email=updated.email,
        full_name=updated.full_name,
        role=updated.role.value,
        created_at=updated.created_at,
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate user (admin-only soft-delete)",
    description=(
        "Soft-delete a user account (admin-only). Sets is_active=False "
        "and deleted_at=<now>, revokes all refresh tokens immediately. "
        "Soft-deleted users return 404 in all queries."
    ),
)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_role("admin")),  # noqa: B008
    user_service: UserService = Depends(_get_user_service),  # noqa: B008
) -> None:
    """
    Deactivate a user account (admin-only soft-delete).

    **Authorization Rules:**
    - Admin-only; non-admin → 403 Forbidden
    - Sets is_active=False and deleted_at=<now>

    **Side Effects:**
    - All refresh tokens for the user are revoked immediately
    - All user sessions become invalid
    - Deactivation creates an audit log entry

    **Success Response (204 No Content):**
    - No response body

    **Error Responses:**
    - 401 Unauthorized: Missing or invalid access token
    - 403 Forbidden: User is not admin
    - 404 Not Found: User not found, inactive, or already soft-deleted
    """
    try:
        await user_service.deactivate_user(
            actor=current_user,
            user_id=user_id,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
