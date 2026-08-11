"""Unit tests for authentication and authorization middleware dependencies.

Tests the FastAPI dependencies for get_current_user and require_role
per design.md § Authentication Middleware and Requirement 4 in requirements.md.

**Validates: Requirement 4 (Authentication Middleware)**

Traces to: 22-Engineering-Backlog E4.T5
Traces to: design.md § Authentication Middleware
Traces to: 07-Backend-Development-Standards §4 (dependency injection)
"""

from datetime import UTC, datetime
from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.dependencies.auth import get_current_user, require_role
from app.domain.entities.user import User, UserRole
from app.infrastructure.security.jwt import InvalidTokenError, TokenExpiredError


# ===========================================================================
# Fixtures: Test Data
# ===========================================================================


@pytest.fixture
def valid_user_id() -> UUID:
    """Factory fixture for creating valid User IDs."""
    return uuid4()


@pytest.fixture
def valid_user(valid_user_id: UUID) -> User:
    """Factory fixture for creating valid active User instances."""
    return User(
        id=valid_user_id,
        email="user@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
        full_name="Test User",
    )


@pytest.fixture
def inactive_user(valid_user_id: UUID) -> User:
    """Factory fixture for creating inactive User instances."""
    return User(
        id=valid_user_id,
        email="inactive@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.VIEWER,
        is_active=False,
        created_at=datetime.now(tz=UTC),
    )


