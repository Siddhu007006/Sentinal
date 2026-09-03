"""
Test database fixtures and configuration for pytest.

Provides reusable fixtures for integration testing with a real PostgreSQL
database. Fixtures handle session lifecycle and transaction management to
ensure test isolation (no data leakage between tests).

Session-Scoped Engine Lifecycle (Windows-Compatible):
  - Engine created ONCE per pytest session in pytest_sessionstart
  - Engine tied to current event loop (avoids loop-connection mismatch)
  - Function-scoped AsyncSession for test isolation
  - Function-scoped database cleanup (truncate tables before/after each test)
  - Engine disposed once in pytest_sessionfinish (outside any test loop context)

This architecture solves the Windows asyncio event loop corruption by:
  - Creating engine once (not per-test)
  - Using engine across multiple event loop recreations
  - Disposing engine outside of any async context
  - Preventing connection reuse across incompatible event loops

Database Isolation:
  - Function-scoped reset_database_tables fixture truncates all test tables
  - Runs before and after each test to prevent data leakage between tests

Traces to: 11-Testing-Strategy (fixture patterns)
Traces to: 07-Backend-Development-Standards (test isolation)
Traces to: 22-Engineering-Backlog E3.T1 (database fixtures)
"""

import asyncio
import gc
import os
import subprocess
import sys
import time
import warnings
from collections.abc import Generator
from contextlib import suppress
from urllib.parse import urlsplit, urlunsplit

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
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

# Module-level session-scoped engine (created once, disposed once per pytest session)
_session_engine: AsyncEngine | None = None
# Privileged cleanup engine (schema_owner role) for table truncation.
# sentinel_api deliberately lacks TRUNCATE (audit_logs immutability), so
# test isolation must run through the schema owner.
_cleanup_engine: AsyncEngine | None = None

settings = Settings()

test_db_url = settings.database.url
migration_db_url = settings.database.migration_url

test_parts = urlsplit(test_db_url)
migration_parts = urlsplit(migration_db_url)

cleanup_db_url = urlunsplit(
    (
        "postgresql+asyncpg",
        (
            f"{migration_parts.username}:{migration_parts.password}"
            f"@{test_parts.hostname}:{test_parts.port}"
        ),
        test_parts.path,
        test_parts.query,
        "",
    )
)

def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest environment."""
    os.environ["ENVIRONMENT"] = "test"


def pytest_sessionstart(session: pytest.Session) -> None:
    """Run database migrations and create session-scoped engine.

    This hook runs AFTER collection completes, so --collect-only does not require
    a live database. Only when tests actually execute are migrations and engine
    creation needed.
    """
    global _session_engine

    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

    # Try to run migrations, but don't fail if database is unavailable
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            db_err = result.stderr.lower()
            if "connection refused" in db_err or "could not connect" in db_err:
                print("Database unavailable - migrations skipped", file=sys.stderr)
            else:
                msg = f"Migration failed with code {result.returncode}"
                print(msg, file=sys.stderr)
                if result.stderr:
                    print(f"stderr: {result.stderr}", file=sys.stderr)
        else:
            print("Database migrations completed successfully", file=sys.stdout)
    except subprocess.TimeoutExpired:
        print("Alembic migration timed out", file=sys.stderr)
    except Exception as e:
        print(f"Failed to run migrations: {e}", file=sys.stderr)

    # Create session-scoped engine for the test session with NullPool
    try:
        settings = Settings()
        test_db_url = settings.database.url

        _session_engine = create_async_engine(
            test_db_url,
            poolclass=NullPool,
            echo=False,
        )
        print("Session-scoped database engine created", file=sys.stdout)
    except Exception as e:
        print(f"Error: Failed to create session-scoped engine: {e}", file=sys.stderr)
        _session_engine = None

    # Create privileged cleanup engine (schema_owner) for TRUNCATE isolation.
    # sentinel_api must NOT be able to truncate tables (audit immutability),
    # so per-test cleanup connects as the schema owner instead.
    global _cleanup_engine
    try:
        _cleanup_engine = create_async_engine(
            cleanup_db_url,
            poolclass=NullPool,
            echo=False,
        )
        print("Cleanup engine (schema_owner) created", file=sys.stdout)
    except Exception as e:
        print(f"Error: Failed to create cleanup engine: {e}", file=sys.stderr)
        _cleanup_engine = None


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Dispose the session-scoped engine after all tests complete.

    This ensures the engine is disposed exactly once, at the correct lifecycle
    boundary, outside of any test's event loop context.
    """
    global _session_engine, _cleanup_engine

    if _session_engine is not None:
        try:
            import asyncio as asyncio_module
            asyncio_module.run(_session_engine.dispose())
            print("Session-scoped database engine disposed", file=sys.stdout)
        except Exception as e:
            print(f"Failed to dispose session engine: {e}", file=sys.stderr)
        finally:
            _session_engine = None

    if _cleanup_engine is not None:
        try:
            import asyncio as asyncio_module
            asyncio_module.run(_cleanup_engine.dispose())
            print("Cleanup database engine disposed", file=sys.stdout)
        except Exception as e:
            print(f"Failed to dispose cleanup engine: {e}", file=sys.stderr)
        finally:
            _cleanup_engine = None


