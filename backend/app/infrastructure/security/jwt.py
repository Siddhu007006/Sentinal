"""JWT Token Service for authentication and authorization.

Provides JWT creation, validation, and claim verification with HS256/RS256
algorithm support.

Per design.md § JWT Token Service and Requirement 3 in requirements.md:
- TokenPayload contains all required claims: sub, role, exp, iat, jti
- Access tokens: 15-minute lifetime, includes role claim
- Refresh tokens: 30-day lifetime, no role claim
- Each token has unique jti for revocation tracking
- Validates signature, expiry, and required claims
- Raises TokenExpiredError on expired token
- Raises InvalidTokenError on invalid signature or missing claims

Traces to: 08-Security-Architecture §4 (JWT authentication)
Traces to: 05-API-Specification §2 (token lifetimes)
Traces to: 07-Backend-Development-Standards §11 (key management)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import ExpiredSignatureError
from jwt.exceptions import InvalidTokenError as JWTInvalidTokenError


if TYPE_CHECKING:
    from app.domain.entities.user import UserRole


class TokenExpiredError(Exception):
    """Raised when a JWT token has expired."""

    pass


class InvalidTokenError(Exception):
    """Raised when a JWT token signature or structure is invalid."""

    pass


@dataclass
class TokenPayload:
    """Decoded JWT payload with all required claims.

    Per Requirement 3, all tokens must include:
    - sub: subject (user_id as UUID)
    - exp: expiration time (as datetime)
    - iat: issued at time (as datetime)
    - jti: unique token ID for revocation tracking

    Access tokens additionally include:
    - role: user's role (admin, analyst, viewer)

    Refresh tokens do not include role.
    """

    sub: UUID  # subject (user_id)
    exp: datetime  # expiration time
    iat: datetime  # issued at
    jti: str  # JWT ID (unique token identifier)
    role: UserRole | None = None  # role (access tokens only)

    def is_expired(self) -> bool:
        """Check if token is expired.

        Returns:
            True if token has expired, False otherwise.
        """
        return datetime.now(tz=UTC) > self.exp


class TokenService:
    """JWT token management per 08-Security-Architecture.md §4.

    Access tokens: 15-minute lifetime, included in every request
    Refresh tokens: 30-day lifetime, used only on POST /auth/refresh

    Per 05-API-Specification.md §2 assumptions.

    Attributes:
        ACCESS_TOKEN_EXPIRY_MINUTES: Lifetime for access tokens (15)
        REFRESH_TOKEN_EXPIRY_DAYS: Lifetime for refresh tokens (30)
    """

    # Token lifetimes per Requirement 3
    ACCESS_TOKEN_EXPIRY_MINUTES = 15
    REFRESH_TOKEN_EXPIRY_DAYS = 30

    def __init__(self) -> None:
        """Initialize TokenService with algorithm and keys from settings."""
        from app.core.dependencies import get_settings

        settings = get_settings()

        # Algorithm and key from settings (per 07-Backend-Development-Standards §11)
        self.algorithm = settings.security.jwt_algorithm  # "HS256" or "RS256"

        if self.algorithm == "HS256":
            self.secret_key: str | bytes = (
                settings.security.jwt_secret_key.get_secret_value()
            )
            self.public_key: str | bytes | None = None
        elif self.algorithm == "RS256":
            # For RS256, would read private and public keys
            # This is a placeholder; full implementation depends on RSA key setup
            self.secret_key = settings.security.jwt_secret_key.get_secret_value()
            self.public_key = None
        else:
            msg = f"Unsupported algorithm: {self.algorithm}"
            raise ValueError(msg)

    def create_access_token(
        self, user_id: UUID, role: UserRole
    ) -> str:
        """Create short-lived access token (15 minutes).

        Postconditions:
        - JWT includes: sub, role, exp, iat, jti
        - Expiration is exactly 15 minutes from now
        - Token is signed with configured algorithm

        Args:
            user_id: The user's UUID
            role: The user's role (admin, analyst, viewer)

        Returns:
            JWT string signed with configured algorithm.
        """
        now = datetime.now(tz=UTC)
        expiry = now + timedelta(minutes=self.ACCESS_TOKEN_EXPIRY_MINUTES)

        payload = {
            "sub": str(user_id),
            "role": role.value,  # role.value for string representation
            "exp": expiry,
            "iat": now,
            "jti": str(uuid4()),  # Unique token ID for revocation tracking
        }

        token = jwt.encode(
            payload, self.secret_key, algorithm=self.algorithm
        )
        return token

    def create_refresh_token(self, user_id: UUID) -> str:
        """Create long-lived refresh token (30 days).

        Postconditions:
        - JWT includes: sub, exp, iat, jti
        - Expiration is exactly 30 days from now
        - Token is signed with configured algorithm
        - Does NOT include role claim

        Args:
            user_id: The user's UUID

        Returns:
            JWT string signed with configured algorithm.
        """
        now = datetime.now(tz=UTC)
        expiry = now + timedelta(days=self.REFRESH_TOKEN_EXPIRY_DAYS)

        payload = {
            "sub": str(user_id),
            "exp": expiry,
            "iat": now,
            "jti": str(uuid4()),  # Unique token ID for rotation/revocation
        }

        token = jwt.encode(
            payload, self.secret_key, algorithm=self.algorithm
        )
        return token

    def decode_token(self, token: str) -> TokenPayload:
        """Decode and validate token.

        Validates signature, expiry, and required claims.

        Postconditions:
        - Returns TokenPayload if valid and unexpired
        - Raises TokenExpiredError if exp < now
        - Raises InvalidTokenError if signature/structure invalid
        - Raises InvalidTokenError if required claims missing

        Args:
            token: The JWT token string to decode.

        Returns:
            TokenPayload with all claims.

        Raises:
            TokenExpiredError: If token has expired.
            InvalidTokenError: If signature invalid or required claims missing.
        """
        try:
            # Use appropriate key based on algorithm
            if self.algorithm == "RS256" and self.public_key:
                key: str | bytes = self.public_key
            else:
                key = self.secret_key

            payload = jwt.decode(
                token, key, algorithms=[self.algorithm]
            )

            # Validate required claims per Requirement 3
            required_claims = ["sub", "exp", "iat", "jti"]
            if not all(claim in payload for claim in required_claims):
                msg = "Missing required claims"
                raise InvalidTokenError(msg)

            exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
            iat = datetime.fromtimestamp(payload["iat"], tz=UTC)

            # role is optional (refresh tokens don't have it)
            role_str = payload.get("role")
            role = None
            if role_str:
                from app.domain.entities.user import UserRole
                role = UserRole(role_str)

            token_payload = TokenPayload(
                sub=UUID(payload["sub"]),
                role=role,
                exp=exp,
                iat=iat,
                jti=payload["jti"],
            )

            return token_payload

        except ExpiredSignatureError as e:
            raise TokenExpiredError("Token has expired") from e
        except JWTInvalidTokenError as e:
            raise InvalidTokenError(f"Invalid token: {e!s}") from e
        except (ValueError, TypeError) as e:
            raise InvalidTokenError(f"Token decode failed: {e!s}") from e
