
from __future__ import annotations
from app.models.user import User as UserORM
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

@pytest.mark.asyncio
async def test_insert_audit_log_succeeds(db_session: AsyncSession | None) -> None:
    """Test: INSERT audit record via ORM succeeds.

    **Validates: R2 AC #6**

    Integration test: Verify INSERT is allowed by database role.
    """
    if db_session is None:
        pytest.skip("Database not available")

    user_orm = UserORM(
        id=uuid4(),
        email="audit-test@example.com",
        password_hash="test_hash",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user_orm)
    await db_session.flush()

    audit_log = AuditLog(
        actor_id=user_orm.id,
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
        after_state={"name": "test_asset"},
    )

    db_session.add(audit_log)
    await db_session.commit()

    # Verify insert succeeded
    assert audit_log.id is not None
    assert audit_log.created_at is not None


@pytest.mark.asyncio
async def test_select_audit_logs_succeeds(db_session: AsyncSession | None) -> None:
    """Test: SELECT audit records via ORM succeeds.

    **Validates: R2 AC #7**

    Integration test: Verify SELECT is allowed by database role.
    """
    if db_session is None:
        pytest.skip("Database not available")

    user_orm = UserORM(
        id=uuid4(),
        email="audit-test@example.com",
        password_hash="test_hash",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user_orm)
    await db_session.flush()

    # Insert a record first
    audit_log = AuditLog(
        actor_id=user_orm.id,
        actor_role="analyst",
        action="UPDATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
        before_state={"status": "active"},
        after_state={"status": "archived"},
    )
    db_session.add(audit_log)
    await db_session.commit()

    # Now query it back
    from sqlalchemy import select

    stmt = select(AuditLog).where(AuditLog.id == audit_log.id)
    result = await db_session.execute(stmt)
    retrieved = result.scalar_one_or_none()

    assert retrieved is not None
    assert retrieved.id == audit_log.id
    assert retrieved.action == "UPDATE_ASSET"


@pytest.mark.asyncio
async def test_update_audit_logs_fails_with_permission_error(
    db_session: AsyncSession | None,
) -> None:
    """Test: UPDATE on audit_logs fails with permission error.

    **Validates: R2 AC #4**

    Integration test: Verify UPDATE is denied by database role.
    Attempt to modify an audit log should raise permission denied error.
    """
    if db_session is None:
        pytest.skip("Database not available")

    user_orm = UserORM(
        id=uuid4(),
        email="audit-test@example.com",
        password_hash="test_hash",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user_orm)
    await db_session.flush()

    from sqlalchemy import update
    from sqlalchemy.exc import ProgrammingError

    # Insert a record first
    audit_log = AuditLog(
        actor_id=user_orm.id,
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
    )
    db_session.add(audit_log)
    await db_session.commit()

    # Try to update it (should fail)
    stmt = update(AuditLog).where(AuditLog.id == audit_log.id).values(action="MODIFIED")

    with pytest.raises(ProgrammingError) as exc_info:
        await db_session.execute(stmt)
        await db_session.commit()

    # Verify it's a permission error
    assert "permission" in str(exc_info.value).lower() or "insufficient" in str(
        exc_info.value
    ).lower()


@pytest.mark.asyncio
async def test_delete_audit_logs_fails_with_permission_error(
    db_session: AsyncSession | None,
) -> None:
    """Test: DELETE from audit_logs fails with permission error.

    **Validates: R2 AC #5**

    Integration test: Verify DELETE is denied by database role.
    Attempt to delete an audit log should raise permission denied error.
    """
    if db_session is None:
        pytest.skip("Database not available")

    user_orm = UserORM(
        id=uuid4(),
        email="audit-test@example.com",
        password_hash="test_hash",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user_orm)
    await db_session.flush()

    from sqlalchemy import delete
    from sqlalchemy.exc import ProgrammingError

    # Insert a record first
    audit_log = AuditLog(
        actor_id=user_orm.id,
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
    )
    db_session.add(audit_log)
    await db_session.commit()

    # Try to delete it (should fail)
    stmt = delete(AuditLog).where(AuditLog.id == audit_log.id)

    with pytest.raises(ProgrammingError) as exc_info:
        await db_session.execute(stmt)
        await db_session.commit()

    # Verify it's a permission error
    assert "permission" in str(exc_info.value).lower() or "insufficient" in str(
        exc_info.value
    ).lower()


@pytest.mark.asyncio
async def test_unique_constraint_violation(
    db_session: AsyncSession | None,
) -> None:
    """Test: Unique constraint on (actor_id, resource_id, occurred_at) enforced.

    **Validates: R2 AC #2**

    Integration test: Verify duplicate records are rejected by constraint.
    """
    if db_session is None:
        pytest.skip("Database not available")

    user_orm = UserORM(
        id=uuid4(),
        email="audit-test@example.com",
        password_hash="test_hash",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user_orm)
    await db_session.flush()

    from sqlalchemy.exc import IntegrityError

    actor_id = user_orm.id
    resource_id = uuid4()
    now = datetime.now(UTC)

    # Insert first record
    audit_log_1 = AuditLog(
        actor_id=actor_id,
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=resource_id,
        occurred_at=now,
    )
    db_session.add(audit_log_1)
    await db_session.commit()

    # Try to insert duplicate (same actor, resource, time)
    audit_log_2 = AuditLog(
        actor_id=actor_id,
        actor_role="analyst",
        action="CREATE_ASSET",  # Can be different
        resource_type="DigitalAsset",  # Can be different
        resource_id=resource_id,
        occurred_at=now,  # Same time = duplicate
    )
    db_session.add(audit_log_2)

    with pytest.raises(IntegrityError) as exc_info:
        await db_session.commit()

    # Verify it's a unique constraint violation
    assert "unique" in str(exc_info.value).lower() or "constraint" in str(
        exc_info.value
    ).lower()
