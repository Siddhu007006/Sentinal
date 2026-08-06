"""
Integration tests for RefreshToken ORM model and database constraints.

Tests model operations with a real PostgreSQL database, verifying that
constraints, foreign keys, and indexes work correctly. These tests require
a running database instance.

**Validates: Requirement R5 (ORM Model Test Coverage) — Part 2 (Integration Tests)**

Traces to: 22-Engineering-Backlog E3.T9 (Refresh Tokens ORM Model and Migration task)
Traces to: 07-Backend-Development-Standards §8 (ORM model conventions)
Traces to: 11-Testing-Strategy §6 (integration test patterns)
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken, User


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user for refresh token tests."""
    user = User(
        email="refresh_token_test@example.com",
        password_hash="$2b$12$test_hash_for_refresh_token_tests",  # noqa: S106
        full_name="RefreshToken Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def another_test_user(db_session: AsyncSession) -> User:
    """Create another test user for multi-user tests."""
    user = User(
        email="another_refresh_test@example.com",
        password_hash="$2b$12$another_hash_for_refresh_tests",  # noqa: S106
        full_name="Another RefreshToken Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ===========================================================================
# Test 1: Insert Valid Token
# ===========================================================================


@pytest.mark.asyncio
async def test_insert_valid_refresh_token(
    db_session: AsyncSession, test_user: User
) -> None:
    """Test: Insert valid RefreshToken record succeeds.

    **Validates: R5 AC #6**

    Verifies that a valid token can be inserted to the database.
    """
    token = RefreshToken(
        user_id=test_user.id,
        token_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(token)
    await db_session.commit()

    # Verify record inserted
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.id == token.id)
    )
    retrieved_token = result.scalar_one_or_none()

    assert retrieved_token is not None
    assert retrieved_token.id == token.id
    assert retrieved_token.user_id == test_user.id
    assert retrieved_token.token_hash == "a" * 64
    assert retrieved_token.is_revoked is False


# ===========================================================================
# Test 2: Unique Constraint on token_hash
# ===========================================================================


@pytest.mark.asyncio
async def test_duplicate_token_hash_raises_integrity_error(
    db_session: AsyncSession, test_user: User, another_test_user: User
) -> None:
    """Test: Insert duplicate token_hash raises unique constraint error.

    **Validates: R2 AC #1, R5 AC #7**

    Verifies that the unique constraint on token_hash is enforced.
    """
    # Insert first token
    token1 = RefreshToken(
        user_id=test_user.id,
        token_hash="b" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(token1)
    await db_session.commit()

    # Try to insert duplicate hash for different user (should fail)
    token2 = RefreshToken(
        user_id=another_test_user.id,
        token_hash="b" * 64,  # Duplicate!
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(token2)

    with pytest.raises(IntegrityError):
        await db_session.commit()


# ===========================================================================
# Test 3: Cascade Deletion on User Delete
# ===========================================================================


@pytest.mark.asyncio
async def test_user_deletion_cascades_to_tokens(db_session: AsyncSession) -> None:
    """Test: Deleting user cascades to delete their refresh tokens.

    **Validates: R2 AC #3, R5 AC #8**

    Verifies that ON DELETE CASCADE removes tokens when user is deleted.
    """
    # Create user
    user = User(
        email="cascade_test@example.com",
        password_hash="$2b$12$cascade_test_hash",  # noqa: S106
        full_name="Cascade Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id

    # Create tokens
    token1 = RefreshToken(
        user_id=user_id,
        token_hash="c" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    token2 = RefreshToken(
        user_id=user_id,
        token_hash="d" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add_all([token1, token2])
    await db_session.commit()

    token_ids = [token1.id, token2.id]

    # Delete user
    await db_session.delete(user)
    await db_session.commit()

    # Verify tokens deleted
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.id.in_(token_ids))
    )
    remaining_tokens = result.scalars().all()

    assert remaining_tokens == []


# ===========================================================================
# Test 4: Query Tokens by user_id
# ===========================================================================


@pytest.mark.asyncio
async def test_query_tokens_by_user_id(
    db_session: AsyncSession, test_user: User
) -> None:
    """Test: Query all tokens for a user succeeds.

    **Validates: R2 AC #6, R5 AC #9**

    Verifies that the user_id index enables efficient session listing.
    """
    # Create multiple tokens
    token1 = RefreshToken(
        user_id=test_user.id,
        token_hash="e" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    token2 = RefreshToken(
        user_id=test_user.id,
        token_hash="f" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add_all([token1, token2])
    await db_session.commit()

    # Query by user_id
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.user_id == test_user.id)
    )
    tokens = result.scalars().all()

    assert len(tokens) == 2
    assert token1 in tokens
    assert token2 in tokens


# ===========================================================================
# Test 5: Revoke Token
# ===========================================================================


@pytest.mark.asyncio
async def test_revoke_token(db_session: AsyncSession, test_user: User) -> None:
    """Test: Update token to set is_revoked=True and revoked_at succeeds.

    **Validates: R5 AC #10**

    Verifies that revocation fields can be updated.
    """
    # Create token
    token = RefreshToken(
        user_id=test_user.id,
        token_hash="g" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(token)
    await db_session.commit()

    token_id = token.id

    # Revoke token
    token.is_revoked = True
    token.revoked_at = datetime.now(UTC)
    await db_session.commit()

    # Verify revocation
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.id == token_id)
    )
    revoked_token = result.scalar_one()

    assert revoked_token.is_revoked is True
    assert revoked_token.revoked_at is not None


# ===========================================================================
# Test 6: Query Active Tokens
# ===========================================================================


@pytest.mark.asyncio
async def test_query_active_tokens(db_session: AsyncSession, test_user: User) -> None:
    """Test: Query active tokens (WHERE is_revoked=False) succeeds.

    **Validates: R5 AC #11**

    Verifies that filtering by revocation status works correctly.
    """
    # Create active token
    active = RefreshToken(
        user_id=test_user.id,
        token_hash="h" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        is_revoked=False,
    )

    # Create revoked token
    revoked = RefreshToken(
        user_id=test_user.id,
        token_hash="i" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        is_revoked=True,
        revoked_at=datetime.now(UTC),
    )

    db_session.add_all([active, revoked])
    await db_session.commit()

    # Query active tokens
    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == test_user.id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
    )
    tokens = result.scalars().all()

    assert len(tokens) == 1
    assert tokens[0].id == active.id
    assert tokens[0].is_revoked is False


# ===========================================================================
# Test 7: Standard Validation Query
# ===========================================================================


@pytest.mark.asyncio
async def test_validation_query_pattern(
    db_session: AsyncSession, test_user: User
) -> None:
    """Test: Standard validation query works correctly.

    **Validates: R2 AC #2, R5 AC #12**

    Verifies the standard query pattern used for token validation:
    - token_hash = X
    - is_revoked = false
    - expires_at > now()
    """
    now_utc = datetime.now(UTC)

    # Valid token
    valid = RefreshToken(
        user_id=test_user.id,
        token_hash="j" * 64,
        expires_at=now_utc + timedelta(days=30),
        is_revoked=False,
    )

    # Expired token
    expired = RefreshToken(
        user_id=test_user.id,
        token_hash="k" * 64,
        expires_at=now_utc - timedelta(days=1),  # Past
        is_revoked=False,
    )

    # Revoked token
    revoked = RefreshToken(
        user_id=test_user.id,
        token_hash="l" * 64,
        expires_at=now_utc + timedelta(days=30),
        is_revoked=True,
    )

    db_session.add_all([valid, expired, revoked])
    await db_session.commit()

    # Validation query (should find valid token only)
    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == "j" * 64,
            RefreshToken.is_revoked == False,  # noqa: E712
            RefreshToken.expires_at > now_utc,
        )
    )
    token = result.scalar_one_or_none()

    assert token is not None
    assert token.id == valid.id

    # Same query with expired hash should return None
    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == "k" * 64,
            RefreshToken.is_revoked == False,  # noqa: E712
            RefreshToken.expires_at > now_utc,
        )
    )
    assert result.scalar_one_or_none() is None

    # Same query with revoked hash should return None
    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == "l" * 64,
            RefreshToken.is_revoked == False,  # noqa: E712
            RefreshToken.expires_at > now_utc,
        )
    )
    assert result.scalar_one_or_none() is None


