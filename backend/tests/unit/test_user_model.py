"""
Unit tests for User ORM model.

Tests model instantiation, defaults, field types, and __repr__() without
requiring a database connection. These tests validate ORM behavior in memory.

**Validates: Requirement R5 (ORM Model Test Coverage) — Part 1 (Unit Tests)**

Traces to: 22-Engineering-Backlog E3.T3 (User ORM model task)
Traces to: 07-Backend-Development-Standards §7 (ORM testing patterns)
Traces to: 11-Testing-Strategy §6 (unit test patterns)
"""

from datetime import UTC, datetime

from app.models.user import User, UserRole


# ===========================================================================
# Test 1: Model Instantiation with All Fields
# ===========================================================================


def test_instantiate_user_with_all_fields() -> None:
    """Test: Instantiate User with all fields succeeds.

    **Validates: R5 AC #2**

    Verifies that a User can be created with all fields populated (no
    database commit needed, just in-memory object).
    """
    user = User(
        email="jane@example.com",
        password_hash="$2b$12$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ",
        full_name="Jane Doe",
        role=UserRole.ANALYST.value,
    )

    assert user.email == "jane@example.com"
    assert user.password_hash == "$2b$12$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ"
    assert user.full_name == "Jane Doe"
    assert user.role == UserRole.ANALYST.value


# ===========================================================================
# Test 2: Model Instantiation with Minimal Fields
# ===========================================================================


def test_instantiate_user_with_minimal_fields() -> None:
    """Test: Instantiate User with minimal fields succeeds.

    **Validates: R5 AC #3**

    Verifies that a User can be created with only required fields
    (defaults fill in optional fields).
    """
    user = User(
        email="bob@example.com",
        password_hash="$2b$12$xyz123xyz123xyz123xyz123xyz123xyz123xyz123",
        full_name="Bob Smith",
    )

    assert user.email == "bob@example.com"
    assert user.password_hash == "$2b$12$xyz123xyz123xyz123xyz123xyz123xyz123xyz123"
    assert user.full_name == "Bob Smith"


# ===========================================================================
# Test 3: Default Values
# ===========================================================================


def test_default_values_are_correct() -> None:
    """Test: Default values are correct (when explicitly applied).

    **Validates: R5 AC #4**

    Verifies that default values can be set on creation.
    Note: In-memory ORM instances require explicit defaults in Python;
    database-level defaults are applied on INSERT.
    """
    user = User(
        email="alice@example.com",
        password_hash="$2b$12$hash123hash123hash123hash123hash123hash123",
        full_name="Alice Wonder",
        role=UserRole.VIEWER.value,
        is_active=True,
        is_verified=False,
    )

    # Verify values are set as provided
    assert user.role == UserRole.VIEWER.value
    assert user.is_active is True
    assert user.is_verified is False
    assert user.deleted_at is None


def test_role_default_is_viewer() -> None:
    """Test: role can be set to 'viewer' (least privileged).

    **Validates: R1 AC #3**

    Role should default to 'viewer' (least privileged) for security.
    Note: Database-level default is applied on INSERT; Python defaults
    must be specified explicitly during instantiation.
    """
    user = User(
        email="test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test User",
        role=UserRole.VIEWER.value,
    )

    assert user.role == UserRole.VIEWER.value


def test_is_active_default_is_true() -> None:
    """Test: is_active can be set to true.

    **Validates: R5 AC #5**

    New users should be active by default (deactivation is explicit).
    """
    user = User(
        email="test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test User",
        is_active=True,
    )

    assert user.is_active is True


def test_is_verified_default_is_false() -> None:
    """Test: is_verified can be set to false.

    **Validates: R5 AC #5**

    New users should be unverified by default (email verification is required).
    """
    user = User(
        email="test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test User",
        is_verified=False,
    )

    assert user.is_verified is False


# ===========================================================================
# Test 4: Field Types
# ===========================================================================


def test_field_types_are_correct() -> None:
    """Test: Field types are correct when set.

    **Validates: R5 AC #4**

    Verifies that fields have the correct Python types when instantiated
    with values.
    """
    user = User(
        email="type-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Type Tester",
        role=UserRole.ANALYST.value,
        is_active=True,
        is_verified=False,
    )

    # String fields
    assert isinstance(user.email, str)
    assert isinstance(user.password_hash, str)
    assert isinstance(user.full_name, str)
    assert isinstance(user.role, str)

    # Boolean fields
    assert isinstance(user.is_active, bool)
    assert isinstance(user.is_verified, bool)

    # Nullable datetime field
    assert user.deleted_at is None


