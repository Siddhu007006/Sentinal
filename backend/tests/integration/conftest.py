"""Integration test fixtures for database and session cleanup.

This module provides fixtures that route database access through the
TEST engine (NullPool) instead of the production engine (QueuePool).

Dependency injection:
- Test db_session fixture creates sessions from tests/conftest.py::_session_engine
- NOT from app.infrastructure.database.session::_engine (production)
- This avoids QueuePool singleton persistence across event loops
"""
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.session import get_db_session
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Provide a test database session bound to the TEST engine.

    CRITICAL: This fixture uses the session-scoped TEST engine from
    tests/conftest.py (with NullPool), NOT the production engine from
    app.infrastructure.database.session (with QueuePool).

    Lifecycle:
    1. Session factory created from test engine
    2. Session created from factory (function-scoped)
    3. Session yielded to test
    4. On exit: rollback + close (prevents partial writes)

    The test engine ensures:
    - No connection pooling across event loops
    - Fresh connection per operation
    - Proper cleanup within the active event loop context
    """
    try:
        # Import the TEST engine accessor (module-level function, not a fixture)
        from tests.conftest import get_session_engine

        engine = get_session_engine()
        if engine is None:
            yield None
            return

        # Create a session factory bound to the TEST engine
        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create a fresh session for this test
        session = session_factory()

        try:
            yield session
        finally:
            # Cleanup: rollback to prevent partial writes
            await session.rollback()
            await session.close()
    except Exception:
        yield None


@pytest_asyncio.fixture
async def async_engine() -> AsyncGenerator | None:
    """Provide the TEST async engine for direct use in tests.

    Returns the session-scoped engine created in pytest_sessionstart.
    This engine uses NullPool for compatibility with pytest-asyncio's
    per-test event loops.

    Do not dispose this engine in tests — it is managed by
    pytest_sessionfinish in tests/conftest.py.
    """
    try:
        from tests.conftest import get_session_engine
        engine = get_session_engine()
        if engine is None:
            yield None
        else:
            yield engine
    except Exception:
        yield None


@pytest.fixture
def clean_db() -> None:
    """Fixture indicating database should be clean before test.

    This is satisfied by the parent conftest.py's reset_database_tables fixture,
    which is autouse and function-scoped.
    """
    return None
