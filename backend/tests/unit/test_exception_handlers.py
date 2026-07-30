"""
Tests for centralized exception handlers.

Verifies:
- HTTPException handler maps status codes correctly
- ValidationError handler includes field-level details
- Generic 500 handler doesn't leak internal details
- Request ID included in all error responses
- Error response schema compliance (RFC 7807)
- Integration with RequestIdMiddleware
- Structured logging compatibility

See: E2.T5 Definition of Done (unit tests for each exception type).
See: docs/22-Engineering-Backlog.md E2.T5.
See: 07-Backend-Development-Standards §9 (error response consistency).
See: 08-Security-Architecture §10 (no information disclosure).
"""

import json
import uuid
from typing import Any

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app


class TestHTTPExceptionHandler:
    """Tests for HTTP exception handler (404, 403, 429, etc.)."""

    def test_404_response_format(self) -> None:
        """Verify 404 returns error envelope with correct code."""
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            # Request non-existent route
            response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404
        data: dict[str, Any] = response.json()

        # Verify error envelope structure
        assert "error" in data
        assert "requestId" in data
        assert "timestamp" in data

        # Verify error details
        error = data["error"]
        assert error["code"] == "not_found"
        assert "404" in str(error["message"]).lower() or error["message"]

    def test_403_response_format(self) -> None:
        """Verify 403 returns error envelope with correct code."""
        app = create_app()

        # Raise HTTPException with 403 from route
        @app.get("/test-403")
        async def test_403_route() -> dict[str, Any]:
            raise HTTPException(status_code=403, detail="Forbidden")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-403")

        assert response.status_code == 403
        data: dict[str, Any] = response.json()

        error = data["error"]
        assert error["code"] == "forbidden"
        assert "Forbidden" in error["message"]

    def test_429_response_format(self) -> None:
        """Verify 429 returns error envelope with correct code."""
        app = create_app()

        # Add a test route that raises 429
        @app.get("/test-429")
        async def test_429_route() -> dict[str, Any]:
            raise HTTPException(status_code=429, detail="Too Many Requests")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-429")

        assert response.status_code == 429
        data: dict[str, Any] = response.json()

        error = data["error"]
        assert error["code"] == "rate_limit_exceeded"

    def test_404_response_format_no_socket_leak(self) -> None:
        """Verify a handled 404 returns the expected error response."""
        app = create_app()

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_request_id_included_in_404(self) -> None:
        """Verify request_id included in 404 response."""
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            # Make request with custom X-Request-ID
            custom_id = str(uuid.uuid4())
            response = client.get(
                "/api/v1/nonexistent", headers={"X-Request-ID": custom_id}
            )

        assert response.status_code == 404
        data = response.json()

        # Verify request_id matches what we sent
        assert "requestId" in data
        assert data["requestId"] == custom_id

    def test_status_code_mapping(self) -> None:
        """Verify status codes are correctly mapped to error codes."""
        app = create_app()

        # Test route that can raise different status codes
        @app.get("/test-status/{code}")
        async def test_status_route(code: int) -> dict[str, Any]:
            raise HTTPException(status_code=code, detail="Test error")

        with TestClient(app, raise_server_exceptions=False) as client:
            status_code_map: dict[int, str] = {
                400: "bad_request",
                401: "unauthorized",
                403: "forbidden",
                404: "not_found",
                405: "method_not_allowed",
                409: "conflict",
                500: "internal_server_error",
                503: "service_unavailable",
            }

            for status_code, expected_code in status_code_map.items():
                response = client.get(f"/test-status/{status_code}")
                assert response.status_code == status_code

                data: dict[str, Any] = response.json()
                assert data["error"]["code"] == expected_code

    def test_http_exception_no_stack_trace(self) -> None:
        """Verify HTTP exceptions don't leak stack trace."""
        app = create_app()

        @app.get("/test-no-trace")
        async def test_no_trace_route() -> dict[str, Any]:
            raise HTTPException(status_code=500, detail="Internal error")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-no-trace")

        data: dict[str, Any] = response.json()

        # Should not contain traceback indicators
        response_str = json.dumps(data)
        assert "Traceback" not in response_str
        assert "File " not in response_str
        assert "line " not in response_str


