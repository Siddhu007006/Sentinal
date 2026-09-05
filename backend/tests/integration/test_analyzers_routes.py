"""Integration tests for analyzer route handlers (E6.T8)."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.session import get_db_session
from app.main import create_app
from tests.conftest import get_session_engine


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client with database session override."""
    app = create_app()
    engine = get_session_engine()
    assert engine is not None

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /analyzers
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_list_analyzers_returns_all_registered(client: TestClient) -> None:
    """GET /analyzers returns list of all registered analyzers."""
    response = client.get("/api/v1/analyzers")
    assert response.status_code == 200

    data = response.json()
    assert "analyzers" in data
    assert "total" in data
    assert isinstance(data["analyzers"], list)
    assert data["total"] >= 1  # At least metadata analyzer should be registered

    # Check that each analyzer has required fields
    for analyzer in data["analyzers"]:
        assert "key" in analyzer
        assert "version" in analyzer
        assert "description" in analyzer


@pytest.mark.integration
def test_list_analyzers_includes_metadata_analyzer(client: TestClient) -> None:
    """GET /analyzers includes the metadata analyzer."""
    response = client.get("/api/v1/analyzers")
    assert response.status_code == 200

    data = response.json()
    analyzer_keys = [a["key"] for a in data["analyzers"]]
    assert "metadata" in analyzer_keys

    # Check metadata analyzer details
    metadata_analyzer = next(a for a in data["analyzers"] if a["key"] == "metadata")
    assert metadata_analyzer["version"] == "1.0.0"
    assert "metadata" in metadata_analyzer["description"].lower()


# ---------------------------------------------------------------------------
# GET /analyzers/{analyzerId}
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_get_analyzer_returns_details_for_existing(client: TestClient) -> None:
    """GET /analyzers/{analyzerId} returns details for existing analyzer."""
    response = client.get("/api/v1/analyzers/metadata")
    assert response.status_code == 200

    data = response.json()
    assert data["key"] == "metadata"
    assert data["version"] == "1.0.0"
    assert "description" in data


@pytest.mark.integration
def test_get_analyzer_returns_404_for_nonexistent(client: TestClient) -> None:
    """GET /analyzers/{analyzerId} returns 404 for nonexistent analyzer."""
    response = client.get("/api/v1/analyzers/nonexistent")
    assert response.status_code == 404
