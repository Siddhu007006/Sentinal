"""
Concurrent refresh token rotation test.

Tests that the atomic database-level synchronization prevents race condition
where two concurrent refresh requests against the same token result in exactly
one success (200) and one failure (409), with no duplicate valid replacement
tokens issued.

This test validates E4V.T5-R1 specification for atomic refresh token rotation
in multi-instance SaaS environments.

Key test scenario:
1. User logs in → receives tokens (access_token_1, refresh_token_1)
2. Two concurrent requests both attempt POST /auth/refresh with refresh_token_1
3. Database-level atomic UPDATE ensures:
   - Request A: UPDATE ... SET is_revoked=TRUE WHERE jti=$1 AND is_revoked=FALSE
     → succeeds (1 row updated), receives refresh_token_2
   - Request B: same UPDATE statement → fails (0 rows updated, already revoked)
     → gets 409 Conflict with TokenAlreadyRotatedException
4. Verify: refresh_token_1 is revoked, only refresh_token_2 is valid

Traces to: E4V.T5-R1 Specification § Concurrent Integration Test
Traces to: 08-Security-Architecture §5 (Token lifecycle, atomicity)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app


if TYPE_CHECKING:
    pass


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient for concurrent tests.
    
    Creates a fresh app instance for each test to ensure clean database state.
    Uses ASGITransport for proper async/await support.
    
    Yields:
        AsyncClient: Async HTTP client connected to test app
    """
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


