"""
Unit tests for database engine disposal on application shutdown.

Tests verify that:
1. Engine disposal is called during lifespan shutdown
2. Shutdown completes cleanly even if disposal encounters errors
3. Failure to dispose is logged (searchable in logs)
4. Engine disposal doesn't break existing lifespan behavior

See: E3.T1 Requirements R2 (Application Shutdown Lifecycle)
See: 07-Backend-Development-Standards §8 (lifecycle management)
See: 09-Deployment-Architecture §3 (graceful shutdown)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestEngineDisposalOnShutdown:
    """Tests for engine disposal during application shutdown."""

    def test_engine_disposal_called_on_shutdown(self) -> None:
        """Engine disposal is called when lifespan exits (shutdown)."""

        async def run_shutdown_with_mock() -> bool:
            from app.main import lifespan

            # Mock the engine to verify dispose is called
            with patch(
                "app.main._engine",
                new_callable=AsyncMock,
            ) as mock_engine:
                mock_engine.dispose = AsyncMock()

                # Create a mock FastAPI app
                app = FastAPI()

                # Call lifespan: startup -> yield -> shutdown
                async with lifespan(app):
                    # During yield, engine is not disposed
                    pass

                # After exiting, shutdown has run
                # Verify dispose was called
                return mock_engine.dispose.called

        result = asyncio.run(run_shutdown_with_mock())
        assert result

    def test_engine_disposal_success_logged(self) -> None:
        """Successful engine disposal is logged with info level."""

        async def run_shutdown_and_verify_log() -> bool:
            from app.main import lifespan

            # Mock the engine to verify dispose is called and logs success
            with patch(
                "app.main._engine",
                new_callable=AsyncMock,
            ) as mock_engine, patch(
                "app.main.get_logger"
            ) as mock_get_logger:
                mock_engine.dispose = AsyncMock()

                # Mock logger
                mock_logger = MagicMock()
                mock_logger.info = MagicMock()
                mock_get_logger.return_value = mock_logger

                app = FastAPI()

                async with lifespan(app):
                    pass

                # Verify logger.info was called
                assert mock_logger.info.called
                # Check that at least one info call mentions disposal
                calls = mock_logger.info.call_args_list
                return any("disposed" in str(call).lower() for call in calls)

        result = asyncio.run(run_shutdown_and_verify_log())
        assert result

    def test_engine_disposal_failure_logged_as_error(self) -> None:
        """Engine disposal failure is logged as error."""

        async def run_shutdown_with_failure() -> bool:
            from app.main import lifespan

            with patch(
                "app.main._engine",
                new_callable=AsyncMock,
            ) as mock_engine, patch(
                "app.main.get_logger"
            ) as mock_get_logger:
                # Make dispose raise an exception
                mock_engine.dispose = AsyncMock(
                    side_effect=RuntimeError("Connection pool error")
                )

                # Mock logger
                mock_logger = MagicMock()
                mock_logger.error = MagicMock()
                mock_get_logger.return_value = mock_logger

                app = FastAPI()

                # Should not raise even though disposal fails
                async with lifespan(app):
                    pass

                # Verify logger.error was called
                assert mock_logger.error.called
                # Check error message mentions disposal
                calls = mock_logger.error.call_args_list
                return any("Failed to dispose" in str(call) for call in calls)

        result = asyncio.run(run_shutdown_with_failure())
        assert result

    def test_shutdown_completes_despite_disposal_error(self) -> None:
        """Shutdown completes even if disposal encounters errors."""

        async def run_shutdown_with_disposal_error() -> bool:
            from app.main import lifespan

            with patch(
                "app.main._engine",
                new_callable=AsyncMock,
            ) as mock_engine, patch("app.main.get_logger"):
                # Make dispose raise
                mock_engine.dispose = AsyncMock(
                    side_effect=RuntimeError("Simulated disposal error")
                )

                app = FastAPI()

                # Should complete without raising
                try:
                    async with lifespan(app):
                        pass
                    return True
                except Exception:
                    return False

        result = asyncio.run(run_shutdown_with_disposal_error())
        assert result, "Shutdown should complete despite disposal error"

    def test_engine_none_skips_disposal_gracefully(self) -> None:
        """If engine is None, disposal is skipped gracefully."""

        async def run_shutdown_with_none_engine() -> bool:
            from app.main import lifespan

            with patch(
                "app.main._engine",
                new=None,
            ), patch("app.main.get_logger"):
                app = FastAPI()

                # Should not raise
                try:
                    async with lifespan(app):
                        pass
                    return True
                except Exception:
                    return False

        result = asyncio.run(run_shutdown_with_none_engine())
        assert result

    def test_lifespan_integration_with_testclient(self) -> None:
        """Lifespan with engine disposal works in TestClient context."""
        from app.main import create_app

        app = create_app()

        # TestClient enters/exits lifespan (exercises full shutdown path)
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
            assert response.status_code == 200

        # After TestClient context exits, shutdown has run


class TestLifespanBehaviorUnchanged:
    """Verify existing lifespan behavior is not regressed."""

    def test_lifespan_logging_still_configured(self) -> None:
        """Logging is still configured in startup (existing behavior)."""
        from app.main import create_app

        app = create_app()

        with TestClient(app) as client:
            # Health endpoint should work (requires logging)
            response = client.get("/api/v1/health")
            assert response.status_code == 200

    def test_lifespan_settings_still_loaded(self) -> None:
        """Settings are still loaded in startup (existing behavior)."""
        from app.main import create_app

        # create_app should load settings without error
        app = create_app()
        assert app is not None
        assert isinstance(app, FastAPI)
