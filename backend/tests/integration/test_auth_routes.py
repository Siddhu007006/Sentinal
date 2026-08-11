"""
Integration tests for authentication routes.

Tests auth endpoints via AsyncClient:
- POST /auth/register (user creation)
- POST /auth/login (authentication)
- POST /auth/refresh (token refresh)
- POST /auth/logout (session revocation)
- GET /auth/me (authenticated profile)

Validates: Requirement 6 (Auth Route Handlers) in requirements.md
Traces to: design.md § Auth Flows
Traces to: 07-Backend-Development-Standards §4 (route handlers)

Async Architecture:
- Uses httpx.AsyncClient for async HTTP testing
- Integrated with pytest-asyncio for proper event loop management
- All test methods are async functions with await calls
- Proper database isolation via async_engine fixture
- Cross-platform compatible (Windows, Linux, CI)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app


if TYPE_CHECKING:
    pass


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient for auth routes integration tests.
    
    Creates a fresh app instance and AsyncClient for each test.
    Uses async context manager for proper lifespan management.
    ASGITransport bridges the gap between AsyncClient and FastAPI app.
    
    The client fixture properly manages the FastAPI lifespan, ensuring
    startup and shutdown events are triggered within the test's event loop.
    All database access happens through the app's dependency injection,
    ensuring the same event loop is used throughout.
    
    Yields:
        AsyncClient: Async HTTP client connected to test app
    """
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


class TestAuthRegister:
    """Tests for POST /auth/register endpoint."""

    async def test_register_success(self, client: AsyncClient) -> None:
        """Test successful user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@sentinel.local",
                "password": "SuperSecureP@ss123",
                "full_name": "New User",
            },
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@sentinel.local"
        assert data["fullName"] == "New User"
        assert data["role"] == "viewer"
        assert "userId" in data
        assert "createdAt" in data
        # Ensure password is NOT in response
        assert "passwordHash" not in data
        assert "password" not in data

    async def test_register_duplicate_email(self, client: AsyncClient) -> None:
        """Test registration fails with duplicate email."""
        # Create first user
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "alice@sentinel.local",
                "password": "SuperSecureP@ss123",
                "full_name": "Alice",
            },
        )

        # Try to create second user with same email
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "alice@sentinel.local",
                "password": "DifferentP@ss456",
                "full_name": "Alice 2",
            },
        )

        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "conflict"

    async def test_register_weak_password(self, client: AsyncClient) -> None:
        """Test registration fails with weak password (< 12 chars)."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@sentinel.local",
                "password": "Short1!",  # Only 7 characters
                "full_name": "Weak Pass",
            },
        )

        # Pydantic validation happens first, returns 422 for schema errors
        # Password validation happens at schema level, so this gets 422
        assert response.status_code == 422
        data = response.json()
        assert "validation_error" in data["error"]["code"]

    async def test_register_invalid_email(self, client: AsyncClient) -> None:
        """Test registration fails with invalid email format."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SuperSecureP@ss123",
                "full_name": "Bad Email",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "validation" in data["error"]["code"]

    async def test_register_missing_email(self, client: AsyncClient) -> None:
        """Test registration fails when email is missing."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "password": "SuperSecureP@ss123",
                "full_name": "No Email",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "validation_error" in data["error"]["code"]

    async def test_register_optional_full_name(self, client: AsyncClient) -> None:
        """Test registration succeeds without full_name."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "noname@sentinel.local",
                "password": "SuperSecureP@ss123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "noname@sentinel.local"
        assert data["fullName"] is None


class TestAuthLogin:
    """Tests for POST /auth/login endpoint."""

    @pytest_asyncio.fixture
    async def registered_user(self, client: AsyncClient) -> dict:
        """Fixture: register a test user."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "testuser@sentinel.local",
                "password": "SuperSecureP@ss123",
                "full_name": "Test User",
            },
        )
        assert response.status_code == 201
        return response.json()

    async def test_login_success(
        self, client: AsyncClient, registered_user: dict
    ) -> None:
        """Test successful login returns tokens."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "testuser@sentinel.local",
                "password": "SuperSecureP@ss123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        assert len(data["accessToken"]) > 0
        assert len(data["refreshToken"]) > 0

    async def test_login_wrong_password(
        self, client: AsyncClient, registered_user: dict
    ) -> None:
        """Test login fails with wrong password."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "testuser@sentinel.local",
                "password": "WrongPassword123",
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert "unauthorized" in data["error"]["code"]

    async def test_login_user_not_found(self, client: AsyncClient) -> None:
        """Test login fails when user doesn't exist."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@sentinel.local",
                "password": "AnyPassword123",
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert "unauthorized" in data["error"]["code"]
        # Should not reveal whether user exists
        # Check that if detail exists, it doesn't contain "not found"
        if "detail" in data["error"]:
            assert "not found" not in data["error"]["detail"].lower()

    async def test_login_missing_credentials(self, client: AsyncClient) -> None:
        """Test login fails when credentials are missing."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "testuser@sentinel.local",
            },
        )

        assert response.status_code == 422


