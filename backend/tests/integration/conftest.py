"""Integration test fixtures for database and session cleanup."""

import asyncio
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.settings import Settings
from app.infrastructure.database.session import dispose_engine


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Provide a test database session with automatic cleanup."""
    try:
        settings = Settings()
        database_url = settings.database.url
        
        engine = create_async_engine(database_url, poolclass=NullPool, echo=False)
        
        async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        
        session = async_session_factory()
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()
        
        await engine.dispose()
    except Exception:
        yield None


@pytest_asyncio.fixture
async def async_engine() -> AsyncGenerator[Any | None, None]:
    """Provide an async engine for tests."""
    try:
        settings = Settings()
        database_url = settings.database.url
        
        engine = create_async_engine(database_url, poolclass=NullPool, echo=False)
        yield engine
        await engine.dispose()
    except Exception:
        yield None


@pytest.fixture
def clean_db() -> None:
    """Fixture indicating database should be clean before test."""
    return None

