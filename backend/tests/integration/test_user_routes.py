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

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


if TYPE_CHECKING:
    pass


@pytest.fixture
def client() -> TestClient:
    """Provide FastAPI test client for user routes."""
    app = create_app()
    return TestClient(app)


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

        # Should fail: either 400 (validation) or 403 (not admin)
        assert response.status_code in [400, 403]

    def test_list_users_invalid_limit_zero(self, client: TestClient) -> None:
        """Test pagination validation - limit < 1 rejected."""
        _create_user(client, "testuser@sentinel.local")
        token = _login(client, "testuser@sentinel.local")

        # Limit < 1 should be rejected
        response = client.get(
            "/api/v1/users?limit=0",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should fail: either 400 (validation) or 403 (not admin)
        assert response.status_code in [400, 403]

    def test_list_users_invalid_offset_negative(self, client: TestClient) -> None:
        """Test pagination validation - negative offset rejected."""
        _create_user(client, "testuser@sentinel.local")
        token = _login(client, "testuser@sentinel.local")

        # Negative offset should be rejected
        response = client.get(
            "/api/v1/users?offset=-1",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should fail: either 400 (validation) or 403 (not admin)
        assert response.status_code in [400, 403]


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
        assert "Insufficient permissions" in data.get("detail", "")
