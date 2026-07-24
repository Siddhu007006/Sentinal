"""Tests for database session dependency export.

Verifies that get_db_session is properly exported from app.core.dependencies
and is available for use in route handlers via FastAPI's Depends() mechanism.

Related to: E3.T1 (Database Foundation: Connection & Session Management)
Requirement: R1 (Export Database Dependency)
"""

import inspect
from typing import get_type_hints

from app.core.dependencies import get_db_session
from app.infrastructure.database.session import (
    get_db_session as get_db_session_original,
)


class TestGetDbSessionExport:
    """Test suite for get_db_session export from dependencies module."""

    def test_get_db_session_is_exported(self) -> None:
        """Verify get_db_session is exported from app.core.dependencies."""
        from app.core.dependencies import get_db_session as exported_func

        assert exported_func is not None
        assert callable(exported_func)

    def test_get_db_session_is_same_as_source(self) -> None:
        """Verify the exported function is the same as the original."""
        # Both should reference the same function object
        assert get_db_session is get_db_session_original

    def test_get_db_session_callable(self) -> None:
        """Verify get_db_session is callable."""
        assert callable(get_db_session)

    def test_get_db_session_type_hints_preserved(self) -> None:
        """Verify type hints are preserved in the export."""
        hints = get_type_hints(get_db_session)

        # Should have 'settings' parameter and 'return' type
        assert "settings" in hints
        assert "return" in hints

        # Return type should be an AsyncGenerator of AsyncSession
        return_type_str = str(hints["return"])
        assert "AsyncGenerator" in return_type_str
        assert "AsyncSession" in return_type_str

    def test_get_db_session_signature(self) -> None:
        """Verify the function signature is as expected."""
        sig = inspect.signature(get_db_session)

        # Should have 'settings' parameter
        assert "settings" in sig.parameters

        # Should have return annotation
        assert sig.return_annotation is not None

    def test_get_db_session_in_all_exports(self) -> None:
        """Verify get_db_session is in __all__ list."""
        from app.core import dependencies

        assert hasattr(dependencies, "__all__")
        assert "get_db_session" in dependencies.__all__

    def test_get_db_session_docstring(self) -> None:
        """Verify get_db_session has documentation."""
        assert get_db_session.__doc__ is not None
        assert "FastAPI dependency" in get_db_session.__doc__

    def test_import_from_dependencies_module(self) -> None:
        """Test that the import from dependencies module works."""
        # This is the recommended way for route handlers
        from app.core.dependencies import get_db_session as db_dep

        assert db_dep is not None
        assert callable(db_dep)

    def test_no_circular_imports(self) -> None:
        """Verify importing from dependencies doesn't create circular imports."""
        # If this succeeds, there are no circular imports
        from app.core.dependencies import (
            get_db_session,
            get_logger,
            get_request_context,
            get_settings,
        )

        assert get_db_session is not None
        assert get_logger is not None
        assert get_request_context is not None
        assert get_settings is not None

    def test_app_startup_with_export(self) -> None:
        """Verify the application can start with the export."""
        # This would catch any import-time errors
        from app.main import app

        assert app is not None
