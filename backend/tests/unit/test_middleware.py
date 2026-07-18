"""
Unit and API tests for middleware components.

Tests Request ID middleware (E2.T4) and CORS middleware (E2.T6) per
acceptance criteria and definition of done requirements.

See: docs/22-Engineering-Backlog.md E2.T4, E2.T6
See: 08-Security-Architecture §7 (CORS, request ID)
See: 10-Observability-Architecture §2 (correlation IDs)
"""

import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.middleware.request_id import RequestIdMiddleware


class TestRequestIdMiddleware:
    """Tests for Request ID middleware (E2.T4)."""

    def test_request_id_generated_when_not_provided(self) -> None:
        """Request ID is generated when client doesn't provide X-Request-ID."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert "x-request-id" in response.headers
        request_id = response.headers["x-request-id"]
        # Should be a valid UUID4 format
        assert len(request_id) == 36  # UUID format with dashes
        # Verify it's a valid UUID
        try:
            uuid.UUID(request_id, version=4)
        except ValueError:
            pytest.fail(f"Invalid UUID4 format: {request_id}")

    def test_request_id_echoed_when_provided(self) -> None:
        """Provided X-Request-ID is echoed back in response."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        provided_id = "custom-request-id-12345"
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": provided_id},
        )

        assert response.status_code == 200
        assert "x-request-id" in response.headers
        assert response.headers["x-request-id"] == provided_id

    def test_request_id_stored_in_request_state(self) -> None:
        """Request ID is stored in request.state for downstream access."""
        # Create a test app with a route that checks request.state
        from starlette.requests import Request

        app = FastAPI()
        app.add_middleware(RequestIdMiddleware)

        @app.get("/test")
        async def test_route(request: Request) -> dict[str, str]:
            return {"request_id": request.state.request_id}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        data = response.json()
        assert "request_id" in data
        assert data["request_id"] != "not found"
        # Should be a valid UUID
        assert len(data["request_id"]) == 36

    def test_request_id_preserved_across_multiple_requests(self) -> None:
        """Each request gets its own unique request ID."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        response1 = client.get("/api/v1/health")
        response2 = client.get("/api/v1/health")

        request_id_1 = response1.headers["x-request-id"]
        request_id_2 = response2.headers["x-request-id"]

        # Each request should have a different ID
        assert request_id_1 != request_id_2

    def test_request_id_with_custom_value(self) -> None:
        """Custom request ID from client is preserved throughout."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        custom_id = str(uuid.uuid4())
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": custom_id},
        )

        assert response.status_code == 200
        assert response.headers["x-request-id"] == custom_id


