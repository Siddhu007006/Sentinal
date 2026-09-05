"""Integration tests for analysis route handlers (E6.T7)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.session import get_db_session
from app.main import create_app
from app.models.analysis import Analysis
from app.models.digital_asset import DigitalAsset
from app.models.user import User
from tests.conftest import get_session_engine


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
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


def _create_user(
    client: TestClient,
    email: str,
    password: str = "SuperSecureP@ss123",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Analysis Test User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SuperSecureP@ss123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]  # type: ignore[no-any-return]


def _set_role(user_id: str, role: str) -> None:
    async def update_role() -> None:
        engine = get_session_engine()
        assert engine is not None
        async with engine.begin() as connection:
            await connection.execute(
                update(User).where(User.id == UUID(user_id)).values(role=role)
            )

    asyncio.run(update_role())


def _seed_asset(
    user_id: str,
    *,
    asset_id: UUID | None = None,
    normalized_value: str | None = None,
) -> UUID:
    asset_id = asset_id or uuid4()
    # Use unique normalized value to avoid duplicate key violations
    normalized_value = normalized_value or f"test_{asset_id}.pdf"
    # Generate unique sha256 hash based on asset_id
    sha256_hash = asset_id.hex + "a" * (64 - len(asset_id.hex))

    async def insert_asset() -> None:
        engine = get_session_engine()
        assert engine is not None
        async with engine.begin() as connection:
            await connection.execute(
                DigitalAsset.__table__.insert(),  # type: ignore[attr-defined]
                {
                    "id": asset_id,
                    "user_id": UUID(user_id),
                    "asset_type": "file",
                    "sha256_hash": sha256_hash,
                    "mime_type": "application/pdf",
                    "size_bytes": 1024,
                    "raw_value": "test.pdf",
                    "normalized_value": normalized_value,
                    "storage_key": f"test/{asset_id}.pdf",
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                },
            )

    asyncio.run(insert_asset())
    return asset_id


def _seed_analysis(
    asset_id: UUID,
    user_id: str,
    *,
    analysis_id: UUID | None = None,
    status: str = "pending",
) -> UUID:
    analysis_id = analysis_id or uuid4()

    async def insert_analysis() -> None:
        engine = get_session_engine()
        assert engine is not None
        async with engine.begin() as connection:
            await connection.execute(
                Analysis.__table__.insert(),  # type: ignore[attr-defined]
                {
                    "id": analysis_id,
                    "digital_asset_id": asset_id,
                    "requested_by": UUID(user_id),
                    "analyzer_key": "metadata",
                    "analyzer_version": "1.0.0",
                    "analyzer_slugs": ["metadata"],
                    "status": status,
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                },
            )

    asyncio.run(insert_analysis())
    return analysis_id


@pytest.mark.integration
def test_request_analysis_requires_auth(client: TestClient) -> None:
    """POST /assets/{assetId}/analyses requires authentication."""
    asset_id = uuid4()
    response = client.post(
        f"/api/v1/assets/{asset_id}/analyses",
        json={"analyzerKey": "metadata"},
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_request_analysis_requires_analyst_or_admin_role(client: TestClient) -> None:
    """POST /assets/{assetId}/analyses requires analyst or admin role."""
    # Create regular user
    _create_user(client, "regular@example.com")
    token = _login(client, "regular@example.com")

    asset_id = uuid4()
    response = client.post(
        f"/api/v1/assets/{asset_id}/analyses",
        json={"analyzerKey": "metadata"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.integration
def test_request_analysis_returns_404_for_nonexistent_asset(client: TestClient) -> None:
    """POST /assets/{assetId}/analyses returns 404 for unknown asset."""
    user = _create_user(client, "analyst@example.com")
    _set_role(user["userId"], "analyst")
    token = _login(client, "analyst@example.com")

    asset_id = uuid4()
    response = client.post(
        f"/api/v1/assets/{asset_id}/analyses",
        json={"analyzerKey": "metadata"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.integration
def test_request_analysis_returns_404_for_non_owned_asset(client: TestClient) -> None:
    """POST /assets/{assetId}/analyses returns 404 for non-owned asset."""
    user1 = _create_user(client, "analyst1@example.com")
    _set_role(user1["userId"], "analyst")
    token1 = _login(client, "analyst1@example.com")

    user2 = _create_user(client, "analyst2@example.com")
    _set_role(user2["userId"], "analyst")

    # Asset owned by user2
    asset_id = _seed_asset(user2["userId"])

    # User1 tries to analyze user2's asset
    response = client.post(
        f"/api/v1/assets/{asset_id}/analyses",
        json={"analyzerKey": "metadata"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 404  # Not 403 - enumeration prevention


@pytest.mark.integration
def test_request_analysis_creates_pending_analysis(client: TestClient) -> None:
    """POST /assets/{assetId}/analyses creates pending analysis and returns 202."""
    user = _create_user(client, "analyst@example.com")
    _set_role(user["userId"], "analyst")
    token = _login(client, "analyst@example.com")

    asset_id = _seed_asset(user["userId"])

    response = client.post(
        f"/api/v1/assets/{asset_id}/analyses",
        json={"analyzerKey": "metadata"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202

    data = response.json()
    assert data["assetId"] == str(asset_id)
    assert data["requestedBy"] == user["userId"]
    assert data["analyzerKey"] == "metadata"
    assert data["status"] == "pending"
    assert data["analysisId"] is not None


@pytest.mark.integration
def test_list_asset_analyses_requires_auth(client: TestClient) -> None:
    """GET /assets/{assetId}/analyses requires authentication."""
    asset_id = uuid4()
    response = client.get(f"/api/v1/assets/{asset_id}/analyses")
    assert response.status_code == 401


@pytest.mark.integration
def test_list_asset_analyses_filters_by_asset(client: TestClient) -> None:
    """GET /assets/{assetId}/analyses returns analyses for specific asset."""
    user = _create_user(client, "analyst@example.com")
    _set_role(user["userId"], "analyst")
    token = _login(client, "analyst@example.com")

    asset1_id = _seed_asset(user["userId"])
    asset2_id = _seed_asset(user["userId"])

    _seed_analysis(asset1_id, user["userId"])
    _seed_analysis(asset2_id, user["userId"])

    response = client.get(
        f"/api/v1/assets/{asset1_id}/analyses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["assetId"] == str(asset1_id)


@pytest.mark.integration
def test_list_analyses_requires_auth(client: TestClient) -> None:
    """GET /analyses requires authentication."""
    response = client.get("/api/v1/analyses")
    assert response.status_code == 401


@pytest.mark.integration
def test_list_analyses_filters_by_user_for_non_admin(client: TestClient) -> None:
    """GET /analyses returns only user's own analyses for non-admin."""
    user1 = _create_user(client, "analyst1@example.com")
    _set_role(user1["userId"], "analyst")
    token1 = _login(client, "analyst1@example.com")

    user2 = _create_user(client, "analyst2@example.com")
    _set_role(user2["userId"], "analyst")

    asset1_id = _seed_asset(user1["userId"])
    asset2_id = _seed_asset(user2["userId"])

    _seed_analysis(asset1_id, user1["userId"])
    _seed_analysis(asset2_id, user2["userId"])

    response = client.get(
        "/api/v1/analyses",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["requestedBy"] == user1["userId"]


@pytest.mark.integration
def test_list_analyses_returns_all_for_admin(client: TestClient) -> None:
    """GET /analyses returns all analyses for admin."""
    user1 = _create_user(client, "analyst1@example.com")
    _set_role(user1["userId"], "analyst")

    user2 = _create_user(client, "analyst2@example.com")
    _set_role(user2["userId"], "analyst")

    admin = _create_user(client, "admin@example.com")
    _set_role(admin["userId"], "admin")
    admin_token = _login(client, "admin@example.com")

    asset1_id = _seed_asset(user1["userId"])
    asset2_id = _seed_asset(user2["userId"])

    _seed_analysis(asset1_id, user1["userId"])
    _seed_analysis(asset2_id, user2["userId"])

    response = client.get(
        "/api/v1/analyses",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data["items"]) == 2


@pytest.mark.integration
def test_get_analysis_requires_auth(client: TestClient) -> None:
    """GET /analyses/{analysisId} requires authentication."""
    analysis_id = uuid4()
    response = client.get(f"/api/v1/analyses/{analysis_id}")
    assert response.status_code == 401


@pytest.mark.integration
def test_get_analysis_returns_404_for_nonexistent(client: TestClient) -> None:
    """GET /analyses/{analysisId} returns 404 for unknown analysis."""
    user = _create_user(client, "analyst@example.com")
    _set_role(user["userId"], "analyst")
    token = _login(client, "analyst@example.com")

    analysis_id = uuid4()
    response = client.get(
        f"/api/v1/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.integration
def test_get_analysis_returns_404_for_non_owned_analysis(client: TestClient) -> None:
    """GET /analyses/{analysisId} returns 404 for non-owned analysis."""
    user1 = _create_user(client, "analyst1@example.com")
    _set_role(user1["userId"], "analyst")
    token1 = _login(client, "analyst1@example.com")

    user2 = _create_user(client, "analyst2@example.com")
    _set_role(user2["userId"], "analyst")

    asset_id = _seed_asset(user2["userId"])
    analysis_id = _seed_analysis(asset_id, user2["userId"])

    response = client.get(
        f"/api/v1/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 404  # Not 403 - enumeration prevention


@pytest.mark.integration
def test_get_analysis_returns_detail_for_owner(client: TestClient) -> None:
    """GET /analyses/{analysisId} returns analysis detail for owner."""
    user = _create_user(client, "analyst@example.com")
    _set_role(user["userId"], "analyst")
    token = _login(client, "analyst@example.com")

    asset_id = _seed_asset(user["userId"])
    analysis_id = _seed_analysis(asset_id, user["userId"])

    response = client.get(
        f"/api/v1/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["analysisId"] == str(analysis_id)
    assert data["assetId"] == str(asset_id)
    assert data["requestedBy"] == user["userId"]
    assert data["status"] == "pending"


@pytest.mark.integration
def test_cancel_analysis_requires_auth(client: TestClient) -> None:
    """POST /analyses/{analysisId}/cancel requires authentication."""
    analysis_id = uuid4()
    response = client.post(f"/api/v1/analyses/{analysis_id}/cancel")
    assert response.status_code == 401


@pytest.mark.integration
def test_cancel_analysis_transitions_to_cancelled(client: TestClient) -> None:
    """POST /analyses/{analysisId}/cancel transitions pending analysis to cancelled."""
    user = _create_user(client, "analyst@example.com")
    _set_role(user["userId"], "analyst")
    token = _login(client, "analyst@example.com")

    asset_id = _seed_asset(user["userId"])
    analysis_id = _seed_analysis(asset_id, user["userId"], status="pending")

    response = client.post(
        f"/api/v1/analyses/{analysis_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["analysisId"] == str(analysis_id)
    assert data["status"] == "cancelled"


@pytest.mark.integration
def test_cancel_analysis_returns_404_for_non_owned(client: TestClient) -> None:
    """POST /analyses/{analysisId}/cancel returns 404 for non-owned analysis."""
    user1 = _create_user(client, "analyst1@example.com")
    _set_role(user1["userId"], "analyst")
    token1 = _login(client, "analyst1@example.com")

    user2 = _create_user(client, "analyst2@example.com")
    _set_role(user2["userId"], "analyst")

    asset_id = _seed_asset(user2["userId"])
    analysis_id = _seed_analysis(asset_id, user2["userId"])

    response = client.post(
        f"/api/v1/analyses/{analysis_id}/cancel",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 404
