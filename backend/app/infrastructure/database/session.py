"""
Database session management.

Provides async SQLAlchemy session factory and FastAPI dependency for
request-scoped database sessions. All database access in the application
flows through sessions obtained from this module.

Session lifecycle is strictly managed:
- Acquire: Session created at request start
- Yield: Session available to request handler
- Commit: Auto-commit on successful request completion
- Rollback: Auto-rollback on any exception
- Close: Session always closed, even on exception

This implements the Unit-of-Work pattern at the request boundary, ensuring
transactional consistency without manual session management in business logic.

Engine lifecycle:
- Created once on first database access
- Reused for entire application lifetime
- Disposed during application shutdown via dispose_engine(), called from
  the application lifespan in app/main.py

Traces to: 07-Backend-Development-Standards §8 (transactions, session lifecycle)
Traces to: 22-Engineering-Backlog E3.T1 (session factory, request-scoped DI)
"""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.settings import Settings
from app.infrastructure.database.engine import create_database_engine


# Module-level singletons.
# Engine and session factory are created once on first use and reused
# for all subsequent requests. This avoids recreating infrastructure
# on every request.
#
# Engine disposal is handled by the application lifespan (app/main.py),
# which calls dispose_engine() on shutdown to close the connection pool.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings) -> AsyncEngine | None:
    """
    Get the application's database engine instance.

    Returns the lazily-initialized engine singleton. This getter pattern
    allows the engine to be recreated or swapped without requiring consumers
    to re-import references.

    The engine is initialized on first call to _get_session_factory() and
    cached at module level for the lifetime of the application.

    Args:
        settings: Application settings containing database configuration

    Returns:
        The AsyncEngine instance, or None if not yet initialized

    Note:
        This getter is preferred over directly importing _engine because:
        - Allows engine lifecycle management (recreation, swapping)
        - Prevents stale references if _engine is reassigned
        - Centralizes access point for testing and lifecycle control
        - Supports graceful shutdown (engine.dispose() during app shutdown)

    Usage in application lifespan shutdown:
        ```python
        from app.core.settings import get_settings
        from app.infrastructure.database.session import get_engine

        engine = get_engine(get_settings())
        if engine is not None:
            await engine.dispose()
        ```
    """
    return _engine


def _get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """
    Get or create the async session factory singleton.

    The engine and session factory are created once on first call and cached
    at module level. Subsequent calls return the cached factory.

    This is safe because:
    - Settings don't change during application lifetime
    - Engine configuration is immutable after creation
    - Factory can safely produce multiple concurrent sessions
    - Module-level variables are thread-safe in Python (GIL)

    Configuration:
        - expire_on_commit=False: Prevents lazy-loading queries after commit
          (all data must be loaded before commit, enforcing explicit loading)
        - class_=AsyncSession: Explicit session class (for type clarity)

    Args:
        settings: Application settings containing database configuration

    Returns:
        Configured async session factory (cached after first call)

    Note:
        This function is internal. Use get_db_session() for dependency injection.

    Performance:
        The engine and session factory are initialized once and reused for all
        subsequent requests, avoiding repeated engine and factory construction.
    """
    global _engine, _session_factory

    if _session_factory is None:
        _engine = create_database_engine(settings)
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _session_factory

def _get_settings() -> Settings:
    """Provide application settings to FastAPI without creating an import cycle."""
    from app.core.dependencies import get_settings

    return get_settings()


async def get_db_session(
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> AsyncGenerator[AsyncSession]:
    """
    FastAPI dependency providing request-scoped database session.

    This is the ONLY way database sessions should be obtained in the application.
    All route handlers, services, and repositories that need database access
    must declare this as a dependency.
    """
    session_factory = _get_session_factory(settings)
    session = session_factory()

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Dispose the database engine and reset cached globals."""

    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()

    _engine = None
    _session_factory = None
