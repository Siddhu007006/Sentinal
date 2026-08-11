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
- TODO: Must be disposed during application shutdown (await engine.dispose())
  to properly close connection pool. Currently not implemented - engine will
  be cleaned up on process termination.

Traces to: 07-Backend-Development-Standards §8 (transactions, session lifecycle)
Traces to: 22-Engineering-Backlog E3.T1 (session factory, request-scoped DI)
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.settings import Settings
from app.infrastructure.database.engine import create_database_engine


# Module-level singletons.
# Engine and session factory are created once on first use and reused
# for all subsequent requests. This avoids recreating infrastructure
# on every request.
#
# Note: Engine should be disposed during application shutdown with
# await engine.dispose() to properly close the connection pool.
# This will be implemented when wiring application startup/shutdown lifecycle.
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


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """
    FastAPI dependency providing request-scoped database session.

    This is the ONLY way database sessions should be obtained in the application.
    All route handlers, services, and repositories that need database access
    must declare this as a dependency.

    Lifecycle (automatic, per request):
        1. Session created from factory
        2. Session yielded to request handler
        3. On success: session.commit() → session.close()
        4. On exception: session.rollback() → session.close() → re-raise

    The commit/rollback/close sequence is guaranteed even if the request
    handler raises an exception, preventing connection leaks and ensuring
    transactional consistency.

    Usage in route handlers:
        ```python
        @router.get("/users/{user_id}")
        async def get_user(
            user_id: UUID,
            db: AsyncSession = Depends(get_db_session),
        ) -> UserResponse:
            # db is request-scoped, auto-managed
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(404)
            return UserResponse.from_orm(user)
            # Auto-commit on success, auto-rollback on HTTPException
        ```

    Usage in Application services:
        ```python
        class UserService:
            def __init__(self, db: AsyncSession):
                self.db = db

            async def create_user(self, data: CreateUserData) -> User:
                user = User(**data.model_dump())
                self.db.add(user)
                await self.db.flush()  # Get ID without committing
                return user
                # Service doesn't commit — request handler commits
        ```

    Yields:
        AsyncSession: Request-scoped database session

    Raises:
        Any exception from request handler (after rollback + close)

    Security considerations (08-Security-Architecture):
        - No connection string leakage (managed internally)
        - Automatic rollback prevents partial writes on error
        - Session isolation ensures no cross-request data leakage

    Performance considerations (07-Backend-Development-Standards §13):
        - Engine and factory cached at module level
        - Connections reused from pool
        - expire_on_commit=False reduces post-commit query load
        - Explicit session.close() returns connection to pool immediately
    """
    # Import here to avoid circular import at module level
    from app.core.dependencies import get_settings as _get_settings_func

    settings = _get_settings_func()
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
