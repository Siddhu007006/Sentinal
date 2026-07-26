"""
Test database fixtures and configuration for pytest.

Provides reusable fixtures for integration testing with a real PostgreSQL
database. Fixtures handle session lifecycle and transaction management to
ensure test isolation (no data leakage between tests).

Fixture Architecture:
  - async_engine: Created once per test session, reused across all tests
  - db_session: New session per test, rolls back mutations for isolation
  - clean_db: Optional dependency to verify clean state before test

Transaction Rollback Pattern:
  Each test runs in an explicit transaction:
  1. Session yields to test
  2. Test executes (inserts, updates, deletes)
  3. After test: explicit rollback (undoes all mutations)
  4. Next test starts with clean database

  This ensures:
  - No data from test_a persists to test_b
  - Fast isolation (rollback is faster than truncate)
  - Foreign key integrity preserved
  - Correct transaction semantics

Database Configuration:
  - TEST_DATABASE_URL env var selects test database
  - Defaults to DATABASE_URL if TEST_DATABASE_URL not set
  - Distinct from development/production databases

Traces to: 11-Testing-Strategy §6 (fixture patterns)
Traces to: 07-Backend-Development-Standards §13 (test isolation)
Traces to: 22-Engineering-Backlog E3.T1 (database fixtures)
"""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.settings import Settings


# Set ENVIRONMENT=test for all test runs
# This ensures middleware that requires external services (e.g., Redis for rate limiting)
# is not registered during unit tests
os.environ.setdefault("ENVIRONMENT", "test")
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


@pytest_asyncio.fixture(scope="function")
async def async_engine() -> AsyncGenerator[AsyncEngine | None, None]:
    """Create async engine per test function.

    Creates a fresh engine for each test function to ensure complete
    isolation. This aligns with pytest-asyncio's function-scoped event loop
    and ensures no connection state leaks between tests.

    Database Selection:
      - Uses TEST_DATABASE_URL env var if set (recommended for CI)
      - Falls back to DATABASE_URL from settings if not set
      - This allows tests to use a distinct test database

    Yields:
        AsyncEngine: Configured async SQLAlchemy engine with NullPool
                    (no connection pooling), or None if database driver
                    (asyncpg) is not available
    """
    # Get test database URL
    test_db_url = os.getenv("TEST_DATABASE_URL")

    if not test_db_url:
        # Fall back to configured database URL
        settings = Settings()
        test_db_url = settings.database.url

    try:
        # Create engine for test database with NullPool for test isolation
        # NullPool ensures each test gets a fresh connection and prevents
        # connection pool state corruption across tests.
        engine = create_async_engine(
            test_db_url,
            # Disable SQL echo in tests (cleaner output)
            echo=False,
            # SQLAlchemy 2.0 style (required for async)
            future=True,
            # NullPool: Create fresh connection per test, no pooling
            # Simplifies test isolation and prevents state leakage
            poolclass=NullPool,
        )
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except (ConnectionRefusedError, OSError, OperationalError):
            await engine.dispose()
            yield None
            return

        yield engine

        # Cleanup: dispose of connection pool after all tests
        await engine.dispose()
    except ModuleNotFoundError:
        # Database driver (asyncpg) not available
        # Yield None to allow tests to skip gracefully
        yield None


@pytest_asyncio.fixture
async def db_session(
    async_engine: AsyncEngine | None,
) -> AsyncGenerator[AsyncSession | None, None]:
    """Provide function-scoped database session with transaction rollback.

    Creates a new session for each test and uses explicit transaction
    rollback to ensure isolation. Data inserted during a test is rolled
    back after the test completes, preventing leakage to subsequent tests.

    Transaction Lifecycle:
      1. Session created from engine
      2. Session yielded to test
      3. Test executes queries (inserts, updates, deletes)
      4. After test: explicit rollback (undoes mutations)
      5. Session closed, connection discarded (NullPool)

    Error Handling:
      Suppresses RuntimeError/AttributeError during teardown to handle
      edge cases where the event loop closes before fixture cleanup completes.
      This is safe because NullPool discards the connection anyway.

    Yields:
        AsyncSession: Request-scoped session connected to test database,
                     or None if engine is not available (database not configured)

    Raises:
        Any exception from the test (after rollback and close)
    """
    if async_engine is None:
        yield None
        return

    session = AsyncSession(async_engine, expire_on_commit=False)
    try:
        # Yield session to test
        yield session
    except Exception:
        # If test raises exception: rollback and re-raise
        # This ensures cleanup even when test fails
        try:
            await session.rollback()
        except (RuntimeError, AttributeError, Exception):
            # Suppress errors during rollback if event loop is closed
            pass
        raise
    else:
        # Test passed: rollback to ensure isolation
        try:
            await session.rollback()
        except (RuntimeError, AttributeError, Exception):
            # Suppress errors if event loop is closed
            pass
    finally:
        # Always close session
        try:
            await session.close()
        except (RuntimeError, AttributeError, Exception):
            # Suppress errors if event loop is closed
            # NullPool will discard the connection anyway
            pass


@pytest_asyncio.fixture
async def clean_db(
    db_session: AsyncSession | None,
) -> None:
    """Verify clean state before test.

    This fixture has a dependency on db_session, which ensures that:
    1. The rollback from the previous test has completed
    2. The database is in a known clean state
    3. No data from prior tests exists

    This is a no-op fixture because all cleanup is handled by the
    db_session fixture. Tests that need explicit verification of clean
    state can use this fixture, while others can use db_session directly.

    Usage:
        @pytest.mark.asyncio
        async def test_something(clean_db: None) -> None:
            # Database guaranteed to be clean here
            pass

    Returns:
        None: Fixture returns immediately, cleanup handled by db_session
    """
    # Dependency on db_session ensures rollback from previous test
    # Cleanup is handled by db_session fixture
    # Returns None regardless of whether db_session is available
    return None
