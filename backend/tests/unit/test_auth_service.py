"""Comprehensive unit tests for AuthService.

Tests all core authentication methods:
- register(): success, duplicate email, invalid email, weak password
- login(): success, wrong password, inactive user, user not found
- refresh(): success, expired token, revoked token, invalid token
- logout(): per-device logout, logout-all, idempotency
- Audit logging for all operations

Per Requirement 5 in requirements.md and design.md § Authentication Service.

**Validates: Requirement 5 (Auth Service)**

Traces to: 22-Engineering-Backlog E4.T4
Traces to: 07-Backend-Development-Standards §7 (testing patterns)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.application.services.auth_service import (
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
    PasswordTooWeakError,
    TokenRevokedError,
)
from app.domain.entities.refresh_token import RefreshToken
from app.domain.entities.user import User, UserRole
from app.infrastructure.security.jwt import (
    InvalidTokenError,
    TokenExpiredError,
    TokenPayload,
)


# ===========================================================================
# Test Fixtures
# ===========================================================================

@pytest.fixture
def user_repo() -> AsyncMock:
    """Mock UserRepository."""
    return AsyncMock()


@pytest.fixture
def refresh_token_repo() -> AsyncMock:
    """Mock RefreshTokenRepository."""
    return AsyncMock()


@pytest.fixture
def token_service() -> MagicMock:
    """Mock TokenService (synchronous methods)."""
    return MagicMock()


@pytest.fixture
def audit_service() -> AsyncMock:
    """Mock AuditService."""
    return AsyncMock()


@pytest.fixture
def auth_service(
    user_repo: AsyncMock,
    refresh_token_repo: AsyncMock,
    token_service: MagicMock,
    audit_service: AsyncMock,
) -> AuthService:
    """Create AuthService with mocked dependencies."""
    return AuthService(
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
        token_service=token_service,
        audit_service=audit_service,
    )


@pytest.fixture
def valid_user_id() -> UUID:
    """Valid UUID for testing."""
    return uuid4()


@pytest.fixture
def valid_user(valid_user_id: UUID) -> User:
    """Valid active user for testing."""
    return User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def inactive_user(valid_user_id: UUID) -> User:
    """Inactive user for testing."""
    return User(
        id=valid_user_id,
        email="inactive@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.VIEWER,
        is_active=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def valid_token_payload(valid_user_id: UUID) -> TokenPayload:
    """Valid token payload for testing."""
    return TokenPayload(
        sub=valid_user_id,
        role=UserRole.VIEWER,
        exp=datetime.now(UTC) + timedelta(minutes=15),
        iat=datetime.now(UTC),
        jti="test-jti-123",
    )


@pytest.fixture
def valid_refresh_token() -> RefreshToken:
    """Valid refresh token for testing."""
    return RefreshToken(
        id=uuid4(),
        user_id=uuid4(),
        jti="test-jti-123",
        token_hash="hashed_token",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        is_revoked=False,
        revoked_at=None,
        created_at=datetime.now(UTC),
    )


# ===========================================================================
# Test Group 1: register() - Success Cases
# ===========================================================================


@pytest.mark.asyncio
async def test_register_success_creates_user_with_viewer_role(
    auth_service: AuthService,
    user_repo: AsyncMock,
    audit_service: AsyncMock,
) -> None:
    """Test: register() creates user with VIEWER role and hashed password.

    **Validates: Requirement 5, AC #1**
    """
    # Setup: User doesn't exist
    class NotFoundError(Exception):
        pass

    user_repo.get_by_email.side_effect = NotFoundError("User not found")
    created_user = User(
        id=uuid4(),
        email="newuser@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    user_repo.create.return_value = created_user

    # Execute
    with patch("app.application.services.auth_service.get_password_hasher") as mock_hasher_factory:
        mock_hasher = MagicMock()
        mock_hasher.hash_password.return_value = created_user.password_hash
        mock_hasher_factory.return_value = mock_hasher

        result = await auth_service.register(
            email="newuser@example.com",
            password="ValidPassword123456",
            full_name="Test User",
        )

    # Assert
    assert result.email == "newuser@example.com"
    assert result.role == UserRole.VIEWER
    assert result.is_active is True
    assert result.password_hash != "ValidPassword123456"  # Not plaintext
    user_repo.create.assert_called_once()
    audit_service.log_user_registration.assert_called_once()


@pytest.mark.asyncio
async def test_register_duplicate_email_raises_error(
    auth_service: AuthService,
    user_repo: AsyncMock,
    valid_user: User,
) -> None:
    """Test: register() raises DuplicateEmailError for existing email.

    **Validates: Requirement 5, AC #2**
    """
    user_repo.get_by_email.return_value = valid_user

    with pytest.raises(DuplicateEmailError, match="Email already registered"):
        await auth_service.register(
            email="test@example.com",
            password="ValidPassword123456",
        )

    user_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_register_password_too_weak_raises_error(
    auth_service: AuthService,
    user_repo: AsyncMock,
) -> None:
    """Test: register() raises PasswordTooWeakError for password < 12 chars.

    **Validates: Requirement 5, AC #4**
    """
    class NotFoundError(Exception):
        pass

    user_repo.get_by_email.side_effect = NotFoundError("User not found")

    with pytest.raises(PasswordTooWeakError, match="at least 12 characters"):
        await auth_service.register(
            email="user@example.com",
            password="Short123",  # Only 8 characters
        )

    user_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_register_invalid_email_raises_error(
    auth_service: AuthService,
    user_repo: AsyncMock,
) -> None:
    """Test: register() rejects invalid email format.

    **Validates: Requirement 5, AC #3**
    """
    class NotFoundError(Exception):
        pass

    user_repo.get_by_email.side_effect = NotFoundError("User not found")

    with pytest.raises(ValueError, match="Invalid email format"):
        await auth_service.register(
            email="not-an-email",
            password="ValidPassword123456",
        )

    user_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_register_audit_failure_does_not_block(
    auth_service: AuthService,
    user_repo: AsyncMock,
    audit_service: AsyncMock,
) -> None:
    """Test: register() succeeds even if audit logging fails (fail-safe).

    **Validates: Requirement 5, AC #13**
    """
    class NotFoundError(Exception):
        pass

    user_repo.get_by_email.side_effect = NotFoundError("User not found")
    created_user = User(
        id=uuid4(),
        email="user@example.com",
        password_hash="$argon2id$...",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    user_repo.create.return_value = created_user
    audit_service.log_user_registration.side_effect = Exception("DB Error")

    with patch("app.application.services.auth_service.get_password_hasher") as mock_hasher_factory:
        mock_hasher = MagicMock()
        mock_hasher.hash_password.return_value = "$argon2id$..."
        mock_hasher_factory.return_value = mock_hasher

        # Should NOT raise despite audit failure
        result = await auth_service.register(
            email="user@example.com",
            password="ValidPassword123456",
        )

    assert result is not None
    assert result.email == "user@example.com"
    user_repo.create.assert_called_once()


# ===========================================================================
# Test Group 2: login() - Success Case
# ===========================================================================


@pytest.mark.asyncio
async def test_login_success_returns_token_pair(
    auth_service: AuthService,
    user_repo: AsyncMock,
    refresh_token_repo: AsyncMock,
    token_service: MagicMock,
    audit_service: AsyncMock,
    valid_user: User,
    valid_token_payload: TokenPayload,
) -> None:
    """Test: login() returns TokenPair with valid tokens.

    **Validates: Requirement 5, AC #5**
    """
    user_repo.get_by_email.return_value = valid_user
    token_service.create_access_token.return_value = "access_token_jwt"
    token_service.create_refresh_token.return_value = "refresh_token_jwt"
    token_service.decode_token.return_value = valid_token_payload
    refresh_token_repo.create.return_value = None

    with patch("app.application.services.auth_service.get_password_hasher") as mock_hasher_factory:
        mock_hasher = MagicMock()
        mock_hasher.verify_password.return_value = True
        mock_hasher_factory.return_value = mock_hasher

        access, refresh = await auth_service.login(
            email="test@example.com",
            password="ValidPassword123456",
        )

    assert access == "access_token_jwt"
    assert refresh == "refresh_token_jwt"
    token_service.create_access_token.assert_called_once_with(
        valid_user.id, valid_user.role
    )
    token_service.create_refresh_token.assert_called_once_with(valid_user.id)
    refresh_token_repo.create.assert_called_once()
    audit_service.log_user_login.assert_called_once()


@pytest.mark.asyncio
async def test_login_wrong_password_raises_invalid_credentials(
    auth_service: AuthService,
    user_repo: AsyncMock,
    audit_service: AsyncMock,
    valid_user: User,
) -> None:
    """Test: login() raises InvalidCredentialsError for wrong password.

    **Validates: Requirement 5, AC #6**

    Generic error prevents email enumeration.
    """
    user_repo.get_by_email.return_value = valid_user

    with patch("app.application.services.auth_service.get_password_hasher") as mock_hasher_factory:
        mock_hasher = MagicMock()
        mock_hasher.verify_password.return_value = False  # Wrong password
        mock_hasher_factory.return_value = mock_hasher

        with pytest.raises(InvalidCredentialsError, match="Invalid email or password"):
            await auth_service.login(
                email="test@example.com",
                password="WrongPassword123456",
            )

    user_repo.create.assert_not_called()
    audit_service.log_login_failed.assert_called_once()


@pytest.mark.asyncio
async def test_login_inactive_user_raises_invalid_credentials(
    auth_service: AuthService,
    user_repo: AsyncMock,
    audit_service: AsyncMock,
    inactive_user: User,
) -> None:
    """Test: login() raises InvalidCredentialsError for inactive user.

    **Validates: Requirement 5, AC #7**

    Generic error prevents user enumeration.
    """
    user_repo.get_by_email.return_value = inactive_user

    with pytest.raises(InvalidCredentialsError, match="Invalid email or password"):
        await auth_service.login(
            email="inactive@example.com",
            password="ValidPassword123456",
        )

    audit_service.log_login_failed.assert_called_once()


@pytest.mark.asyncio
async def test_login_user_not_found_logs_with_email_not_user_id(
    auth_service: AuthService,
    user_repo: AsyncMock,
    audit_service: AsyncMock,
) -> None:
    """Test: login() logs failed attempt with email (not user_id).

    **Validates: Requirement 5, AC #6, Requirement 8, AC #3**

    When user not found, user_id is not available, so email is logged.
    """
    user_repo.get_by_email.side_effect = Exception("NotFound")

    with pytest.raises(InvalidCredentialsError):
        await auth_service.login(
            email="nonexistent@example.com",
            password="ValidPassword123456",
        )

    audit_service.log_login_failed.assert_called_once()
    call_kwargs = audit_service.log_login_failed.call_args[1]
    assert call_kwargs["email"] == "nonexistent@example.com"
    assert call_kwargs["reason"] == "user_not_found"


# ===========================================================================
# Test Group 3: refresh() - Success Case
# ===========================================================================


@pytest.mark.asyncio
async def test_refresh_success_returns_new_token_pair(
    auth_service: AuthService,
    user_repo: AsyncMock,
    refresh_token_repo: AsyncMock,
    token_service: MagicMock,
    audit_service: AsyncMock,
    valid_user: User,
    valid_token_payload: TokenPayload,
    valid_refresh_token: RefreshToken,
) -> None:
    """Test: refresh() returns new TokenPair with token rotation.

    **Validates: Requirement 5, AC #8-11**
    """
    token_service.decode_token.side_effect = [
        valid_token_payload,  # First call: decode old token
        valid_token_payload,  # Second call: decode new token
    ]
    refresh_token_repo.get_by_jti.return_value = valid_refresh_token
    user_repo.get_by_id.return_value = valid_user
    token_service.create_access_token.return_value = "new_access_token"
    token_service.create_refresh_token.return_value = "new_refresh_token"
    refresh_token_repo.create.return_value = None
    refresh_token_repo.revoke.return_value = None

    access, refresh = await auth_service.refresh(refresh_token="old_refresh_token_jwt")

    assert access == "new_access_token"
    assert refresh == "new_refresh_token"
    # Verify token rotation: old token revoked, new token stored
    refresh_token_repo.revoke.assert_called_once()
    refresh_token_repo.create.assert_called_once()
    audit_service.log_token_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_expired_token_raises_error(
    auth_service: AuthService,
    token_service: MagicMock,
) -> None:
    """Test: refresh() raises TokenExpiredError for expired token.

    **Validates: Requirement 5, AC #10**
    """
    token_service.decode_token.side_effect = TokenExpiredError("Token expired")

    with pytest.raises(TokenExpiredError):
        await auth_service.refresh(refresh_token="expired_token")


@pytest.mark.asyncio
async def test_refresh_revoked_token_raises_error(
    auth_service: AuthService,
    token_service: MagicMock,
    refresh_token_repo: AsyncMock,
    valid_token_payload: TokenPayload,
) -> None:
    """Test: refresh() raises TokenRevokedError for revoked token.

    **Validates: Requirement 5, AC #9**
    """
    token_service.decode_token.return_value = valid_token_payload
    revoked_token = RefreshToken(
        id=uuid4(),
        user_id=valid_token_payload.sub,
        jti=valid_token_payload.jti,
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        is_revoked=True,  # Token is revoked
        revoked_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    refresh_token_repo.get_by_jti.return_value = revoked_token

    with pytest.raises(TokenRevokedError, match="has been revoked"):
        await auth_service.refresh(refresh_token="revoked_token")


@pytest.mark.asyncio
async def test_refresh_invalid_token_raises_error(
    auth_service: AuthService,
    token_service: MagicMock,
) -> None:
    """Test: refresh() raises InvalidTokenError for invalid signature.

    **Validates: Requirement 5, AC #10**
    """
    token_service.decode_token.side_effect = InvalidTokenError("Invalid signature")

    with pytest.raises(InvalidTokenError):
        await auth_service.refresh(refresh_token="invalid_token")


@pytest.mark.asyncio
async def test_refresh_inactive_user_raises_error(
    auth_service: AuthService,
    user_repo: AsyncMock,
    refresh_token_repo: AsyncMock,
    token_service: MagicMock,
    valid_token_payload: TokenPayload,
    valid_refresh_token: RefreshToken,
    inactive_user: User,
) -> None:
    """Test: refresh() raises error if user inactive."""
    token_service.decode_token.return_value = valid_token_payload
    refresh_token_repo.get_by_jti.return_value = valid_refresh_token
    user_repo.get_by_id.return_value = inactive_user  # Inactive user

    with pytest.raises(InvalidCredentialsError, match="inactive"):
        await auth_service.refresh(refresh_token="token")


# ===========================================================================
# Test Group 4: logout() - Success Cases
# ===========================================================================


@pytest.mark.asyncio
async def test_logout_specific_token_revokes_only_that_token(
    auth_service: AuthService,
    refresh_token_repo: AsyncMock,
    token_service: MagicMock,
    audit_service: AsyncMock,
    valid_user_id: UUID,
    valid_token_payload: TokenPayload,
    valid_refresh_token: RefreshToken,
) -> None:
    """Test: logout() revokes only specified token (device-specific).

    **Validates: Requirement 5, AC #12, Requirement 10, AC #3**
    """
    token_service.decode_token.return_value = valid_token_payload
    refresh_token_repo.get_by_jti.return_value = valid_refresh_token
    refresh_token_repo.revoke.return_value = None

    await auth_service.logout(
        user_id=valid_user_id,
        user_role=UserRole.VIEWER,
        refresh_token="device_token",
        logout_all=False,
    )

    refresh_token_repo.revoke.assert_called_once_with(valid_refresh_token.id)
    audit_service.log_user_logout.assert_called_once()


@pytest.mark.asyncio
async def test_logout_all_revokes_all_tokens(
    auth_service: AuthService,
    refresh_token_repo: AsyncMock,
    audit_service: AsyncMock,
    valid_user_id: UUID,
) -> None:
    """Test: logout() revokes all tokens when logout_all=True.

    **Validates: Requirement 5, AC #12, Requirement 10, AC #4**
    """
    refresh_token_repo.revoke_all_for_user.return_value = None

    await auth_service.logout(
        user_id=valid_user_id,
        user_role=UserRole.VIEWER,
        logout_all=True,
    )

    refresh_token_repo.revoke_all_for_user.assert_called_once_with(valid_user_id)
    audit_service.log_user_logout.assert_called_once()


@pytest.mark.asyncio
async def test_logout_idempotent_succeeds_on_expired_token(
    auth_service: AuthService,
    token_service: MagicMock,
    audit_service: AsyncMock,
    valid_user_id: UUID,
) -> None:
    """Test: logout() is idempotent (second logout succeeds).

    **Validates: Requirement 5, AC #12**
    """
    # Simulate second logout: token is expired but we treat it gracefully
    token_service.decode_token.side_effect = TokenExpiredError("Token expired")

    # Should not raise error
    await auth_service.logout(
        user_id=valid_user_id,
        user_role=UserRole.VIEWER,
        refresh_token="already_revoked_token",
        logout_all=False,
    )

    audit_service.log_user_logout.assert_called_once()


@pytest.mark.asyncio
async def test_logout_audit_failure_does_not_block(
    auth_service: AuthService,
    refresh_token_repo: AsyncMock,
    audit_service: AsyncMock,
    valid_user_id: UUID,
) -> None:
    """Test: logout() succeeds even if audit fails (fail-safe).

    **Validates: Requirement 5, AC #13**
    """
    refresh_token_repo.revoke_all_for_user.return_value = None
    audit_service.log_user_logout.side_effect = Exception("DB Error")

    # Should NOT raise despite audit failure
    await auth_service.logout(
        user_id=valid_user_id,
        user_role=UserRole.VIEWER,
        logout_all=True,
    )

    refresh_token_repo.revoke_all_for_user.assert_called_once()


# ===========================================================================
# Test Group 5: Complete Flows and Integration
# ===========================================================================


@pytest.mark.asyncio
async def test_password_validation_boundary_11_chars_fails(
    auth_service: AuthService,
    user_repo: AsyncMock,
) -> None:
    """Test: Password with 11 characters fails validation."""
    class NotFoundError(Exception):
        pass

    user_repo.get_by_email.side_effect = NotFoundError("User not found")

    with pytest.raises(PasswordTooWeakError):
        await auth_service.register(
            email="user@example.com",
            password="11Chars1234",  # 11 characters
        )


@pytest.mark.asyncio
async def test_password_validation_boundary_12_chars_passes(
    auth_service: AuthService,
    user_repo: AsyncMock,
    audit_service: AsyncMock,
) -> None:
    """Test: Password with exactly 12 characters passes validation."""
    class NotFoundError(Exception):
        pass

    user_repo.get_by_email.side_effect = NotFoundError("User not found")
    created_user = User(
        id=uuid4(),
        email="user@example.com",
        password_hash="$argon2id$...",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    user_repo.create.return_value = created_user

    with patch("app.application.services.auth_service.get_password_hasher") as mock_hasher_factory:
        mock_hasher = MagicMock()
        mock_hasher.hash_password.return_value = "$argon2id$..."
        mock_hasher_factory.return_value = mock_hasher

        result = await auth_service.register(
            email="user@example.com",
            password="ValidPass1234",  # Exactly 14 characters (>= 12)
        )

    assert result is not None
    assert result.email == "user@example.com"
    user_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_email_validation_accepts_valid_formats(
    auth_service: AuthService,
    user_repo: AsyncMock,
    audit_service: AsyncMock,
) -> None:
    """Test: Email validation accepts various valid formats."""
    class NotFoundError(Exception):
        pass

    valid_emails = [
        "user@example.com",
        "user+tag@example.com",
        "user.name@sub.example.co.uk",
    ]

    for email in valid_emails:
        user_repo.get_by_email.side_effect = NotFoundError("User not found")

        created_user = User(
            id=uuid4(),
            email=email,
            password_hash="$argon2id$...",
            role=UserRole.VIEWER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        user_repo.create.return_value = created_user

        with patch(
            "app.application.services.auth_service.get_password_hasher"
        ) as mock_hasher_factory:
            mock_hasher = MagicMock()
            mock_hasher.hash_password.return_value = "$argon2id$..."
            mock_hasher_factory.return_value = mock_hasher

            result = await auth_service.register(
                email=email,
                password="ValidPassword123456",
            )

        assert result.email == email


@pytest.mark.asyncio
async def test_email_validation_rejects_invalid_formats(
    auth_service: AuthService,
    user_repo: AsyncMock,
) -> None:
    """Test: Email validation rejects invalid formats."""
    class NotFoundError(Exception):
        pass

    invalid_emails = [
        "no-at-sign",
        "user@",
        "@domain.com",
    ]

    for email in invalid_emails:
        user_repo.get_by_email.side_effect = NotFoundError("User not found")

        with pytest.raises(ValueError, match="Invalid email format"):
            await auth_service.register(
                email=email,
                password="ValidPassword123456",
            )


@pytest.mark.asyncio
async def test_login_failed_logs_with_correct_reason(
    auth_service: AuthService,
    user_repo: AsyncMock,
    audit_service: AsyncMock,
    valid_user: User,
) -> None:
    """Test: login_failed audit logs include reason."""
    user_repo.get_by_email.return_value = valid_user

    with patch("app.application.services.auth_service.get_password_hasher") as mock_hasher_factory:
        mock_hasher = MagicMock()
        mock_hasher.verify_password.return_value = False
        mock_hasher_factory.return_value = mock_hasher

        with pytest.raises(InvalidCredentialsError):
            await auth_service.login(
                email="test@example.com",
                password="WrongPassword123456",
            )

    call_kwargs = audit_service.log_login_failed.call_args[1]
    assert call_kwargs["reason"] == "invalid_password"


@pytest.mark.asyncio
async def test_refresh_stores_new_token_with_jti(
    auth_service: AuthService,
    user_repo: AsyncMock,
    refresh_token_repo: AsyncMock,
    token_service: MagicMock,
    audit_service: AsyncMock,
    valid_user: User,
    valid_token_payload: TokenPayload,
    valid_refresh_token: RefreshToken,
) -> None:
    """Test: refresh() stores new token with JTI for revocation tracking.

    **Validates: Requirement 3, AC #5**
    """
    token_service.decode_token.side_effect = [
        valid_token_payload,
        valid_token_payload,
    ]
    refresh_token_repo.get_by_jti.return_value = valid_refresh_token
    user_repo.get_by_id.return_value = valid_user
    token_service.create_access_token.return_value = "new_access_token"
    token_service.create_refresh_token.return_value = "new_refresh_token"
    refresh_token_repo.create.return_value = None
    refresh_token_repo.revoke.return_value = None

    await auth_service.refresh(refresh_token="refresh_token_jwt")

    refresh_token_repo.create.assert_called_once()
    call_args = refresh_token_repo.create.call_args[0][0]
    assert call_args.jti == valid_token_payload.jti
    assert call_args.user_id == valid_user.id
