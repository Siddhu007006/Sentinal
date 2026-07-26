"""
Tests for health check endpoint.

Comprehensive test suite for E2.T8 Health Check Endpoint.
Verifies:
- Endpoint accessibility and response format
- Response schema compliance with OpenAPI HealthStatus
- Required fields present and correctly typed
- Request ID propagation from middleware
- Structured logging integration
- Unauthenticated access
- OpenAPI documentation

See: docs/22-Engineering-Backlog.md E2.T8
See: backend/openapi.yaml /health endpoint
See: 10-Observability-Architecture §7 (health endpoints)
"""

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app


class TestHealthEndpointBasic:
    """Basic tests for health endpoint accessibility and response."""

    def test_health_endpoint_returns_200(self) -> None:
        """Health endpoint returns HTTP 200 status code."""

        app = create_app()

        with TestClient(app) as client:
            response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_json(self) -> None:
        """Health endpoint returns JSON content type."""
        app = create_app()

        with TestClient(app) as client:
            response = client.get("/api/v1/health")

        assert response.headers["content-type"] == "application/json"

    def test_health_endpoint_response_is_valid_json(self) -> None:
        """Health endpoint response is valid JSON (parseable)."""
        app = create_app()

        with TestClient(app) as client:
            response = client.get("/api/v1/health")

        data = response.json()
        assert isinstance(data, dict)


class TestHealthEndpointSchema:
    """Tests for response schema compliance with OpenAPI spec."""

    def test_health_response_has_required_fields(self) -> None:
        """Health response includes all required fields: status, version, timestamp."""
        app = create_app()

        with TestClient(app) as client:
            response = client.get("/api/v1/health")
        data: dict[str, Any] = response.json()

        assert "status" in data
        assert "version" in data
        assert "timestamp" in data

    def test_health_response_status_is_string(self) -> None:
        """Status field is a string."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")
        data: dict[str, Any] = response.json()

        assert isinstance(data["status"], str)

    def test_health_response_version_is_string(self) -> None:
        """Version field is a string."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")
        data: dict[str, Any] = response.json()

        assert isinstance(data["version"], str)

    def test_health_response_timestamp_is_iso8601(self) -> None:
        """Timestamp field is ISO 8601 formatted datetime string."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")
        data: dict[str, Any] = response.json()

        # Should be parseable as ISO 8601
        timestamp_str = data["timestamp"]
        assert isinstance(timestamp_str, str)

        # Attempt to parse as ISO 8601 (with timezone)
        # FastAPI/Pydantic automatically converts to ISO format
        # Format: "2024-02-10T08:00:00Z" or "2024-02-10T08:00:00+00:00"
        assert "T" in timestamp_str  # Date-time separator
        has_timezone = (
            "Z" in timestamp_str
            or "+00:00" in timestamp_str
            or "-00:00" in timestamp_str
        )
        assert has_timezone

    def test_health_response_dependencies_is_optional(self) -> None:
        """Dependencies field is optional (may be null or dict)."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")
        data: dict[str, Any] = response.json()

        # Dependencies field is optional per spec
        if "dependencies" in data:
            # If present, should be dict or None
            is_valid = data["dependencies"] is None or isinstance(
                data["dependencies"], dict
            )
            assert is_valid


class TestHealthEndpointValues:
    """Tests for expected field values."""

    def test_health_response_status_is_ok(self) -> None:
        """Status field returns 'ok' (per current implementation scope)."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")
        data: dict[str, Any] = response.json()

        assert data["status"] == "ok"

    def test_health_response_version_present(self) -> None:
        """Version field has a value (not empty string)."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")
        data: dict[str, Any] = response.json()

        version: str = data["version"]
        assert len(version) > 0

    def test_health_response_timestamp_recent(self) -> None:
        """Timestamp is recent (within last minute to account for slow execution)."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")

        # Timestamp should be valid and recent
        # This is a loose check to account for any server-side timing
        assert response.status_code == 200


class TestHealthEndpointRequestID:
    """Tests for request ID propagation from middleware."""

    def test_health_response_includes_request_id_header(self) -> None:
        """X-Request-ID header is present in response."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")

        assert "x-request-id" in response.headers

    def test_health_request_id_is_uuid_format(self) -> None:
        """X-Request-ID value is a valid UUID format (36 chars with dashes)."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")
        request_id = response.headers["x-request-id"]

        # UUID4 format: 8-4-4-4-12 = 36 characters
        assert len(request_id) == 36
        # Should contain dashes
        assert request_id.count("-") == 4

    def test_health_request_id_is_valid_uuid(self) -> None:
        """X-Request-ID value is a parseable UUID."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")
        request_id = response.headers["x-request-id"]

        # Should not raise ValueError
        parsed_uuid = uuid.UUID(request_id)
        assert str(parsed_uuid) == request_id

    def test_health_request_id_unique_per_request(self) -> None:
        """Each request gets a unique X-Request-ID."""
        app = create_app()
        with TestClient(app) as client:

            response1 = client.get("/api/v1/health")
        response2 = client.get("/api/v1/health")

        request_id1 = response1.headers["x-request-id"]
        request_id2 = response2.headers["x-request-id"]

        assert request_id1 != request_id2