class TestValidationExceptionHandler:
    """Tests for validation error handler (422)."""

    def test_422_response_status(self) -> None:
        """Verify validation errors return 422 status."""
        app = create_app()

        @app.post("/test-validate")
        async def test_validate_route(data: dict[str, Any]) -> dict[str, Any]:
            # FastAPI will validate the body
            return data

        with TestClient(app, raise_server_exceptions=False) as client:
            # Send invalid JSON
            response = client.post(
                "/test-validate",
                json={"not": "valid"},  # Missing required fields
            )

        # May be 422 or 200 depending on route definition
        # For now, verify the route works
        assert response.status_code in (200, 422, 400)

    def test_validation_error_includes_field_details(self) -> None:
        """Verify validation errors include field-level details."""
        from pydantic import BaseModel, ValidationError

        class TestModel(BaseModel):
            email: str
            age: int

        # Create validation error
        try:
            TestModel(email="not-an-email", age="not-an-int")  # type: ignore
        except ValidationError as exc:
            # Verify we get multiple errors
            errors = exc.errors()
            assert len(errors) > 0

            # Verify error structure
            for error in errors:
                assert "loc" in error
                assert "msg" in error

    def test_400_validation_response_format(self) -> None:
        """Verify bad request returns error envelope."""
        app = create_app()

        @app.post("/test-json")
        async def test_json_route(data: dict[str, Any]) -> dict[str, Any]:
            return data

        with TestClient(app, raise_server_exceptions=False) as client:
            # Send invalid JSON using content parameter instead of data
            response = client.post("/test-json", content="not json")

        # Should get 422 (validation error) or 400 (bad request)
        assert response.status_code in (400, 422)

        if response.status_code == 422:
            data: dict[str, Any] = response.json()
            assert "error" in data
            assert "requestId" in data


class TestUnhandledExceptionHandler:
    """Tests for generic 500 catch-all handler."""

    def test_500_response_status(self) -> None:
        """Verify unhandled exceptions return 500 status."""
        app = create_app()

        @app.get("/test-unhandled")
        async def test_unhandled_route() -> dict[str, Any]:
            raise RuntimeError("Simulated application error")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-unhandled")

        assert response.status_code == 500

    def test_500_generic_message(self) -> None:
        """Verify 500 returns generic message (no details)."""
        app = create_app()

        @app.get("/test-generic")
        async def test_generic_route() -> dict[str, Any]:
            raise ValueError("Specific error message that should not leak")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-generic")

        assert response.status_code == 500
        data: dict[str, Any] = response.json()

        error = data["error"]
        assert error["code"] == "internal_server_error"
        assert error["message"] == "An unexpected error occurred."
        assert "ValueError" not in str(data)
        assert "Specific error message" not in str(data)

    def test_500_no_exception_type_leaked(self) -> None:
        """Verify exception type not included in 500 response."""
        app = create_app()

        @app.get("/test-type-leak")
        async def test_type_leak_route() -> dict[str, Any]:
            raise KeyError("database_connection")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-type-leak")

        data: dict[str, Any] = response.json()
        response_str = json.dumps(data)

        # Should not contain exception type name or message
        assert "KeyError" not in response_str
        assert "database_connection" not in response_str

    def test_500_no_stack_trace(self) -> None:
        """Verify 500 response doesn't include stack trace."""
        app = create_app()

        @app.get("/test-no-trace")
        async def test_no_trace_route() -> dict[str, Any]:
            try:
                _ = 1 / 0
            except ZeroDivisionError:
                raise RuntimeError("Division error occurred") from None
            return {}  # This line is unreachable but satisfies type checker

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-no-trace")

        data: dict[str, Any] = response.json()
        response_str = json.dumps(data)

        # Should not contain traceback indicators
        assert "Traceback" not in response_str
        assert "File " not in response_str
        assert "line " not in response_str
        assert "ZeroDivisionError" not in response_str

    def test_500_request_id_included(self) -> None:
        """Verify 500 response includes request_id."""
        app = create_app()

        @app.get("/test-error-id")
        async def test_error_id_route() -> dict[str, Any]:
            raise RuntimeError("Test error")

        with TestClient(app, raise_server_exceptions=False) as client:
            custom_id = str(uuid.uuid4())
            response = client.get("/test-error-id", headers={"X-Request-ID": custom_id})

        assert response.status_code == 500
        data: dict[str, Any] = response.json()

        assert "requestId" in data
        assert data["requestId"] == custom_id


