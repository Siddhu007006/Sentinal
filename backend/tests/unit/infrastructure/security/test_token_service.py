"""Tests for JWT Token Service.

Tests verify:
- Token creation with correct lifetimes (15 min access, 30 day refresh)
- Token decoding with claim validation
- Token expiry detection
- Invalid signature/structure handling
- Unique JTI per token
- Access tokens include role claim; refresh tokens do not
- Algorithm/key configuration

Per Requirement 3 in requirements.md and design.md § JWT Token Service.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest

from app.domain.entities.user import UserRole
from app.infrastructure.security.jwt import (
    InvalidTokenError,
    TokenExpiredError,
    TokenPayload,
    TokenService,
)


class TestTokenPayload:
    """Test suite for TokenPayload dataclass."""

    def test_token_payload_creation(self) -> None:
        """Test that TokenPayload can be created with all required fields."""
        user_id = uuid4()
        now = datetime.now(tz=UTC)
        expiry = now + timedelta(minutes=15)

        payload = TokenPayload(
            sub=user_id,
            exp=expiry,
            iat=now,
            jti="test-jti-123",
            role=UserRole.ADMIN,
        )

        assert payload.sub == user_id
        assert payload.exp == expiry
        assert payload.iat == now
        assert payload.jti == "test-jti-123"
        assert payload.role == UserRole.ADMIN

    def test_token_payload_without_role(self) -> None:
        """Test that TokenPayload can be created without role (refresh tokens)."""
        user_id = uuid4()
        now = datetime.now(tz=UTC)
        expiry = now + timedelta(days=30)

        payload = TokenPayload(
            sub=user_id,
            exp=expiry,
            iat=now,
            jti="test-jti-456",
        )

        assert payload.sub == user_id
        assert payload.role is None

    def test_is_expired_returns_true_when_expired(self) -> None:
        """Test that is_expired returns True for expired token."""
        user_id = uuid4()
        now = datetime.now(tz=UTC)
        past_expiry = now - timedelta(minutes=1)

        payload = TokenPayload(
            sub=user_id,
            exp=past_expiry,
            iat=now - timedelta(minutes=15),
            jti="test-jti-789",
        )

        assert payload.is_expired() is True

    def test_is_expired_returns_false_when_not_expired(self) -> None:
        """Test that is_expired returns False for valid token."""
        user_id = uuid4()
        now = datetime.now(tz=UTC)
        future_expiry = now + timedelta(minutes=15)

        payload = TokenPayload(
            sub=user_id,
            exp=future_expiry,
            iat=now,
            jti="test-jti-101",
        )

        assert payload.is_expired() is False


class TestTokenService:
    """Test suite for TokenService."""

    @pytest.fixture
    def token_service(self) -> TokenService:
        """Create a TokenService instance."""
        return TokenService()

    @pytest.fixture
    def user_id(self) -> UUID:
        """Create a test user ID."""
        return uuid4()

    # Access Token Tests

    def test_create_access_token_returns_string(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that create_access_token returns a JWT string."""
        token = token_service.create_access_token(user_id, UserRole.ADMIN)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_is_valid_jwt(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that access token is a valid JWT (can be decoded)."""
        token = token_service.create_access_token(
            user_id, UserRole.ANALYST
        )

        # Should not raise an exception
        decoded = token_service.decode_token(token)
        assert decoded is not None

    def test_create_access_token_includes_all_required_claims(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that access token includes all required claims."""
        token = token_service.create_access_token(user_id, UserRole.VIEWER)
        decoded = token_service.decode_token(token)

        assert decoded.sub == user_id
        assert decoded.role == UserRole.VIEWER
        assert decoded.jti is not None
        assert decoded.exp is not None
        assert decoded.iat is not None

    def test_create_access_token_has_15_minute_expiry(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that access token has exactly 15-minute expiry."""
        before = datetime.now(tz=UTC)
        token = token_service.create_access_token(user_id, UserRole.ADMIN)
        after = datetime.now(tz=UTC)
        decoded = token_service.decode_token(token)

        # Expiry should be ~15 minutes from now
        expected_expiry_min = before + timedelta(
            minutes=token_service.ACCESS_TOKEN_EXPIRY_MINUTES - 1
        )
        expected_expiry_max = after + timedelta(
            minutes=token_service.ACCESS_TOKEN_EXPIRY_MINUTES + 1
        )

        assert expected_expiry_min <= decoded.exp <= expected_expiry_max

    def test_create_access_token_each_token_has_unique_jti(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that each access token has a unique JTI."""
        token1 = token_service.create_access_token(user_id, UserRole.ADMIN)
        token2 = token_service.create_access_token(user_id, UserRole.ADMIN)

        decoded1 = token_service.decode_token(token1)
        decoded2 = token_service.decode_token(token2)

        # JTIs should be different
        assert decoded1.jti != decoded2.jti

    # Refresh Token Tests

    def test_create_refresh_token_returns_string(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that create_refresh_token returns a JWT string."""
        token = token_service.create_refresh_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token_is_valid_jwt(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that refresh token is a valid JWT (can be decoded)."""
        token = token_service.create_refresh_token(user_id)

        # Should not raise an exception
        decoded = token_service.decode_token(token)
        assert decoded is not None

    def test_create_refresh_token_includes_required_claims(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that refresh token includes required claims."""
        token = token_service.create_refresh_token(user_id)
        decoded = token_service.decode_token(token)

        assert decoded.sub == user_id
        assert decoded.jti is not None
        assert decoded.exp is not None
        assert decoded.iat is not None

    def test_create_refresh_token_does_not_include_role(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that refresh token does NOT include role claim."""
        token = token_service.create_refresh_token(user_id)
        decoded = token_service.decode_token(token)

        assert decoded.role is None

    def test_create_refresh_token_has_30_day_expiry(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that refresh token has exactly 30-day expiry."""
        before = datetime.now(tz=UTC)
        token = token_service.create_refresh_token(user_id)
        after = datetime.now(tz=UTC)
        decoded = token_service.decode_token(token)

        # Expiry should be ~30 days from now
        expected_expiry_min = before + timedelta(
            days=token_service.REFRESH_TOKEN_EXPIRY_DAYS - 1
        )
        expected_expiry_max = after + timedelta(
            days=token_service.REFRESH_TOKEN_EXPIRY_DAYS + 1
        )

        assert expected_expiry_min <= decoded.exp <= expected_expiry_max

    def test_create_refresh_token_each_token_has_unique_jti(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that each refresh token has a unique JTI."""
        token1 = token_service.create_refresh_token(user_id)
        token2 = token_service.create_refresh_token(user_id)

        decoded1 = token_service.decode_token(token1)
        decoded2 = token_service.decode_token(token2)

        # JTIs should be different
        assert decoded1.jti != decoded2.jti

    # Decode Token Tests

    def test_decode_token_with_valid_token_succeeds(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that decode_token succeeds with a valid token."""
        token = token_service.create_access_token(user_id, UserRole.ADMIN)
        decoded = token_service.decode_token(token)

        assert decoded.sub == user_id
        assert decoded.role == UserRole.ADMIN

    def test_decode_token_with_expired_token_raises_token_expired_error(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that decode_token raises TokenExpiredError for expired token."""
        # Create a token and manually manipulate it to be expired
        # by using jwt.encode with a past expiry time
        now = datetime.now(tz=UTC)
        past_expiry = now - timedelta(seconds=1)

        payload = {
            "sub": str(user_id),
            "role": "admin",
            "exp": past_expiry,
            "iat": now,
            "jti": str(uuid4()),
        }

        token = jwt.encode(
            payload,
            token_service.secret_key,
            algorithm=token_service.algorithm,
        )

        with pytest.raises(TokenExpiredError):
            token_service.decode_token(token)

    def test_decode_token_with_invalid_signature_raises_invalid_token_error(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that decode_token raises InvalidTokenError for invalid signature."""
        # Create a valid token
        token = token_service.create_access_token(user_id, UserRole.ADMIN)

        # Tamper with the token (corrupt signature)
        tampered_token = token[:-5] + "XXXXX"

        with pytest.raises(InvalidTokenError):
            token_service.decode_token(tampered_token)

    def test_decode_token_with_malformed_token_raises_invalid_token_error(
        self, token_service: TokenService
    ) -> None:
        """Test decode_token raises InvalidTokenError for malformed."""
        malformed_token = "not.a.valid.token"  # noqa: S105

        with pytest.raises(InvalidTokenError):
            token_service.decode_token(malformed_token)

    def test_decode_token_with_empty_token_raises_invalid_token_error(
        self, token_service: TokenService
    ) -> None:
        """Test that decode_token raises InvalidTokenError for empty token."""
        with pytest.raises(InvalidTokenError):
            token_service.decode_token("")

    def test_decode_token_missing_required_claim_raises_invalid_token_error(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test decode_token raises error when required claim missing."""
        # Create a token without jti (required claim)
        now = datetime.now(tz=UTC)
        expiry = now + timedelta(minutes=15)

        payload = {
            "sub": str(user_id),
            "role": "admin",
            "exp": expiry,
            "iat": now,
            # Missing "jti" claim
        }

        token = jwt.encode(
            payload,
            token_service.secret_key,
            algorithm=token_service.algorithm,
        )

        with pytest.raises(InvalidTokenError, match="Missing required claims"):
            token_service.decode_token(token)

    def test_decode_token_returns_token_payload_instance(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that decode_token returns a TokenPayload instance."""
        token = token_service.create_access_token(user_id, UserRole.ANALYST)
        decoded = token_service.decode_token(token)

        assert isinstance(decoded, TokenPayload)

    # Algorithm and Configuration Tests

    def test_token_service_uses_configured_algorithm(
        self, token_service: TokenService
    ) -> None:
        """Test that TokenService uses the configured algorithm."""
        # Default should be HS256
        assert token_service.algorithm in ["HS256", "RS256"]

    def test_token_service_has_secret_key(
        self, token_service: TokenService
    ) -> None:
        """Test that TokenService has a secret key."""
        assert token_service.secret_key is not None
        assert len(token_service.secret_key) > 0

    # Cross-Role Tests

    def test_different_roles_in_access_tokens(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that different roles are correctly encoded in access tokens."""
        for role in [UserRole.ADMIN, UserRole.ANALYST, UserRole.VIEWER]:
            token = token_service.create_access_token(user_id, role)
            decoded = token_service.decode_token(token)

            assert decoded.role == role

    # Token Payload Fields

    def test_token_payload_sub_is_uuid(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that TokenPayload.sub is a UUID."""
        token = token_service.create_access_token(user_id, UserRole.ADMIN)
        decoded = token_service.decode_token(token)

        assert isinstance(decoded.sub, UUID)
        assert decoded.sub == user_id

    def test_token_payload_exp_is_datetime(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that TokenPayload.exp is a datetime."""
        token = token_service.create_access_token(user_id, UserRole.ADMIN)
        decoded = token_service.decode_token(token)

        assert isinstance(decoded.exp, datetime)

    def test_token_payload_iat_is_datetime(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that TokenPayload.iat is a datetime."""
        token = token_service.create_access_token(user_id, UserRole.ADMIN)
        decoded = token_service.decode_token(token)

        assert isinstance(decoded.iat, datetime)

    def test_token_payload_jti_is_string(
        self, token_service: TokenService, user_id: UUID
    ) -> None:
        """Test that TokenPayload.jti is a string."""
        token = token_service.create_access_token(user_id, UserRole.ADMIN)
        decoded = token_service.decode_token(token)

        assert isinstance(decoded.jti, str)
        assert len(decoded.jti) > 0


class TestTokenServiceIntegration:
    """Integration tests for token lifecycle."""

    def test_token_lifecycle_access_token(self) -> None:
        """Test complete lifecycle of access token: create -> decode -> check expiry."""
        user_id = uuid4()
        service = TokenService()

        # Create
        token = service.create_access_token(user_id, UserRole.ADMIN)
        assert isinstance(token, str)

        # Decode
        payload = service.decode_token(token)
        assert payload.sub == user_id
        assert payload.role == UserRole.ADMIN

        # Check expiry
        assert not payload.is_expired()

    def test_token_lifecycle_refresh_token(self) -> None:
        """Test refresh token lifecycle: create -> decode -> expiry."""
        user_id = uuid4()
        service = TokenService()

        # Create
        token = service.create_refresh_token(user_id)
        assert isinstance(token, str)

        # Decode
        payload = service.decode_token(token)
        assert payload.sub == user_id
        assert payload.role is None

        # Check expiry
        assert not payload.is_expired()

    def test_multiple_users_have_separate_tokens(self) -> None:
        """Test that different users have separate tokens."""
        user1_id = uuid4()
        user2_id = uuid4()
        service = TokenService()

        token1 = service.create_access_token(user1_id, UserRole.ADMIN)
        token2 = service.create_access_token(user2_id, UserRole.ANALYST)

        payload1 = service.decode_token(token1)
        payload2 = service.decode_token(token2)

        assert payload1.sub == user1_id
        assert payload2.sub == user2_id
        assert payload1.sub != payload2.sub

    def test_same_user_different_token_instances(self) -> None:
        """Test that same user can have multiple token instances."""
        user_id = uuid4()
        service = TokenService()

        token1 = service.create_access_token(user_id, UserRole.ADMIN)
        token2 = service.create_access_token(user_id, UserRole.ADMIN)

        # Tokens should be different strings (different JTI)
        assert token1 != token2

        # But decode to same user
        payload1 = service.decode_token(token1)
        payload2 = service.decode_token(token2)

        assert payload1.sub == payload2.sub == user_id
        # But different JTI (for revocation tracking)
        assert payload1.jti != payload2.jti
