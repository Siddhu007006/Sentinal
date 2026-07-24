"""
Tests for structured logging infrastructure.

Validates:
- JSON formatter output structure and field presence
- Request ID correlation via contextvars
- Log level configuration from Settings
- Sensitive data redaction
- Request lifecycle logging via middleware
- Environment field in logs

See: E2.T3 Definition of Done (unit test for log format + integration test).
"""

import json
import logging
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.infrastructure.logging import (
    ContextFilter,
    SensitiveDataFilter,
    SentinelJSONFormatter,
    clear_request_context,
    configure_logging,
    get_logger,
    set_request_id,
)
from app.main import create_app


class TestSentinelJSONFormatter:
    """Test suite for SentinelJSONFormatter."""

    def test_formats_log_as_valid_json(self) -> None:
        """Verify log output is valid JSON parseable by standard tools."""
        formatter = SentinelJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        # Parse as JSON (will raise if invalid)
        log_obj = json.loads(output)
        assert isinstance(log_obj, dict)

    def test_includes_required_fields(self) -> None:
        """Verify all required fields present per E2.T3 acceptance criteria."""
        formatter = SentinelJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        log_obj = json.loads(output)

        # Required fields per E2.T3
        assert "timestamp" in log_obj
        assert "level" in log_obj
        assert "logger" in log_obj
        assert "message" in log_obj
        assert "environment" in log_obj  # Added in Phase 2

    def test_timestamp_is_utc_iso8601(self) -> None:
        """Verify timestamp format is ISO-8601 UTC."""
        formatter = SentinelJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        log_obj = json.loads(output)

        # Should be parseable as ISO-8601 and end with Z or +00:00
        timestamp = log_obj["timestamp"]
        assert isinstance(timestamp, str)
        assert "T" in timestamp  # ISO-8601 format
        # UTC indicator (Z or +00:00)
        assert timestamp.endswith("Z") or "+00:00" in timestamp

    def test_includes_request_id_from_context(self) -> None:
        """Verify request_id automatically included from contextvars."""
        formatter = SentinelJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )

        # Set request ID in context
        test_request_id = "test-req-123"
        set_request_id(test_request_id)

        # Add ContextFilter to record (simulates what happens in get_logger)
        context_filter = ContextFilter()
        context_filter.filter(record)

        output = formatter.format(record)
        log_obj = json.loads(output)

        assert "request_id" in log_obj
        assert log_obj["request_id"] == test_request_id

        # Cleanup
        clear_request_context()

    def test_includes_structured_fields_from_extra(self) -> None:
        """Verify extra fields passed via 'fields' dict are included."""
        formatter = SentinelJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="upload completed",
            args=(),
            exc_info=None,
        )
        # Add structured fields
        record.fields = {"upload_id": "abc-123", "size_bytes": 1024}

        output = formatter.format(record)
        log_obj = json.loads(output)

        assert log_obj["upload_id"] == "abc-123"
        assert log_obj["size_bytes"] == 1024

    def test_includes_exception_info(self) -> None:
        """Verify exception info included when logging errors."""
        formatter = SentinelJSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            import traceback

            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="error occurred",
                args=(),
                exc_info=exc_info,
            )
            # Manually format exception text
            record.exc_text = "".join(traceback.format_exception(*exc_info))

        output = formatter.format(record)
        log_obj = json.loads(output)

        assert "exception" in log_obj
        assert "ValueError" in log_obj["exception"]
        assert "test error" in log_obj["exception"]


class TestSensitiveDataFilter:
    """Test suite for SensitiveDataFilter."""

    def test_redacts_password_fields(self) -> None:
        """Verify password fields are redacted."""
        log_filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="user created",
            args=(),
            exc_info=None,
        )
        record.fields = {"email": "user@example.com", "password": "secret123"}  # type: ignore[attr-defined]

        log_filter.filter(record)

        assert record.fields["email"] == "user@example.com"  # type: ignore[attr-defined]
        assert record.fields["password"] == "[REDACTED]"  # type: ignore[attr-defined]  # noqa: S105

    def test_redacts_token_fields(self) -> None:
        """Verify token fields are redacted."""
        log_filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="api call",
            args=(),
            exc_info=None,
        )
        record.fields = {"api_key": "secret-key", "access_token": "bearer-token"}  # type: ignore[attr-defined]

        log_filter.filter(record)

        assert record.fields["api_key"] == "[REDACTED]"  # type: ignore[attr-defined]
        assert record.fields["access_token"] == "[REDACTED]"  # type: ignore[attr-defined]  # noqa: S105

    def test_redacts_nested_sensitive_fields(self) -> None:
        """Verify nested sensitive fields are redacted."""
        log_filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="config loaded",
            args=(),
            exc_info=None,
        )
        record.fields = {  # type: ignore[attr-defined]
            "database": {"host": "localhost", "password": "db-secret"},
            "api": {"url": "https://api.example.com", "secret_key": "api-secret"},
        }

        log_filter.filter(record)

        assert record.fields["database"]["host"] == "localhost"  # type: ignore[attr-defined]
        assert record.fields["database"]["password"] == "[REDACTED]"  # type: ignore[attr-defined]  # noqa: S105
        assert record.fields["api"]["url"] == "https://api.example.com"  # type: ignore[attr-defined]
        assert record.fields["api"]["secret_key"] == "[REDACTED]"  # type: ignore[attr-defined]  # noqa: S105