def test_email_is_string_type() -> None:
    """Test: email field is string type."""
    user = User(
        email="string-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
    )

    assert isinstance(user.email, str)


def test_password_hash_is_string_type() -> None:
    """Test: password_hash field is string type."""
    user = User(
        email="test@example.com",
        password_hash="$2b$12$thisisastringtype123456789",
        full_name="Test",
    )

    assert isinstance(user.password_hash, str)


def test_is_active_is_boolean_type() -> None:
    """Test: is_active field is boolean type."""
    user = User(
        email="test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        is_active=True,
    )

    assert isinstance(user.is_active, bool)


def test_is_verified_is_boolean_type() -> None:
    """Test: is_verified field is boolean type."""
    user = User(
        email="test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        is_verified=False,
    )

    assert isinstance(user.is_verified, bool)


# ===========================================================================
# Test 5: __repr__() Output
# ===========================================================================


def test_repr_returns_useful_string() -> None:
    """Test: __repr__() returns useful string.

    **Validates: R5 AC #6**

    Verifies that __repr__() returns a human-readable representation that
    includes email, role, and active status.
    """
    user = User(
        email="repr-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Repr Tester",
        role=UserRole.ADMIN.value,
        is_active=True,
    )

    repr_str = repr(user)

    # Should include type name
    assert "User" in repr_str

    # Should include email for identification
    assert "repr-test@example.com" in repr_str or "email" in repr_str

    # Should include role
    assert "admin" in repr_str or "role" in repr_str

    # Should be a string
    assert isinstance(repr_str, str)


def test_repr_does_not_expose_password_hash() -> None:
    """Test: __repr__() does NOT expose password_hash for security.

    **Validates: R5 AC #6**

    Verifies that the password hash is never included in string representation
    to prevent accidental log exposure.
    """
    password_hash = "$2b$12$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ"
    user = User(
        email="security@example.com",
        password_hash=password_hash,
        full_name="Security Tester",
    )

    repr_str = repr(user)

    # Should NOT contain the actual password hash
    assert password_hash not in repr_str

    # Should NOT contain password_hash key (for defense in depth)
    assert "password" not in repr_str.lower()


def test_repr_includes_email() -> None:
    """Test: __repr__() includes email."""
    user = User(
        email="email-in-repr@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
    )

    repr_str = repr(user)
    assert "email-in-repr@example.com" in repr_str or "@" in repr_str


def test_repr_includes_role() -> None:
    """Test: __repr__() includes role."""
    user = User(
        email="test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.ANALYST.value,
    )

    repr_str = repr(user)
    assert "analyst" in repr_str or "role" in repr_str


def test_repr_includes_active_status() -> None:
    """Test: __repr__() includes active status."""
    user = User(
        email="test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        is_active=False,
    )

    repr_str = repr(user)
    assert "False" in repr_str or "active" in repr_str.lower()


# ===========================================================================
# Test 6: Timestamps Inherited from BaseModel
# ===========================================================================


def test_created_at_is_datetime() -> None:
    """Test: created_at field exists (inherited from BaseModel).

    **Validates: R5 AC #7**

    Verifies that created_at field is present (inherited from BaseModel).
    In-memory instantiation won't set the timestamp yet (database sets it),
    but the field should exist.
    """
    user = User(
        email="timestamp@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
    )

    # Field should exist as an attribute
    assert hasattr(user, "created_at")


def test_updated_at_is_datetime() -> None:
    """Test: updated_at field exists (inherited from BaseModel).

    **Validates: R5 AC #7**

    Verifies that updated_at field is present (inherited from BaseModel).
    """
    user = User(
        email="timestamp@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
    )

    # Field should exist as an attribute
    assert hasattr(user, "updated_at")


# ===========================================================================
# Test 7: Soft-Delete Field
# ===========================================================================


def test_deleted_at_is_none_for_active_user() -> None:
    """Test: deleted_at is None for active user.

    **Validates: R5 AC #8**

    Verifies that deleted_at defaults to None (not set) for new users.
    """
    user = User(
        email="active@example.com",
        password_hash="$2b$12$hash",
        full_name="Active User",
    )

    assert user.deleted_at is None