class TestConcurrentTokenRefresh:
    """Tests for concurrent refresh token rotation (atomic synchronization)."""

    @pytest_asyncio.fixture
    async def user_with_refresh_token(
        self, client: AsyncClient
    ) -> dict:
        """Fixture: register user, login, return tokens."""
        # Register
        reg_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "concurrent@sentinel.local",
                "password": "SuperSecureP@ss123",
                "full_name": "Concurrent Test User",
            },
        )
        assert reg_response.status_code == 201

        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "concurrent@sentinel.local",
                "password": "SuperSecureP@ss123",
            },
        )
        assert login_response.status_code == 200
        return login_response.json()

    async def test_concurrent_refresh_exact_one_success(
        self, client: AsyncClient, user_with_refresh_token: dict
    ) -> None:
        """
        Test concurrent refresh requests result in exactly one success.

        Race condition test:
        - Two concurrent POST /auth/refresh requests with same refresh_token
        - One succeeds (200), one fails (409)
        - Both tokens share same JTI (JWT ID) to trigger atomic UPDATE race

        Database-level behavior:
        - Request A: atomic UPDATE token set is_revoked=TRUE where jti=$1 and is_revoked=FALSE
          → succeeds (1 row updated)
        - Request B: same UPDATE → fails (0 rows updated, already revoked by Request A)

        Postconditions:
        - Exactly one request gets HTTP 200 with new tokens
        - Exactly one request gets HTTP 409 Conflict
        - No duplicate valid replacement tokens issued
        """
        old_refresh_token = user_with_refresh_token["refreshToken"]

        # Define concurrent refresh requests
        async def refresh_request() -> dict:
            """Execute single refresh request, return response status and data."""
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": old_refresh_token},
            )
            return {
                "status_code": response.status_code,
                "body": response.json() if response.text else None,
            }

        # Execute two refresh requests concurrently
        # Both use the same old_refresh_token, triggering the race condition
        results = await asyncio.gather(
            refresh_request(),
            refresh_request(),
            return_exceptions=True,
        )

        # Verify no exceptions were raised in either request
        assert len(results) == 2
        assert not isinstance(results[0], Exception), f"Request 0 raised: {results[0]}"
        assert not isinstance(results[1], Exception), f"Request 1 raised: {results[1]}"

        # Separate success and conflict
        success_results = [r for r in results if r["status_code"] == 200]
        conflict_results = [r for r in results if r["status_code"] == 409]

        # Verify: exactly one 200, exactly one 409
        assert len(success_results) == 1, (
            f"Expected exactly 1 success (200), got {len(success_results)}. "
            f"Results: {results}"
        )
        assert len(conflict_results) == 1, (
            f"Expected exactly 1 conflict (409), got {len(conflict_results)}. "
            f"Results: {results}"
        )

        # Extract tokens from successful response
        successful_response = success_results[0]
        assert "body" in successful_response
        assert successful_response["body"] is not None
        assert "accessToken" in successful_response["body"]
        assert "refreshToken" in successful_response["body"]

        new_access_token = successful_response["body"]["accessToken"]
        new_refresh_token = successful_response["body"]["refreshToken"]

        # Verify: new tokens are different from old token
        assert new_refresh_token != old_refresh_token, (
            "Token was not rotated (new token equals old token)"
        )

    async def test_concurrent_refresh_new_tokens_valid(
        self, client: AsyncClient, user_with_refresh_token: dict
    ) -> None:
        """
        Test that the new tokens from successful concurrent refresh are valid.

        After one request succeeds with new tokens:
        - New access token works with /auth/me (valid JWT)
        - New refresh token can be used for next refresh
        - Old refresh token is revoked (cannot be used again)
        """
        old_refresh_token = user_with_refresh_token["refreshToken"]
        old_access_token = user_with_refresh_token["accessToken"]

        async def refresh_request() -> dict:
            """Execute single refresh request."""
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": old_refresh_token},
            )
            return {
                "status_code": response.status_code,
                "body": response.json() if response.text else None,
            }

        # Execute two refresh requests concurrently
        results = await asyncio.gather(
            refresh_request(),
            refresh_request(),
        )

        # Find the successful response
        success_response = next(
            (r for r in results if r["status_code"] == 200), None
        )
        assert success_response is not None, (
            f"No successful response found. Results: {results}"
        )

        new_access_token = success_response["body"]["accessToken"]
        new_refresh_token = success_response["body"]["refreshToken"]

        # Verify new access token works with /auth/me
        me_response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert me_response.status_code == 200, (
            f"New access token invalid. Response: {me_response.json()}"
        )
        me_data = me_response.json()
        assert me_data["email"] == "concurrent@sentinel.local"

        # Verify new refresh token can be used for next refresh
        next_refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": new_refresh_token},
        )
        assert next_refresh_response.status_code == 200, (
            f"New refresh token invalid. Response: {next_refresh_response.json()}"
        )

        # Verify old refresh token is now revoked (trying to use it fails)
        old_refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )
        assert old_refresh_response.status_code in [401, 409], (
            f"Old token should be revoked but got {old_refresh_response.status_code}. "
            f"Response: {old_refresh_response.json()}"
        )

    async def test_concurrent_refresh_multiple_runs(
        self, client: AsyncClient, user_with_refresh_token: dict
    ) -> None:
        """
        Test concurrent refresh atomicity across multiple runs.

        Executes concurrent refresh 5+ times to catch any intermittent race windows
        or timing-dependent failures. Each run should result in exactly one 200 and
        one 409.
        """
        num_runs = 5
        all_results = []

        for run_num in range(num_runs):
            # Get fresh tokens for each run
            login_response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "concurrent@sentinel.local",
                    "password": "SuperSecureP@ss123",
                },
            )
            assert login_response.status_code == 200
            tokens = login_response.json()
            current_refresh_token = tokens["refreshToken"]

            async def refresh_request() -> dict:
                """Execute single refresh request."""
                response = await client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": current_refresh_token},
                )
                return {
                    "status_code": response.status_code,
                    "body": response.json() if response.text else None,
                }

            # Execute two refresh requests concurrently
            results = await asyncio.gather(
                refresh_request(),
                refresh_request(),
            )

            # Record results
            all_results.append(
                {
                    "run": run_num + 1,
                    "success_count": len(
                        [r for r in results if r["status_code"] == 200]
                    ),
                    "conflict_count": len(
                        [r for r in results if r["status_code"] == 409]
                    ),
                    "details": results,
                }
            )

        # Verify all runs had exactly one 200 and one 409
        for result in all_results:
            assert result["success_count"] == 1, (
                f"Run {result['run']}: expected 1 success, got {result['success_count']}. "
                f"Details: {result['details']}"
            )
            assert result["conflict_count"] == 1, (
                f"Run {result['run']}: expected 1 conflict, got {result['conflict_count']}. "
                f"Details: {result['details']}"
            )

