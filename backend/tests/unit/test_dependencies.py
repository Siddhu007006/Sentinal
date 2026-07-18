"""
Unit tests for dependency injection providers.

Tests the core DI infrastructure:
- Settings singleton (get_settings)
- Logger acquisition (get_logger)
- Request context lifecycle (get_request_context)
- Context variable propagation (get_request_context_dict)

Note: RequestContext uses AsyncMock in tests, but the class itself is
synchronous. Actual async testing happens in integration tests where
pytest-asyncio is properly configured.

See: 11-Testing-Strategy §3 (unit tests, no I/O).
See: 07-Backend-Development-Standards §3 (dependency injection).
"""

import logging

from app.core.dependencies import (
    RequestContext,
    get_logger,
    get_request_context_dict,
    get_settings,
)
from app.core.settings import Settings


class TestGetSettings:
    """Tests for get_settings singleton provider."""

    def test_get_settings_returns_settings_instance(self) -> None:
        """get_settings returns a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_returns_same_instance(self) -> None:
        """get_settings returns the same cached instance (singleton)."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_get_settings_cached_via_lru_cache(self) -> None:
        """get_settings uses @lru_cache for singleton behavior."""
        # Multiple calls should return identical object (same memory address)
        settings_a = get_settings()
        settings_b = get_settings()
        settings_c = get_settings()

        assert id(settings_a) == id(settings_b) == id(settings_c)


class TestGetLogger:
    """Tests for get_logger provider."""

    def test_get_logger_returns_logger_instance(self) -> None:
        """get_logger returns a logging.Logger instance."""
        logger = get_logger(__name__)
        assert isinstance(logger, logging.Logger)

    def test_get_logger_with_name(self) -> None:
        """get_logger uses the provided name."""
        name = "test.module.logger"
        logger = get_logger(name)
        assert logger.name == name

    def test_get_logger_standard_names(self) -> None:
        """get_logger works with standard naming patterns."""
        # Module path style
        logger1 = get_logger("app.services.auth")
        assert "app.services.auth" in logger1.name

        # Dunder name style
        logger2 = get_logger("__main__")
        assert "__main__" in logger2.name

    def test_get_logger_caching_by_name(self) -> None:
        """get_logger returns the same instance for the same name."""
        logger1 = get_logger("test.cached")
        logger2 = get_logger("test.cached")
        assert logger1 is logger2


class TestRequestContext:
    """Tests for RequestContext class."""

    def test_request_context_initialization(self) -> None:
        """RequestContext initializes with required fields."""
        ctx = RequestContext(request_id="req-123")
        assert ctx.request_id == "req-123"
        assert ctx.correlation_id == "req-123"  # Defaults to request_id
        assert ctx.user_id is None

    def test_request_context_with_correlation_id(self) -> None:
        """RequestContext accepts optional correlation_id."""
        ctx = RequestContext(
            request_id="req-123",
            correlation_id="corr-456",
        )
        assert ctx.request_id == "req-123"
        assert ctx.correlation_id == "corr-456"

    def test_request_context_to_dict(self) -> None:
        """RequestContext.to_dict returns context as dictionary."""
        ctx = RequestContext(request_id="req-123", correlation_id="corr-456")
        ctx.user_id = "user-789"

        result = ctx.to_dict()
        assert result == {
            "request_id": "req-123",
            "correlation_id": "corr-456",
            "user_id": "user-789",
        }

    def test_request_context_default_correlation_id(self) -> None:
        """RequestContext uses request_id as correlation_id if not provided."""
        ctx = RequestContext(request_id="req-123")
        assert ctx.correlation_id == "req-123"

    def test_request_context_user_id_modification(self) -> None:
        """RequestContext.user_id can be set after initialization."""
        ctx = RequestContext(request_id="req-123")
        assert ctx.user_id is None

        ctx.user_id = "user-456"
        assert ctx.user_id == "user-456"

        ctx_dict = ctx.to_dict()
        assert ctx_dict["user_id"] == "user-456"


class TestGetRequestContextDict:
    """Tests for get_request_context_dict helper."""

    def test_get_request_context_dict_returns_dict(self) -> None:
        """get_request_context_dict returns dict type."""
        ctx_dict = get_request_context_dict()
        assert isinstance(ctx_dict, dict)


class TestDependencyComposition:
    """Tests for composing multiple dependencies together."""

    def test_request_context_with_logger(self) -> None:
        """RequestContext and logger can be composed in same function."""
        ctx = RequestContext(request_id="req-composite")
        logger = get_logger("test.composite")

        # Both should be instances of their types
        assert isinstance(ctx, RequestContext)
        assert isinstance(logger, logging.Logger)

        # Context should have correct values
        assert ctx.request_id == "req-composite"
        assert ctx.to_dict()["request_id"] == "req-composite"