def get_session_engine() -> AsyncEngine | None:
    """Get the session-scoped engine for test fixtures.

    This is NOT a fixture, but a module-level function to avoid
    scope mismatch with pytest-asyncio's function-scoped event_loop.
    """
    return _session_engine


@pytest.fixture(autouse=True)
def reset_database_tables(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Clean test tables before and after each test.

    Deliberately a SYNC fixture so truncation also runs around sync tests
    (an async autouse fixture is skipped for sync tests, which let state
    leak between tests and across runs). Runs as the schema_owner role
    because sentinel_api lacks TRUNCATE privileges by design (audit_logs
    immutability). Each cleanup runs on its own short-lived event loop;
    the cleanup engine uses NullPool, so every TRUNCATE checks out and
    disposes a fresh connection (no connections cross event loops).

    Self-healing: migration-lifecycle tests legitimately drop the schema
    (alembic downgrade base). If the expected tables are missing at
    cleanup time, the schema is restored with `alembic upgrade head`
    before truncating, so a dropped schema never cascades errors into
    unrelated tests.
    """
    if "integration" not in str(request.path).replace("\\", "/").split("/"):
        yield
        return

    expected_tables = (
        "reports",
        "user_refresh_tokens",
        "audit_logs",
        "analyses",
        "digital_assets",
        "uploads",
        "users",
    )

    def restore_schema_if_needed() -> None:
        assert _cleanup_engine is not None
        engine = _cleanup_engine

        async def _schema_needs_restore() -> bool:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
                present = {row[0] for row in result.fetchall()}
                missing = [t for t in expected_tables if t not in present]
                if missing:
                    return True

                # Migration-lifecycle tests can also restore the schema
                # themselves while leaving audit_logs with full DML
                # (default privileges). Detect the broken immutability.
                audit = await conn.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.role_table_grants "
                        "WHERE table_schema = 'public' "
                        "AND table_name = 'audit_logs' "
                        "AND grantee = 'sentinel_api' "
                        "AND privilege_type IN ('UPDATE', 'DELETE', 'TRUNCATE')"
                    )
                )
                forbidden = audit.scalar_one()
                return forbidden > 0

        if not asyncio.run(_schema_needs_restore()):
            return

        print(
            "Schema incomplete or audit immutability broken; restoring",
            file=sys.stderr,
        )
        backend_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".."
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )

        # Re-apply the audit_logs immutability fix: the migration
        # default privileges grant full DML, and nothing else reapplies
        # the INSERT-only restriction after a schema restore (mirrors
        # docker/bootstrap/fix_audit_logs_post_migration.sql).
        async def _apply_audit_fix() -> None:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "REVOKE ALL PRIVILEGES ON TABLE public.audit_logs "
                        "FROM sentinel_api"
                    )
                )
                await conn.execute(
                    text(
                        "GRANT SELECT ON TABLE public.audit_logs "
                        "TO sentinel_api"
                    )
                )
                await conn.execute(
                    text(
                        "GRANT INSERT ON TABLE public.audit_logs "
                        "TO sentinel_api"
                    )
                )

        asyncio.run(_apply_audit_fix())

    def cleanup() -> None:
        if _cleanup_engine is None:
            return

        restore_schema_if_needed()

        async def _truncate() -> None:
            async with _cleanup_engine.begin() as conn:
                await conn.execute(
                    text(
                        "TRUNCATE TABLE "
                        "reports, "
                        "user_refresh_tokens, "
                        "audit_logs, "
                        "analyses, "
                        "digital_assets, "
                        "uploads, "
                        "users "
                        "RESTART IDENTITY CASCADE"
                    )
                )

        asyncio.run(_truncate())

    cleanup()

    yield

    cleanup()



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

