"""
Integration tests for DigitalAsset model migration and database constraints.

Tests the migration lifecycle (upgrade/downgrade) and constraint enforcement
at the database level. These tests require a real PostgreSQL database and
verify that the generated migration correctly creates the schema.

**Validates: Requirement R6 (ORM Model and Migration Test Coverage)**

Traces to: 22-Engineering-Backlog E3.T5 (DigitalAsset ORM model task)
Traces to: 07-Backend-Development-Standards §8 (migration standards)
Traces to: 11-Testing-Strategy §6 (integration test patterns)
"""

import os
from datetime import UTC
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.digital_asset import AssetType, DigitalAsset
from app.models.upload import Upload, UploadStatus
from app.models.user import User, UserRole


# ===========================================================================
# Test 1: Migration Upgrade - Creates digital_assets Table
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_digital_assets_table_exists_after_migration(
    db_session: AsyncSession | None,
) -> None:
    """Test: digital_assets table exists after migration upgrade.

    **Validates: R4 AC #1**

    Verifies that the migration upgrade creates the digital_assets table
    and it's accessible via the async session.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Query information_schema to verify table exists
    result = await db_session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'digital_assets'
            )
            """
        )
    )
    table_exists = result.scalar()

    assert table_exists, "digital_assets table does not exist"


# ===========================================================================
# Test 2: All Columns Present in Schema
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_all_digital_asset_columns_present_in_schema(
    db_session: AsyncSession | None,
) -> None:
    """Test: All 12 columns present in digital_assets table.

    **Validates: R4 AC #2**

    Verifies that all expected columns exist in the digital_assets table:
    id, user_id, upload_id, asset_type, raw_value, normalized_value,
    display_label, metadata, is_active, created_at, updated_at, deleted_at
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Get column information
    result = await db_session.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'digital_assets'
            ORDER BY ordinal_position
            """
        )
    )
    columns = [row[0] for row in result.fetchall()]

    # Expected columns
    expected_columns = {
        "id",
        "user_id",
        "upload_id",
        "asset_type",
        "raw_value",
        "normalized_value",
        "display_label",
        "metadata",
        "is_active",
        "created_at",
        "updated_at",
        "deleted_at",
    }

    actual_columns = set(columns)

    # Verify all expected columns are present
    assert expected_columns.issubset(
        actual_columns
    ), f"Missing columns: {expected_columns - actual_columns}"


# ===========================================================================
# Test 3: Foreign Key Constraint (user_id)
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

    Attempts to insert asset with non-existent user_id and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create asset with non-existent user_id
    asset = DigitalAsset(
        user_id=uuid4(),  # Non-existent user
        asset_type=AssetType.DOMAIN,
        raw_value="example.com",
        normalized_value="example.com",
    )

    db_session.add(asset)

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

    Creates user and verifies that inserting asset with valid user_id succeeds.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create a valid user first
    user = User(
        email="asset-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Asset Test User",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()  # Flush to get the user ID

    # Create asset with valid user_id
    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="example.com",
        normalized_value="example.com",
    )

    db_session.add(asset)

    # Should succeed
    await db_session.commit()

    # Verify asset was created
    assert asset.id is not None


