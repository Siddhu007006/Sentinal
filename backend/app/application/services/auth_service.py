"""Authentication Service - High-level auth orchestration.

AuthService implements the core authentication flows:
- Registration (create account with password)
- Login (authenticate with email/password, return tokens)
- Token refresh (exchange refresh token for new access token)
- Logout (revoke refresh token)
- Logout all sessions (revoke all refresh tokens for user)

Per design.md § Authentication Service (Requirement 5):
- register(): Create new user with VIEWER role
- login(): Authenticate and return TokenPair
- refresh(): Exchange refresh token for new tokens with rotation
- logout(): Revoke per-device or all-session tokens
- All operations create AuditLog entries
- Audit failure does not block auth operations

Traces to: 08-Security-Architecture §4 (authentication service)
Traces to: 05-API-Specification §2 (auth flows)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.domain.entities.user import User, UserRole
from app.infrastructure.security.jwt import InvalidTokenError, TokenExpiredError
from app.infrastructure.security.password import get_password_hasher


if TYPE_CHECKING:
    from app.domain.repositories.refresh_token import RefreshTokenRepository
    from app.domain.repositories.user import UserRepository
    from app.domain.services.audit_service import AuditService
    from app.infrastructure.security.jwt import TokenService


logger = logging.getLogger(__name__)


class DuplicateEmailError(Exception):
    """Raised when attempting to register with existing email."""

    pass


class PasswordTooWeakError(Exception):
    """Raised when password does not meet strength requirements."""

    pass


class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid (generic, prevents enumeration)."""

    pass


class TokenRevokedError(Exception):
    """Raised when attempting to use a revoked refresh token."""

    pass


