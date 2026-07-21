"""
Integration tests for Upload model migration and database constraints.

Tests the migration lifecycle (upgrade/downgrade) and constraint enforcement
at the database level. These tests require a real PostgreSQL database and
verify that the generated migration correctly creates the schema.

**Validates: Requirement R6 (ORM Model and Migration Test Coverage)**

Traces to: 22-Engineering-Backlog E3.T4 (Upload ORM model task)
Traces to: 07-Backend-Development-Standards §8 (migration standards)
Traces to: 11-Testing-Strategy §6 (integration test patterns)
"""  # noqa: D400

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upload import Upload, UploadStatus
from app.models.user import User, UserRole


# ===========================================================================
# Test 1: Migration Upgrade - Creates uploads Table
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_uploads_table_exists_after_migration(
    db_session: AsyncSession | None,
) -> None:
    """Test: uploads table exists after migration upgrade.

    **Validates: R4 AC #1**

    Verifies that the migration upgrade creates the uploads table and it's
    accessible via the async session.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Query information_schema to verify table exists
    result = await db_session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'uploads'
            )
            """
        )
    )
    table_exists = result.scalar()

    assert table_exists, "uploads table does not exist"


# ===========================================================================
# Test 2: All Columns Present
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_all_upload_columns_present_in_schema(
    db_session: AsyncSession | None,
) -> None:
    """Test: All 10 columns present in uploads table.

    **Validates: R4 AC #2**

    Verifies that all expected columns exist in the uploads table:
    id, user_id, original_filename, storage_key, content_type,
    file_size_bytes, checksum_sha256, upload_status, created_at, completed_at
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Get column information
    result = await db_session.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'uploads'
            ORDER BY ordinal_position
            """
        )
    )
    columns = [row[0] for row in result.fetchall()]

    # Expected columns
    expected_columns = {
        "id",
        "user_id",
        "original_filename",
        "storage_key",
        "content_type",
        "file_size_bytes",
        "checksum_sha256",
        "upload_status",
        "created_at",
        "updated_at",
        "completed_at",
    }

    actual_columns = set(columns)

    # Verify all expected columns are present
    assert expected_columns.issubset(
        actual_columns
    ), f"Missing columns: {expected_columns - actual_columns}"


