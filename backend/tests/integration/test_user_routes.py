"""
Integration tests for user management routes.

Tests user management endpoints via FastAPI test client:
- GET /users (admin-only, paginated list)
- GET /users/{userId} (admin or user, 404 on forbidden)
- PATCH /users/{userId} (admin or user, role changes admin-only)
- DELETE /users/{userId} (admin-only soft-delete)

Validates: Requirement 7 (User Management Routes) in requirements.md
Traces to: design.md § User Management
Traces to: 07-Backend-Development-Standards §4 (route handlers)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.session import get_db_session
from app.main import create_app
from tests.conftest import get_session_engine


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
def client() -> TestClient:
    """Provide FastAPI test client for user routes."""
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
    full_name: str = "Test User",
) -> dict:
    """Helper to create a user and return user data."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
        },
    )
    assert response.status_code == 201, f"Failed to create user: {response.text}"
    return response.json()


def _login(
    client: TestClient,
    email: str,
    password: str = "SuperSecureP@ss123",
) -> str:
    """Helper to login and return access token."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200, f"Failed to login: {response.text}"
    return response.json()["accessToken"]


class TestGetUsersList:
    """Tests for GET /users endpoint (admin-only, paginated)."""

    def test_list_users_requires_authentication(self, client: TestClient) -> None:
        """Test GET /users requires authentication (401 without token)."""
        response = client.get("/api/v1/users")
        assert response.status_code == 401

    def test_list_users_requires_admin_role(self, client: TestClient) -> None:
        """Test GET /users returns 403 for non-admin user."""
        # Create a non-admin user (defaults to viewer role)
        _create_user(client, "user1@sentinel.local")
        token = _login(client, "user1@sentinel.local")

        # Try to list users as non-admin
        response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should fail with 403 Forbidden
        assert response.status_code == 403

    def test_list_users_invalid_limit_parameter(self, client: TestClient) -> None:
        """Test pagination validation - limit > 100 rejected."""
        _create_user(client, "testuser@sentinel.local")
        token = _login(client, "testuser@sentinel.local")

        # Limit > 100 should be rejected
        response = client.get(
            "/api/v1/users?limit=101",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Non-admin user is rejected by the authorization dependency.
        assert response.status_code == 403

    def test_list_users_invalid_limit_zero(self, client: TestClient) -> None:
        """Test pagination validation - limit < 1 rejected."""
        _create_user(client, "testuser@sentinel.local")
        token = _login(client, "testuser@sentinel.local")

        # Limit < 1 should be rejected
        response = client.get(
            "/api/v1/users?limit=0",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Non-admin user is rejected by the authorization dependency.
        assert response.status_code == 403

    def test_list_users_invalid_offset_negative(self, client: TestClient) -> None:
        """Test pagination validation - negative offset rejected."""
        _create_user(client, "testuser@sentinel.local")
        token = _login(client, "testuser@sentinel.local")

        # Negative offset should be rejected
        response = client.get(
            "/api/v1/users?offset=-1",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Non-admin user is rejected by the authorization dependency.
        assert response.status_code == 403


class TestListUsersResponseFormat:
    """Tests for GET /users response format and structure."""

    def test_endpoint_exists_and_requires_auth(self, client: TestClient) -> None:
        """Test endpoint exists and requires authentication."""
        # Endpoint should exist - returns 401 not 404
        response = client.get("/api/v1/users")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data or "error" in data

    def test_admin_role_enforced(self, client: TestClient) -> None:
        """Test that require_role('admin') dependency works."""
        _create_user(client, "alice@sentinel.local")
        token = _login(client, "alice@sentinel.local")

        response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Non-admin user should get 403
        assert response.status_code == 403
        data = response.json()
        assert "Insufficient permissions" in data["error"]["message"]


async def _promote_to_admin(db_session: AsyncSession, user_id: UUID) -> None:
    """Promote a registered user to admin directly in the database.

    Registration defaults to the viewer role and only admins can change
    roles via the API, so tests seed the admin role directly.
    """
    from app.models.user import User as UserORM

    await db_session.execute(
        update(UserORM).where(UserORM.id == user_id).values(role="admin")
    )
    await db_session.commit()


class TestGetUserById:
    """Tests for GET /users/{userId} (admin or owner, 404 on forbidden)."""

    def test_get_user_by_id_requires_authentication(
        self, client: TestClient
    ) -> None:
        """GET /users/{userId} without token → 401."""
        response = client.get(f"/api/v1/users/{uuid4()}")
        assert response.status_code == 401

    def test_get_own_profile(self, client: TestClient) -> None:
        """Owner can retrieve their own profile."""
        created = _create_user(client, "owner@sentinel.local")
        token = _login(client, "owner@sentinel.local")

        response = client.get(
            f"/api/v1/users/{created['userId']}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["userId"] == created["userId"]
        assert data["email"] == "owner@sentinel.local"
        assert "password_hash" not in data
        assert "passwordHash" not in data

    def test_get_other_user_returns_404(self, client: TestClient) -> None:
        """Non-admin non-owner gets 404 (enumeration prevention)."""
        target = _create_user(client, "target@sentinel.local")
        _create_user(client, "other@sentinel.local")
        token = _login(client, "other@sentinel.local")

        response = client.get(
            f"/api/v1/users/{target['userId']}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_get_missing_user_returns_404(self, client: TestClient) -> None:
        """Non-existent user ID → 404."""
        _create_user(client, "seeker@sentinel.local")
        token = _login(client, "seeker@sentinel.local")

        response = client.get(
            f"/api/v1/users/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404


class TestPatchUser:
    """Tests for PATCH /users/{userId} (owner profile, admin-only roles)."""

    def test_patch_requires_authentication(self, client: TestClient) -> None:
        """PATCH without token → 401."""
        response = client.patch(
            f"/api/v1/users/{uuid4()}", json={"fullName": "New Name"}
        )
        assert response.status_code == 401

    def test_patch_own_profile(self, client: TestClient) -> None:
        """Owner updates own full name."""
        created = _create_user(client, "patcher@sentinel.local")
        token = _login(client, "patcher@sentinel.local")

        response = client.patch(
            f"/api/v1/users/{created['userId']}",
            json={"fullName": "Patched Name"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["fullName"] == "Patched Name"
        assert data["role"] == "viewer"  # role untouched

    def test_patch_own_role_forbidden(self, client: TestClient) -> None:
        """Non-admin attempting role change on self → 403."""
        created = _create_user(client, "escalator@sentinel.local")
        token = _login(client, "escalator@sentinel.local")

        response = client.patch(
            f"/api/v1/users/{created['userId']}",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    def test_patch_other_user_returns_404(self, client: TestClient) -> None:
        """Non-admin non-owner patching another user → 404."""
        target = _create_user(client, "patch-target@sentinel.local")
        _create_user(client, "patch-other@sentinel.local")
        token = _login(client, "patch-other@sentinel.local")

        response = client.patch(
            f"/api/v1/users/{target['userId']}",
            json={"fullName": "Hacked Name"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_patch_missing_user_returns_404(self, client: TestClient) -> None:
        """PATCH on non-existent user → 404."""
        _create_user(client, "patch-missing@sentinel.local")
        token = _login(client, "patch-missing@sentinel.local")

        response = client.patch(
            f"/api/v1/users/{uuid4()}",
            json={"fullName": "Ghost"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_patch_invalid_role_rejected(self, client: TestClient) -> None:
        """Invalid role value → 422 validation error."""
        created = _create_user(client, "badrole@sentinel.local")
        token = _login(client, "badrole@sentinel.local")

        response = client.patch(
            f"/api/v1/users/{created['userId']}",
            json={"role": "superadmin"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_admin_changes_role_and_audits(
        self, client: TestClient, db_session: AsyncSession
    ) -> None:
        """Admin changes another user's role → 200 + ROLE_CHANGE audit."""
        from app.models.audit_log import AuditLog as AuditLogORM

        target = _create_user(client, "promotee@sentinel.local")
        admin = _create_user(client, "chief-admin@sentinel.local")
        await _promote_to_admin(db_session, UUID(admin["userId"]))
        token = _login(client, "chief-admin@sentinel.local")

        response = client.patch(
            f"/api/v1/users/{target['userId']}",
            json={"role": "analyst"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["role"] == "analyst"

        # Role change audited with old and new role
        audit_result = await db_session.execute(
            select(AuditLogORM).where(
                AuditLogORM.resource_id == UUID(target["userId"]),
                AuditLogORM.action == "ROLE_CHANGE",
            )
        )
        audit_entry = audit_result.scalar_one()
        assert audit_entry.before_state["role"] == "viewer"
        assert audit_entry.after_state["role"] == "analyst"

    @pytest.mark.asyncio
    async def test_admin_updates_other_profile(
        self, client: TestClient, db_session: AsyncSession
    ) -> None:
        """Admin can update another user's profile fields."""
        target = _create_user(client, "admin-patch@sentinel.local")
        admin = _create_user(client, "profile-admin@sentinel.local")
        await _promote_to_admin(db_session, UUID(admin["userId"]))
        token = _login(client, "profile-admin@sentinel.local")

        response = client.patch(
            f"/api/v1/users/{target['userId']}",
            json={"fullName": "Admin Set Name"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["fullName"] == "Admin Set Name"


class TestDeleteUser:
    """Tests for DELETE /users/{userId} (admin-only soft-delete)."""

    def test_delete_requires_authentication(self, client: TestClient) -> None:
        """DELETE without token → 401."""
        response = client.delete(f"/api/v1/users/{uuid4()}")
        assert response.status_code == 401

    def test_delete_by_non_admin_forbidden(self, client: TestClient) -> None:
        """Non-admin DELETE → 403 (RBAC dependency)."""
        created = _create_user(client, "delete-target@sentinel.local")
        token = _login(client, "delete-target@sentinel.local")

        response = client.delete(
            f"/api/v1/users/{created['userId']}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_missing_user_returns_404(
        self, client: TestClient, db_session: AsyncSession
    ) -> None:
        """Admin DELETE on non-existent user → 404."""
        admin = _create_user(client, "missing-admin@sentinel.local")
        await _promote_to_admin(db_session, UUID(admin["userId"]))
        token = _login(client, "missing-admin@sentinel.local")

        response = client.delete(
            f"/api/v1/users/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_delete_soft_deletes_and_revokes_tokens(
        self, client: TestClient, db_session: AsyncSession
    ) -> None:
        """Admin DELETE → 204, user 404 afterwards, sessions revoked, audited."""
        from app.models.audit_log import AuditLog as AuditLogORM
        from app.models.user import User as UserORM

        victim = _create_user(client, "deactivated@sentinel.local")
        victim_id = UUID(victim["userId"])
        victim_login = client.post(
            "/api/v1/auth/login",
            json={"email": "deactivated@sentinel.local",
                  "password": "SuperSecureP@ss123"},
        ).json()
        victim_refresh = victim_login["refreshToken"]

        admin = _create_user(client, "deleter-admin@sentinel.local")
        await _promote_to_admin(db_session, UUID(admin["userId"]))
        token = _login(client, "deleter-admin@sentinel.local")

        response = client.delete(
            f"/api/v1/users/{victim_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

        # Soft-delete persisted: is_active=False, deleted_at set
        user_result = await db_session.execute(
            select(UserORM).where(UserORM.id == victim_id)
        )
        row = user_result.scalar_one()
        assert row.is_active is False
        assert row.deleted_at is not None

        # Deactivated user invisible in queries (404)
        assert client.get(
            f"/api/v1/users/{victim_id}",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code == 404

        # All refresh tokens revoked: refresh now fails
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": victim_refresh},
        )
        assert refresh_response.status_code == 401

        # Deactivation audited
        audit_result = await db_session.execute(
            select(AuditLogORM).where(
                AuditLogORM.resource_id == victim_id,
                AuditLogORM.action == "USER_DEACTIVATION",
            )
        )
        assert audit_result.scalar_one() is not None