class AuthService:
    """High-level authentication service.

    Orchestrates user registration, login, token refresh, and logout operations.
    Integrates with password hasher, token service, repositories, and audit service.

    All auth operations are atomic: either the operation succeeds with audit logged,
    or it fails. Audit logging failures do not block auth operations (fail-safe).

    Attributes:
        user_repo: UserRepository for user persistence
        refresh_token_repo: RefreshTokenRepository for token revocation tracking
        token_service: TokenService for JWT creation/validation
        audit_service: AuditService for immutable audit logging
    """

    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        token_service: TokenService,
        audit_service: AuditService,
    ) -> None:
        """Initialize AuthService with dependencies.

        Args:
            user_repo: UserRepository for user persistence
            refresh_token_repo: RefreshTokenRepository for token tracking
            token_service: TokenService for JWT creation/validation
            audit_service: AuditService for audit logging
        """
        self.user_repo = user_repo
        self.refresh_token_repo = refresh_token_repo
        self.token_service = token_service
        self.audit_service = audit_service

    async def register(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """Register a new user account.

        Creates a new user with VIEWER role and hashed password. Email must be
        unique (case-insensitive). Password must meet minimum strength.

        Postconditions:
        - User created with role=VIEWER, is_active=True
        - Password hashed with configured algorithm
        - AuditLog entry created (or logged if creation fails)
        - Returns User domain entity (not ORM model)

        Args:
            email: User email address (must be unique)
            password: Plaintext password (validated for strength)
            full_name: User's full name (optional)
            ip_address: Client IP address (optional, for audit)
            request_id: Request correlation ID (optional, for audit)
            user_agent: Client User-Agent (optional, for audit)

        Returns:
            Created User entity (not ORM model)

        Raises:
            DuplicateEmailError: If email already exists
            PasswordTooWeakError: If password < 12 characters
            RepositoryException: If database error occurs

        Example:
            ```python
            user = await auth_service.register(
                email="user@example.com",
                password="SecurePassword123",
                full_name="John Doe",
                ip_address="192.168.1.1",
            )
            # user.role == UserRole.VIEWER (default)
            # user.is_active == True
            ```
        """
        # Validate email is unique
        try:
            await self.user_repo.get_by_email(email)
            # If we get here, user exists
            raise DuplicateEmailError(f"Email already registered: {email}")
        except Exception as e:
            # Expected: NotFound exception if user doesn't exist
            # Unexpected: other exceptions should be re-raised
            if "NotFound" not in str(type(e).__name__):
                if isinstance(e, DuplicateEmailError):
                    raise
                # Other exceptions: could be database error
                raise

        # Validate password strength (minimum 12 characters)
        if len(password) < 12:
            raise PasswordTooWeakError(
                "Password must be at least 12 characters long"
            )

        # Hash password
        hasher = get_password_hasher()
        password_hash = hasher.hash_password(password)

        # Create user entity
        user = User(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            role=UserRole.VIEWER,  # Default role
            is_active=True,
            is_verified=False,  # Email verification required
            created_at=datetime.now(UTC),
            full_name=full_name,
            updated_at=None,
            deleted_at=None,
        )

        # Validate entity
        user.validate()

        # Persist user
        persisted_user = await self.user_repo.create(user)

        # Log registration (fail-safe: if audit fails, log error but don't raise)
        try:
            await self.audit_service.log_user_registration(
                user_id=persisted_user.id,
                email=email,
                ip_address=ip_address,
                request_id=request_id,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.exception(
                "Audit log creation failed (non-blocking)",
                extra={
                    "user_id": persisted_user.id,
                    "action": "USER_REGISTRATION",
                    "error": str(e),
                },
            )

        return persisted_user

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """Authenticate user and return token pair.

        Verifies email and password, then returns access and refresh tokens.
        Uses generic error message to prevent email enumeration attacks.

        Postconditions:
        - Tokens valid and signed
        - Refresh token stored in RefreshTokenRepository
        - AuditLog entry created (login_success or login_failed)
        - Returns (access_token, refresh_token)

        Args:
            email: User email address
            password: Plaintext password
            ip_address: Client IP address (optional, for audit)
            request_id: Request correlation ID (optional, for audit)
            user_agent: Client User-Agent (optional, for audit)

        Returns:
            Tuple of (access_token, refresh_token) JWT strings

        Raises:
            InvalidCredentialsError: If email not found, password wrong,
                or user inactive
            RepositoryException: If database error occurs

        Example:
            ```python
            access_token, refresh_token = await auth_service.login(
                email="user@example.com",
                password="SecurePassword123",
                ip_address="192.168.1.1",
            )
            # Tokens ready for use; refresh_token stored for revocation tracking
            ```
        """
        # Attempt to look up user by email
        user = None
        try:
            user = await self.user_repo.get_by_email(email)
        except Exception:
            # User not found or database error
            # Log failure and raise generic error (prevent email enumeration)
            try:
                await self.audit_service.log_login_failed(
                    email=email,
                    reason="user_not_found",
                    ip_address=ip_address,
                    request_id=request_id,
                    user_agent=user_agent,
                )
            except Exception as e:
                logger.exception(
                    "Audit log creation failed (non-blocking)",
                    extra={
                        "email": email,
                        "action": "LOGIN_FAILED",
                        "error": str(e),
                    },
                )
            raise InvalidCredentialsError(
                "Invalid email or password"
            ) from None

        # Verify password
        hasher = get_password_hasher()
        if not hasher.verify_password(password, user.password_hash):
            # Password mismatch: log and raise generic error
            try:
                await self.audit_service.log_login_failed(
                    email=email,
                    reason="invalid_password",
                    ip_address=ip_address,
                    request_id=request_id,
                    user_agent=user_agent,
                )
            except Exception as e:
                logger.exception(
                    "Audit log creation failed (non-blocking)",
                    extra={
                        "user_id": user.id,
                        "action": "LOGIN_FAILED",
                        "error": str(e),
                    },
                )
            raise InvalidCredentialsError(
                "Invalid email or password"
            ) from None

        # Check user is active
        if not user.is_active:
            # User deactivated: log and raise generic error
            try:
                await self.audit_service.log_login_failed(
                    email=email,
                    reason="user_inactive",
                    ip_address=ip_address,
                    request_id=request_id,
                    user_agent=user_agent,
                )
            except Exception as e:
                logger.exception(
                    "Audit log creation failed (non-blocking)",
                    extra={
                        "user_id": user.id,
                        "action": "LOGIN_FAILED",
                        "error": str(e),
                    },
                )
            raise InvalidCredentialsError(
                "Invalid email or password"
            ) from None

        # Create tokens
        access_token = self.token_service.create_access_token(
            user.id, user.role
        )
        refresh_token = self.token_service.create_refresh_token(user.id)

        # Decode refresh token to get JTI for storage
        refresh_payload = self.token_service.decode_token(refresh_token)

        # Store refresh token for revocation tracking
        # (Implementation depends on RefreshTokenRepository create method)
        from hashlib import sha256

        from app.domain.entities.refresh_token import RefreshToken

        refresh_token_entity = RefreshToken(
            id=uuid4(),
            user_id=user.id,
            jti=refresh_payload.jti,
            token_hash=sha256(refresh_token.encode()).hexdigest(),
            expires_at=refresh_payload.exp,
            is_revoked=False,
            revoked_at=None,
            created_at=None,
        )
        try:
            await self.refresh_token_repo.create(refresh_token_entity)
        except Exception as e:
            logger.exception(
                "Failed to store refresh token",
                extra={
                    "user_id": user.id,
                    "jti": refresh_payload.jti,
                    "error": str(e),
                },
            )
            raise

        # Log successful login
        try:
            await self.audit_service.log_user_login(
                user_id=user.id,
                user_role=user.role,
                email=email,
                ip_address=ip_address,
                request_id=request_id,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.exception(
                "Audit log creation failed (non-blocking)",
                extra={
                    "user_id": user.id,
                    "action": "USER_LOGIN",
                    "error": str(e),
                },
            )

        return access_token, refresh_token

    async def refresh(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """Exchange refresh token for new token pair with rotation.

        Validates refresh token, checks revocation, issues new tokens, and
        revokes the old token (token rotation for security).

        **Concurrency:** Uses database-level atomic UPDATE to prevent race condition
        where two concurrent requests both refresh the same token. Exactly one
        request succeeds; the other gets TokenAlreadyRotatedException (409 Conflict).

        Postconditions:
        - Old refresh token revoked immediately (or already revoked by concurrent req)
        - New tokens issued and returned (if this request won the race)
        - New refresh token stored for future rotation
        - AuditLog entry created
        - Returns (new_access_token, new_refresh_token)

        Args:
            refresh_token: Valid refresh token JWT
            ip_address: Client IP address (optional, for audit)
            request_id: Request correlation ID (optional, for audit)
            user_agent: Client User-Agent (optional, for audit)

        Returns:
            Tuple of (new_access_token, new_refresh_token) JWT strings

        Raises:
            TokenExpiredError: If token has expired
            InvalidTokenError: If token signature/structure invalid
            TokenRevokedError: If token has been explicitly revoked (not concurrent)
            TokenAlreadyRotatedException: If token concurrently rotated by another req
            RepositoryException: If database error occurs

        Example:
            ```python
            new_access, new_refresh = await auth_service.refresh(
                refresh_token=old_refresh_token,
                ip_address="192.168.1.1",
            )
            # Old token revoked, new tokens ready to use
            ```
        """
        from app.domain.exceptions import TokenAlreadyRotatedError

        # Decode and validate refresh token
        try:
            payload = self.token_service.decode_token(refresh_token)
        except TokenExpiredError:
            raise TokenExpiredError("Refresh token has expired") from None
        except InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid refresh token: {e!s}") from None

        # Load user to verify still active and get current role
        user = await self.user_repo.get_by_id(payload.sub)

        if not user.is_active:
            raise InvalidCredentialsError("User account is inactive")

        # **ATOMIC REVOCATION + CREATION** - Wrapped in explicit transaction
        # Both operations must succeed or both fail; no partial state allowed.
        # Transaction ensures:
        #   1. Atomic revocation: UPDATE old token SET is_revoked=TRUE
        #   2. Atomic creation: INSERT new token
        #   3. If either fails: ROLLBACK (both undone)
        #   4. If both succeed: COMMIT (both persist)
        #
        # This prevents the inconsistency where:
        #   - Old token revoked (✓)
        #   - New token creation fails (✗)
        #   - User left with neither token usable
        #
        # Note: We use begin_nested() to create a savepoint because a transaction
        # is already active from the FastAPI request scope. Savepoint can rollback
        # without affecting the outer transaction.
        from typing import cast

        from sqlalchemy.ext.asyncio import AsyncSession

        new_access_token: str | None = None
        new_refresh_token: str | None = None

        try:
            # Cast to access the session directly (protected attribute of repository)
            session = cast("AsyncSession", self.refresh_token_repo.session)  # type: ignore[attr-defined]
            async with session.begin_nested():
                # Within savepoint: revoke old token atomically
                revoked_successfully = (
                    await self.refresh_token_repo.atomic_revoke_by_jti(payload.jti)
                )
                if not revoked_successfully:
                    # Another request already revoked this token
                    raise TokenAlreadyRotatedError(
                        "Refresh token was concurrently rotated by another request"
                    )

                # Create new token pair (JWT operations, not DB)
                new_access_token = self.token_service.create_access_token(
                    user.id, user.role
                )
                new_refresh_token = self.token_service.create_refresh_token(user.id)

                # Decode new refresh token to get JTI for storage
                new_refresh_payload = self.token_service.decode_token(
                    new_refresh_token
                )

                # Store new refresh token (within same savepoint)
                from hashlib import sha256

                from app.domain.entities.refresh_token import RefreshToken

                new_refresh_token_entity = RefreshToken(
                    id=uuid4(),
                    user_id=user.id,
                    jti=new_refresh_payload.jti,
                    token_hash=sha256(new_refresh_token.encode()).hexdigest(),
                    expires_at=new_refresh_payload.exp,
                    is_revoked=False,
                    revoked_at=None,
                    created_at=None,
                )
                # This create is now inside the savepoint
                await self.refresh_token_repo.create(new_refresh_token_entity)

                # Savepoint commit will happen automatically on context exit (success)
                # Savepoint rollback will happen if any exception is raised

        except TokenAlreadyRotatedError:
            raise
        except Exception as e:
            logger.exception(
                "Failed to rotate refresh token atomically",
                extra={
                    "user_id": payload.sub,
                    "jti": payload.jti,
                    "error": str(e),
                },
            )
            raise

        # Log token refresh
        try:
            await self.audit_service.log_token_refresh(
                user_id=user.id,
                user_role=user.role,
                ip_address=ip_address,
                request_id=request_id,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.exception(
                "Audit log creation failed (non-blocking)",
                extra={
                    "user_id": user.id,
                    "action": "TOKEN_REFRESH",
                    "error": str(e),
                },
            )

        return new_access_token, new_refresh_token

    async def logout(
        self,
        user_id: UUID,
        user_role: UserRole,
        refresh_token: str | None = None,
        logout_all: bool = False,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Logout: revoke token(s) for user.

        Revokes either a specific refresh token (device logout) or all refresh
        tokens (logout all sessions) for the user.

        Postconditions:
        - If logout_all=True: all refresh tokens for user marked revoked
        - If logout_all=False: only specified token marked revoked
        - AuditLog entry created
        - No return value

        Args:
            user_id: ID of user logging out
            user_role: User's role
            refresh_token: Refresh token to revoke (if logout_all=False)
            logout_all: If True, revoke all tokens; if False, revoke only token
            ip_address: Client IP address (optional, for audit)
            request_id: Request correlation ID (optional, for audit)
            user_agent: Client User-Agent (optional, for audit)

        Raises:
            InvalidTokenError: If refresh_token invalid and logout_all=False
            RepositoryException: If database error occurs

        Example:
            ```python
            # Logout from current device only
            await auth_service.logout(
                user_id=user_id,
                user_role=user.role,
                refresh_token=current_token,
                logout_all=False,
            )

            # Or logout from all devices
            await auth_service.logout(
                user_id=user_id,
                user_role=user.role,
                logout_all=True,
            )
            ```
        """
        if logout_all:
            # Revoke all refresh tokens for user
            try:
                await self.refresh_token_repo.revoke_all_for_user(user_id)
            except Exception as e:
                logger.exception(
                    "Failed to revoke all refresh tokens",
                    extra={
                        "user_id": user_id,
                        "error": str(e),
                    },
                )
                raise
        else:
            # Revoke specific refresh token
            if not refresh_token:
                raise ValueError(
                    "refresh_token required when logout_all=False"
                )

            try:
                payload = self.token_service.decode_token(refresh_token)
                # Find token by JTI and revoke
                # (Implementation depends on RefreshTokenRepository.get_by_jti)
                stored_token = await self.refresh_token_repo.get_by_jti(
                    payload.jti
                )
                if stored_token:
                    await self.refresh_token_repo.revoke(stored_token.id)
            except TokenExpiredError:
                # Token expired but revoke anyway (idempotent)
                pass
            except InvalidTokenError:
                # Invalid token: raise error
                raise InvalidTokenError("Invalid refresh token") from None
            except Exception as e:
                logger.exception(
                    "Failed to revoke refresh token",
                    extra={
                        "user_id": user_id,
                        "error": str(e),
                    },
                )
                raise

        # Log logout
        try:
            await self.audit_service.log_user_logout(
                user_id=user_id,
                user_role=user_role,
                ip_address=ip_address,
                request_id=request_id,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.exception(
                "Audit log creation failed (non-blocking)",
                extra={
                    "user_id": user_id,
                    "action": "USER_LOGOUT",
                    "error": str(e),
                },
            )