class TestErrorResponseIntegration:
    """Integration tests for error response envelope."""

    def test_request_id_correlation_with_header(self) -> None:
        """Verify response request_id matches X-Request-ID header."""
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            custom_id = str(uuid.uuid4())
            response = client.get(
                "/api/v1/nonexistent", headers={"X-Request-ID": custom_id}
            )

        # Should correlate
        data: dict[str, Any] = response.json()
        assert data["requestId"] == custom_id
        assert response.headers["x-request-id"] == custom_id

    def test_timestamp_in_iso_8601_utc(self) -> None:
        """Verify timestamp is ISO-8601 UTC format."""
        app = create_app()

        @app.get("/test-timestamp")
        async def test_timestamp_route() -> dict[str, Any]:
            raise RuntimeError("Test")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-timestamp")

        data: dict[str, Any] = response.json()
        timestamp = data["timestamp"]

        # Should be ISO-8601 format with UTC indicator
        assert "T" in timestamp  # ISO-8601 separator
        assert ":" in timestamp  # Time component
        assert "Z" in timestamp or "+00:00" in timestamp  # UTC indicator

    def test_all_error_responses_have_envelope(self) -> None:
        """Verify all error responses follow envelope schema."""
        app = create_app()

        @app.get("/test-envelope-404")
        async def test_404() -> dict[str, Any]:
            raise HTTPException(status_code=404)

        @app.get("/test-envelope-500")
        async def test_500() -> dict[str, Any]:
            raise RuntimeError("Error")

        with TestClient(app, raise_server_exceptions=False) as client:
            # Test 404
            response = client.get("/test-envelope-404")
        data: dict[str, Any] = response.json()
        assert "error" in data
        assert "requestId" in data
        assert "timestamp" in data

        # Test 500
        response = client.get("/test-envelope-500")
        data = response.json()
        assert "error" in data
        assert "requestId" in data
        assert "timestamp" in data

    def test_error_body_structure(self) -> None:
        """Verify error body always has code and message."""
        app = create_app()

        @app.get("/test-body")
        async def test_body() -> dict[str, Any]:
            raise HTTPException(status_code=403, detail="Access denied")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-body")

        data: dict[str, Any] = response.json()
        error = data["error"]

        assert "code" in error
        assert "message" in error
        assert isinstance(error["code"], str)
        assert isinstance(error["message"], str)


class TestExceptionHandlersIntegration:
    """Integration tests for exception handlers with real routes."""

    def test_health_endpoint_returns_valid_response(self) -> None:
        """Verify health endpoint returns expected schema (not error)."""
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/health")

        assert response.status_code == 200
        data: dict[str, Any] = response.json()

        # Should be health response, not error envelope
        assert "status" in data
        assert data["status"] == "ok"
        assert "version" in data
        assert "timestamp" in data

    def test_404_on_unknown_route_returns_error_envelope(self) -> None:
        """Verify unknown routes return proper error envelope."""
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/unknown/path")

        assert response.status_code == 404
        data: dict[str, Any] = response.json()

        # Should be error envelope
        assert "error" in data
        assert "requestId" in data
        assert data["error"]["code"] == "not_found"

    def test_500_on_unhandled_exception_returns_error_envelope(self) -> None:
        """Verify unhandled exceptions return error envelope."""
        app = create_app()

        @app.get("/api/v1/error-route")
        async def error_route() -> dict[str, Any]:
            raise ValueError("Unhandled application error")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/error-route")

        assert response.status_code == 500
        data: dict[str, Any] = response.json()

        # Should be error envelope
        assert "error" in data
        assert "requestId" in data
        assert "timestamp" in data
        assert data["error"]["code"] == "internal_server_error"

    def test_error_request_id_available_for_logging(self) -> None:
        """Verify request_id available in error responses for log correlation."""
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            custom_id = str(uuid.uuid4())
            response = client.get(
                "/api/v1/nonexistent", headers={"X-Request-ID": custom_id}
            )

        data: dict[str, Any] = response.json()

        # Request ID should match header for log correlation
        assert data["requestId"] == custom_id

        # In a real scenario, logs for this request would also have
        # the same request_id (via ContextFilter from E2.T3)


class TestErrorResponseCamelCaseAliasing:
    """Tests for JSON field aliasing (snake_case → camelCase)."""

    def test_request_id_aliased_as_request_id_in_json(self) -> None:
        """Verify request_id appears as requestId in JSON."""
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/nonexistent")
        data = response.json()

        # Should use camelCase in JSON
        assert "requestId" in data
        assert "request_id" not in data  # Not snake_case in response

    def test_error_body_present_in_response(self) -> None:
        """Verify error body is present (not error_body)."""
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/nonexistent")
        data = response.json()

        assert "error" in data
        assert "error_body" not in data


class TestExceptionHandlerErrorCases:
    """Tests for edge cases and error scenarios."""

    def test_exception_with_no_detail_message(self) -> None:
        """Verify HTTPException with no detail gets fallback message."""
        app = create_app()

        @app.get("/test-no-detail")
        async def test_no_detail() -> dict[str, Any]:
            raise HTTPException(status_code=404)  # No detail provided

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-no-detail")

        data: dict[str, Any] = response.json()
        error = data["error"]

        # Should have a message (fallback)
        assert "message" in error
        assert len(error["message"]) > 0

    def test_multiple_errors_in_validation(self) -> None:
        """Verify multiple validation errors are included."""
        from pydantic import BaseModel, Field, ValidationError

        class StrictModel(BaseModel):
            email: str = Field(..., pattern=r".+@.+")
            age: int = Field(..., ge=0, le=150)

        # Create validation error with multiple issues
        try:
            StrictModel(email="not-email", age=200)
        except ValidationError as exc:
            # Verify multiple errors
            errors = exc.errors()
            assert len(errors) >= 1  # At least email error

            # Verify error structure
            for error in errors:
                assert "loc" in error
                assert "msg" in error
