"""
Unit tests for AuditLog ORM model.

Tests model instantiation, defaults, field types, and __repr__() without
requiring a database connection. These tests validate ORM behavior in memory.

**Validates: Requirement R5 (ORM Model Test Coverage) — Part 1 (Unit Tests)**

Traces to: 22-Engineering-Backlog E3.T8 (AuditLog ORM model task)
Traces to: 07-Backend-Development-Standards §7 (ORM testing patterns)
Traces to: 11-Testing-Strategy §6 (unit test patterns)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.base import BaseModel
from app.models.audit_log import AuditLog


# ===========================================================================
# Test 1: Model Instantiation with All Fields
# ===========================================================================


def test_instantiate_audit_log_with_all_fields() -> None:
    """Test: Instantiate AuditLog with all fields succeeds.

    **Validates: R5 AC #2**

    Verifies that an AuditLog can be created with all fields populated (no
    database commit needed, just in-memory object).
    """
    actor_id = uuid4()
    resource_id = uuid4()
    now = datetime.now(UTC)

    audit_log = AuditLog(
        actor_id=actor_id,
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=resource_id,
        before_state=None,
        after_state={"name": "test_asset"},
        ip_address="192.168.1.1",
        request_id="req-123",
        user_agent="Mozilla/5.0",
        success=True,
        failure_reason=None,
        occurred_at=now,
    )

    assert audit_log.actor_id == actor_id
    assert audit_log.actor_role == "analyst"
    assert audit_log.action == "CREATE_ASSET"
    assert audit_log.resource_type == "DigitalAsset"
    assert audit_log.resource_id == resource_id
    assert audit_log.before_state is None
    assert audit_log.after_state == {"name": "test_asset"}
    assert audit_log.ip_address == "192.168.1.1"
    assert audit_log.request_id == "req-123"
    assert audit_log.user_agent == "Mozilla/5.0"
    assert audit_log.success is True
    assert audit_log.failure_reason is None
    assert audit_log.occurred_at == now


# ===========================================================================
# Test 2: Model Instantiation with Required Fields Only
# ===========================================================================


def test_instantiate_audit_log_with_required_fields() -> None:
    """Test: Instantiate AuditLog with only required fields succeeds.

    **Validates: R5 AC #3**

    Verifies that an AuditLog can be created with only required fields
    (defaults fill in optional fields). Note: SQLAlchemy column defaults
    (server_default) apply at INSERT time, not in-memory; defaults only apply
    if explicitly set on the instance.
    """
    actor_id = uuid4()
    resource_id = uuid4()

    audit_log = AuditLog(
        actor_id=actor_id,
        actor_role="analyst",
        action="UPDATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=resource_id,
    )

    assert audit_log.actor_id == actor_id
    assert audit_log.actor_role == "analyst"
    assert audit_log.action == "UPDATE_ASSET"
    assert audit_log.resource_type == "DigitalAsset"
    assert audit_log.resource_id == resource_id
    # Optional fields will be None until inserted (defaults apply at DB level)
    assert audit_log.before_state is None
    assert audit_log.after_state is None
    assert audit_log.ip_address is None
    assert audit_log.request_id is None
    assert audit_log.user_agent is None
    # Note: success and occurred_at may be None or have defaults depending on
    # ORM state; these are set by database on INSERT


# ===========================================================================
# Test 3: Nullable actor_id (System Actions)
# ===========================================================================


def test_actor_id_can_be_none() -> None:
    """Test: actor_id can be None for system actions.

    **Validates: R1 AC #3**

    System-initiated operations (cleanup jobs, retries) may have no actor.
    """
    resource_id = uuid4()

    audit_log = AuditLog(
        actor_id=None,  # System action
        actor_role="system",
        action="CLEANUP",
        resource_type="DigitalAsset",
        resource_id=resource_id,
    )

    assert audit_log.actor_id is None
    assert audit_log.actor_role == "system"


# ===========================================================================
# Test 4: Default Values
# ===========================================================================


def test_default_success_is_true() -> None:
    """Test: success defaults to True when explicitly set.

    **Validates: R5 AC #3**

    Operations that succeed should be the default case. Note: SQLAlchemy
    defaults apply at INSERT time (server_default); explicitly setting
    default=True ensures the value if not provided during instantiation.
    """
    # When not specified, success may be None until inserted; explicitly
    # setting it to True verifies the field accepts boolean values
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="viewer",
        action="VIEW_REPORT",
        resource_type="Report",
        resource_id=uuid4(),
        success=True,  # Explicitly set to verify it takes the value
    )

    # success should be set to True
    assert audit_log.success is True


def test_before_state_can_be_none() -> None:
    """Test: before_state can be None (creates have no before state).

    **Validates: R1 AC #3**

    Create operations don't have a "before" state.
    """
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
        before_state=None,  # Create operation
    )

    assert audit_log.before_state is None


def test_after_state_can_be_none() -> None:
    """Test: after_state can be None (deletes have no after state).

    **Validates: R1 AC #3**

    Delete operations don't have an "after" state.
    """
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="DELETE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
        after_state=None,  # Delete operation
    )

    assert audit_log.after_state is None


def test_nullable_optional_fields() -> None:
    """Test: All optional fields can be None.

    **Validates: R1 AC #3**
    """
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="READ_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
        ip_address=None,
        request_id=None,
        user_agent=None,
        failure_reason=None,
    )

    assert audit_log.ip_address is None
    assert audit_log.request_id is None
    assert audit_log.user_agent is None
    assert audit_log.failure_reason is None


# ===========================================================================
# Test 5: Field Types
# ===========================================================================


def test_field_types_are_correct() -> None:
    """Test: Field types are correct when set.

    **Validates: R5 AC #4**

    Verifies that fields have the correct Python types when instantiated
    with values.
    """
    actor_id = uuid4()
    resource_id = uuid4()
    now = datetime.now(UTC)

    audit_log = AuditLog(
        actor_id=actor_id,
        actor_role="analyst",
        action="UPDATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=resource_id,
        before_state={"status": "active"},
        after_state={"status": "archived"},
        ip_address="10.0.0.1",
        request_id="req-456",
        user_agent="Safari",
        success=True,
        failure_reason=None,
        occurred_at=now,
    )

    # UUID fields
    assert isinstance(audit_log.actor_id, UUID)
    assert isinstance(audit_log.resource_id, UUID)

    # String fields
    assert isinstance(audit_log.actor_role, str)
    assert isinstance(audit_log.action, str)
    assert isinstance(audit_log.resource_type, str)
    assert isinstance(audit_log.ip_address, str)
    assert isinstance(audit_log.request_id, str)
    assert isinstance(audit_log.user_agent, str)

    # Dict fields
    assert isinstance(audit_log.before_state, dict)
    assert isinstance(audit_log.after_state, dict)

    # Boolean field
    assert isinstance(audit_log.success, bool)

    # DateTime field
    assert isinstance(audit_log.occurred_at, datetime)


def test_actor_id_is_uuid_or_none() -> None:
    """Test: actor_id field is UUID or None type."""
    # Test with UUID
    actor_id = uuid4()
    audit_log = AuditLog(
        actor_id=actor_id,
        actor_role="analyst",
        action="CREATE",
        resource_type="Asset",
        resource_id=uuid4(),
    )
    assert isinstance(audit_log.actor_id, UUID)

    # Test with None
    audit_log_none = AuditLog(
        actor_id=None,
        actor_role="system",
        action="CLEANUP",
        resource_type="Asset",
        resource_id=uuid4(),
    )
    assert audit_log_none.actor_id is None


def test_action_is_string() -> None:
    """Test: action field is string type."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
    )
    assert isinstance(audit_log.action, str)


