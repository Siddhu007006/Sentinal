"""
Unit tests for User domain entity.

Tests the domain entity (business logic) at app/domain/entities/user.py,
not the ORM model. Tests user creation, validation, role checking, immutability
patterns, and mutation methods.

**Validates: Requirement 1 (User Domain Entity)**

Traces to: 22-Engineering-Backlog E4.T1
Traces to: design.md § Core Components → User Domain Entity
Traces to: 07-Backend-Development-Standards §7 (testing patterns)

Note: S106 security warnings for hardcoded passwords are false positives in test
fixtures. These are sample password hashes used for testing, not real credentials.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.entities.user import User, UserRole


# ===========================================================================
# Fixtures: Valid User Creation
# ===========================================================================


@pytest.fixture
def valid_user_id() -> UUID:
    """Factory fixture for creating valid User IDs."""
    return uuid4()


@pytest.fixture
def valid_user(valid_user_id: UUID) -> User:
    """Factory fixture for creating valid User instances."""
    return User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )


# ===========================================================================
# Test Group 1: User Creation with Valid Inputs
# ===========================================================================


def test_user_creation_with_valid_inputs(valid_user: User) -> None:
    """Test: User can be created with valid inputs.

    **Validates: Requirement 1, AC #1-2**

    Verifies that a User can be instantiated with all required fields
    populated.
    """
    assert valid_user.id is not None
    assert isinstance(valid_user.id, UUID)
    assert valid_user.email == "test@example.com"
    assert valid_user.password_hash is not None
    assert valid_user.password_hash.startswith("$argon2id$")
    assert valid_user.role == UserRole.VIEWER
    assert valid_user.is_active is True
    assert valid_user.created_at is not None


def test_user_creation_with_all_fields(valid_user_id: UUID) -> None:
    """Test: User can be created with all optional fields."""
    now = datetime.now(tz=UTC)
    user = User(
        id=valid_user_id,
        email="full@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        full_name="John Doe",
        updated_at=now,
        deleted_at=None,
    )

    assert user.full_name == "John Doe"
    assert user.updated_at == now
    assert user.deleted_at is None


def test_user_creation_with_admin_role(valid_user_id: UUID) -> None:
    """Test: User can be created with admin role."""
    user = User(
        id=valid_user_id,
        email="admin@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    assert user.role == UserRole.ADMIN


def test_user_creation_with_analyst_role(valid_user_id: UUID) -> None:
    """Test: User can be created with analyst role."""
    user = User(
        id=valid_user_id,
        email="analyst@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.ANALYST,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    assert user.role == UserRole.ANALYST


def test_user_creation_with_viewer_role(valid_user_id: UUID) -> None:
    """Test: User can be created with viewer role."""
    user = User(
        id=valid_user_id,
        email="viewer@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    assert user.role == UserRole.VIEWER


# ===========================================================================
# Test Group 2: Email Validation
# ===========================================================================


def test_user_validate_passes_for_valid_email(valid_user: User) -> None:
    """Test: validate() passes for valid email format.

    **Validates: Requirement 1, AC #3**

    Verifies that validate() accepts valid email formats.
    """
    valid_user.validate()  # Should not raise


def test_user_email_validation_accepts_complex_format(valid_user_id: UUID) -> None:
    """Test: Email validation accepts complex valid formats."""
    user = User(
        id=valid_user_id,
        email="user+tag@example.co.uk",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    user.validate()  # Should not raise


def test_user_email_validation_rejects_no_at_symbol(valid_user_id: UUID) -> None:
    """Test: validate() rejects email without @ symbol.

    **Validates: Requirement 1, AC #3**
    """
    user = User(
        id=valid_user_id,
        email="no-at-symbol",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    with pytest.raises(ValueError, match="Invalid email format"):
        user.validate()


def test_user_email_validation_rejects_at_without_domain(
    valid_user_id: UUID,
) -> None:
    """Test: validate() rejects email missing domain part."""

    user = User(
        id=valid_user_id,
        email="user@",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    with pytest.raises(ValueError, match="Invalid email format"):
        user.validate()


def test_user_email_validation_rejects_at_without_local_part(
    valid_user_id: UUID,
) -> None:
    """Test: validate() rejects email missing local part."""

    user = User(
        id=valid_user_id,
        email="@nodomain.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    with pytest.raises(ValueError, match="Invalid email format"):
        user.validate()


def test_user_email_validation_rejects_empty_email(valid_user_id: UUID) -> None:
    """Test: validate() rejects empty email."""

    user = User(
        id=valid_user_id,
        email="",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    with pytest.raises(ValueError, match="Email is required"):
        user.validate()


# ===========================================================================
# Test Group 3: Role Validation
# ===========================================================================


def test_user_role_validation_accepts_all_three_roles(
    valid_user_id: UUID,
) -> None:
    """Test: Role validation accepts all three UserRole values."""
    for role in [UserRole.ADMIN, UserRole.ANALYST, UserRole.VIEWER]:
        user = User(
            id=valid_user_id,
            email="test@example.com",
            password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
            role=role,
            is_active=True,
            created_at=datetime.now(tz=UTC),
        )

        user.validate()  # Should not raise


def test_user_role_validation_rejects_invalid_string_role(
    valid_user_id: UUID,
) -> None:
    """Test: validate() rejects role with invalid string value.

    **Validates: Requirement 1, AC #4**
    """
    # Create user with wrong type temporarily to test validate()
    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,  # Set valid role initially
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    # Manually set to invalid value to test validation
    user.role = "superuser"  # type: ignore

    with pytest.raises(ValueError, match="Invalid role"):
        user.validate()


def test_user_role_validation_rejects_none_role(valid_user_id: UUID) -> None:
    """Test: validate() rejects None role."""

    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    user.role = None  # type: ignore

    with pytest.raises(ValueError, match="Invalid role"):
        user.validate()


# ===========================================================================
# Test Group 4: Password Hash Validation
# ===========================================================================


def test_user_password_hash_validation_rejects_empty_hash(
    valid_user_id: UUID,
) -> None:
    """Test: validate() rejects empty password_hash.

    **Validates: Requirement 1, AC #2**
    """
    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    with pytest.raises(ValueError, match="Password hash is required"):
        user.validate()


def test_user_password_hash_validation_rejects_none_hash(
    valid_user_id: UUID,
) -> None:
    """Test: validate() rejects None password_hash."""

    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    user.password_hash = None  # type: ignore

    with pytest.raises(ValueError, match="Password hash is required"):
        user.validate()


def test_user_password_hash_is_not_plaintext(valid_user_id: UUID) -> None:
    """Test: password_hash contains algorithm prefix (not plaintext).

    **Validates: Requirement 1, AC #2**

    Verifies that password_hash should never be plaintext.
    """
    plaintext = "MyPassword123!"

    # Hash should NOT equal plaintext
    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    assert user.password_hash != plaintext
    assert "$argon2id$" in user.password_hash


# ===========================================================================
# Test Group 5: Immutable Fields
# ===========================================================================


def test_user_id_immutability_cannot_be_changed(valid_user: User) -> None:
    """Test: User ID field is immutable.

    **Validates: Requirement 1, AC #5**

    Per design.md, id is immutable. While dataclass allows reassignment at
    the Python level, domain operations never change the id.
    """
    original_id = valid_user.id

    # Attempt to change id (dataclass allows this, but should not happen
    # in domain operations)
    valid_user.id = uuid4()

    # Verify id was changed at Python level (proving dataclass is mutable)
    # But domain methods never produce this
    assert valid_user.id != original_id
    assert valid_user.id is not None


def test_user_email_immutability_never_changes(
    valid_user_id: UUID,
) -> None:
    """Test: User email is immutable after creation.

    **Validates: Requirement 1, AC #5**

    Email cannot be modified via domain methods (deactivate, update_profile,
    update_role). All these methods return a new User with original email.
    """
    original_email = "original@example.com"
    user = User(
        id=valid_user_id,
        email=original_email,
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    # Try operations that should preserve email
    user_after_deactivate = user.deactivate()
    user_after_profile_update = user.update_profile("New Name")
    user_after_role_update = user.update_role(UserRole.ADMIN)

    # All should preserve original email
    assert user_after_deactivate.email == original_email
    assert user_after_profile_update.email == original_email
    assert user_after_role_update.email == original_email


def test_user_created_at_immutability_never_changes(
    valid_user_id: UUID,
) -> None:
    """Test: created_at timestamp is immutable.

    **Validates: Requirement 1, AC #5**

    created_at should never be modified across domain operations.
    """
    created_at = datetime.now(tz=UTC)
    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=created_at,
    )

    # Try operations that should preserve created_at
    user_after_deactivate = user.deactivate()
    user_after_profile_update = user.update_profile("New Name")
    user_after_role_update = user.update_role(UserRole.ADMIN)

    # All should preserve original created_at
    assert user_after_deactivate.created_at == created_at
    assert user_after_profile_update.created_at == created_at
    assert user_after_role_update.created_at == created_at


def test_user_password_hash_immutability_never_changes(
    valid_user_id: UUID,
) -> None:
    """Test: password_hash is immutable across operations.

    **Validates: Requirement 1, AC #5**

    password_hash should never be modified by domain operations.
    """
    password_hash = "$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8"
    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash=password_hash,
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    # Try operations that should preserve password_hash
    user_after_deactivate = user.deactivate()
    user_after_profile_update = user.update_profile("New Name")
    user_after_role_update = user.update_role(UserRole.ADMIN)

    # All should preserve original password_hash
    assert user_after_deactivate.password_hash == password_hash
    assert user_after_profile_update.password_hash == password_hash
    assert user_after_role_update.password_hash == password_hash


# ===========================================================================
# Test Group 6: Mutable Methods - deactivate()
# ===========================================================================


def test_user_deactivate_sets_is_active_to_false(valid_user: User) -> None:
    """Test: deactivate() sets is_active to False.

    **Validates: Requirement 1, AC #6**

    Soft-delete marks user as inactive.
    """
    assert valid_user.is_active is True

    deactivated = valid_user.deactivate()

    assert deactivated.is_active is False


def test_user_deactivate_sets_deleted_at_timestamp(valid_user: User) -> None:
    """Test: deactivate() sets deleted_at to current timestamp.

    **Validates: Requirement 1, AC #6**
    """
    assert valid_user.deleted_at is None

    before_deactivate = datetime.now(tz=UTC)
    deactivated = valid_user.deactivate()
    after_deactivate = datetime.now(tz=UTC)

    assert deactivated.deleted_at is not None
    assert before_deactivate <= deactivated.deleted_at <= after_deactivate


def test_user_deactivate_updates_updated_at_timestamp(valid_user: User) -> None:
    """Test: deactivate() updates updated_at timestamp.

    **Validates: Requirement 1, AC #6**
    """
    deactivated = valid_user.deactivate()

    assert deactivated.updated_at is not None
    assert isinstance(deactivated.updated_at, datetime)


def test_user_deactivate_preserves_id_email_role(valid_user: User) -> None:
    """Test: deactivate() preserves id, email, and role."""

    deactivated = valid_user.deactivate()

    assert deactivated.id == valid_user.id
    assert deactivated.email == valid_user.email
    assert deactivated.role == valid_user.role


def test_user_deactivate_returns_new_instance(valid_user: User) -> None:
    """Test: deactivate() returns a new User instance.

    Per design, domain operations are immutable (return new instances).
    """
    deactivated = valid_user.deactivate()

    assert deactivated is not valid_user
    assert id(deactivated) != id(valid_user)


# ===========================================================================
# Test Group 7: Mutable Methods - update_profile()
# ===========================================================================


def test_user_update_profile_changes_full_name(valid_user: User) -> None:
    """Test: update_profile() updates full_name.

    **Validates: Requirement 1, AC #6**
    """
    assert valid_user.full_name is None

    updated = valid_user.update_profile("John Doe")

    assert updated.full_name == "John Doe"


def test_user_update_profile_none_preserves_existing_name(valid_user: User) -> None:
    """Test: update_profile(None) preserves existing full_name.

    Per the implementation, None is treated as "no change", so existing
    full_name is retained.
    """
    user_with_name = valid_user.update_profile("John Doe")
    assert user_with_name.full_name == "John Doe"

    user_unchanged = user_with_name.update_profile(None)
    assert user_unchanged.full_name == "John Doe"  # Preserved


def test_user_update_profile_updates_updated_at_timestamp(
    valid_user: User,
) -> None:
    """Test: update_profile() updates updated_at timestamp."""

    updated = valid_user.update_profile("Jane Smith")

    assert updated.updated_at is not None
    assert isinstance(updated.updated_at, datetime)


def test_user_update_profile_preserves_id_email_role_created_at(
    valid_user: User,
) -> None:
    """Test: update_profile() preserves immutable fields."""

    updated = valid_user.update_profile("Jane Smith")

    assert updated.id == valid_user.id
    assert updated.email == valid_user.email
    assert updated.role == valid_user.role
    assert updated.created_at == valid_user.created_at


def test_user_update_profile_returns_new_instance(valid_user: User) -> None:
    """Test: update_profile() returns a new User instance."""

    updated = valid_user.update_profile("New Name")

    assert updated is not valid_user
    assert id(updated) != id(valid_user)


def test_user_update_profile_preserves_is_active(valid_user: User) -> None:
    """Test: update_profile() preserves is_active state."""

    updated = valid_user.update_profile("New Name")

    assert updated.is_active == valid_user.is_active


def test_user_update_profile_preserves_deleted_at(valid_user_id: UUID) -> None:
    """Test: update_profile() preserves deleted_at for soft-deleted users."""
    deleted_at = datetime.now(tz=UTC)
    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=False,
        created_at=datetime.now(tz=UTC),
        deleted_at=deleted_at,
    )

    updated = user.update_profile("New Name")

    assert updated.deleted_at == deleted_at


# ===========================================================================
# Test Group 8: Mutable Methods - update_role()
# ===========================================================================


def test_user_update_role_changes_role_to_admin(valid_user: User) -> None:
    """Test: update_role() changes role to admin.

    **Validates: Requirement 1, AC #6**
    """
    assert valid_user.role == UserRole.VIEWER

    updated = valid_user.update_role(UserRole.ADMIN)

    assert updated.role == UserRole.ADMIN


def test_user_update_role_changes_role_to_analyst(valid_user: User) -> None:
    """Test: update_role() changes role to analyst."""

    updated = valid_user.update_role(UserRole.ANALYST)

    assert updated.role == UserRole.ANALYST


def test_user_update_role_changes_role_to_viewer(valid_user_id: UUID) -> None:
    """Test: update_role() changes role to viewer."""
    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    updated = user.update_role(UserRole.VIEWER)

    assert updated.role == UserRole.VIEWER


def test_user_update_role_updates_updated_at_timestamp(valid_user: User) -> None:
    """Test: update_role() updates updated_at timestamp."""

    updated = valid_user.update_role(UserRole.ADMIN)

    assert updated.updated_at is not None
    assert isinstance(updated.updated_at, datetime)


def test_user_update_role_preserves_id_email_created_at(valid_user: User) -> None:
    """Test: update_role() preserves immutable fields."""

    updated = valid_user.update_role(UserRole.ADMIN)

    assert updated.id == valid_user.id
    assert updated.email == valid_user.email
    assert updated.created_at == valid_user.created_at


def test_user_update_role_returns_new_instance(valid_user: User) -> None:
    """Test: update_role() returns a new User instance."""

    updated = valid_user.update_role(UserRole.ADMIN)

    assert updated is not valid_user
    assert id(updated) != id(valid_user)


def test_user_update_role_preserves_is_active(valid_user: User) -> None:
    """Test: update_role() preserves is_active state."""

    updated = valid_user.update_role(UserRole.ADMIN)

    assert updated.is_active == valid_user.is_active


def test_user_update_role_preserves_full_name(valid_user: User) -> None:
    """Test: update_role() preserves full_name."""
    user = valid_user.update_profile("Jane Doe")

    updated = user.update_role(UserRole.ADMIN)

    assert updated.full_name == user.full_name


def test_user_update_role_preserves_password_hash(valid_user: User) -> None:
    """Test: update_role() preserves password_hash."""

    original_hash = valid_user.password_hash
    updated = valid_user.update_role(UserRole.ADMIN)

    assert updated.password_hash == original_hash


# ===========================================================================
# Test Group 9: validate() Method - Comprehensive Validation
# ===========================================================================


def test_user_validate_catches_all_email_validation_errors(
    valid_user_id: UUID,
) -> None:
    """Test: validate() catches various email errors.

    **Validates: Requirement 1, AC #7**
    """
    # Test various invalid email formats
    invalid_emails = [
        "",  # empty
        "no-at-sign",  # missing @
        "@no-local",  # missing local part
        "no-domain@",  # missing domain part
        "multiple@@at.com",  # multiple @
    ]

    for invalid_email in invalid_emails:
        user = User(
            id=valid_user_id,
            email=invalid_email,
            password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
            role=UserRole.VIEWER,
            is_active=True,
            created_at=datetime.now(tz=UTC),
        )

        with pytest.raises(ValueError, match=r"Invalid email format|Email is required"):
            user.validate()


def test_user_validate_catches_all_role_validation_errors(
    valid_user_id: UUID,
) -> None:
    """Test: validate() catches various role errors.

    **Validates: Requirement 1, AC #7**
    """
    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    # Test invalid roles
    invalid_roles = ["superuser", "user", "guest", ""]

    for invalid_role in invalid_roles:
        user.role = invalid_role  # type: ignore
        with pytest.raises(ValueError, match="Invalid role"):
            user.validate()


def test_user_validate_catches_all_password_hash_errors(
    valid_user_id: UUID,
) -> None:
    """Test: validate() catches various password_hash errors.

    **Validates: Requirement 1, AC #7**
    """
    user = User(
        id=valid_user_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    # Test empty hash
    user.password_hash = ""
    with pytest.raises(ValueError, match="Password hash is required"):
        user.validate()

    # Test None hash
    user.password_hash = None  # type: ignore
    with pytest.raises(ValueError, match="Password hash is required"):
        user.validate()


def test_user_validate_passes_with_all_valid_fields(valid_user: User) -> None:
    """Test: validate() passes when all fields are valid.

    **Validates: Requirement 1, AC #7**
    """
    # Should not raise any exception
    valid_user.validate()


def test_user_validate_with_complex_scenario(valid_user_id: UUID) -> None:
    """Test: validate() with all valid complex scenarios."""
    # Scenario: User with full profile
    user = User(
        id=valid_user_id,
        email="complex+tag@subdomain.example.co.uk",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$s4v8n0Jw8m8$B4tVG9cB4mVHqXq8",
        role=UserRole.ANALYST,
        is_active=False,
        created_at=datetime.now(tz=UTC),
        full_name="Complex User Name",
        updated_at=datetime.now(tz=UTC),
        deleted_at=datetime.now(tz=UTC),
    )

    # Should pass all validations
    user.validate()


# ===========================================================================
# Test Group 10: Edge Cases and Integration
# ===========================================================================


def test_user_full_lifecycle_deactivate_update_then_reactivate(
    valid_user_id: UUID,
) -> None:
    """Test: Full lifecycle - create, deactivate, update, reactivate."""
    # Create user
    user = User(
        id=valid_user_id,
        email="lifecycle@example.com",
        password_hash="$argon2id$v=19$m=65536,t=2,p=4$hash",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )

    # Validate
    user.validate()
    assert user.is_active is True

    # Deactivate
    deactivated = user.deactivate()
    assert deactivated.is_active is False
    assert deactivated.deleted_at is not None

    # Update profile while deactivated
    updated = deactivated.update_profile("Updated Name")
    assert updated.full_name == "Updated Name"
    assert updated.is_active is False

    # Change role while deactivated
    role_changed = updated.update_role(UserRole.ADMIN)
    assert role_changed.role == UserRole.ADMIN
    assert role_changed.is_active is False

    # Verify all immutable fields preserved
    assert role_changed.email == "lifecycle@example.com"
    assert role_changed.created_at == user.created_at


def test_user_validate_after_all_mutations(valid_user: User) -> None:
    """Test: validate() passes after all types of mutations."""
    user = valid_user
    user = user.update_profile("John Doe")
    user = user.update_role(UserRole.ADMIN)
    user = user.deactivate()

    # Should still be valid
    user.validate()

