"""
Unit tests for FastAPI application factory.

Tests create_app() factory function, lifespan management, middleware
registration, exception handler registration, and router configuration
per E2.T2 acceptance criteria.

See: 07-Backend-Development-Standards §3 (application factory).
See: docs/22-Engineering-Backlog.md E2.T2 (Application Factory).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestCreateApp:
    """Tests for create_app factory function."""

    def test_create_app_returns_fastapi_instance(self) -> None:
        """create_app returns a FastAPI application instance."""
        from app.main import create_app

        app = create_app()

        assert isinstance(app, FastAPI)
        assert app.title == "Sentinel"
        assert app.version == "1.0.0"

    def test_create_app_loads_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """create_app loads settings via get_settings()."""
        from app.main import create_app

        # Ensure settings load successfully (will raise if invalid)
        app = create_app()

        # Verify app was created
        assert app is not None
        assert isinstance(app, FastAPI)

    def test_create_app_registers_routes(self) -> None:
        """create_app registers API v1 routes with correct prefix."""
        from app.main import create_app

        app = create_app()

        # Check that routes are registered
        # Use getattr to get path safely (some routes may not have path attr)
        route_paths = [getattr(route, "path", "") for route in app.routes]

        # Should have /api/v1/health from api_v1_router
        assert any("/api/v1" in path for path in route_paths)

    def test_create_app_configures_openapi_urls(self) -> None:
        """create_app configures OpenAPI documentation URLs."""
        from app.main import create_app

        app = create_app()

        assert app.docs_url == "/api/v1/docs"
        assert app.redoc_url == "/api/v1/redoc"
        assert app.openapi_url == "/api/v1/openapi.json"

    def test_create_app_configures_cors_middleware(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_app configures CORS middleware with settings."""
        # Set CORS origins in environment
        monkeypatch.setenv("CORS_ORIGINS", "http://test.example.com")
        # Set other required settings
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

        # Check that middleware is registered
        # FastAPI wraps middleware in Middleware class
        assert len(app.user_middleware) > 0
        # Verify we have multiple middleware (CORS + RequestId)
        assert len(app.user_middleware) >= 2

    def test_create_app_registers_exception_handlers(self) -> None:
        """create_app registers centralized exception handlers."""
        from app.main import create_app

        app = create_app()

        # Verify exception handlers are registered
        # FastAPI stores these in app.exception_handlers
        assert len(app.exception_handlers) > 0

    def test_create_app_includes_middleware_stack(self) -> None:
        """create_app includes middleware stack (CORS and RequestId)."""
        from app.main import create_app

        app = create_app()

        # Check that middleware is registered
        # FastAPI wraps user middleware, so we verify count
        assert len(app.user_middleware) >= 2  # At least CORS + RequestId


class TestAppModuleLevel:
    """Tests for module-level app instance."""

    def test_app_module_level_instance_exists(self) -> None:
        """main.py exports module-level 'app' instance for uvicorn."""
        from app.main import app

        assert isinstance(app, FastAPI)

    def test_app_is_created_via_factory(self) -> None:
        """Module-level app is created via create_app() factory."""
        from app.main import app, create_app

        # Both should be FastAPI instances
        assert isinstance(app, FastAPI)
        assert callable(create_app)

        # create_app should return a FastAPI instance
        new_app = create_app()
        assert isinstance(new_app, FastAPI)
        # New instance should be different (factory creates new)
        assert new_app is not app


class TestHealthEndpoint:
    """Tests for health check endpoint via TestClient."""

    def test_health_endpoint_accessible(self) -> None:
        """GET /api/v1/health returns 200 with expected schema."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"  # Health endpoint returns "ok" not "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_health_endpoint_includes_request_id(self) -> None:
        """Health endpoint response includes X-Request-ID header."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/health")

        assert "x-request-id" in response.headers
        # Should be a valid UUID format
        request_id = response.headers["x-request-id"]
        assert len(request_id) == 36  # UUID4 format with dashes


class TestOpenAPIDocumentation:
    """Tests for OpenAPI documentation endpoints."""

    def test_openapi_docs_accessible(self) -> None:
        """OpenAPI docs endpoint is accessible."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/docs")

        # Should return HTML (docs UI)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_json_accessible(self) -> None:
        """OpenAPI schema JSON endpoint is accessible."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "Sentinel"
        assert data["info"]["version"] == "1.0.0"

    def test_redoc_accessible(self) -> None:
        """ReDoc documentation endpoint is accessible."""
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/redoc")

        # Should return HTML (ReDoc UI)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestLifespanManagement:
    """Tests for application lifespan management."""

    def test_lifespan_is_configured(self) -> None:
        """Lifespan context manager is configured on the application."""
        from app.main import create_app

        app = create_app()

        # Lifespan is configured
        assert app.router.lifespan_context is not None

    def test_app_can_be_used_with_testclient(self) -> None:
        """Application can be used with TestClient (exercises lifespan)."""
        from app.main import create_app

        app = create_app()

        # TestClient automatically handles lifespan startup/shutdown
        with TestClient(app) as client:
            # During lifespan, app should be operational
            response = client.get("/api/v1/health")
            assert response.status_code == 200

        # After exiting, shutdown hooks have executed
        # (Currently no-op, but validates the pattern)