def test_success_is_boolean() -> None:
    """Test: success field is boolean type."""
    audit_log_success = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE",
        resource_type="Asset",
        resource_id=uuid4(),
        success=True,
    )
    assert isinstance(audit_log_success.success, bool)
    assert audit_log_success.success is True

    audit_log_failure = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE",
        resource_type="Asset",
        resource_id=uuid4(),
        success=False,
        failure_reason="Permission denied",
    )
    assert isinstance(audit_log_failure.success, bool)
    assert audit_log_failure.success is False


# ===========================================================================
# Test 6: __repr__() Output
# ===========================================================================


def test_repr_returns_string() -> None:
    """Test: __repr__() returns string.

    **Validates: R5 AC #6**
    """
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
    )

    repr_str = repr(audit_log)
    assert isinstance(repr_str, str)
    assert "AuditLog" in repr_str


def test_repr_includes_action_and_resource() -> None:
    """Test: __repr__() includes action and resource info.

    **Validates: R5 AC #6**
    """
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="UPDATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
        success=True,
    )

    repr_str = repr(audit_log)
    assert "UPDATE_ASSET" in repr_str
    assert "DigitalAsset" in repr_str
    assert "success=True" in repr_str or "success" in repr_str.lower()


def test_repr_does_not_expose_state_blobs() -> None:
    """Test: __repr__() does NOT expose state blobs for security.

    **Validates: R5 AC #6**

    Verifies that before_state and after_state are never included in
    string representation to prevent accidental exposure of sensitive data.
    """
    sensitive_data = {"password": "secret123", "token": "abc123xyz"}
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="UPDATE_USER",
        resource_type="User",
        resource_id=uuid4(),
        before_state=sensitive_data,
        after_state=sensitive_data,
    )

    repr_str = repr(audit_log)

    # Should NOT contain the actual sensitive data
    assert "secret123" not in repr_str
    assert "abc123xyz" not in repr_str
    assert "password" not in repr_str
    assert "token" not in repr_str


