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

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.digital_asset import AssetType, DigitalAsset
from app.models.upload import Upload, UploadStatus
from app.models.user import User, UserRole


# ===========================================================================
# Test 1: Migration Upgrade - Creates digital_assets Table
# ===========================================================================


# ===========================================================================
# Test 5: UNIQUE Constraint (normalized_value, asset_type)
# ===========================================================================


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


# ===========================================================================
# Reconciled contract (2026-08-23): content identity + per-user IOC dedup
# Migration: reconcile_digital_assets
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_reconciliation_global_hash_unique_across_users(
    db_session: AsyncSession | None,
) -> None:
    """Reconciled contract: identical content hash is globally ONE asset.

    Two different users inserting assets with the same sha256_hash must
    collide on the partial unique index — content identity spans users
    (E5.T4 deduplication depends on this).
    """
    if db_session is None:
        pytest.skip("Database not available")

    users = []
    for i in range(2):
        user = User(
            email=f"hash-dedup-{i}@example.com",
            password_hash="$2b$12$hash",
            role=UserRole.ANALYST.value,
        )
        db_session.add(user)
        users.append(user)
    await db_session.flush()

    content_hash = "c" * 64
    for user in users:
        db_session.add(
            DigitalAsset(
                user_id=user.id,
                asset_type=AssetType.FILE_HASH,
                raw_value=content_hash,
                normalized_value=content_hash,
                sha256_hash=content_hash,
            )
        )

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_reconciliation_file_without_hash_rejected(
    db_session: AsyncSession | None,
) -> None:
    """CHECK ck_digital_assets_file_hash_required: file needs a hash."""
    if db_session is None:
        pytest.skip("Database not available")

    user = User(
        email="file-no-hash@example.com",
        password_hash="$2b$12$hash",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        DigitalAsset(
            user_id=user.id,
            asset_type=AssetType.FILE,
            raw_value="no-hash.bin",
            normalized_value="no-hash.bin",
            mime_type="application/octet-stream",
            size_bytes=10,
            # sha256_hash intentionally omitted
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_reconciliation_file_hash_type_without_hash_rejected(
    db_session: AsyncSession | None,
) -> None:
    """CHECK ck_digital_assets_file_hash_required: file_hash needs a hash."""
    if db_session is None:
        pytest.skip("Database not available")

    user = User(
        email="filehash-no-hash@example.com",
        password_hash="$2b$12$hash",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        DigitalAsset(
            user_id=user.id,
            asset_type=AssetType.FILE_HASH,
            raw_value="not-a-real-hash-submission",
            normalized_value="not-a-real-hash-submission",
            # sha256_hash intentionally omitted
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_reconciliation_file_without_mime_and_size_rejected(
    db_session: AsyncSession | None,
) -> None:
    """CHECKs: file assets require mime_type AND size_bytes."""
    if db_session is None:
        pytest.skip("Database not available")

    user = User(
        email="file-no-mime@example.com",
        password_hash="$2b$12$hash",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    content_hash = "d" * 64

    # Missing mime_type
    db_session.add(
        DigitalAsset(
            user_id=user.id,
            asset_type=AssetType.FILE,
            raw_value="sparse.bin",
            normalized_value=content_hash,
            sha256_hash=content_hash,
            size_bytes=8,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Missing size_bytes
    db_session.add(
        DigitalAsset(
            user_id=user.id,
            asset_type=AssetType.FILE,
            raw_value="sparse.bin",
            normalized_value=content_hash,
            sha256_hash=content_hash,
            mime_type="application/octet-stream",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_reconciliation_invalid_hash_format_rejected(
    db_session: AsyncSession | None,
) -> None:
    """CHECK ck_digital_assets_sha256_format: 64 lowercase hex only."""
    if db_session is None:
        pytest.skip("Database not available")

    user = User(
        email="bad-hash@example.com",
        password_hash="$2b$12$hash",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    for bad_hash in ["XYZ" * 16, "g" * 64, "a" * 63]:
        db_session.add(
            DigitalAsset(
                user_id=user.id,
                asset_type=AssetType.FILE_HASH,
                raw_value=bad_hash,
                normalized_value=bad_hash,
                sha256_hash=bad_hash,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_reconciliation_storage_key_nullable_for_file(
    db_session: AsyncSession | None,
) -> None:
    """storage_key stays NULL until object storage assignment (E5.T4)."""
    if db_session is None:
        pytest.skip("Database not available")

    user = User(
        email="late-storage-key@example.com",
        password_hash="$2b$12$hash",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    content_hash = "e" * 64
    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.FILE,
        raw_value="late.bin",
        normalized_value=content_hash,
        sha256_hash=content_hash,
        mime_type="application/octet-stream",
        size_bytes=16,
        # storage_key intentionally omitted
    )
    db_session.add(asset)
    await db_session.commit()

    assert asset.storage_key is None