# ===========================================================================
# Test 8: Query Expired Tokens (Cleanup Pattern)
# ===========================================================================


@pytest.mark.asyncio
async def test_query_expired_tokens(
    db_session: AsyncSession, test_user: User
) -> None:
    """Test: Query expired, non-revoked tokens for cleanup.

    **Validates: R2 AC #7**

    Verifies the query pattern used by cleanup jobs to find tokens to delete:
    - is_revoked = false
    - expires_at < now()
    """
    now_utc = datetime.now(UTC)

    # Expired, not revoked (should be cleaned up)
    expired_active = RefreshToken(
        user_id=test_user.id,
        token_hash="m" * 64,
        expires_at=now_utc - timedelta(days=1),
        is_revoked=False,
    )

    # Active, not expired (should NOT be cleaned up)
    valid = RefreshToken(
        user_id=test_user.id,
        token_hash="n" * 64,
        expires_at=now_utc + timedelta(days=30),
        is_revoked=False,
    )

    # Expired but revoked (should NOT be cleaned up by this query)
    expired_revoked = RefreshToken(
        user_id=test_user.id,
        token_hash="o" * 64,
        expires_at=now_utc - timedelta(days=1),
        is_revoked=True,
    )

    db_session.add_all([expired_active, valid, expired_revoked])
    await db_session.commit()

    # Cleanup query (find expired, non-revoked tokens)
    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.is_revoked == False,  # noqa: E712
            RefreshToken.expires_at < now_utc,
        )
    )
    cleanup_tokens = result.scalars().all()

    # Should find only the expired, active token
    assert len(cleanup_tokens) == 1
    assert cleanup_tokens[0].id == expired_active.id


