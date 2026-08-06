"""
Redis client lifecycle management.

Provides centralized management of the Redis connection used by the rate
limiting middleware and other cache/queue operations.

The Redis client is created lazily on first use and cached at module level
for the application lifetime. It is explicitly closed during application
shutdown to release the connection pool.

This follows the same lifecycle pattern as the database engine (see
app/infrastructure/database/session.py).

Traces to: 08-Security-Architecture §7 (rate limiting)
Traces to: 22-Engineering-Backlog E2.T7 (rate limiting implementation)
"""

import logging
import os

import redis


logger = logging.getLogger(__name__)

# Module-level singleton for Redis client
_redis_client: redis.Redis | None = None


def get_redis_client(redis_url: str | None = None) -> redis.Redis | None:
    """
    Get or create the Redis client singleton.

    The client is created lazily on first call and cached at module level.
    Subsequent calls return the cached client.

    Args:
        redis_url: Redis connection URL. If not provided, falls back to
                   REDIS_URL environment variable or default localhost.

    Returns:
        Redis client instance, or None if initialization failed

    Note:
        This getter is preferred over direct imports because:
        - Allows client lifecycle management (recreation, replacement)
        - Prevents stale references if client is reassigned
        - Centralizes access point for testing and lifecycle control
        - Supports graceful shutdown (client.close() during app shutdown)

    Usage in middleware:
        ```python
        redis_client = get_redis_client(settings.queue.broker_url)
        if redis_client:
            redis_client.incr(counter_key)
        ```

    Usage in application lifespan shutdown:
        ```python
        redis_client = get_redis_client()
        if redis_client:
            redis_client.close()
        ```
    """
    global _redis_client

    if _redis_client is None:
        url = redis_url or os.environ.get("REDIS_URL")
        if not url:
            raise ValueError("REDIS_URL environment variable must be set")
        try:
            _redis_client = redis.from_url(
                url,
                decode_responses=True,
            )  # type: ignore[no-untyped-call]
            logger.info("Redis client initialized successfully")
        except redis.RedisError as e:
            logger.error(
                f"Failed to initialize Redis client: {e}",
                exc_info=True,
            )
            _redis_client = None

    return _redis_client


def close_redis_client() -> None:
    """
    Close the Redis client and release the connection pool.

    Should be called during application shutdown (in the lifespan
    shutdown hook) to ensure proper resource cleanup.

    Usage in application lifespan:
        ```python
        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
            # Startup...
            yield
            # Shutdown...
            close_redis_client()
        ```
    """
    global _redis_client

    if _redis_client is not None:
        try:
            _redis_client.close()
            logger.info("Redis client closed")
            _redis_client = None
        except redis.RedisError as e:
            logger.error(
                f"Error closing Redis client: {e}",
                exc_info=True,
            )
