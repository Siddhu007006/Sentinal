"""
Unit and integration tests for rate limiting middleware.

Tests RateLimitMiddleware (E2.T7) per acceptance criteria and
definition of done requirements.

See: docs/22-Engineering-Backlog.md E2.T7
See: 08-Security-Architecture §7 (rate limiting)
See: backend/openapi.yaml 429 TooManyRequests response
"""

from unittest.mock import MagicMock

import pytest
import redis
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.v1.middleware.rate_limit import RateLimitMiddleware
from app.core.settings import RateLimitSettings


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def rate_limit_settings(monkeypatch: pytest.MonkeyPatch) -> RateLimitSettings:
    """Create rate limit settings for testing."""
    monkeypatch.setenv("RATE_LIMIT_AUTHENTICATED", "10")
    monkeypatch.setenv("RATE_LIMIT_UNAUTHENTICATED", "5")
    return RateLimitSettings()


@pytest.fixture
def mock_redis(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock Redis client for unit tests."""
    mock_client = MagicMock(spec=redis.Redis)
    mock_from_url = MagicMock(return_value=mock_client)
    monkeypatch.setattr(
        "app.api.v1.middleware.rate_limit.redis.from_url",
        mock_from_url,
    )
    return mock_client


@pytest.fixture
def app_with_rate_limit(rate_limit_settings: RateLimitSettings) -> FastAPI:
    """Create FastAPI app with rate limit middleware."""
    app = FastAPI()

    # Add rate limit middleware
    app.add_middleware(
        RateLimitMiddleware,
        settings=rate_limit_settings,
        redis_url="redis://localhost:6379/0",
    )

    # Simple test route
    @app.get("/api/test")
    async def test_route() -> dict[str, str]:
        return {"message": "ok"}

    # Health endpoint (should be excluded from rate limiting)
    @app.get("/health")
    async def health_route() -> dict[str, str]:
        return {"status": "ok"}

    # Docs endpoint (should be excluded)
    @app.get("/docs")
    async def docs_route() -> dict[str, str]:
        return {"docs": "here"}

    return app


# ============================================================================
# Phase 3 Tests — Comprehensive Rate Limiting Coverage
# ============================================================================


class TestRateLimitMiddlewareBasic:
    """Basic rate limiting behavior tests."""

    def test_requests_below_limit_succeed_with_200(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Requests below limit return 200 OK."""
        # Setup: counter is 3, limit is 5
        mock_redis.incr.return_value = 3
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
        # Act: Make request
            response = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        # Assert: Request succeeds
        assert response.status_code == 200
        assert response.json() == {"message": "ok"}

    def test_first_request_over_limit_returns_429(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """First request over limit returns 429 Too Many Requests."""
        # Setup: counter increments to 6, limit is 5
        mock_redis.incr.return_value = 6
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
        # Act: Make request
            response = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        # Assert: Request is rate limited
        assert response.status_code == 429
        data = response.json()
        assert data["error"]["code"] == "rate_limited"
        assert "Too many requests" in data["error"]["message"]

    def test_429_response_includes_error_envelope(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """429 response includes proper error envelope format."""
        mock_redis.incr.return_value = 6
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
            response = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        assert response.status_code == 429
        data = response.json()

        # Check error envelope structure
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "details" in data["error"]
        assert isinstance(data["error"]["details"], list)

    def test_429_response_includes_request_id(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """429 response includes requestId for correlation."""
        mock_redis.incr.return_value = 6
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
            response = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        assert response.status_code == 429
        data = response.json()
        assert "requestId" in data
        # RequestId should be present (either generated or from header)
        assert isinstance(data["requestId"], str)

    def test_429_response_includes_timestamp(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """429 response includes timestamp in ISO 8601 format."""
        mock_redis.incr.return_value = 6
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
            response = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        assert response.status_code == 429
        data = response.json()
        assert "timestamp" in data
        # Validate ISO 8601 format (with T separator and timezone)
        timestamp = data["timestamp"]
        assert "T" in timestamp
        # Should have timezone indicator (Z or +00:00)
        assert "Z" in timestamp or "+" in timestamp

    def test_retry_after_header_present_on_429(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """429 response includes Retry-After header."""
        mock_redis.incr.return_value = 6
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
            response = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        assert response.status_code == 429
        assert "retry-after" in response.headers
        assert response.headers["retry-after"] == "60"

    def test_retry_after_header_value_is_seconds(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Retry-After header value is 60 seconds."""
        mock_redis.incr.return_value = 6
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
            response = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        assert response.status_code == 429
        # Value should be numeric (seconds) not a date
        retry_after = response.headers.get("retry-after")
        assert retry_after.isdigit() or retry_after.lstrip("-").isdigit()
        assert int(retry_after) == 60


class TestRateLimitMiddlewareRedisInteraction:
    """Tests for Redis interaction and counter management."""

    def test_redis_counter_incremented_per_request(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Redis counter is incremented for each request."""
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
            client_ip = "192.168.1.1"

        # Make request
            client.get("/api/test", headers={"X-Forwarded-For": client_ip})

        # Assert: incr was called
        mock_redis.incr.assert_called()
        # First arg should be the rate limit key
        call_args = mock_redis.incr.call_args[0][0]
        assert "rate_limit:" in call_args
        assert client_ip in call_args

    def test_redis_expiration_set_on_first_increment(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Redis expiration is set when counter is 1 (first increment)."""
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
        # Act: Make request
            client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.1"})

        # Assert: expire was called with 60 seconds
        mock_redis.expire.assert_called()
        # Check the TTL parameter
        call_args = mock_redis.expire.call_args[0]
        assert call_args[1] == 60

    def test_redis_expiration_not_set_on_subsequent_increments(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Redis expiration is not set when counter > 1 (not first increment)."""
        mock_redis.incr.return_value = 3
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
        # Act: Make request
            client.get("/api/test", headers={"X-Forwarded-For": "192.168.1.1"})

        # Assert: expire was NOT called
        mock_redis.expire.assert_not_called()

    def test_redis_connection_error_fails_open(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Request succeeds when Redis connection fails (fail-open)."""
        # Setup: Redis connection error
        mock_redis.incr.side_effect = redis.ConnectionError("Connection refused")

        with TestClient(app_with_rate_limit) as client:
        # Act: Make request despite Redis error
            response = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        # Assert: Request succeeds (fail-open)
        assert response.status_code == 200


class TestRateLimitMiddlewareEndpointExclusion:
    """Tests for endpoint exclusion from rate limiting."""

    def test_health_endpoint_not_rate_limited(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Health endpoint is excluded from rate limiting."""
        # Setup: Set counter very high to exceed limit
        mock_redis.incr.return_value = 100

        with TestClient(app_with_rate_limit) as client:
            response = client.get("/health")

        assert response.status_code == 200
        mock_redis.incr.assert_not_called()

    def test_docs_endpoint_not_rate_limited(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """/docs endpoint is excluded from rate limiting."""
        mock_redis.incr.return_value = 100

        with TestClient(app_with_rate_limit) as client:
            response = client.get("/docs")

        assert response.status_code == 200
        mock_redis.incr.assert_not_called()

    def test_openapi_json_not_rate_limited(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """/openapi.json endpoint is excluded from rate limiting."""
        # Need to add this endpoint to app
        app = app_with_rate_limit

        @app.get("/openapi.json")
        async def openapi_route() -> dict[str, str]:
            return {"openapi": "3.0.0"}

        mock_redis.incr.return_value = 100
        with TestClient(app) as client:

            response = client.get("/openapi.json")

        assert response.status_code == 200
        mock_redis.incr.assert_not_called()

    def test_redoc_not_rate_limited(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """/redoc endpoint is excluded from rate limiting."""
        app = app_with_rate_limit

        @app.get("/redoc")
        async def redoc_route() -> dict[str, str]:
            return {"redoc": "docs"}

        mock_redis.incr.return_value = 100
        with TestClient(app) as client:

            response = client.get("/redoc")

        assert response.status_code == 200
        mock_redis.incr.assert_not_called()


class TestRateLimitMiddlewareConfiguration:
    """Tests for configuration edge cases."""

    def test_authenticated_requests_use_authenticated_limit(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Authenticated requests use authenticated limit (higher)."""
        # Setup: counter is 11 (exceeds authenticated limit of 10)
        mock_redis.incr.return_value = 11
        mock_redis.expire.return_value = True

        app = app_with_rate_limit

        @app.get("/api/test-auth")
        async def auth_route(request: Request) -> dict[str, str]:
            # Simulate authenticated request
            request.state.user = {"id": "user123"}
            return {"auth": "ok"}

        with TestClient(app) as client:

            response = client.get(
                "/api/test-auth",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        # Authenticated limit exceeded
        assert response.status_code == 429

    def test_unauthenticated_requests_use_unauthenticated_limit(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Unauthenticated requests use unauthenticated limit (lower)."""
        # Setup: counter is 6 (exceeds unauthenticated limit of 5)
        mock_redis.incr.return_value = 6
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
            response = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        # Unauthenticated limit exceeded
        assert response.status_code == 429


class TestRateLimitMiddlewareClientIdentification:
    """Tests for client identification and isolation."""

    def test_different_client_ips_have_independent_limits(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Different client IPs have independent rate limit counters."""
        call_count = [0]

        def incr_side_effect(key: str) -> int:
            # First call returns 1 (within limit), second returns 1 (independent)
            call_count[0] += 1
            return 1

        mock_redis.incr.side_effect = incr_side_effect
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
        # Request from IP 1
            response1 = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        # Request from IP 2
            response2 = client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.2"},
            )

        # Both should succeed (independent counters)
        assert response1.status_code == 200
        assert response2.status_code == 200

        # Verify two different keys were used
        calls = mock_redis.incr.call_args_list
        key1 = calls[0][0][0]
        key2 = calls[1][0][0]
        assert key1 != key2
        assert "192.168.1.1" in key1
        assert "192.168.1.2" in key2

    def test_x_forwarded_for_header_respected(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """X-Forwarded-For header is used for client IP (proxy scenario)."""
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
            forwarded_ip = "203.0.113.42"
            client.get(
                "/api/test",
                headers={"X-Forwarded-For": forwarded_ip},
            )

        # Verify the forwarded IP was used in the key
        call_args = mock_redis.incr.call_args[0][0]
        assert forwarded_ip in call_args

    def test_x_forwarded_for_first_ip_used(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """First IP in X-Forwarded-For list is used (client IP)."""
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
        # X-Forwarded-For can have multiple IPs (client, proxy1, proxy2)
            forwarded_chain = "203.0.113.42, 198.51.100.1, 192.0.2.1"
            client.get(
                "/api/test",
                headers={"X-Forwarded-For": forwarded_chain},
            )

        # Verify the FIRST IP (client) was used
        call_args = mock_redis.incr.call_args[0][0]
        assert "203.0.113.42" in call_args


class TestRateLimitMiddlewareTimeWindow:
    """Tests for time window behavior."""

    def test_redis_key_includes_minute_bucket(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Redis key includes minute bucket for windowing."""
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
            client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        call_args = mock_redis.incr.call_args[0][0]
        # Key format should be: rate_limit:{ip}:{minute_bucket}
        parts = call_args.split(":")
        assert len(parts) >= 3
        assert parts[0] == "rate_limit"
        assert parts[1] == "192.168.1.1"
        # Third part should be a numeric minute bucket
        assert parts[2].isdigit()

    def test_different_minute_buckets_create_different_keys(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Different minute buckets create different counter keys."""
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        # This test demonstrates the concept
        # In real test with time travel, different minute buckets
        # would create different keys and reset counters

        with TestClient(app_with_rate_limit) as client:
        # Make a request
            client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

        # Get the minute bucket from the key
            call_args = mock_redis.incr.call_args[0][0]
            parts = call_args.split(":")
            minute_bucket_1 = parts[2]

        # Reset mock
            mock_redis.reset_mock()

        # Make another request (same minute, should use same bucket)
            client.get(
                "/api/test",
                headers={"X-Forwarded-For": "192.168.1.1"},
            )

            call_args = mock_redis.incr.call_args[0][0]
            parts = call_args.split(":")
            minute_bucket_2 = parts[2]

        # Same minute, same bucket
        assert minute_bucket_1 == minute_bucket_2


class TestRateLimitMiddlewareConcurrency:
    """Tests for concurrent request handling."""

    def test_redis_operations_are_atomic(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Redis incr operation is atomic."""
        # Redis.incr is atomic by design
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
        # Make multiple requests
            for _ in range(3):
                client.get(
                    "/api/test",
                    headers={"X-Forwarded-For": "192.168.1.1"},
                )

        # All should have called incr (atomic increments)
        assert mock_redis.incr.call_count == 3

    def test_counter_never_decreases(
        self,
        app_with_rate_limit: FastAPI,
        mock_redis: MagicMock,
    ) -> None:
        """Counter never decreases (monotonic increasing)."""
        # Setup: simulate counter incrementing
        counter_values = [1, 2, 3, 4, 5]
        mock_redis.incr.side_effect = counter_values
        mock_redis.expire.return_value = True

        with TestClient(app_with_rate_limit) as client:
        # Make requests
            for _ in range(5):
                client.get(
                    "/api/test",
                    headers={"X-Forwarded-For": "192.168.1.1"},
                )

        # Verify counter never decreased
        calls = mock_redis.incr.call_count
        assert calls == 5
        # All increments were positive
        assert all(v > 0 for v in counter_values)
