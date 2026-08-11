"""
Test database fixtures and configuration for pytest.

Provides reusable fixtures for integration testing with a real PostgreSQL
database. Fixtures handle session lifecycle and transaction management to
ensure test isolation (no data leakage between tests).

Event Loop Isolation (Windows):
  On Windows, each test function gets a fresh event loop (pytest-asyncio).
  The app's database engine maintains a module-level singleton in session.py.
  When a new event loop is created, the old engine's connection pool has stale
  references to the previous loop, causing "Task attached to different loop" errors.
  
  Solution:
  - Reset app.infrastructure.database.session module globals before each test
  - This forces create_app() to initialize a fresh engine in the new loop
  - Each test gets a clean, isolated event loop + engine pair

Database Isolation:
  - Users created in test_a's fixtures persist in the database
  - When test_b's AsyncClient tries to register with same email, it fails
  - Solution: Truncate test tables before and after each test

Traces to: 11-Testing-Strategy §6 (fixture patterns)
Traces to: 07-Backend-Development-Standards §13 (test isolation)
Traces to: 22-Engineering-Backlog E3.T1 (database fixtures)
"""

import asyncio
import gc
import os
import subprocess
import sys
import time
import warnings
from contextlib import suppress

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.settings import Settings


# Windows asyncio event loop policy fix for asyncpg compatibility.
if sys.platform == "win32":
    try:
        from asyncio import WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    except (ImportError, RuntimeError, AttributeError):
        pass

# Set ENVIRONMENT=test for all test runs
os.environ.setdefault("ENVIRONMENT", "test")


def pytest_configure(config: pytest.Config) -> None:
    """Run database migrations before test collection."""
    os.environ["ENVIRONMENT"] = "test"
    
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"\nWarning: Alembic migration returned {result.returncode}", file=sys.stderr)
            if result.stderr:
                print(f"stderr: {result.stderr}", file=sys.stderr)
        else:
            print(f"\n✓ Database migrations completed successfully", file=sys.stdout)
    except subprocess.TimeoutExpired:
        print("\nWarning: Alembic migration timed out", file=sys.stderr)
    except Exception as e:
        print(f"\nWarning: Failed to run migrations: {e}", file=sys.stderr)


@pytest_asyncio.fixture(autouse=True)
async def reset_database_engine() -> None:
    """Reset app.infrastructure.database.session module globals before each test.
    
    CRITICAL FOR WINDOWS EVENT LOOP ISOLATION:
    The app's engine is a module-level singleton in session.py (_engine, _session_factory).
    When pytest-asyncio creates a new event loop for each test, the old engine's
    connection pool still has references to the previous loop.
    
    This fixture ensures each test gets a fresh engine tied to its own event loop:
    1. Before test: Reset module globals (set _engine = None, _session_factory = None)
    2. Test runs: create_app() builds fresh engine in current event loop
    3. After test: Engine disposed, ready for next test's fresh loop
    
    This also provides database cleanup (truncate tables) before and after each test,
    ensuring test isolation (no user from test_a persists to test_b).
    """
    # Get database URL for cleanup - use migration URL (schema_owner role) for full cleanup permissions
    test_db_url = os.getenv("TEST_DATABASE_URL")
    if not test_db_url:
        settings = Settings()
        # Use migration URL (with schema_owner role) for cleanup, not runtime URL (sentinel_api role)
        # Convert from sync postgresql:// to async postgresql+asyncpg://
        migration_url = settings.database.migration_url
        test_db_url = migration_url.replace("postgresql://", "postgresql+asyncpg://")
    
    # BEFORE TEST: Cleanup database tables
    cleanup_engine = create_async_engine(test_db_url, poolclass=NullPool, echo=False)
    async with cleanup_engine.begin() as conn:
        # Delete from tables in dependency order (foreign keys first)
        for table in ["reports", "user_refresh_tokens", "audit_logs", "analyses", "digital_assets", "uploads", "users"]:
            try:
                result = await conn.execute(text(f"DELETE FROM {table}"))
            except Exception:
                # Table may not exist or already empty
                pass
    await cleanup_engine.dispose()
    
    # BEFORE TEST: Reset session module globals
    # This forces a fresh engine to be created when create_app() runs
    try:
        import app.infrastructure.database.session as session_module
        session_module._engine = None
        session_module._session_factory = None
    except Exception:
        pass
    
    yield
    
    # AFTER TEST: Reset globals again (cleanup for next test)
    try:
        import app.infrastructure.database.session as session_module
        if session_module._engine is not None:
            await session_module._engine.dispose()
        session_module._engine = None
        session_module._session_factory = None
    except Exception:
        pass
    
    # AFTER TEST: Cleanup database tables
    cleanup_engine = create_async_engine(test_db_url, poolclass=NullPool, echo=False)
    async with cleanup_engine.begin() as conn:
        for table in ["reports", "user_refresh_tokens", "audit_logs", "analyses", "digital_assets", "uploads", "users"]:
            try:
                result = await conn.execute(text(f"DELETE FROM {table}"))
            except Exception:
                pass
    await cleanup_engine.dispose()


# Windows-only: ensure background anyio/from_thread portals and their
# ProactorEventLoop self-pipe sockets have time to shut down.
@pytest.fixture(autouse=True)
def ensure_background_cleanup() -> None:
    """Clean up background resources on Windows to avoid ResourceWarnings."""
    yield
    if sys.platform != "win32":
        return
    with suppress(Exception), warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        gc.collect()
        time.sleep(0.05)
        gc.collect()