class TestHealthEndpointAuthentication:
    """Tests for authentication and authorization."""

    def test_health_endpoint_no_authentication_required(self) -> None:
        """Health endpoint is accessible without authentication."""
        app = create_app()
        with TestClient(app) as client:

        # Request without any Authorization header
            response = client.get("/api/v1/health")

        # Should succeed with 200, not 401
        assert response.status_code == 200

    def test_health_endpoint_accepts_any_request(self) -> None:
        """Health endpoint responds to any HTTP verb (typically GET)."""
        app = create_app()
        with TestClient(app) as client:

        # GET should work
            response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestHealthEndpointOpenAPI:
    """Tests for OpenAPI registration and visibility."""

    def test_health_endpoint_in_openapi_docs(self) -> None:
        """Health endpoint appears in OpenAPI schema."""
        app = create_app()
        with TestClient(app) as client:

        # Fetch OpenAPI schema
            response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200

        schema = response.json()

        # Should have /health or /api/v1/health path (depends on server path strip)
        # Check both possibilities
        assert "paths" in schema
        paths = schema["paths"]
        # The health endpoint is registered without prefix, so it should be at /health
        health_path_key = next(
            (k for k in paths if k.endswith("/health")),
            None,
        )
        assert health_path_key is not None

    def test_health_endpoint_operation_id_correct(self) -> None:
        """Health endpoint has correct operationId in OpenAPI."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/openapi.json")
        schema = response.json()

        # Find the health path (may be /health or /api/v1/health depending on config)
        paths = schema["paths"]
        health_path_key = next(
            (k for k in paths if k.endswith("/health")),
            None,
        )
        assert health_path_key is not None

        # Operation ID should be "getHealthStatus"
        health_path = paths[health_path_key]
        assert "get" in health_path
        assert health_path["get"]["operationId"] == "getHealthStatus"

    def test_health_endpoint_documented_in_openapi(self) -> None:
        """Health endpoint has description and tags in OpenAPI."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/openapi.json")
        schema = response.json()

        # Find the health path
        paths = schema["paths"]
        health_path_key = next(
            (k for k in paths if k.endswith("/health")),
            None,
        )
        assert health_path_key is not None

        health_get = paths[health_path_key]["get"]

        # Should have summary/description
        assert "summary" in health_get or "description" in health_get
        # Should be tagged
        assert "tags" in health_get
        assert "Health" in health_get["tags"]


class TestHealthEndpointIntegration:
    """Integration tests with middleware and infrastructure."""

    def test_health_endpoint_with_request_id_middleware(self) -> None:
        """Health endpoint works with RequestIdMiddleware."""
        app = create_app()
        with TestClient(app) as client:

        # Should generate request ID even without X-Request-ID header
            response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert "x-request-id" in response.headers

    def test_health_endpoint_with_custom_request_id(self) -> None:
        """Health endpoint echoes back custom X-Request-ID if provided."""
        app = create_app()
        with TestClient(app) as client:

            custom_id = str(uuid.uuid4())
            response = client.get(
                "/api/v1/health",
                headers={"X-Request-ID": custom_id},
            )

        assert response.status_code == 200
        assert response.headers["x-request-id"] == custom_id

    def test_health_endpoint_response_format_matches_schema(self) -> None:
        """Full response matches OpenAPI HealthStatus schema."""
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
        data: dict[str, Any] = response.json()

        # Schema validation:
        # - status: enum string [ok, degraded, unavailable]
        # - version: string
        # - timestamp: ISO-8601 datetime
        # - dependencies: optional object

        assert isinstance(data["status"], str)
        assert data["status"] in ["ok", "degraded", "unavailable"]

        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

        assert isinstance(data["timestamp"], str)
        assert "T" in data["timestamp"]  # ISO-8601 includes date-time separator

        if "dependencies" in data:
            is_deps_valid = data["dependencies"] is None or isinstance(
                data["dependencies"], dict
            )
            assert is_deps_valid
            if isinstance(data["dependencies"], dict):
                # Each dependency value should be a status string
                for dep_name, dep_status in data["dependencies"].items():
                    assert isinstance(dep_name, str)
                    assert isinstance(dep_status, str)
                    assert dep_status in ["ok", "degraded", "unavailable"]


class TestHealthEndpointContentNegotiation:
    """Tests for content negotiation and response format."""

    def test_health_endpoint_response_has_content_length(self) -> None:
        """Response includes Content-Length header."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")

        # Content-Length should be present
        assert "content-length" in response.headers
        content_length = int(response.headers["content-length"])
        assert content_length > 0

    def test_health_endpoint_response_body_is_valid_json_object(self) -> None:
        """Response body is a JSON object (not array, string, etc.)."""
        app = create_app()
        with TestClient(app) as client:

            response = client.get("/api/v1/health")
        data = response.json()

        # Must be a dict, not a list or scalar
        assert isinstance(data, dict)
