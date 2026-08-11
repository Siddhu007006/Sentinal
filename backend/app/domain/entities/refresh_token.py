"""RefreshToken domain entity.

Represents a refresh token session. Used to track active refresh tokens,
detect revocation, and implement token rotation for security.

Per design.md § Token Lifecycle:
- Each login creates independent refresh token (separate session)
- User can log in from multiple devices simultaneously
- logout(refresh_token) revokes only that token (device-specific)
- logout_all_sessions(user_id) revokes all tokens for user
- Refresh of revoked token → TokenRevokedError
- Token revocation checked on every refresh (not cached)

Traces to: 08-Security-Architecture §4 (token lifecycle)
Traces to: 05-API-Specification §2 (session management)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass
class RefreshToken:
    """
    Refresh token entity for session management.

    Tracks active refresh tokens, enables revocation, and supports
    token rotation for enhanced security.

    Invariants:
    - jti (JWT ID) is unique within the database
    - user_id references a valid User
    - expires_at is in UTC timezone
    - Once revoked (is_revoked=True), token cannot be used
    - Revoked_at timestamp captures when revocation occurred
    - user_agent and ip_address capture session context

    Attributes:
        id: Unique identifier for this refresh token record
        user_id: ID of the user who owns this token
        jti: JWT ID from the token (unique identifier for revocation)
        token_hash: Hashed token (for secure storage, not plaintext JWT)
        expires_at: Expiration time in UTC
        is_revoked: Whether token has been revoked
        revoked_at: Timestamp of revocation (None if not revoked)
        user_agent: Client HTTP User-Agent header (session context)
        ip_address: Client IP address (session context)
        created_at: Timestamp of token creation
    """

    id: UUID
    user_id: UUID
    jti: str  # JWT ID for revocation tracking
    token_hash: str  # Hashed token for secure storage
    expires_at: datetime
    is_revoked: bool
    revoked_at: datetime | None
    created_at: datetime | None
    user_agent: str | None = None  # Client context (HTTP User-Agent)
    ip_address: str | None = None  # Client context (IP address)

    def validate(self) -> None:
        """Validate invariants.

        Raises:
            ValueError: If any invariant violated
        """
        if not self.user_id:
            raise ValueError("user_id is required")
        if not self.jti or not isinstance(self.jti, str):
            raise ValueError("jti must be a non-empty string")
        if not self.expires_at:
            raise ValueError("expires_at is required")
        if self.is_revoked and not self.revoked_at:
            msg = "revoked_at must be set if is_revoked=True"
            raise ValueError(msg)