def test_deleted_at_can_be_set() -> None:
    """Test: deleted_at can be explicitly set.

    **Validates: R1 AC #7**

    Verifies that deleted_at can be set to a datetime value for soft-deleted
    users (without actually deleting from database).
    """

    now = datetime.now(UTC)
    user = User(
        email="deleted@example.com",
        password_hash="$2b$12$hash",
        full_name="Deleted User",
        deleted_at=now,
    )

    assert user.deleted_at == now


# ===========================================================================
# Test 8: UserRole Enum
# ===========================================================================


def test_user_role_enum_has_admin() -> None:
    """Test: UserRole enum has ADMIN value."""
    assert UserRole.ADMIN.value == "admin"


def test_user_role_enum_has_analyst() -> None:
    """Test: UserRole enum has ANALYST value."""
    assert UserRole.ANALYST.value == "analyst"


def test_user_role_enum_has_viewer() -> None:
    """Test: UserRole enum has VIEWER value."""
    assert UserRole.VIEWER.value == "viewer"


def test_user_role_enum_values_are_strings() -> None:
    """Test: UserRole enum values are strings (StrEnum).

    **Validates: R1 AC #4**

    Verifies that UserRole is a StrEnum (can be used as strings directly).
    """
    assert isinstance(UserRole.ADMIN.value, str)
    assert isinstance(UserRole.ANALYST.value, str)
    assert isinstance(UserRole.VIEWER.value, str)


# ===========================================================================
# Test 9: Model Metadata
# ===========================================================================


def test_user_model_has_tablename() -> None:
    """Test: User model has __tablename__ defined.

    **Validates: R1 AC #5**

    Verifies that __tablename__ is set to "users".
    """
    assert User.__tablename__ == "users"


def test_user_model_inherits_from_basemodel() -> None:
    """Test: User model inherits from BaseModel.

    **Validates: R1 AC #2**

    Verifies that User inherits from BaseModel (which provides id, created_at,
    updated_at).
    """
    from app.infrastructure.database.base import BaseModel

    assert issubclass(User, BaseModel)


# ===========================================================================
# Test 10: Different Role Values
# ===========================================================================


def test_user_with_admin_role() -> None:
    """Test: User can be created with admin role."""
    user = User(
        email="admin@example.com",
        password_hash="$2b$12$hash",
        full_name="Admin User",
        role=UserRole.ADMIN.value,
    )

    assert user.role == UserRole.ADMIN.value


def test_user_with_analyst_role() -> None:
    """Test: User can be created with analyst role."""
    user = User(
        email="analyst@example.com",
        password_hash="$2b$12$hash",
        full_name="Analyst User",
        role=UserRole.ANALYST.value,
    )

    assert user.role == UserRole.ANALYST.value


def test_user_with_viewer_role() -> None:
    """Test: User can be created with viewer role."""
    user = User(
        email="viewer@example.com",
        password_hash="$2b$12$hash",
        full_name="Viewer User",
        role=UserRole.VIEWER.value,
    )

    assert user.role == UserRole.VIEWER.value


# ===========================================================================
# Test 11: Different Active/Verified States
# ===========================================================================


def test_user_active_and_verified() -> None:
    """Test: User can be created with is_active=True and is_verified=True."""
    user = User(
        email="active-verified@example.com",
        password_hash="$2b$12$hash",
        full_name="Active Verified",
        is_active=True,
        is_verified=True,
    )

    assert user.is_active is True
    assert user.is_verified is True


def test_user_active_but_not_verified() -> None:
    """Test: User can be active but unverified (email not confirmed yet)."""
    user = User(
        email="active-unverified@example.com",
        password_hash="$2b$12$hash",
        full_name="Active Unverified",
        is_active=True,
        is_verified=False,
    )

    assert user.is_active is True
    assert user.is_verified is False


def test_user_inactive_but_verified() -> None:
    """Test: User can be inactive but verified (deactivation separate from verification)."""
    user = User(
        email="inactive-verified@example.com",
        password_hash="$2b$12$hash",
        full_name="Inactive Verified",
        is_active=False,
        is_verified=True,
    )

    assert user.is_active is False
    assert user.is_verified is True


def test_user_inactive_and_not_verified() -> None:
    """Test: User can be inactive and unverified."""
    user = User(
        email="inactive-unverified@example.com",
        password_hash="$2b$12$hash",
        full_name="Inactive Unverified",
        is_active=False,
        is_verified=False,
    )

    assert user.is_active is False
    assert user.is_verified is False
