from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.dependencies import get_upload_service
from app.domain.entities.upload import Upload as DomainUpload
from app.infrastructure.database.session import get_db_session
from app.main import create_app
from app.models.upload import Upload, UploadStatus
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


def _upload_entity(user_id: str, upload_id: UUID | None = None) -> DomainUpload:
    now = datetime.now(UTC)
    return DomainUpload(
        id=upload_id or uuid4(),
        user_id=UUID(user_id),
        original_filename="report.pdf",
        storage_key="uploads/test/report.pdf",
        content_type="application/pdf",
        file_size_bytes=12,
        upload_status=UploadStatus.COMPLETED.value,
        created_at=now,
        checksum_sha256="a" * 64,
        digital_asset_id=uuid4(),
        completed_at=now,
        updated_at=now,
    )


def _override_upload_service(client: TestClient, upload: DomainUpload) -> AsyncMock:
    service = AsyncMock()
    service.process_upload.return_value = upload
    client.app.dependency_overrides[get_upload_service] = lambda: service
    return service


def _set_user_role(user_id: str, role: str) -> None:
    async def update_role() -> None:
        engine = get_session_engine()
        assert engine is not None
        async with engine.begin() as conn:
            await conn.execute(
                update(User).where(User.id == UUID(user_id)).values(role=role)
            )

    import asyncio

    asyncio.run(update_role())


class TestUploadRoutes:
    def test_create_upload_returns_upload(self, client: TestClient) -> None:
        user = _create_user(client, "upload-analyst@sentinel.local")
        _set_user_role(user["userId"], "analyst")
        token = _login(client, "upload-analyst@sentinel.local")
        upload = _upload_entity(user["userId"])
        service = _override_upload_service(client, upload)

        response = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("report.pdf", b"%PDF-1.7 test", "application/pdf")},
        )

        assert response.status_code == 201, response.text
        assert response.json()["uploadId"] == str(upload.id)
        service.process_upload.assert_awaited_once()

    def test_create_upload_requires_authentication(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("report.pdf", b"%PDF-1.7 test", "application/pdf")},
        )

        assert response.status_code == 401

    def test_create_upload_rejects_viewer(self, client: TestClient) -> None:
        _create_user(client, "upload-viewer@sentinel.local")
        token = _login(client, "upload-viewer@sentinel.local")

        response = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("report.pdf", b"%PDF-1.7 test", "application/pdf")},
        )

        assert response.status_code == 403

    def test_create_upload_replays_idempotent_request(
        self, client: TestClient
    ) -> None:
        user = _create_user(client, "upload-idempotent@sentinel.local")
        _set_user_role(user["userId"], "analyst")
        token = _login(client, "upload-idempotent@sentinel.local")
        upload = _upload_entity(user["userId"])
        service = _override_upload_service(client, upload)
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "upload-retry-001",
        }
        file_data = {"file": ("report.pdf", b"%PDF-1.7 test", "application/pdf")}

        first_response = client.post(
            "/api/v1/uploads", headers=headers, files=file_data
        )
        second_response = client.post(
            "/api/v1/uploads", headers=headers, files=file_data
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 201
        assert second_response.json() == first_response.json()
        assert service.process_upload.await_count == 2
        assert all(
            call.kwargs["idempotency_key"] == "upload-retry-001"
            for call in service.process_upload.await_args_list
        )

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
        assert not any(
            item["originalFilename"] == "theirs.pdf" for item in payload["items"]
        )

        other_response = client.get(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {token_two}"},
        )
        assert other_response.status_code == 200
        payload_two = other_response.json()
        assert all(item["userId"] == user_two_id for item in payload_two["items"])

    def test_get_upload_allows_owner(self, client: TestClient) -> None:
        user = _create_user(client, "upload-detail-owner@sentinel.local")
        token = _login(client, "upload-detail-owner@sentinel.local")
        upload_id = uuid4()

        async def seed_upload() -> None:
            engine = get_session_engine()
            assert engine is not None
            async with engine.begin() as conn:
                await conn.execute(
                    Upload.__table__.insert(),
                    {
                        "id": upload_id,
                        "user_id": UUID(user["userId"]),
                        "original_filename": "owned.pdf",
                        "storage_key": f"uploads/{upload_id}/owned.pdf",
                        "content_type": "application/pdf",
                        "file_size_bytes": 42,
                        "upload_status": UploadStatus.PENDING.value,
                        "checksum_sha256": None,
                        "digital_asset_id": None,
                        "idempotency_key": None,
                        "completed_at": None,
                        "updated_at": datetime.now(UTC),
                    },
                )

        import asyncio

        asyncio.run(seed_upload())
        response = client.get(
            f"/api/v1/uploads/{upload_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["uploadId"] == str(upload_id)
        assert response.json()["originalFilename"] == "owned.pdf"

    def test_get_upload_returns_404_for_non_owner(self, client: TestClient) -> None:
        owner = _create_user(client, "upload-detail-owner-2@sentinel.local")
        other = _create_user(client, "upload-detail-other@sentinel.local")
        token = _login(client, "upload-detail-other@sentinel.local")
        upload_id = uuid4()

        async def seed_upload() -> None:
            engine = get_session_engine()
            assert engine is not None
            async with engine.begin() as conn:
                await conn.execute(
                    Upload.__table__.insert(),
                    {
                        "id": upload_id,
                        "user_id": UUID(owner["userId"]),
                        "original_filename": "private.pdf",
                        "storage_key": f"uploads/{upload_id}/private.pdf",
                        "content_type": "application/pdf",
                        "file_size_bytes": 42,
                        "upload_status": UploadStatus.PENDING.value,
                        "checksum_sha256": None,
                        "digital_asset_id": None,
                        "idempotency_key": None,
                        "completed_at": None,
                        "updated_at": datetime.now(UTC),
                    },
                )

        import asyncio

        asyncio.run(seed_upload())
        response = client.get(
            f"/api/v1/uploads/{upload_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert other["userId"] != owner["userId"]