@pytest.fixture
def admin_user(valid_user_id: UUID) -> User:
    """Factory fixture for creating admin User instances."""
    return User(
        id=valid_user_id,
        email="admin@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )


@pytest.fixture
def analyst_user(valid_user_id: UUID) -> User:
    """Factory fixture for creating analyst User instances."""
    return User(
        id=valid_user_id,
        email="analyst@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.ANALYST,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )


# ===========================================================================
# Tests: get_current_user()
# ===========================================================================


@pytest.mark.asyncio
async def test_get_current_user_valid_token(
    valid_user: User,
) -> None:
    """Test: valid token → returns User.

    Per Requirement 4.9: When token is valid and User is active,
    the dependency returns the User object.
    """
    # Setup mock repository
    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=valid_user)

    # Setup mock token service
    mock_token_service = MagicMock()
    from app.infrastructure.security.jwt import TokenPayload

    payload = TokenPayload(
        sub=valid_user.id,
        role=valid_user.role,
        exp=datetime.now(tz=UTC),
        iat=datetime.now(tz=UTC),
        jti="test-jti",
    )
    mock_token_service.decode_token.return_value = payload

    # Mock TokenService class
    with patch(
        "app.api.v1.dependencies.auth.TokenService",
        return_value=mock_token_service,
    ):
        # Call dependency with valid Bearer token
        header = "Bearer valid.jwt.token"
        user = await get_current_user(
            authorization=header,
            user_repo=mock_repo,
        )

        # Assert user returned
        assert user == valid_user
        assert user.is_active is True
        mock_repo.get_by_id.assert_called_once_with(valid_user.id)


@pytest.mark.asyncio
async def test_get_current_user_missing_header() -> None:
    """Test: missing header → 401 Unauthorized.

    Per Requirement 4.2: When Authorization header is missing,
    the dependency raises 401 Unauthorized.
    """
    mock_repo = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization=None, user_repo=mock_repo)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Missing authorization header" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_malformed_header() -> None:
    """Test: malformed header → 401 Unauthorized.

    Per Requirement 4.3: When Authorization header format is invalid
    (not "Bearer <token>"), the dependency raises 401 Unauthorized.
    """
    mock_repo = AsyncMock()

    # Test various malformed formats
    malformed_headers = [
        "Bearer",  # Missing token
        "bearer token",  # Lowercase bearer with space (ok but wrong format)
        "Basic token",  # Wrong scheme
        "token",  # No scheme
        "Bearer token extra",  # Extra parts
        "",  # Empty
    ]

    for header in malformed_headers:
        if header == "bearer token":
            # This actually passes because bearer is case-insensitive
            continue

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                authorization=header,
                user_repo=mock_repo,
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_expired_token(
    valid_user: User,
) -> None:
    """Test: expired token → 401 Unauthorized.

    Per Requirement 4.4: When token is expired,
    the dependency raises 401 Unauthorized.
    """
    mock_repo = AsyncMock()
    mock_token_service = MagicMock()
    mock_token_service.decode_token.side_effect = TokenExpiredError(
        "Token has expired"
    )

    with patch(
        "app.api.v1.dependencies.auth.TokenService",
        return_value=mock_token_service,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                authorization="Bearer expired.jwt.token",
                user_repo=mock_repo,
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_invalid_signature() -> None:
    """Test: invalid signature → 401 Unauthorized.

    Per Requirement 4.5: When token has an invalid signature,
    the dependency raises 401 Unauthorized.
    """
    mock_repo = AsyncMock()
    mock_token_service = MagicMock()
    mock_token_service.decode_token.side_effect = InvalidTokenError(
        "Invalid signature"
    )

    with patch(
        "app.api.v1.dependencies.auth.TokenService",
        return_value=mock_token_service,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                authorization="Bearer invalid.jwt.token",
                user_repo=mock_repo,
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_user_not_found(
    valid_user: User,
) -> None:
    """Test: user not found → 401 Unauthorized.

    Per Requirement 4.7: When User is not found (user_id in token
    does not exist), the dependency raises 401 Unauthorized.
    """
    mock_repo = AsyncMock()
    mock_repo.get_by_id.side_effect = Exception("User not found")

    mock_token_service = MagicMock()
    from app.infrastructure.security.jwt import TokenPayload

    payload = TokenPayload(
        sub=valid_user.id,
        role=valid_user.role,
        exp=datetime.now(tz=UTC),
        iat=datetime.now(tz=UTC),
        jti="test-jti",
    )
    mock_token_service.decode_token.return_value = payload

    with patch(
        "app.api.v1.dependencies.auth.TokenService",
        return_value=mock_token_service,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                authorization="Bearer valid.jwt.token",
                user_repo=mock_repo,
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_inactive_user(
    inactive_user: User,
) -> None:
    """Test: inactive user → 401 Unauthorized.

    Per Requirement 4.8: When User's is_active is False,
    the dependency raises 401 Unauthorized (inactive users cannot authenticate).
    """
    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=inactive_user)

    mock_token_service = MagicMock()
    from app.infrastructure.security.jwt import TokenPayload

    payload = TokenPayload(
        sub=inactive_user.id,
        role=inactive_user.role,
        exp=datetime.now(tz=UTC),
        iat=datetime.now(tz=UTC),
        jti="test-jti",
    )
    mock_token_service.decode_token.return_value = payload

    with patch(
        "app.api.v1.dependencies.auth.TokenService",
        return_value=mock_token_service,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                authorization="Bearer valid.jwt.token",
                user_repo=mock_repo,
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "inactive" in exc_info.value.detail.lower()


# ===========================================================================
# Tests: require_role() Factory and Role Dependency
# ===========================================================================


@pytest.mark.asyncio
async def test_require_role_single_role_match(
    admin_user: User,
) -> None:
    """Test: require_role("admin") with admin user → passes.

    Per Requirement 4.11: When authenticated user's role matches
    required role, the dependency passes and returns User.
    """
    # Create the role check dependency
    role_dep = require_role("admin")

    # Call the dependency with admin user
    user = await role_dep(admin_user)

    assert user == admin_user
    assert user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_require_role_single_role_mismatch(
    valid_user: User,  # VIEWER
) -> None:
    """Test: require_role("admin") with viewer user → 403 Forbidden.

    Per Requirement 4.11: When authenticated user's role does not match
    required role, the dependency raises 403 Forbidden.
    """
    role_dep = require_role("admin")

    with pytest.raises(HTTPException) as exc_info:
        await role_dep(valid_user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_require_role_multiple_roles_first_match(
    admin_user: User,
) -> None:
    """Test: require_role(["admin", "analyst"]) with admin → passes.

    Per Requirement 4.12: Where multiple roles acceptable, dependency
    accepts any role in the list.
    """
    role_dep = require_role(["admin", "analyst"])

    user = await role_dep(admin_user)

    assert user == admin_user


@pytest.mark.asyncio
async def test_require_role_multiple_roles_second_match(
    analyst_user: User,
) -> None:
    """Test: require_role(["admin", "analyst"]) with analyst → passes.

    Per Requirement 4.12: Where multiple roles acceptable, dependency
    accepts any role in the list.
    """
    role_dep = require_role(["admin", "analyst"])

    user = await role_dep(analyst_user)

    assert user == analyst_user


@pytest.mark.asyncio
async def test_require_role_multiple_roles_no_match(
    valid_user: User,  # VIEWER
) -> None:
    """Test: require_role(["admin", "analyst"]) with viewer → 403 Forbidden.

    Per Requirement 4.12: Where user's role not in required list,
    raises 403 Forbidden.
    """
    role_dep = require_role(["admin", "analyst"])

    with pytest.raises(HTTPException) as exc_info:
        await role_dep(valid_user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# Tests: Integration - Multiple Dependencies
# ===========================================================================


@pytest.mark.asyncio
async def test_both_dependencies_with_authorized_user(
    admin_user: User,
) -> None:
    """Test: get_current_user + require_role with authorized user → passes.

    Both dependencies should pass when user is authenticated and has
    required role.
    """
    # Setup mock repository
    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=admin_user)

    # Setup mock token service
    mock_token_service = MagicMock()
    from app.infrastructure.security.jwt import TokenPayload

    payload = TokenPayload(
        sub=admin_user.id,
        role=admin_user.role,
        exp=datetime.now(tz=UTC),
        iat=datetime.now(tz=UTC),
        jti="test-jti",
    )
    mock_token_service.decode_token.return_value = payload

    with patch(
        "app.api.v1.dependencies.auth.TokenService",
        return_value=mock_token_service,
    ):
        # Get current user
        user = await get_current_user(
            authorization="Bearer valid.jwt.token",
            user_repo=mock_repo,
        )

        # Apply role requirement
        role_dep = require_role("admin")
        authorized_user = await role_dep(user)

        assert authorized_user == admin_user


@pytest.mark.asyncio
async def test_both_dependencies_with_unauthorized_user(
    valid_user: User,  # VIEWER
) -> None:
    """Test: get_current_user passes, require_role fails for unauthorized user.

    Authentication succeeds but authorization (role check) fails.
    """
    # Setup mock repository
    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=valid_user)

    # Setup mock token service
    mock_token_service = MagicMock()
    from app.infrastructure.security.jwt import TokenPayload

    payload = TokenPayload(
        sub=valid_user.id,
        role=valid_user.role,
        exp=datetime.now(tz=UTC),
        iat=datetime.now(tz=UTC),
        jti="test-jti",
    )
    mock_token_service.decode_token.return_value = payload

    with patch(
        "app.api.v1.dependencies.auth.TokenService",
        return_value=mock_token_service,
    ):
        # Get current user (succeeds)
        user = await get_current_user(
            authorization="Bearer valid.jwt.token",
            user_repo=mock_repo,
        )

        assert user == valid_user

        # Apply role requirement (fails)
        role_dep = require_role("admin")
        with pytest.raises(HTTPException) as exc_info:
            await role_dep(user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# Tests: Edge Cases
# ===========================================================================


@pytest.mark.asyncio
async def test_get_current_user_with_uppercase_bearer() -> None:
    """Test: Authorization header with uppercase "BEARER" → works.

    The Bearer keyword should be case-insensitive per HTTP specification.
    """
    valid_user_id = uuid4()
    valid_user = User(
        id=valid_user_id,
        email="user@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=valid_user)

    mock_token_service = MagicMock()
    from app.infrastructure.security.jwt import TokenPayload

    payload = TokenPayload(
        sub=valid_user.id,
        role=valid_user.role,
        exp=datetime.now(tz=UTC),
        iat=datetime.now(tz=UTC),
        jti="test-jti",
    )
    mock_token_service.decode_token.return_value = payload

    with patch(
        "app.api.v1.dependencies.auth.TokenService",
        return_value=mock_token_service,
    ):
        # Test with uppercase BEARER
        user = await get_current_user(
            authorization="BEARER valid.jwt.token",
            user_repo=mock_repo,
        )

        assert user == valid_user


@pytest.mark.asyncio
async def test_require_role_with_list_of_single_role() -> None:
    """Test: require_role(["admin"]) with admin user → passes.

    Single role can also be passed as a list with one element.
    """
    admin_user_id = uuid4()
    admin_user = User(
        id=admin_user_id,
        email="admin@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    role_dep = require_role(["admin"])

    user = await role_dep(admin_user)

    assert user == admin_user


@pytest.mark.asyncio
async def test_require_role_all_three_roles() -> None:
    """Test: require_role(["admin", "analyst", "viewer"]) → accepts all roles."""
    admin_user_id = uuid4()

    for role in [UserRole.ADMIN, UserRole.ANALYST, UserRole.VIEWER]:
        user = User(
            id=admin_user_id,
            email="user@example.com",
            password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
            role=role,
            is_active=True,
            created_at=datetime.now(tz=UTC),
        )

        role_dep = require_role(["admin", "analyst", "viewer"])

        result = await role_dep(user)

        assert result == user
        assert result.role == role
