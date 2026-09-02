from __future__ import annotations
from datetime import UTC, datetime
from uuid import uuid4


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.session import get_db_session
from app.main import create_app
from app.models.upload import Upload, UploadStatus
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
    full_name: str = "Test User",
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str, password: str = "SuperSecureP@ss123") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]


class TestUploadRoutes:
    def test_list_uploads_requires_authentication(self, client: TestClient) -> None:
        response = client.get("/api/v1/uploads")
        assert response.status_code == 401

    def test_list_uploads_returns_only_current_users_uploads(
        self, client: TestClient
    ) -> None:
        user_one = _create_user(client, "upload-owner@sentinel.local")
        user_two = _create_user(client, "upload-other@sentinel.local")

        token_one = _login(client, "upload-owner@sentinel.local")
        token_two = _login(client, "upload-other@sentinel.local")

        user_one_id = user_one["userId"]
        user_two_id = user_two["userId"]

        # Seed uploads through the real database session to keep the test focused
        # on the list authorization and scoping logic, not the upload service.
        async def seed_uploads() -> None:
            engine = get_session_engine()
            assert engine is not None
            async with engine.begin() as conn:
                await conn.execute(
                    Upload.__table__.insert(),
                    [
                        {
                            "id": uuid4(),
                            "user_id": user_one_id,
                            "original_filename": "mine.pdf",
                            "storage_key": f"uploads/{uuid4()}/mine.pdf",
                            "content_type": "application/pdf",
                            "file_size_bytes": 42,
                            "upload_status": UploadStatus.PENDING.value,
                            "checksum_sha256": None,
                            "digital_asset_id": None,
                            "idempotency_key": None,
                            "completed_at": None,
                            "updated_at": datetime.now(UTC),
                            "deleted_at": None,
                        },
                        {
                            "id": uuid4(),
                            "user_id": user_two_id,
                            "original_filename": "theirs.pdf",
                            "storage_key": f"uploads/{uuid4()}/theirs.pdf",
                            "content_type": "application/pdf",
                            "file_size_bytes": 84,
                            "upload_status": UploadStatus.PENDING.value,
                            "checksum_sha256": None,
                            "digital_asset_id": None,
                            "idempotency_key": None,
                            "completed_at": None,
                            "updated_at": datetime.now(UTC),
                            "deleted_at": None,
                        },
                    ],
                )

        import asyncio
        asyncio.run(seed_uploads())

        response = client.get(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {token_one}"},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["items"]
        assert all(item["userId"] == user_one_id for item in payload["items"])
        assert not any(item["originalFilename"] == "theirs.pdf" for item in payload["items"])

        other_response = client.get(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {token_two}"},
        )
        assert other_response.status_code == 200
        payload_two = other_response.json()
        assert all(item["userId"] == user_two_id for item in payload_two["items"])