class TestAuthRefresh:
    """Tests for POST /auth/refresh endpoint."""

    @pytest_asyncio.fixture
    async def login_tokens(self, client: AsyncClient) -> dict:
        """Fixture: register and login a user to get tokens."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@sentinel.local",
                "password": "SuperSecureP@ss123",
                "full_name": "Refresh Test",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "refresh@sentinel.local",
                "password": "SuperSecureP@ss123",
            },
        )
        assert response.status_code == 200
        return response.json()

    async def test_refresh_success(
        self, client: AsyncClient, login_tokens: dict
    ) -> None:
        """Test token refresh returns new token pair."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login_tokens["refreshToken"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        # New tokens should be different from old ones (token rotation)
        assert data["accessToken"] != login_tokens["accessToken"]
        assert data["refreshToken"] != login_tokens["refreshToken"]

    async def test_refresh_invalid_token(self, client: AsyncClient) -> None:
        """Test refresh fails with invalid token."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "unauthorized" in data["error"]["code"]

    async def test_refresh_missing_token(self, client: AsyncClient) -> None:
        """Test refresh fails when refresh_token is missing."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={},
        )

        assert response.status_code == 422


class TestAuthLogout:
    """Tests for POST /auth/logout endpoint."""

    @pytest_asyncio.fixture
    async def login_with_token(self, client: AsyncClient) -> dict:
        """Fixture: register, login, return access token and refresh token."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "logout@sentinel.local",
                "password": "SuperSecureP@ss123",
                "full_name": "Logout Test",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "logout@sentinel.local",
                "password": "SuperSecureP@ss123",
            },
        )
        assert response.status_code == 200
        return response.json()

    async def test_logout_device_specific(
        self, client: AsyncClient, login_with_token: dict
    ) -> None:
        """Test logout with specific refresh token."""
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {login_with_token['accessToken']}"},
            json={"refresh_token": login_with_token["refreshToken"]},
        )

        assert response.status_code == 204
        # 204 No Content should have empty body
        assert response.text == ""

    async def test_logout_missing_auth_header(self, client: AsyncClient) -> None:
        """Test logout fails without authentication."""
        response = await client.post(
            "/api/v1/auth/logout",
            json={},
        )

        assert response.status_code == 401
        data = response.json()
        assert "unauthorized" in data["error"]["code"]

    async def test_logout_invalid_token(self, client: AsyncClient) -> None:
        """Test logout fails with invalid access token."""
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer invalid.token.here"},
            json={},
        )

        assert response.status_code == 401


class TestAuthMe:
    """Tests for GET /auth/me endpoint."""

    @pytest_asyncio.fixture
    async def authenticated_user(self, client: AsyncClient) -> dict:
        """Fixture: register and login a user, return user data and token."""
        reg_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "me@sentinel.local",
                "password": "SuperSecureP@ss123",
                "full_name": "Me Test",
            },
        )
        assert reg_response.status_code == 201

        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "me@sentinel.local",
                "password": "SuperSecureP@ss123",
            },
        )
        assert login_response.status_code == 200

        return {
            "user": reg_response.json(),
            "tokens": login_response.json(),
        }

    async def test_get_me_success(
        self, client: AsyncClient, authenticated_user: dict
    ) -> None:
        """Test /auth/me returns authenticated user's profile."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {authenticated_user['tokens']['accessToken']}"
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@sentinel.local"
        assert data["fullName"] == "Me Test"
        assert data["role"] == "viewer"
        assert data["userId"] == authenticated_user["user"]["userId"]
        # Ensure password is NOT in response
        assert "passwordHash" not in data
        assert "password" not in data

    async def test_get_me_missing_token(self, client: AsyncClient) -> None:
        """Test /auth/me fails without authentication."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401
        data = response.json()
        assert "unauthorized" in data["error"]["code"]

    async def test_get_me_invalid_token(self, client: AsyncClient) -> None:
        """Test /auth/me fails with invalid token."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "unauthorized" in data["error"]["code"]
