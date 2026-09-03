from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.session import get_db_session
from app.main import create_app
from app.models.digital_asset import DigitalAsset
from app.models.user import User
from tests.conftest import get_session_engine


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    engine = get_session_engine()
    assert engine is not None

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db_session() -> AsyncSession:
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
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Asset Test User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SuperSecureP@ss123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]


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
    deleted_at: datetime | None = None,
) -> UUID:
    asset_id = asset_id or uuid4()

    async def insert_asset() -> None:
        engine = get_session_engine()
        assert engine is not None
        async with engine.begin() as connection:
            await connection.execute(
                DigitalAsset.__table__.insert(),
                {
                    "id": asset_id,
                    "user_id": UUID(user_id),
                    "asset_type": "domain",
                    "raw_value": normalized_value or "example.com",
                    "normalized_value": normalized_value or "example.com",
                    "display_label": "Test asset",
                    "metadata": {"source": "integration-test"},
                    "is_active": True,
                    "sha256_hash": None,
                    "mime_type": None,
                    "size_bytes": None,
                    "storage_key": None,
                    "deleted_at": deleted_at,
                },
            )

    asyncio.run(insert_asset())
    return asset_id


def _get_asset_deleted_at(asset_id: UUID) -> datetime | None:
    async def fetch_asset() -> datetime | None:
        engine = get_session_engine()
        assert engine is not None
        async with engine.connect() as connection:
            result = await connection.execute(
                select(DigitalAsset.deleted_at).where(DigitalAsset.id == asset_id)
            )
            return result.scalar_one()

    return asyncio.run(fetch_asset())


class TestAssetRoutes:
    def test_asset_routes_require_authentication(self, client: TestClient) -> None:
        asset_id = uuid4()
        assert client.get("/api/v1/assets").status_code == 401
        assert client.get(f"/api/v1/assets/{asset_id}").status_code == 401
        assert client.delete(f"/api/v1/assets/{asset_id}").status_code == 401

    def test_list_assets_returns_active_assets_for_current_user(
        self, client: TestClient
    ) -> None:
        owner = _create_user(client, "asset-owner@sentinel.local")
        other = _create_user(client, "asset-other@sentinel.local")
        token = _login(client, "asset-owner@sentinel.local")
        _seed_asset(owner["userId"], normalized_value="owner.example.com")
        _seed_asset(other["userId"], normalized_value="other.example.com")
        _seed_asset(
            owner["userId"],
            normalized_value="deleted.example.com",
            deleted_at=datetime.now(UTC),
        )

        response = client.get(
            "/api/v1/assets",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["paginationInfo"]["total"] == 1
        assert [item["normalizedValue"] for item in payload["items"]] == [
            "owner.example.com"
        ]

    def test_get_asset_returns_detail_to_owner(self, client: TestClient) -> None:
        user = _create_user(client, "asset-detail-owner@sentinel.local")
        token = _login(client, "asset-detail-owner@sentinel.local")
        asset_id = _seed_asset(user["userId"], normalized_value="detail.example.com")

        response = client.get(
            f"/api/v1/assets/{asset_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["assetId"] == str(asset_id)
        assert response.json()["metadata"] == {"source": "integration-test"}

    def test_get_asset_returns_404_for_non_owner(self, client: TestClient) -> None:
        owner = _create_user(client, "asset-private-owner@sentinel.local")
        _create_user(client, "asset-private-other@sentinel.local")
        token = _login(client, "asset-private-other@sentinel.local")
        asset_id = _seed_asset(owner["userId"], normalized_value="private.example.com")

        response = client.get(
            f"/api/v1/assets/{asset_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_owner_delete_soft_deletes_asset(self, client: TestClient) -> None:
        user = _create_user(client, "asset-delete-owner@sentinel.local")
        token = _login(client, "asset-delete-owner@sentinel.local")
        asset_id = _seed_asset(user["userId"], normalized_value="delete.example.com")

        response = client.delete(
            f"/api/v1/assets/{asset_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 204
        assert _get_asset_deleted_at(asset_id) is not None

    def test_admin_can_delete_another_users_asset(self, client: TestClient) -> None:
        owner = _create_user(client, "asset-admin-owner@sentinel.local")
        admin = _create_user(client, "asset-admin@sentinel.local")
        _set_role(admin["userId"], "admin")
        token = _login(client, "asset-admin@sentinel.local")
        asset_id = _seed_asset(
            owner["userId"], normalized_value="admin-delete.example.com"
        )

        response = client.delete(
            f"/api/v1/assets/{asset_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 204
        assert _get_asset_deleted_at(asset_id) is not None

    def test_non_owner_cannot_delete_asset(self, client: TestClient) -> None:
        owner = _create_user(client, "asset-delete-private-owner@sentinel.local")
        _create_user(client, "asset-delete-private-other@sentinel.local")
        token = _login(client, "asset-delete-private-other@sentinel.local")
        asset_id = _seed_asset(
            owner["userId"], normalized_value="protected.example.com"
        )

        response = client.delete(
            f"/api/v1/assets/{asset_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert _get_asset_deleted_at(asset_id) is None

    def test_deleted_asset_is_absent_from_list_and_detail(
        self, client: TestClient
    ) -> None:
        user = _create_user(client, "asset-deleted-hidden@sentinel.local")
        token = _login(client, "asset-deleted-hidden@sentinel.local")
        asset_id = _seed_asset(
            user["userId"],
            normalized_value="hidden.example.com",
            deleted_at=datetime.now(UTC),
        )

        list_response = client.get(
            "/api/v1/assets",
            headers={"Authorization": f"Bearer {token}"},
        )
        detail_response = client.get(
            f"/api/v1/assets/{asset_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert list_response.status_code == 200
        assert list_response.json()["items"] == []
        assert detail_response.status_code == 404
