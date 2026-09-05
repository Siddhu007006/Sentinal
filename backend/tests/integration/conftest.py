"""Integration test fixtures for database and session cleanup.

This module provides fixtures that route database access through the
TEST engine (NullPool) instead of the production engine (QueuePool).

Dependency injection:
|- Test db_session fixture creates sessions from tests/conftest.py::_session_engine
|- NOT from app.infrastructure.database.session::_engine (production)
|- This avoids QueuePool singleton persistence across event loops
"""
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from datetime import UTC, datetime

from uuid import uuid4

from app.domain.entities.user import User, UserRole
from app.domain.repositories.user import UserRepository

from app.domain.repositories.analysis import AnalysisRepository
from app.domain.repositories.digital_asset import DigitalAssetRepository
from app.domain.services.storage_adapter import StorageAdapter
from app.infrastructure.database.repositories.analysis import (
    PostgreSQLAnalysisRepository,
)
from app.infrastructure.database.repositories.digital_asset import (
    PostgreSQLDigitalAssetRepository,
)
from app.infrastructure.database.repositories.user import (
    PostgreSQLUserRepository,
)

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


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Provide a Redis client for integration testing."""
    redis = Redis.from_url(
        "redis://localhost:6379/15",
        decode_responses=True,
    )
    try:
        await redis.ping()
        yield redis
    except Exception as exc:
        pytest.skip(f"Redis unavailable: {exc}")
    finally:
        await redis.aclose()


@pytest_asyncio.fixture
async def analysis_repo(db_session: AsyncSession) -> AnalysisRepository:
    """Provide an AnalysisRepository instance for testing."""
    if db_session is None:
        pytest.skip("Database unavailable")
    return PostgreSQLAnalysisRepository(db_session)


@pytest_asyncio.fixture
async def asset_repo(db_session: AsyncSession) -> DigitalAssetRepository:
    """Provide a DigitalAssetRepository instance for testing."""
    if db_session is None:
        pytest.skip("Database unavailable")
    return PostgreSQLDigitalAssetRepository(db_session)

@pytest_asyncio.fixture
async def user_repo(db_session: AsyncSession) -> UserRepository:
    """Provide a UserRepository instance for integration tests."""
    if db_session is None:
        pytest.skip("Database unavailable")
    return PostgreSQLUserRepository(db_session)


@pytest_asyncio.fixture
async def user(
    user_repo: UserRepository,
) -> User:
    """Create a persisted analyst user for integration tests."""
    user = User(
        id=uuid4(),
        email=f"worker-test-{uuid4()}@example.com",
        password_hash="test-password-hash",
        role=UserRole.ANALYST,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(UTC),
    )
    await user_repo.create(user)
    return user

@pytest_asyncio.fixture
async def storage_adapter() -> StorageAdapter:
    """Provide a real S3StorageAdapter for integration tests.

    Skips only if:
    - aioboto3 is genuinely not importable
    - Storage settings cannot be resolved
    - MinIO/S3 endpoint is not reachable at the configured URL
    """
    try:
        import aioboto3  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"Storage adapter requires aioboto3: {exc}")

    from app.core.settings import Settings, StorageSettings
    from app.infrastructure.storage.s3_adapter import S3StorageAdapter

    try:
        settings = Settings().storage
    except Exception:
        settings = StorageSettings(
            S3_ENDPOINT_URL="http://localhost:9000",
            S3_BUCKET_NAME="sentinel-assets",
            S3_ACCESS_KEY=SecretStr("minioadmin"),
            S3_SECRET_KEY=SecretStr("minioadmin"),
        )

    from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

    adapter = S3StorageAdapter(settings)
    try:
        async with adapter._client() as client:
            try:
                await client.head_bucket(Bucket=settings.bucket_name)
            except ClientError:
                await client.create_bucket(Bucket=settings.bucket_name)
    except EndpointConnectionError as exc:
        pytest.skip(f"MinIO not reachable at {settings.endpoint_url}: {exc}")
    except (ClientError, BotoCoreError, OSError) as exc:
        pytest.skip(f"Storage adapter cannot initialize: {exc}")

    return adapter