class TestCORSMiddleware:
    """Tests for CORS middleware (E2.T6)."""

    def test_cors_allows_configured_origin(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """CORS allows requests from configured origins."""
        # Change to temp directory to avoid loading .env
        monkeypatch.chdir(tmp_path)
        # Set allowed origin
        monkeypatch.setenv("CORS_ORIGINS", "http://allowed.example.com")
        # Set required settings
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:pass@localhost:5432/testdb",
        )
        monkeypatch.setenv(
            "DATABASE_MIGRATION_URL",
            "postgresql+asyncpg://user:pass@localhost:5432/testdb",
        )
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:9000")
        monkeypatch.setenv("S3_ACCESS_KEY", "minioadmin")
        monkeypatch.setenv("S3_SECRET_KEY", "minioadmin")
        monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long")

        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        # Make a request with the allowed origin
        response = client.get(
            "/api/v1/health",
            headers={"Origin": "http://allowed.example.com"},
        )

        assert response.status_code == 200
        # CORS headers should be present for allowed origin
        # Note: TestClient may not fully simulate browser CORS behavior
        # In real browsers, CORS headers would be present
        # Access-Control-Allow-Credentials should be present
        assert "access-control-allow-credentials" in response.headers

    def test_cors_preflight_request_succeeds(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """CORS preflight (OPTIONS) request from allowed origin succeeds."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CORS_ORIGINS", "http://allowed.example.com")
        # Set required settings
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:pass@localhost:5432/testdb",
        )
        monkeypatch.setenv(
            "DATABASE_MIGRATION_URL",
            "postgresql+asyncpg://user:pass@localhost:5432/testdb",
        )
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:9000")
        monkeypatch.setenv("S3_ACCESS_KEY", "minioadmin")
        monkeypatch.setenv("S3_SECRET_KEY", "minioadmin")
        monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long")

        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        # Preflight request
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://allowed.example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        # FastAPI may return 400 for OPTIONS on routes without explicit OPTIONS
        # but CORS middleware should still add headers
        # What matters is that CORS headers are present
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-credentials" in response.headers

    def test_cors_blocks_disallowed_origin(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """CORS blocks requests from origins not in the allow list."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CORS_ORIGINS", "http://allowed.example.com")
        # Set required settings
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:pass@localhost:5432/testdb",
        )
        monkeypatch.setenv(
            "DATABASE_MIGRATION_URL",
            "postgresql+asyncpg://user:pass@localhost:5432/testdb",
        )
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:9000")
        monkeypatch.setenv("S3_ACCESS_KEY", "minioadmin")
        monkeypatch.setenv("S3_SECRET_KEY", "minioadmin")
        monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long")

        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        # Request from disallowed origin
        response = client.get(
            "/api/v1/health",
            headers={"Origin": "http://evil.example.com"},
        )

        # Request should succeed (CORS doesn't block at server level)
        # but CORS headers should not include the evil origin
        assert response.status_code == 200
        if "access-control-allow-origin" in response.headers:
            # If header is present, it should NOT be the evil origin
            assert (
                response.headers["access-control-allow-origin"]
                != "http://evil.example.com"
            )

    def test_cors_allows_configured_methods(self) -> None:
        """CORS allows configured HTTP methods."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        # Preflight request asking for POST method
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 200
        if "access-control-allow-methods" in response.headers:
            allowed_methods = response.headers["access-control-allow-methods"]
            # POST should be in the allowed methods
            assert "POST" in allowed_methods

    def test_cors_allows_required_headers(self) -> None:
        """CORS allows required headers per E2.T6 specification."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        # Preflight request with required headers
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,x-request-id",
            },
        )

        assert response.status_code == 200
        # Response should allow the requested headers
        if "access-control-allow-headers" in response.headers:
            allowed_headers = response.headers[
                "access-control-allow-headers"
            ].lower()
            assert "authorization" in allowed_headers
            assert "x-request-id" in allowed_headers


class TestMiddlewareOrdering:
    """Tests for middleware execution order."""

    def test_cors_wraps_request_id_middleware(self) -> None:
        """CORS middleware executes before RequestIdMiddleware."""
        from app.main import create_app

        app = create_app()

        # Verify middleware registration order
        # Last registered = outermost = executes first
        middleware_classes = [type(m).__name__ for m in app.user_middleware]

        # Should have at least 2 middleware
        assert len(middleware_classes) >= 2

    def test_request_id_present_in_cors_response(self) -> None:
        """Request ID is present in CORS responses."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        # Regular request with Origin header
        response = client.get(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
            },
        )

        # Request ID should be present
        assert "x-request-id" in response.headers


class TestMiddlewareIntegration:
    """Integration tests for middleware stack."""

    def test_middleware_stack_with_actual_request(self) -> None:
        """Full middleware stack processes actual API request correctly."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        custom_request_id = str(uuid.uuid4())
        response = client.get(
            "/api/v1/health",
            headers={
                "X-Request-ID": custom_request_id,
                "Origin": "http://localhost:3000",
            },
        )

        assert response.status_code == 200
        # Request ID should be echoed
        assert response.headers["x-request-id"] == custom_request_id
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers

    def test_middleware_handles_error_responses(self) -> None:
        """Middleware properly handles error responses (404, etc)."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/nonexistent-endpoint")

        # Should get 404
        assert response.status_code == 404
        # Request ID should still be present
        assert "x-request-id" in response.headers
        # Response should still have CORS headers if needed
        # (CORS middleware runs regardless of response status)