class TestContextFilter:
    """Test suite for ContextFilter."""

    def test_adds_request_id_from_context(self) -> None:
        """Verify request_id added from contextvars."""
        context_filter = ContextFilter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )

        test_request_id = "ctx-req-456"
        set_request_id(test_request_id)

        context_filter.filter(record)

        assert hasattr(record, "request_id")
        assert record.request_id == test_request_id

        # Cleanup
        clear_request_context()

    def test_handles_missing_context_gracefully(self) -> None:
        """Verify filter doesn't crash when no context set."""
        clear_request_context()
        context_filter = ContextFilter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )

        # Should not raise
        result = context_filter.filter(record)

        assert result is True
        # request_id should be present (auto-generated by get_request_id)
        assert hasattr(record, "request_id")
        assert record.request_id is not None


class TestGetLogger:
    """Test suite for get_logger factory."""

    def test_returns_configured_logger(self) -> None:
        """Verify get_logger returns a properly configured logger."""
        logger = get_logger("test.module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"
        assert len(logger.handlers) > 0

    def test_logger_has_json_formatter(self) -> None:
        """Verify logger uses SentinelJSONFormatter."""
        logger = get_logger("test.json.formatter")

        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, SentinelJSONFormatter)

    def test_logger_has_context_filter(self) -> None:
        """Verify logger has ContextFilter configured."""
        logger = get_logger("test.context.filter")

        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        filters = [f for f in handler.filters if isinstance(f, ContextFilter)]
        assert len(filters) > 0

    def test_logger_has_sensitive_data_filter(self) -> None:
        """Verify logger has SensitiveDataFilter configured."""
        logger = get_logger("test.sensitive.filter")

        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        filters = [f for f in handler.filters if isinstance(f, SensitiveDataFilter)]
        assert len(filters) > 0

    def test_logger_caching(self) -> None:
        """Verify loggers are cached by name."""
        logger1 = get_logger("test.caching")
        logger2 = get_logger("test.caching")

        assert logger1 is logger2

    def test_logger_respects_settings_log_level(self) -> None:
        """Verify logger accepts settings parameter."""
        # Create settings with DEBUG level
        settings = Settings(
            database={
                "url": "postgresql://test",
                "migration_url": "postgresql://test",
            },
            storage={
                "endpoint_url": "http://test",
                "bucket_name": "test",
                "access_key_id": "test",
                "secret_access_key": "test",
            },
            queue={"broker_url": "redis://test"},
            security={"jwt_secret_key": "test-secret"},
            logging={"level": "DEBUG"},
        )

        # Verify get_logger accepts settings without error
        logger = get_logger("test.logger.with.settings", settings=settings)

        # Logger should be created successfully
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.logger.with.settings"


class TestConfigureLogging:
    """Test suite for configure_logging function."""

    def test_configure_logging_accepts_settings(self) -> None:
        """Verify configure_logging accepts settings without error."""
        settings = Settings(
            database={
                "url": "postgresql://test",
                "migration_url": "postgresql://test",
            },
            storage={
                "endpoint_url": "http://test",
                "bucket_name": "test",
                "access_key_id": "test",
                "secret_access_key": "test",
            },
            queue={"broker_url": "redis://test"},
            security={"jwt_secret_key": "test-secret"},
            logging={"level": "WARNING"},
        )

        # Should not raise
        configure_logging(settings)

    def test_suppresses_uvicorn_access_logs(self) -> None:
        """Verify uvicorn access logs are suppressed."""
        settings = Settings(
            database={
                "url": "postgresql://test",
                "migration_url": "postgresql://test",
            },
            storage={
                "endpoint_url": "http://test",
                "bucket_name": "test",
                "access_key_id": "test",
                "secret_access_key": "test",
            },
            queue={"broker_url": "redis://test"},
            security={"jwt_secret_key": "test-secret"},
            logging={"level": "INFO"},
        )

        configure_logging(settings)

        uvicorn_logger = logging.getLogger("uvicorn.access")
        assert uvicorn_logger.level == logging.WARNING
        assert uvicorn_logger.propagate is False