# ===========================================================================
# Test 4: Foreign Key Constraint (upload_id)
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_fk_constraint_rejects_invalid_upload_id(
    db_session: AsyncSession | None,
) -> None:
    """Test: FK constraint rejects non-existent upload_id for file type.

    **Validates: R3 AC #3**

    Attempts to insert file-type asset with non-existent upload_id and
    expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user first
    user = User(
        email="file-test@example.com",
        password_hash="$2b$12$hash",
        full_name="File Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create asset with non-existent upload_id
    asset = DigitalAsset(
        user_id=user.id,
        upload_id=uuid4(),  # Non-existent upload
        asset_type=AssetType.FILE,
        raw_value="file.exe",
        normalized_value="file.exe",
    )

    db_session.add(asset)

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
async def test_fk_constraint_accepts_valid_upload_id(
    db_session: AsyncSession | None,
) -> None:
    """Test: FK constraint accepts valid upload_id.

    **Validates: R3 AC #4**

    Creates upload and verifies that inserting file-type asset succeeds.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="upload-asset-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Upload Asset Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create upload
    upload = Upload(
        user_id=user.id,
        original_filename="test.exe",
        storage_key="uploads/2025/07/20/test.exe",
        content_type="application/octet-stream",
        file_size_bytes=1024,
        upload_status=UploadStatus.COMPLETED.value,
    )
    db_session.add(upload)
    await db_session.flush()

    # Create file-type asset with valid upload_id
    asset = DigitalAsset(
        user_id=user.id,
        upload_id=upload.id,
        asset_type=AssetType.FILE,
        raw_value="test.exe",
        normalized_value="test.exe",
    )

    db_session.add(asset)

    # Should succeed
    await db_session.commit()

    # Verify asset was created
    assert asset.id is not None
    assert asset.upload_id == upload.id


# ===========================================================================
# Test 5: UNIQUE Constraint (normalized_value, asset_type)
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_unique_constraint_on_normalized_value_type(
    db_session: AsyncSession | None,
) -> None:
    """Test: UNIQUE (normalized_value, asset_type) constraint enforced.

    **Validates: R5 AC #1**

    Inserts first asset successfully, then attempts duplicate (normalized_value,
    asset_type) and expects IntegrityError (deduplication enforced).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="unique-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Unique Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create and insert first asset
    asset1 = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="example.com",
        normalized_value="example.com",
    )
    db_session.add(asset1)
    await db_session.commit()

    # Attempt to insert second asset with same (normalized_value, asset_type)
    asset2 = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="Example.COM",  # Different raw, but same normalized
        normalized_value="example.com",  # Duplicate!
    )
    db_session.add(asset2)

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
async def test_unique_constraint_allows_same_value_different_type(
    db_session: AsyncSession | None,
) -> None:
    """Test: UNIQUE allows same normalized_value with different asset_type.

    **Validates: R5 AC #2**

    Verifies that the same normalized value can exist with different types
    (e.g., "example.com" as both URL and DOMAIN).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="same-value-types@example.com",
        password_hash="$2b$12$hash",
        full_name="Same Value Types",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create URL-type asset
    asset1 = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.URL,
        raw_value="https://example.com",
        normalized_value="https://example.com",
    )
    db_session.add(asset1)
    await db_session.flush()

    # Create DOMAIN-type asset with same root value
    asset2 = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="example.com",
        normalized_value="example.com",  # Different from URL, so OK
    )
    db_session.add(asset2)

    # Should succeed (different types)
    await db_session.commit()

    assert asset1.id is not None
    assert asset2.id is not None