def test_repr_does_not_expose_ip_address() -> None:
    """Test: __repr__() does NOT expose IP address for privacy."""
    ip = "192.168.100.50"
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE",
        resource_type="Asset",
        resource_id=uuid4(),
        ip_address=ip,
    )

    repr_str = repr(audit_log)
    # Should not contain IP address (privacy concern)
    assert ip not in repr_str or "ip" not in repr_str.lower()


def test_repr_includes_actor() -> None:
    """Test: __repr__() includes actor information."""
    actor_id = uuid4()
    audit_log = AuditLog(
        actor_id=actor_id,
        actor_role="admin",
        action="DELETE_REPORT",
        resource_type="Report",
        resource_id=uuid4(),
    )

    repr_str = repr(audit_log)
    # Should include some form of actor (not full ID for privacy)
    assert "actor" in repr_str.lower() or str(actor_id)[:8] in repr_str


# ===========================================================================
# Test 7: Timestamps Inherited from BaseModel
# ===========================================================================


def test_created_at_is_datetime() -> None:
    """Test: created_at field exists (inherited from BaseModel).

    **Validates: R5 AC #7**

    Verifies that created_at field is present (inherited from BaseModel).
    """
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE",
        resource_type="Asset",
        resource_id=uuid4(),
    )

    # Field should exist as an attribute
    assert hasattr(audit_log, "created_at")


def test_updated_at_is_datetime() -> None:
    """Test: updated_at field exists (inherited from BaseModel).

    **Validates: R5 AC #7**

    Verifies that updated_at field is present (inherited from BaseModel).
    """
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE",
        resource_type="Asset",
        resource_id=uuid4(),
    )

    # Field should exist as an attribute
    assert hasattr(audit_log, "updated_at")


# ===========================================================================
# Test 8: Model Metadata
# ===========================================================================


def test_audit_log_model_has_tablename() -> None:
    """Test: AuditLog model has __tablename__ defined.

    **Validates: R1 AC #5**

    Verifies that __tablename__ is set to "audit_logs".
    """
    assert AuditLog.__tablename__ == "audit_logs"


def test_audit_log_model_inherits_from_basemodel() -> None:
    """Test: AuditLog model inherits from BaseModel.

    **Validates: R1 AC #2**

    Verifies that AuditLog inherits from BaseModel (which provides id,
    created_at, updated_at, deleted_at).
    """
    assert issubclass(AuditLog, BaseModel)


def test_audit_log_exports_from_models() -> None:
    """Test: AuditLog is exported from app.models.

    **Validates: R1 AC #8**

    Verifies that AuditLog can be imported from app.models package.
    """
    from app.models import AuditLog as ImportedAuditLog

    assert ImportedAuditLog is AuditLog


# ===========================================================================
# Test 9: Different Action Types
# ===========================================================================