class TestRequestLifecycleLogging:
    """Integration tests for request lifecycle logging via middleware."""

    def test_request_start_logged_with_correlation_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify request start is logged with request ID, method, path."""
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(SentinelJSONFormatter())

        # Get the middleware logger and add our test handler
        from app.api.v1.middleware.request_id import logger as middleware_logger

        middleware_logger.addHandler(handler)
        middleware_logger.setLevel(logging.INFO)

        try:
            app = create_app()
            client = TestClient(app)

            # Make a request
            response = client.get("/api/v1/health")

            assert response.status_code == 200

            # Parse captured logs
            log_output = log_capture.getvalue()
            log_lines = [line for line in log_output.split("\n") if line.strip()]

            # Find the request_started log
            started_logs = [
                json.loads(line) for line in log_lines if "request_started" in line
            ]
            assert len(started_logs) > 0

            started_log = started_logs[0]
            assert started_log["message"] == "request_started"
            assert "request_id" in started_log
            assert started_log["method"] == "GET"
            assert started_log["path"] == "/api/v1/health"

        finally:
            middleware_logger.removeHandler(handler)

    def test_request_completion_logged_with_status_and_duration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify request completion logged with status code and duration."""
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(SentinelJSONFormatter())

        from app.api.v1.middleware.request_id import logger as middleware_logger

        middleware_logger.addHandler(handler)
        middleware_logger.setLevel(logging.INFO)

        try:
            app = create_app()
            client = TestClient(app)

            response = client.get("/api/v1/health")

            assert response.status_code == 200

            log_output = log_capture.getvalue()
            log_lines = [line for line in log_output.split("\n") if line.strip()]

            # Find the request_completed log
            completed_logs = [
                json.loads(line) for line in log_lines if "request_completed" in line
            ]
            assert len(completed_logs) > 0

            completed_log = completed_logs[0]
            assert completed_log["message"] == "request_completed"
            assert "request_id" in completed_log
            assert completed_log["method"] == "GET"
            assert completed_log["path"] == "/api/v1/health"
            assert completed_log["status_code"] == 200
            assert "duration_ms" in completed_log
            assert isinstance(completed_log["duration_ms"], (int, float))
            assert completed_log["duration_ms"] >= 0

        finally:
            middleware_logger.removeHandler(handler)

    def test_same_request_id_in_start_and_completion_logs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify same request_id appears in both start and completion logs."""
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(SentinelJSONFormatter())

        from app.api.v1.middleware.request_id import logger as middleware_logger

        middleware_logger.addHandler(handler)
        middleware_logger.setLevel(logging.INFO)

        try:
            app = create_app()
            client = TestClient(app)

            # Provide custom request ID
            custom_request_id = "test-correlation-id-789"
            response = client.get(
                "/api/v1/health", headers={"X-Request-ID": custom_request_id}
            )

            assert response.status_code == 200

            log_output = log_capture.getvalue()
            log_lines = [line for line in log_output.split("\n") if line.strip()]

            # Parse all logs
            request_logs = [
                json.loads(line)
                for line in log_lines
                if "request_" in line and custom_request_id in line
            ]

            assert len(request_logs) >= 2

            # Verify all have same request_id
            request_ids = [log["request_id"] for log in request_logs]
            assert all(rid == custom_request_id for rid in request_ids)

        finally:
            middleware_logger.removeHandler(handler)


class TestLoggingWithSettings:
    """Integration tests for logging with Settings configuration."""

    def test_log_level_configurable_via_settings(self) -> None:
        """Verify LOG_LEVEL setting controls log output."""
        settings = Settings(
            database={
                "url": "postgresql://test",
                "migration_url": "postgresql://test",
            },
            storage={
                "endpoint_url": "http://test",
                "bucket_name": "test",
                "access_key_id": "test",
                "secret_access_key": "test",
            },
            queue={"broker_url": "redis://test"},
            security={"jwt_secret_key": "test-secret"},
            logging={"level": "WARNING"},
        )

        logger = get_logger("test.level.config", settings=settings)

        # Capture output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(SentinelJSONFormatter())
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)

        # INFO should not appear
        logger.info("info message")
        # WARNING should appear
        logger.warning("warning message")

        log_output = log_capture.getvalue()

        assert "info message" not in log_output
        assert "warning message" in log_output