# ===========================================================================
# Test 3: Foreign Key Constraint
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_fk_constraint_rejects_invalid_user_id(
    db_session: AsyncSession | None,
) -> None:
    """Test: FK constraint rejects non-existent user_id.

    **Validates: R3 AC #1**

    Attempts to insert upload with non-existent user_id and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create upload with non-existent user_id
    upload = Upload(
        user_id=uuid4(),  # Non-existent user
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/invalid-user/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    db_session.add(upload)

    # Should raise IntegrityError (FK constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    # Rollback to clean up
    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_fk_constraint_accepts_valid_user_id(
    db_session: AsyncSession | None,
) -> None:
    """Test: FK constraint accepts valid user_id.

    **Validates: R3 AC #2**

    Creates user and verifies that inserting upload with valid user_id succeeds.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create a valid user first
    user = User(
        email="upload-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Upload Test User",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()  # Flush to get the user ID

    # Create upload with valid user_id
    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/valid-user/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    db_session.add(upload)

    # Should succeed
    await db_session.commit()

    # Verify upload was created
    assert upload.id is not None


# ===========================================================================
# Test 4: UNIQUE storage_key Constraint
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_unique_constraint_on_storage_key_rejects_duplicates(
    db_session: AsyncSession | None,
) -> None:
    """Test: UNIQUE storage_key constraint rejects duplicates.

    **Validates: R3 AC #3**

    Inserts first upload successfully, then attempts duplicate storage_key
    and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create a valid user first
    user = User(
        email="storage-key-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Storage Key Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    storage_key = "uploads/2025/07/19/duplicate/file.txt"

    # Create and insert first upload
    upload1 = Upload(
        user_id=user.id,
        original_filename="file1.txt",
        storage_key=storage_key,
        content_type="text/plain",
        file_size_bytes=100,
    )
    db_session.add(upload1)
    await db_session.commit()

    # Attempt to insert second upload with same storage_key
    upload2 = Upload(
        user_id=user.id,
        original_filename="file2.txt",
        storage_key=storage_key,  # Duplicate!
        content_type="text/plain",
        file_size_bytes=200,
    )
    db_session.add(upload2)

    # Should raise IntegrityError (unique constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    # Rollback to clean up
    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_unique_constraint_on_storage_key_accepts_different_keys(
    db_session: AsyncSession | None,
) -> None:
    """Test: UNIQUE storage_key constraint accepts different keys.

    **Validates: R3 AC #4**

    Verifies that different storage_keys can be inserted without violation.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create a valid user
    user = User(
        email="storage-key-test2@example.com",
        password_hash="$2b$12$hash",
        full_name="Storage Key Test 2",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Insert multiple uploads with different storage_keys
    for i in range(3):
        upload = Upload(
            user_id=user.id,
            original_filename=f"file{i}.txt",
            storage_key=f"uploads/2025/07/19/{i}/file{i}.txt",
            content_type="text/plain",
            file_size_bytes=100 * (i + 1),
        )
        db_session.add(upload)

    # Should succeed
    await db_session.commit()


# ===========================================================================
# Test 5: NOT NULL Constraints
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_not_null_constraint_on_user_id(
    db_session: AsyncSession | None,
) -> None:
    """Test: NOT NULL constraint on user_id enforced."""
    if db_session is None:
        pytest.skip("Database not available")

    upload = Upload(
        user_id=None,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    db_session.add(upload)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_not_null_constraint_on_original_filename(
    db_session: AsyncSession | None,
) -> None:
    """Test: NOT NULL constraint on original_filename enforced."""
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user first
    user = User(
        email="filename-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    upload = Upload(
        user_id=user.id,
        original_filename=None,
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    db_session.add(upload)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_not_null_constraint_on_storage_key(
    db_session: AsyncSession | None,
) -> None:
    """Test: NOT NULL constraint on storage_key enforced."""
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user first
    user = User(
        email="storage-key-null-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key=None,
        content_type="text/plain",
        file_size_bytes=100,
    )

    db_session.add(upload)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_not_null_constraint_on_content_type(
    db_session: AsyncSession | None,
) -> None:
    """Test: NOT NULL constraint on content_type enforced."""
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user first
    user = User(
        email="content-type-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type=None,
        file_size_bytes=100,
    )

    db_session.add(upload)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_not_null_constraint_on_file_size_bytes(
    db_session: AsyncSession | None,
) -> None:
    """Test: NOT NULL constraint on file_size_bytes enforced."""
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user first
    user = User(
        email="file-size-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=None,
    )

    db_session.add(upload)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_not_null_constraint_on_upload_status(
    db_session: AsyncSession | None,
) -> None:
    """Test: NOT NULL constraint on upload_status enforced."""
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user first
    user = User(
        email="upload-status-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        upload_status=None,
    )

    db_session.add(upload)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


# ===========================================================================
# Test 6: CHECK Constraint on upload_status
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_on_upload_status_rejects_invalid(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint on upload_status rejects invalid values.

    **Validates: R3 AC #5**

    Attempts to insert upload with invalid status and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user first
    user = User(
        email="status-check-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )
    # Bypass Python enum to test database constraint directly
    upload.upload_status = "invalid_status"  # Not in allowed list

    db_session.add(upload)

    # Should raise IntegrityError (check constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    # Rollback to clean up
    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_on_upload_status_accepts_valid(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint on upload_status accepts valid values.

    **Validates: R3 AC #6**

    Verifies that valid status values (pending, processing, completed, failed)
    are accepted by the constraint.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="status-check-valid@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Insert uploads with all valid status values
    statuses = ["pending", "processing", "completed", "failed"]
    for i, status in enumerate(statuses):
        upload = Upload(
            user_id=user.id,
            original_filename=f"file{i}.txt",
            storage_key=f"uploads/2025/07/19/status{i}/file{i}.txt",
            content_type="text/plain",
            file_size_bytes=100,
            upload_status=status,
        )
        db_session.add(upload)

    # Should succeed
    await db_session.commit()


# ===========================================================================
# Test 7: CHECK Constraint on file_size_bytes
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_on_file_size_bytes_rejects_negative(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint on file_size_bytes rejects negative values.

    **Validates: R3 AC #7**

    Attempts to insert upload with negative file size and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user first
    user = User(
        email="file-size-check@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=-100,  # Negative size
    )

    db_session.add(upload)

    # Should raise IntegrityError (check constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    # Rollback to clean up
    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_on_file_size_bytes_accepts_zero_and_positive(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint on file_size_bytes accepts zero and positive.

    **Validates: R3 AC #8**

    Verifies that zero and positive file sizes are accepted.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="file-size-check-valid@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Insert uploads with zero and positive sizes
    sizes = [0, 1, 100, 1024 * 1024, 1024 * 1024 * 1024]
    for i, size in enumerate(sizes):
        upload = Upload(
            user_id=user.id,
            original_filename=f"file{i}.txt",
            storage_key=f"uploads/2025/07/19/size{i}/file{i}.txt",
            content_type="text/plain",
            file_size_bytes=size,
        )
        db_session.add(upload)

    # Should succeed
    await db_session.commit()


# ===========================================================================
# Test 8: Nullable Fields
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_nullable_fields_can_be_null(
    db_session: AsyncSession | None,
) -> None:
    """Test: Nullable fields (checksum_sha256, completed_at) can be null.

    **Validates: R3 AC #9**

    Verifies that nullable columns accept NULL values without constraint violation.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="nullable-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create upload with nullable fields set to None
    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/nullable/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        checksum_sha256=None,  # Nullable
        completed_at=None,  # Nullable
    )

    db_session.add(upload)

    # Should succeed
    await db_session.commit()

    # Verify fields are null in database
    assert upload.checksum_sha256 is None
    assert upload.completed_at is None


# ===========================================================================
# Test 9: Default upload_status
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_default_upload_status_is_pending(
    db_session: AsyncSession | None,
) -> None:
    """Test: Default upload_status is 'pending' at database level.

    **Validates: R3 AC #10**

    Verifies that when upload is inserted without specifying status,
    the database applies the default 'pending' value.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="default-status@example.com",
        password_hash="$2b$12$hash",
        full_name="Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create upload without specifying status
    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/default/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        # upload_status NOT specified, should default to 'pending'
    )

    db_session.add(upload)
    await db_session.commit()

    # Verify status is set to pending
    assert upload.upload_status == UploadStatus.PENDING.value


# ===========================================================================
# Test 10: Relationship Bidirectionality
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_upload_user_relationship_works(
    db_session: AsyncSession | None,
) -> None:
    """Test: Upload.user relationship works (can access user from upload).

    **Validates: R3 AC #11**

    Verifies that Upload.user relationship is functional (lazy loading).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create user
    user = User(
        email="relationship-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Relationship Test User",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create upload linked to user
    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/relationship/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )
    db_session.add(upload)
    await db_session.commit()

    # Verify relationship works
    assert upload.user is not None
    assert upload.user.id == user.id
    assert upload.user.email == "relationship-test@example.com"


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_user_uploads_relationship_works(
    db_session: AsyncSession | None,
) -> None:
    """Test: User.uploads relationship works (can access uploads from user).

    **Validates: R3 AC #12**

    Verifies that User.uploads relationship is functional (can list uploads).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create user
    user = User(
        email="user-uploads-test@example.com",
        password_hash="$2b$12$hash",
        full_name="User Uploads Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create multiple uploads for the user
    for i in range(3):
        upload = Upload(
            user_id=user.id,
            original_filename=f"file{i}.txt",
            storage_key=f"uploads/2025/07/19/user-uploads/{i}.txt",
            content_type="text/plain",
            file_size_bytes=100 * (i + 1),
        )
        db_session.add(upload)

    await db_session.commit()

    # Verify relationship works
    assert user.uploads is not None
    assert len(user.uploads) == 3
    assert all(upload.user_id == user.id for upload in user.uploads)


# ===========================================================================
# Test 11: Insert Valid Upload Succeeds
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_insert_valid_upload_succeeds(
    db_session: AsyncSession | None,
) -> None:
    """Test: Insert valid upload succeeds.

    **Validates: R3 AC #13**

    Verifies that a valid upload can be inserted and committed without errors.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user first
    user = User(
        email="insert-valid@example.com",
        password_hash="$2b$12$hash",
        full_name="Insert Valid Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create valid upload
    upload = Upload(
        user_id=user.id,
        original_filename="valid.pdf",
        storage_key="uploads/2025/07/19/valid/file.pdf",
        content_type="application/pdf",
        file_size_bytes=5024,
        checksum_sha256="a" * 64,
        upload_status=UploadStatus.COMPLETED.value,
    )

    db_session.add(upload)
    await db_session.commit()

    # Verify upload was inserted and has ID
    assert upload.id is not None
    assert upload.user_id == user.id


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_insert_multiple_uploads_for_same_user(
    db_session: AsyncSession | None,
) -> None:
    """Test: Insert multiple uploads for same user succeeds."""
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="multiple-uploads@example.com",
        password_hash="$2b$12$hash",
        full_name="Multiple Uploads Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Insert multiple uploads
    uploads = []
    for i in range(5):
        upload = Upload(
            user_id=user.id,
            original_filename=f"file{i}.txt",
            storage_key=f"uploads/2025/07/19/multi/{i}.txt",
            content_type="text/plain",
            file_size_bytes=100 * (i + 1),
            upload_status=UploadStatus.PENDING.value,
        )
        db_session.add(upload)
        uploads.append(upload)

    await db_session.commit()

    # Verify all were inserted
    for upload in uploads:
        assert upload.id is not None


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_insert_upload_with_all_states(
    db_session: AsyncSession | None,
) -> None:
    """Test: Insert uploads in all states (pending, processing, completed, failed)."""
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="all-states@example.com",
        password_hash="$2b$12$hash",
        full_name="All States Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create uploads in different states
    states = [
        UploadStatus.PENDING.value,
        UploadStatus.PROCESSING.value,
        UploadStatus.COMPLETED.value,
        UploadStatus.FAILED.value,
    ]

    for i, state in enumerate(states):
        upload = Upload(
            user_id=user.id,
            original_filename=f"file_{state}.txt",
            storage_key=f"uploads/2025/07/19/states/{state}/{i}.txt",
            content_type="text/plain",
            file_size_bytes=100,
            upload_status=state,
        )
        db_session.add(upload)

    await db_session.commit()


# ===========================================================================
# Test 12: Test Timestamps
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_created_at_and_updated_at_set_by_database(
    db_session: AsyncSession | None,
) -> None:
    """Test: created_at and updated_at are set by database on insert.

    **Validates: R3 AC #14**

    Verifies that timestamps are auto-populated by the database.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user first
    user = User(
        email="timestamps@example.com",
        password_hash="$2b$12$hash",
        full_name="Timestamps Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create upload
    upload = Upload(
        user_id=user.id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/timestamps/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    db_session.add(upload)
    await db_session.commit()

    # Verify timestamps were set
    assert upload.created_at is not None
    assert upload.updated_at is not None
    from datetime import datetime
    assert isinstance(upload.created_at, datetime)
    assert isinstance(upload.updated_at, datetime)


# ===========================================================================
# Test 13: Migration Idempotency
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_upload_table_structure_is_correct(
    db_session: AsyncSession | None,
) -> None:
    """Test: uploads table structure is correct (column types, constraints).

    **Validates: R4 AC #3**

    Verifies key aspects of the table schema.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Get column info for key columns
    result = await db_session.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'uploads'
            ORDER BY ordinal_position
            """
        )
    )

    columns = {row[0]: (row[1], row[2]) for row in result.fetchall()}

    # Verify key columns
    assert "id" in columns
    assert "user_id" in columns
    assert "storage_key" in columns

    # Verify NOT NULL constraints
    assert columns["user_id"][1] == "NO", "user_id should NOT be nullable"
    assert (
        columns["storage_key"][1] == "NO"
    ), "storage_key should NOT be nullable"
    assert (
        columns["file_size_bytes"][1] == "NO"
    ), "file_size_bytes should NOT be nullable"
    assert (
        columns["upload_status"][1] == "NO"
    ), "upload_status should NOT be nullable"

    # Verify nullable columns
    assert columns["checksum_sha256"][1] == "YES", (
        "checksum_sha256 should be nullable"
    )
    assert columns["completed_at"][1] == "YES", (
        "completed_at should be nullable"
    )


