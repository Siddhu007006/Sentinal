"""
Database engine configuration.

Creates and configures the async SQLAlchemy engine for PostgreSQL access.
Connection pooling, timeouts, and all database connectivity settings are
centralized here.

This module is the single point of configuration for database access across
the entire application. All database sessions ultimately trace back to the
engine created here.

Traces to: 04-Database-Design (PostgreSQL as primary datastore)
Traces to: 07-Backend-Development-Standards §8 (async SQLAlchemy, pooling)
Traces to: 22-Engineering-Backlog E3.T1 (database connection configuration)
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.settings import Settings


def create_database_engine(settings: Settings) -> AsyncEngine:
    """
    Create and configure async SQLAlchemy engine.

    Configures connection pooling, timeouts, and engine-level behavior per
    07-Backend-Development-Standards §8 and 08-Security-Architecture §9
    (least privilege, fail fast).

    Connection pool sizing (pool_size + max_overflow) should be tuned based on:
    - API worker count (api_workers setting)
    - Expected concurrent request load
    - Database connection limits
    - Available database resources

    Default pool sizing (5 + 10 = 15 total) is conservative for development
    and small-scale production. Scale up pool_size and max_overflow in
    production based on observed metrics.

    Args:
        settings: Application settings containing database configuration

    Returns:
        Configured async SQLAlchemy engine

    Security considerations (08-Security-Architecture §9):
        - DATABASE_URL must use postgresql+asyncpg:// scheme (async driver)
        - Credentials sourced from environment, never hardcoded
        - Connection string validated at Settings load time
        - pool_pre_ping=True detects stale connections before use

    Performance considerations (07-Backend-Development-Standards §13):
        - Connection pooling reduces per-request connection overhead
        - pool_pre_ping adds latency but prevents "server closed connection"
        - pool_recycle ensures connections don't exceed server timeout
        - pool_timeout prevents indefinite waits under connection exhaustion

    Example:
        >>> from app.core.dependencies import get_settings
        >>> settings = get_settings()
        >>> engine = create_database_engine(settings)
        >>> # Engine is now ready for session factory creation
    """
    return create_async_engine(
        settings.database.url,
        # Connection Pool Configuration
        # ----------------------------
        # pool_size: Connections maintained in the pool (default: 5).
        pool_size=5,
        # max_overflow: Extra connections beyond pool_size under load (default: 10).
        # Total max connections = pool_size + max_overflow = 15.
        max_overflow=10,
        # pool_timeout: Seconds to wait for available connection (default: 30).
        pool_timeout=30,
        # pool_pre_ping: Test connection validity before using it.
        # Detects stale/closed connections (e.g., after network interruption).
        pool_pre_ping=True,
        # pool_recycle: Recycle connections after this many seconds (default: 1 hour).
        # Prevents using connections that exceed server's connection timeout.
        pool_recycle=3600,
        # SQL Echo disabled in production (no query logging).
        echo=False,
        # Async Engine Settings
        # ----------------------
        # future: Enable SQLAlchemy 2.0 API (required for async).
        future=True,
    )
