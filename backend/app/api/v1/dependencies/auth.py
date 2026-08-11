"""Authentication and authorization middleware dependencies.

FastAPI dependency injection for declarative authentication and authorization
per design.md § Authentication Middleware and Requirement 4 in requirements.md:

- get_current_user: Extracts and validates Bearer token, returns authenticated User
- require_role: Factory returning dependency that validates user's role

Usage in route handlers:
    ```python
    @router.get("/users/{user_id}")
    async def get_user(
        user_id: UUID,
        current_user: User = Depends(get_current_user),
    ) -> UserResponse:
        # current_user is injected; token already validated, user is active
        return UserResponse.from_domain(current_user)

    @router.post("/users")
    async def create_user(
        payload: CreateUserRequest,
        current_user: User = Depends(get_current_user),
        _: User = Depends(require_role("admin")),
    ) -> UserResponse:
        # Both dependencies validated: user authenticated AND has admin role
        # If not admin, gets 403 Forbidden before handler is called
        return ...
    ```

Traces to: 07-Backend-Development-Standards §4 (dependency injection)
Traces to: 08-Security-Architecture §5 (authorization checks)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Header, HTTPException, status

from app.core.dependencies import get_user_repository
from app.domain.entities.user import User  # noqa: TC001
from app.infrastructure.security.jwt import (
    InvalidTokenError,
    TokenExpiredError,
    TokenService,
)


if TYPE_CHECKING:
    from collections.abc import Callable

    from app.domain.repositories.user import UserRepository


async def get_current_user(
    authorization: str | None = Header(None),
    user_repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> User:
    """FastAPI dependency that extracts and validates Bearer token.

    Validates the Authorization header contains a valid Bearer token, decodes
    the JWT, and loads the corresponding User from the repository. Performs
    all re-checks per Requirement 4:
    - Token exists and has valid format (Bearer <token>)
    - Token signature is valid
    - Token has not expired
    - User exists in repository
    - User is active (is_active=True)

    Postconditions:
    - Returns User object if all checks pass
    - Raises 401 Unauthorized if header missing/malformed/invalid/expired
    - Raises 401 Unauthorized if user not found or inactive

    Args:
        authorization: Authorization header value (from FastAPI Header)
        user_repo: UserRepository dependency for user lookup

    Returns:
        User entity if authenticated and active

    Raises:
        HTTPException: 401 Unauthorized if auth fails (missing header,
            malformed format, invalid token, expired token, user not found,
            inactive user)

    Example:
        ```python
        @router.get("/profile")
        async def get_profile(
            current_user: User = Depends(get_current_user)
        ) -> UserResponse:
            return UserResponse.from_domain(current_user)
        ```
    """
    # Check Authorization header exists
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse Bearer token from header
    # Expected format: "Bearer <token>"
    parts = authorization.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Decode and validate token
    token_service = TokenService()
    try:
        payload = token_service.decode_token(token)
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Load user from repository by user_id from token
    try:
        user = await user_repo.get_by_id(payload.sub)
    except Exception as e:
        # User not found or database error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or access denied",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Re-check user is active (do not trust token claims alone)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(
    required_roles: str | list[str],
) -> Callable[[User], User]:
    """Factory that returns a FastAPI dependency checking user's role.

    Creates a dependency that validates the authenticated user's role matches
    one of the required roles. Supports both single role (string) and multiple
    roles (list) per Requirement 4.

    Raises 403 Forbidden if user's role is not in required_roles.

    The returned dependency must be used with Depends() in route handlers:

    ```python
    @router.delete("/users/{user_id}")
    async def delete_user(
        user_id: UUID,
        current_user: User = Depends(get_current_user),
        _: User = Depends(require_role("admin")),
    ) -> None:
        # Both get_current_user and require_role("admin") validated
        # If current_user.role != "admin", gets 403 Forbidden
        # Handler only called if both dependencies pass
        await user_repo.delete(user_id)
    ```

    Multiple roles:
    ```python
    _: User = Depends(require_role(["admin", "analyst"]))
    # Passes if user.role is "admin" OR "analyst"
    ```

    Args:
        required_roles: Single role string or list of role strings
            (e.g., "admin" or ["admin", "analyst"])

    Returns:
        Async dependency function that validates role and returns User

    Raises:
        HTTPException: 403 Forbidden if user's role not in required_roles

    Example:
        ```python
        # Single role
        @router.get("/audit-logs")
        async def list_audit_logs(
            current_user: User = Depends(get_current_user),
            _: User = Depends(require_role("admin")),
        ) -> list[AuditLogResponse]:
            # Only admins can access
            return ...

        # Multiple roles
        @router.post("/analyses")
        async def create_analysis(
            current_user: User = Depends(get_current_user),
            _: User = Depends(require_role(["admin", "analyst"])),
        ) -> AnalysisResponse:
            # Admins and analysts can create (viewers cannot)
            return ...
        ```
    """
    # Normalize required_roles to list
    roles = [required_roles] if isinstance(required_roles, str) else required_roles

    # Convert to UserRole enum values for comparison
    required_role_values = list(roles)

    async def role_check(current_user: User) -> User:
        """Inner dependency that checks role and returns user or raises 403.

        Args:
            current_user: Authenticated user (from get_current_user)

        Returns:
            User if role matches required_roles

        Raises:
            HTTPException: 403 Forbidden if role mismatch
        """
        if current_user.role.value not in required_role_values:
            role_list = ", ".join(required_role_values)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role(s): {role_list}",
            )
        return current_user

    return role_check  # type: ignore[return-value]