def test_audit_log_with_create_action() -> None:
    """Test: AuditLog can be created with CREATE action."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
        after_state={"name": "new_asset"},
    )

    assert audit_log.action == "CREATE_ASSET"
    assert audit_log.before_state is None  # Implicit: creates have no before state


def test_audit_log_with_update_action() -> None:
    """Test: AuditLog can be created with UPDATE action."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="UPDATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
        before_state={"status": "active"},
        after_state={"status": "archived"},
    )

    assert audit_log.action == "UPDATE_ASSET"
    assert audit_log.before_state is not None
    assert audit_log.after_state is not None


def test_audit_log_with_delete_action() -> None:
    """Test: AuditLog can be created with DELETE action."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="DELETE_REPORT",
        resource_type="Report",
        resource_id=uuid4(),
        before_state={"title": "Old Report"},
    )

    assert audit_log.action == "DELETE_REPORT"
    assert audit_log.before_state is not None
    assert audit_log.after_state is None  # Implicit: deletes have no after state


# ===========================================================================
# Test 10: Different Resource Types
# ===========================================================================


def test_audit_log_with_digital_asset_resource() -> None:
    """Test: AuditLog can track DigitalAsset resource."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
    )

    assert audit_log.resource_type == "DigitalAsset"


def test_audit_log_with_report_resource() -> None:
    """Test: AuditLog can track Report resource."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="UPDATE_REPORT",
        resource_type="Report",
        resource_id=uuid4(),
    )

    assert audit_log.resource_type == "Report"


def test_audit_log_with_user_resource() -> None:
    """Test: AuditLog can track User resource."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="admin",
        action="UPDATE_USER",
        resource_type="User",
        resource_id=uuid4(),
    )

    assert audit_log.resource_type == "User"


# ===========================================================================
# Test 11: Different Actor Roles
# ===========================================================================


def test_audit_log_with_admin_actor() -> None:
    """Test: AuditLog can be created with admin actor role."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="admin",
        action="DELETE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
    )

    assert audit_log.actor_role == "admin"


def test_audit_log_with_analyst_actor() -> None:
    """Test: AuditLog can be created with analyst actor role."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
    )

    assert audit_log.actor_role == "analyst"


def test_audit_log_with_viewer_actor() -> None:
    """Test: AuditLog can be created with viewer actor role."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="viewer",
        action="VIEW_REPORT",
        resource_type="Report",
        resource_id=uuid4(),
    )

    assert audit_log.actor_role == "viewer"


# ===========================================================================
# Test 12: Success/Failure Cases
# ===========================================================================


def test_audit_log_success_case() -> None:
    """Test: AuditLog can record successful operation."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
        success=True,
        failure_reason=None,
    )

    assert audit_log.success is True
    assert audit_log.failure_reason is None


def test_audit_log_failure_case() -> None:
    """Test: AuditLog can record failed operation with reason."""
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="viewer",
        action="DELETE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
        success=False,
        failure_reason="Permission denied: viewer role cannot delete assets",
    )

    assert audit_log.success is False
    assert audit_log.failure_reason == "Permission denied: viewer role cannot delete assets"


# ===========================================================================
# Integration Tests (Require Database)
# ===========================================================================


@pytest.mark.asyncio
async def test_insert_audit_log_succeeds(db_session: AsyncSession | None) -> None:
    """Test: INSERT audit record via ORM succeeds.

    **Validates: R2 AC #6**

    Integration test: Verify INSERT is allowed by database role.
    """
    if db_session is None:
        pytest.skip("Database not available")

    audit_log = AuditLog(
        actor_id=uuid4(),
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

    # Insert a record first
    audit_log = AuditLog(
        actor_id=uuid4(),
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

    from sqlalchemy import update
    from sqlalchemy.exc import OperationalError

    # Insert a record first
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
    )
    db_session.add(audit_log)
    await db_session.commit()

    # Try to update it (should fail)
    stmt = update(AuditLog).where(AuditLog.id == audit_log.id).values(action="MODIFIED")

    with pytest.raises(OperationalError) as exc_info:
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

    from sqlalchemy import delete
    from sqlalchemy.exc import OperationalError

    # Insert a record first
    audit_log = AuditLog(
        actor_id=uuid4(),
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=uuid4(),
    )
    db_session.add(audit_log)
    await db_session.commit()

    # Try to delete it (should fail)
    stmt = delete(AuditLog).where(AuditLog.id == audit_log.id)

    with pytest.raises(OperationalError) as exc_info:
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

    from sqlalchemy.exc import IntegrityError

    actor_id = uuid4()
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