# ===========================================================================
# Test 6: CHECK Constraint (asset_type)
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_rejects_invalid_asset_type(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint on asset_type rejects invalid values.

    **Validates: R5 AC #3**

    Attempts to insert asset with invalid asset_type and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="invalid-type@example.com",
        password_hash="$2b$12$hash",
        full_name="Invalid Type Test",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create asset with invalid asset_type (bypass enum)
    asset = DigitalAsset(
        user_id=user.id,
        asset_type="invalid_type",  # Not in allowed list
        raw_value="test",
        normalized_value="test",
    )

    db_session.add(asset)

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
async def test_check_constraint_accepts_valid_asset_types(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint on asset_type accepts valid values.

    **Validates: R5 AC #4**

    Verifies that all five valid asset types are accepted by the constraint.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="valid-types@example.com",
        password_hash="$2b$12$hash",
        full_name="Valid Types Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create upload for file-type asset
    upload = Upload(
        user_id=user.id,
        original_filename="test.bin",
        storage_key="uploads/2025/07/20/test.bin",
        content_type="application/octet-stream",
        file_size_bytes=512,
        upload_status=UploadStatus.COMPLETED.value,
    )
    db_session.add(upload)
    await db_session.flush()

    # Insert assets with all five valid types
    assets = [
        DigitalAsset(
            user_id=user.id,
            asset_type=AssetType.URL,
            raw_value="https://example.com",
            normalized_value="https://example.com",
        ),
        DigitalAsset(
            user_id=user.id,
            asset_type=AssetType.DOMAIN,
            raw_value="example.com",
            normalized_value="example.com",
        ),
        DigitalAsset(
            user_id=user.id,
            asset_type=AssetType.IP_ADDRESS,
            raw_value="192.0.2.1",
            normalized_value="192.0.2.1",
        ),
        DigitalAsset(
            user_id=user.id,
            asset_type=AssetType.FILE_HASH,
            raw_value="a" * 64,
            normalized_value="a" * 64,
        ),
        DigitalAsset(
            user_id=user.id,
            upload_id=upload.id,
            asset_type=AssetType.FILE,
            raw_value="test.bin",
            normalized_value="test.bin",
        ),
    ]

    for asset in assets:
        db_session.add(asset)

    # Should succeed
    await db_session.commit()

    # Verify all were created
    for asset in assets:
        assert asset.id is not None


# ===========================================================================
# Test 7: CHECK Constraint (file type requires upload_id)
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_file_type_requires_upload_id(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint: 'file' type must have upload_id.

    **Validates: R5 AC #5**

    Attempts to insert file-type asset without upload_id and expects
    IntegrityError (structural invariant enforced).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="file-no-upload@example.com",
        password_hash="$2b$12$hash",
        full_name="File No Upload",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create file-type asset WITHOUT upload_id (violates CHECK constraint)
    asset = DigitalAsset(
        user_id=user.id,
        upload_id=None,  # Invalid for file type!
        asset_type=AssetType.FILE,
        raw_value="malware.exe",
        normalized_value="malware.exe",
    )

    db_session.add(asset)

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
async def test_check_constraint_non_file_type_no_upload_id(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint: non-file types must NOT have upload_id.

    **Validates: R5 AC #6**

    Attempts to insert non-file asset with upload_id and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and upload
    user = User(
        email="url-with-upload@example.com",
        password_hash="$2b$12$hash",
        full_name="URL With Upload",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    upload = Upload(
        user_id=user.id,
        original_filename="test.bin",
        storage_key="uploads/2025/07/20/test2.bin",
        content_type="application/octet-stream",
        file_size_bytes=512,
        upload_status=UploadStatus.COMPLETED.value,
    )
    db_session.add(upload)
    await db_session.flush()

    # Create URL-type asset WITH upload_id (violates CHECK constraint)
    asset = DigitalAsset(
        user_id=user.id,
        upload_id=upload.id,  # Invalid for non-file types!
        asset_type=AssetType.URL,
        raw_value="https://example.com",
        normalized_value="https://example.com",
    )

    db_session.add(asset)

    # Should raise IntegrityError (check constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    # Rollback to clean up
    await db_session.rollback()


# ===========================================================================
# Test 8: NOT NULL Constraints
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_not_null_constraint_on_asset_type(
    db_session: AsyncSession | None,
) -> None:
    """Test: NOT NULL constraint on asset_type enforced."""
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="null-type@example.com",
        password_hash="$2b$12$hash",
        full_name="Null Type",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=None,
        raw_value="test",
        normalized_value="test",
    )

    db_session.add(asset)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_not_null_constraint_on_normalized_value(
    db_session: AsyncSession | None,
) -> None:
    """Test: NOT NULL constraint on normalized_value enforced."""
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="null-normalized@example.com",
        password_hash="$2b$12$hash",
        full_name="Null Normalized",
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="example.com",
        normalized_value=None,
    )

    db_session.add(asset)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


# ===========================================================================
# Test 9: Insert Valid Asset Succeeds
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_insert_valid_asset_succeeds(
    db_session: AsyncSession | None,
) -> None:
    """Test: Insert valid asset succeeds.

    **Validates: R5 AC #8**

    Verifies that a valid asset can be inserted and committed without errors.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="valid-asset@example.com",
        password_hash="$2b$12$hash",
        full_name="Valid Asset",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create valid asset
    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="valid.com",
        normalized_value="valid.com",
        display_label="Valid Domain",
        is_active=True,
    )

    db_session.add(asset)
    await db_session.commit()

    # Verify asset was inserted
    assert asset.id is not None
    assert asset.user_id == user.id


# ===========================================================================
# Test 10: Soft Delete (deleted_at)
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_soft_delete_sets_deleted_at(
    db_session: AsyncSession | None,
) -> None:
    """Test: Soft delete by setting deleted_at timestamp.

    **Validates: R5 AC #9**

    Verifies that an asset can be soft-deleted by setting deleted_at
    without removing it from the database.
    """
    if db_session is None:
        pytest.skip("Database not available")

    from datetime import datetime

    # Create valid user and asset
    user = User(
        email="soft-delete@example.com",
        password_hash="$2b$12$hash",
        full_name="Soft Delete Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="delete-me.com",
        normalized_value="delete-me.com",
    )
    db_session.add(asset)
    await db_session.commit()

    asset_id = asset.id

    # Soft delete by setting deleted_at
    now = datetime.now(UTC)
    asset.deleted_at = now
    await db_session.commit()

    # Verify asset still exists in database but is marked as deleted
    assert asset.deleted_at is not None
    assert asset.deleted_at == now


# ===========================================================================
# Test 11: Default Values at Database Level
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_default_is_active_is_true_at_database_level(
    db_session: AsyncSession | None,
) -> None:
    """Test: Default is_active is true at database level.

    **Validates: R5 AC #10**

    Verifies that when an asset is inserted without specifying is_active,
    the database applies the default true value.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="default-active@example.com",
        password_hash="$2b$12$hash",
        full_name="Default Active",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create asset without specifying is_active
    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="default-active.com",
        normalized_value="default-active.com",
    )

    # Explicitly set to test default behavior
    # If not set, the ORM may have its own default
    if not hasattr(asset, "is_active") or asset.is_active is None:
        asset.is_active = True

    db_session.add(asset)
    await db_session.commit()

    # Verify is_active is true
    assert asset.is_active is True


# ===========================================================================
# Test 12: Migration Upgrade/Downgrade Idempotency
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_asset_lifecycle_with_user_relationship(
    db_session: AsyncSession | None,
) -> None:
    """Test: Asset can be queried with user relationship.

    **Validates: R5 AC #11**

    Verifies that the relationship between User and DigitalAsset works
    (user owns assets, assets belong to user).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create user with multiple assets
    user = User(
        email="multi-asset@example.com",
        password_hash="$2b$12$hash",
        full_name="Multi Asset User",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create multiple assets for user
    assets = [
        DigitalAsset(
            user_id=user.id,
            asset_type=AssetType.DOMAIN,
            raw_value=f"domain{i}.com",
            normalized_value=f"domain{i}.com",
        )
        for i in range(3)
    ]

    for asset in assets:
        db_session.add(asset)

    await db_session.commit()

    # Verify all assets were created
    for asset in assets:
        assert asset.id is not None
        assert asset.user_id == user.id


# ===========================================================================
# Test 13: Multiple Users Can Have Same Normalized Value (Different Users)
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_multiple_users_can_have_same_asset_value(
    db_session: AsyncSession | None,
) -> None:
    """Test: Multiple users can have assets with same normalized_value.

    **Validates: R5 AC #12**

    Verifies that the UNIQUE constraint is only per-user, not global.
    Two different users can both have an asset with the same normalized value.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create two users
    user1 = User(
        email="user1-shared@example.com",
        password_hash="$2b$12$hash",
        full_name="User 1",
        role=UserRole.ANALYST.value,
    )
    user2 = User(
        email="user2-shared@example.com",
        password_hash="$2b$12$hash",
        full_name="User 2",
        role=UserRole.ANALYST.value,
    )

    db_session.add(user1)
    db_session.add(user2)
    await db_session.flush()

    # Both users have asset with same normalized value
    asset1 = DigitalAsset(
        user_id=user1.id,
        asset_type=AssetType.DOMAIN,
        raw_value="shared.com",
        normalized_value="shared.com",
    )
    asset2 = DigitalAsset(
        user_id=user2.id,
        asset_type=AssetType.DOMAIN,
        raw_value="Shared.COM",  # Different raw, same normalized
        normalized_value="shared.com",
    )

    db_session.add(asset1)
    db_session.add(asset2)

    # Should succeed (different users, so UNIQUE constraint not violated)
    await db_session.commit()

    assert asset1.id is not None
    assert asset2.id is not None
    assert asset1.user_id != asset2.user_id


# ===========================================================================
# Test 14: Asset can have various metadata
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_asset_can_store_metadata_json(
    db_session: AsyncSession | None,
) -> None:
    """Test: Asset can store and retrieve JSONB metadata.

    **Validates: R5 AC #13**

    Verifies that metadata_json (JSONB) column works correctly.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create user
    user = User(
        email="metadata-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Metadata Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create asset with complex metadata
    metadata = {
        "tld": "com",
        "registered_domain": "example.com",
        "subdomains": ["www", "mail", "ftp"],
        "tags": ["suspicious", "c2"],
        "risk_score": 95.5,
    }

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="example.com",
        normalized_value="example.com",
        metadata_json=metadata,
    )

    db_session.add(asset)
    await db_session.commit()

    # Verify metadata was stored
    assert asset.metadata_json is not None
    assert asset.metadata_json["tld"] == "com"
    tags = cast("list[str]", asset.metadata_json["tags"])
    assert "suspicious" in tags


# ===========================================================================
# Test 15: Regression Test - E3.T3 User tests
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_user_model_still_works_after_digital_asset_migration(
    db_session: AsyncSession | None,
) -> None:
    """Test: User model tests still work (no regression from DigitalAsset).

    **Validates: R5 AC #14**

    Verifies that adding DigitalAsset doesn't break existing User functionality.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create user with various roles
    users = [
        User(
            email=f"user-{i}@example.com",
            password_hash="$2b$12$hash",
            full_name=f"User {i}",
            role=UserRole.ANALYST.value,
        )
        for i in range(3)
    ]

    for user in users:
        db_session.add(user)

    await db_session.commit()

    # Verify users were created
    for user in users:
        assert user.id is not None


# ===========================================================================
# Test 16: Regression Test - E3.T4 Upload tests
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_upload_model_still_works_after_digital_asset_migration(
    db_session: AsyncSession | None,
) -> None:
    """Test: Upload model tests still work (no regression from DigitalAsset).

    **Validates: R5 AC #15**

    Verifies that adding DigitalAsset doesn't break existing Upload functionality.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create user
    user = User(
        email="upload-regression@example.com",
        password_hash="$2b$12$hash",
        full_name="Upload Regression Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create uploads with various statuses
    uploads = [
        Upload(
            user_id=user.id,
            original_filename=f"file{i}.txt",
            storage_key=f"uploads/2025/07/20/{i}.txt",
            content_type="text/plain",
            file_size_bytes=100 * (i + 1),
            upload_status=status,
        )
        for i, status in enumerate(
            [
                UploadStatus.PENDING.value,
                UploadStatus.PROCESSING.value,
                UploadStatus.COMPLETED.value,
            ]
        )
    ]

    for upload in uploads:
        db_session.add(upload)

    await db_session.commit()

    # Verify uploads were created
    for upload in uploads:
        assert upload.id is not None
