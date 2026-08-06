"""
RefreshTokenRepository domain interface.

Defines the abstract contract for refresh token server-side session management.
RefreshTokens are immutable after creation - updates are limited to revocation,
deletions are for cleanup only.

Implementations must not leak infrastructure details (SQLAlchemy, ORM models)
to the Domain layer.

The RefreshTokenRepository interface is used by Authentication layer services to
manage refresh tokens, validate token hashes, list active sessions, and revoke
tokens. The Domain layer depends on this interface, not on any concrete PostgreSQL
implementation.

Methods:
    - create(entity: RefreshToken) -> RefreshToken
    - get_by_hash(token_hash: str) -> RefreshToken | None
    - list(skip, limit, sort_by, sort_order, **filters) -> (List[RefreshToken], int)
    - revoke(token_id: UUID) -> RefreshToken
    - list_active_by_user(user_id: UUID, skip, limit) -> (List[RefreshToken], int)
    - delete_expired() -> int (number of tokens deleted)

Immutability:
    - Tokens are immutable after creation (token_hash never changes)
    - Only revoke() modifies tokens (sets is_revoked=True, revoked_at=now())
    - delete() is for cleanup only (expired tokens removal)

Exception Contract:
    - create() may raise UniqueConstraintError on duplicate token_hash
    - get_by_hash() returns None if token not found (never raises)
    - get_by_id() raises NotFound if token not found
    - revoke() raises NotFound if token not found
    - list() returns empty list if no matches found
    - delete_expired() always succeeds (returns count deleted)

Traces to: E3.T10 Specification § Requirement R1 (Domain Interfaces)
Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
Traces to: 03-Architecture §4 (Domain layer)
Traces to: 08-Security-Architecture §5 (JWT and refresh token lifecycle)
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from app.domain.repositories.base import BaseRepository


if TYPE_CHECKING:
    from app.domain.entities.refresh_token import RefreshToken


class RefreshTokenRepository(BaseRepository["RefreshToken"]):
    """
    Abstract repository interface for RefreshToken entity (session management).

    Manages all refresh token persistence operations for the Authentication layer.
    Refresh tokens are immutable after creation and used for session management,
    token rotation, and revocation.

    Implementations handle database-specific details (SQLAlchemy async,
    token hash lookups, session listing, cleanup, etc.) transparently.

    Inherits CRUD methods from BaseRepository[RefreshToken]:
        - create(entity: RefreshToken) -> RefreshToken
        - get_by_id(entity_id: UUID) -> RefreshToken
        - list(skip, limit, sort_by, sort_order, **filters)
          -> (List[RefreshToken], int)

    Explicitly does NOT support:
        - update() except via revoke() method
        - delete() except via delete_expired() for cleanup

    Adds token-specific query methods:
        - get_by_hash(token_hash: str) -> RefreshToken | None
        - revoke(token_id: UUID) -> RefreshToken
        - list_active_by_user(user_id: UUID, skip, limit)
          -> (List[RefreshToken], int)
        - delete_expired() -> int

    Token Lifecycle:
        1. **Issuance:** Client authenticates. Application creates RefreshToken
           with hashed token and expiry. Raw token returned to client (HTTPS).

        2. **Storage:** Client stores token securely (HttpOnly cookie or vault).

        3. **Refresh:** Client sends token. Application calls get_by_hash()
           to validate, then issues new access token and new token (rotation).

        4. **Revocation:** User logs out or security event. Application calls
           revoke() to set is_revoked=True. Token cannot be used again.

        5. **Cleanup:** Background job calls delete_expired() to remove old tokens.

        6. **Deletion:** User deleted. Cascade FK rule removes all their tokens.

    Security Considerations:
        - token_hash is SHA-256 (never plaintext)
        - get_by_hash() returns None (not NotFound) to prevent timing attacks
        - revoke() is immediate (takes effect on next request)
        - Expired tokens auto-cleaned by delete_expired() job
        - IP address and user_agent for audit (not security mechanism)

    Transaction Safety:
        - Methods do NOT commit/rollback transactions
        - Transaction lifecycle is managed by FastAPI dependency injection
        - All repository operations in a request are atomic

    Exception Contract:
        - create() raises UniqueConstraintError on duplicate token_hash
        - get_by_hash() returns None if not found (no exception)
        - get_by_id() raises NotFound if token not found
        - revoke() raises NotFound if token not found
        - list_active_by_user() returns empty list if no tokens
        - delete_expired() always succeeds, returns count deleted

    Example:
        ```python
        # Authentication service depends on the interface
        class TokenService:
            def __init__(self, token_repo: RefreshTokenRepository):
                self.token_repo = token_repo

            async def validate_token(self, raw_token: str) -> RefreshToken | None:
                import hashlib
                token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

                # get_by_hash returns None (not exception) for missing tokens
                token = await self.token_repo.get_by_hash(token_hash)
                if not token or token.is_revoked or token.expires_at < now():
                    return None
                return token

            async def refresh_token(
                self, user_id: UUID, old_token_hash: str
            ) -> (str, RefreshToken):
                # Issue new token
                import secrets, hashlib
                raw_token = secrets.token_urlsafe(48)
                token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

                new_token = await self.token_repo.create(
                    RefreshToken(
                        user_id=user_id,
                        token_hash=token_hash,
                        expires_at=datetime.now(UTC) + timedelta(days=30)
                    )
                )

                # Revoke old token
                old = await self.token_repo.get_by_hash(old_token_hash)
                if old:
                    await self.token_repo.revoke(old.id)

                return raw_token, new_token

            async def logout_user(self, user_id: UUID) -> None:
                # Revoke all user sessions
                results, _ = await self.token_repo.list_active_by_user(
                    user_id, skip=0, limit=1000
                )
                for token in results:
                    await self.token_repo.revoke(token.id)

            async def cleanup_expired(self) -> int:
                # Scheduled job: delete expired tokens
                return await self.token_repo.delete_expired()
        ```

    Traces to: E3.T10 Specification § Requirement R1 (Domain Interfaces)
    Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
    Traces to: 03-Architecture §4 (Domain layer)
    Traces to: 08-Security-Architecture §5 (Refresh token lifecycle)
    """

    @abstractmethod
    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """
        Retrieve refresh token by its SHA-256 hash.

        Looks up a refresh token by the hash of the opaque token value.
        Used for token validation during refresh requests.

        Returns None (not NotFound exception) if token not found. This prevents
        timing attacks that could leak whether a token hash exists in the database.

        Args:
            token_hash: SHA-256 hash of the token value (64 hex characters)

        Returns:
            RefreshToken entity if found, or None if not found

        Note:
            This method returns None instead of raising NotFound to prevent
            timing attacks. Checking for missing tokens should not take
            different time based on database state.

        Example:
            ```python
            import hashlib

            raw_token = "opaque_token_from_client"
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

            token = await token_repo.get_by_hash(token_hash)
            if not token:
                # Token not found or invalid
                raise Unauthorized("Invalid token")
            if token.is_revoked or token.expires_at < now():
                raise Unauthorized("Token revoked or expired")
            ```

        Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
        Traces to: 08-Security-Architecture §5 (Token validation)
        """
        pass

    @abstractmethod
    async def revoke(self, token_id: UUID) -> RefreshToken:
        """
        Revoke a refresh token (explicit session termination).

        Sets is_revoked=True and revoked_at=now() for the specified token.
        The token can no longer be used for refresh operations. This is the
        mechanism for logout, password change, and session termination.

        Args:
            token_id: UUID of the refresh token to revoke

        Returns:
            The revoked token entity with is_revoked=True and revoked_at populated

        Raises:
            NotFound: If token with specified ID not found

        Example:
            ```python
            # User logs out or password changed
            revoked = await token_repo.revoke(token_id)
            # revoked.is_revoked is now True
            # revoked.revoked_at is now set to current timestamp
            ```

        Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
        Traces to: 08-Security-Architecture §5 (Token revocation)
        """
        pass

    @abstractmethod
    async def list_active_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[RefreshToken], int]:
        """
        Retrieve active refresh tokens for a user (current sessions).

        Fetches all active (non-revoked, non-expired) refresh tokens for the
        specified user. This enables "List all my active sessions" UI where
        users can see and revoke individual device sessions.

        Returns only tokens where is_revoked=False and expires_at > now().

        Args:
            user_id: UUID of the user to retrieve tokens for
            skip: Number of tokens to skip (pagination offset), default 0
            limit: Maximum tokens to return per page, default 20

        Returns:
            Tuple of (tokens, total_count) where:
            - tokens: List of active RefreshToken entities for this user
            - total_count: Total number of active tokens for this user

        Example:
            ```python
            results, total = await token_repo.list_active_by_user(
                user_id=user_id,
                skip=0,
                limit=50
            )
            # results: list of 50 active sessions for this user
            # total: total active sessions
            # User can see: "You have 5 active sessions"
            # User can revoke: "Sign out on this device"
            ```

        Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
        Traces to: 08-Security-Architecture §5 (Session management)
        """
        pass

    @abstractmethod
    async def delete_expired(self) -> int:
        """
        Hard-delete all expired refresh tokens (cleanup operation).

        Removes all refresh tokens where expires_at < now() and is_revoked=False.
        This is a scheduled cleanup job to remove old tokens from the database
        and reduce storage overhead.

        Should be run periodically (e.g., once per day) to clean up expired tokens.

        Returns:
            Number of tokens deleted

        Example:
            ```python
            # Scheduled cleanup job
            deleted_count = await token_repo.delete_expired()
            logger.info(f"Deleted {deleted_count} expired refresh tokens")
            ```

        Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
        Traces to: 04-Database-Design §5.2 (Token lifecycle)
        """
        pass