# ===========================================================================
# Test 9: Foreign Key Constraint on user_id
# ===========================================================================


@pytest.mark.asyncio
async def test_foreign_key_constraint_user_id(db_session: AsyncSession) -> None:
    """Test: Foreign key constraint on user_id is enforced.

    **Validates: R2 AC #3**

    Verifies that inserting token with non-existent user_id fails.
    """
    # Non-existent user_id
    fake_user_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    token = RefreshToken(
        user_id=fake_user_id,
        token_hash="p" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(token)

    with pytest.raises(IntegrityError):
        await db_session.commit()


# ===========================================================================
# Test 10: NOT NULL Constraints
# ===========================================================================


@pytest.mark.asyncio
async def test_not_null_constraints(db_session: AsyncSession) -> None:
    """Test: NOT NULL constraints are enforced.

    **Validates: R2 AC #2**

    Verifies that required fields cannot be null.
    """
    # Missing user_id
    token = RefreshToken(
        user_id=None,  # type: ignore[arg-type]
        token_hash="q" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(token)

    with pytest.raises((IntegrityError, ValueError)):
        await db_session.commit()


# ===========================================================================
# Test 11: Multiple Tokens per User
# ===========================================================================


@pytest.mark.asyncio
async def test_multiple_tokens_per_user(
    db_session: AsyncSession, test_user: User
) -> None:
    """Test: Multiple tokens can belong to same user.

    **Validates: R5 AC #9**

    Verifies that a user can have multiple refresh tokens (per-device sessions).
    """
    now = datetime.now(UTC)

    # Create multiple tokens for same user
    tokens = [
        RefreshToken(
            user_id=test_user.id,
            token_hash=chr(97 + i) * 64,  # "a"*64, "b"*64, etc.
            expires_at=now + timedelta(days=30 + i),
            user_agent=f"Device {i}",
        )
        for i in range(5)
    ]

    db_session.add_all(tokens)
    await db_session.commit()

    # Verify all tokens exist
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.user_id == test_user.id)
    )
    retrieved_tokens = result.scalars().all()

    assert len(retrieved_tokens) == 5


# ===========================================================================
# Test 12: Token Session Context
# ===========================================================================


@pytest.mark.asyncio
async def test_token_session_context(db_session: AsyncSession, test_user: User) -> None:
    """Test: Token stores session context (user_agent, ip_address).

    **Validates: R1 AC #3**

    Verifies that optional session context fields are stored and retrieved.
    """
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    ip_address = "192.0.2.42"

    token = RefreshToken(
        user_id=test_user.id,
        token_hash="r" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db_session.add(token)
    await db_session.commit()

    # Retrieve and verify
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.id == token.id)
    )
    retrieved = result.scalar_one()

    assert retrieved.user_agent == user_agent
    assert retrieved.ip_address == ip_address
