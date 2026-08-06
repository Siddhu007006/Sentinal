"""
Comprehensive integration tests for all Phase A repositories.

Tests basic CRUD operations for User, Upload, DigitalAsset, and Analysis
repositories. This file provides broad coverage ensuring all repositories
work correctly with PostgreSQL.

For detailed tests of specific functionality (N+1 prevention, soft-delete,
etc.), see specialized test files:
- test_user_repository.py (User-specific tests)
- test_analysis_repository.py (Analysis + N+1 prevention)
- test_upload_repository.py (Upload-specific tests)
- test_digital_asset_repository.py (DigitalAsset-specific tests)

**Validates: Requirements R1-R10**
- All CRUD operations across all 4 Phase A repositories
- Soft-delete filtering for User and DigitalAsset
- Basic error handling

Traces to: 22-Engineering-Backlog E3.T9 (Repository integration tests)
Traces to: E3.T7 Design §8 (Testing Strategy)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.exceptions import NotFound
from app.infrastructure.database.repositories.analysis import (
    PostgreSQLAnalysisRepository,
)
from app.infrastructure.database.repositories.digital_asset import (
    PostgreSQLDigitalAssetRepository,
)
from app.infrastructure.database.repositories.upload import (
    PostgreSQLUploadRepository,
)
from app.infrastructure.database.repositories.user import PostgreSQLUserRepository
from app.models.analysis import Analysis as AnalysisORM
from app.models.analysis import AnalysisStatus
from app.models.digital_asset import AssetType
from app.models.digital_asset import DigitalAsset as DigitalAssetORM
from app.models.upload import Upload as UploadORM
from app.models.user import User as UserORM


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ===========================================================================
# User Repository CRUD
# ===========================================================================


class TestAllRepositoriesUserCRUD:
    """Basic CRUD tests for UserRepository."""

    @pytest.mark.asyncio
    async def test_user_crud_cycle(self, db_session: AsyncSession | None) -> None:
        """Test complete CRUD cycle for user."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLUserRepository(db_session)

        # Create
        user_orm = UserORM(
            id=uuid4(),
            email="crud@example.com",
            password_hash="test_hash_crud",  # noqa: S106
            is_active=True,
            is_verified=False,
        )
        db_session.add(user_orm)
        await db_session.flush()

        # Read
        created = await repo.get_by_id(user_orm.id)
        assert created.email == "crud@example.com"

        # Update
        updated = await repo.update(user_orm.id, {"is_verified": True})
        assert updated.is_verified is True

        # Delete
        await repo.delete(user_orm.id)
        with pytest.raises(NotFound):
            await repo.get_by_id(user_orm.id)

    @pytest.mark.asyncio
    async def test_user_soft_delete_filtering(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test that soft-deleted users are filtered from list."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLUserRepository(db_session)

        # Create user
        user_orm = UserORM(
            id=uuid4(),
            email="softdel@example.com",
            password_hash="test_hash_softdel",  # noqa: S106
            is_active=True,
            is_verified=False,
        )
        db_session.add(user_orm)
        await db_session.flush()

        # Delete
        await repo.delete(user_orm.id)

        # Should not appear in list
        users, _total = await repo.list(skip=0, limit=100)
        user_ids = {u.id for u in users}
        assert user_orm.id not in user_ids


# ===========================================================================
# Upload Repository CRUD
# ===========================================================================


class TestAllRepositoriesUploadCRUD:
    """Basic CRUD tests for UploadRepository."""

    @pytest.mark.asyncio
    async def test_upload_crud_cycle(self, db_session: AsyncSession | None) -> None:
        """Test complete CRUD cycle for upload."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLUploadRepository(db_session)

        # Create
        user_id = uuid4()
        upload_orm = UploadORM(
            id=uuid4(),
            user_id=user_id,
            file_name="test.txt",
            file_size_bytes=1024,
            status="completed",
            storage_key="s3://bucket/key",
        )
        db_session.add(upload_orm)
        await db_session.flush()

        # Read
        created = await repo.get_by_id(upload_orm.id)
        assert created.file_name == "test.txt"

        # Update
        updated = await repo.update(upload_orm.id, {"status": "archived"})
        assert updated.status == "archived"

        # Delete
        await repo.delete(upload_orm.id)
        with pytest.raises(NotFound):
            await repo.get_by_id(upload_orm.id)

    @pytest.mark.asyncio
    async def test_upload_list_by_user(self, db_session: AsyncSession | None) -> None:
        """Test listing uploads by user."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLUploadRepository(db_session)

        user_id = uuid4()
        # Create 2 uploads for user
        for i in range(2):
            upload_orm = UploadORM(
                id=uuid4(),
                user_id=user_id,
                file_name=f"file{i}.txt",
                file_size_bytes=1024 * (i + 1),
                status="completed",
                storage_key=f"s3://bucket/key{i}",
            )
            db_session.add(upload_orm)
        await db_session.flush()

        # List by user
        uploads, _total = await repo.list_by_user(user_id, skip=0, limit=100)
        assert len(uploads) >= 2
        assert all(u.user_id == user_id for u in uploads)


# ===========================================================================
# DigitalAsset Repository CRUD
# ===========================================================================


class TestAllRepositoriesDigitalAssetCRUD:
    """Basic CRUD tests for DigitalAssetRepository."""

    @pytest.mark.asyncio
    async def test_asset_crud_cycle(self, db_session: AsyncSession | None) -> None:
        """Test complete CRUD cycle for digital asset."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLDigitalAssetRepository(db_session)

        # Create
        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Read
        created = await repo.get_by_id(asset_orm.id)
        assert created.asset_type == AssetType.URL

        # Update
        updated = await repo.update(asset_orm.id, {"asset_type": AssetType.IP})
        assert updated.asset_type == AssetType.IP

        # Delete
        await repo.delete(asset_orm.id)
        with pytest.raises(NotFound):
            await repo.get_by_id(asset_orm.id)

    @pytest.mark.asyncio
    async def test_asset_soft_delete_filtering(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test that soft-deleted assets are filtered from list."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLDigitalAssetRepository(db_session)

        # Create asset
        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Delete
        await repo.delete(asset_orm.id)

        # Should not appear in list
        assets, _total = await repo.list(skip=0, limit=100)
        asset_ids = {a.id for a in assets}
        assert asset_orm.id not in asset_ids

    @pytest.mark.asyncio
    async def test_asset_list_by_user(self, db_session: AsyncSession | None) -> None:
        """Test listing assets by user."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLDigitalAssetRepository(db_session)

        user_id = uuid4()
        # Create 2 assets for user
        for i in range(2):
            asset_orm = DigitalAssetORM(
                id=uuid4(),
                user_id=user_id,
                asset_type=AssetType.URL,
                normalized_value=f"https://example{i}.com",
                sha256_hash=f"hash{i}",
            )
            db_session.add(asset_orm)
        await db_session.flush()

        # List by user
        assets, _total = await repo.list_by_user(user_id, skip=0, limit=100)
        assert len(assets) >= 2
        assert all(a.user_id == user_id for a in assets)


# ===========================================================================
# Analysis Repository CRUD
# ===========================================================================


class TestAllRepositoriesAnalysisCRUD:
    """Basic CRUD tests for AnalysisRepository."""

    @pytest.mark.asyncio
    async def test_analysis_crud_cycle(self, db_session: AsyncSession | None) -> None:
        """Test complete CRUD cycle for analysis."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLAnalysisRepository(db_session)

        # Create asset first
        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Create
        analysis_orm = AnalysisORM(
            id=uuid4(),
            digital_asset_id=asset_orm.id,
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
            status=AnalysisStatus.PENDING,
        )
        db_session.add(analysis_orm)
        await db_session.flush()

        # Read
        created = await repo.get_by_id(analysis_orm.id)
        assert created.analyzer_key == "virustotal"

        # Update
        updated = await repo.update(
            analysis_orm.id, {"status": AnalysisStatus.COMPLETED}
        )
        assert updated.status == AnalysisStatus.COMPLETED

        # Delete
        await repo.delete(analysis_orm.id)
        with pytest.raises(NotFound):
            await repo.get_by_id(analysis_orm.id)

    @pytest.mark.asyncio
    async def test_analysis_list_by_asset(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test listing analyses by asset."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLAnalysisRepository(db_session)

        # Create asset
        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Create 2 analyses for asset
        for i in range(2):
            analysis_orm = AnalysisORM(
                id=uuid4(),
                digital_asset_id=asset_orm.id,
                analyzer_key=f"analyzer{i}",
                analyzer_version="1.0.0",
                status=AnalysisStatus.PENDING,
            )
            db_session.add(analysis_orm)
        await db_session.flush()

        # List by asset
        analyses, _total = await repo.list_by_asset(asset_orm.id, skip=0, limit=100)
        assert len(analyses) >= 2
        assert all(a.digital_asset_id == asset_orm.id for a in analyses)


# ===========================================================================
# Cross-Repository Consistency Tests
# ===========================================================================


class TestAllRepositoriesConsistency:
    """Tests for consistency across repositories."""

    @pytest.mark.asyncio
    async def test_user_can_have_multiple_assets(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test that user can have multiple assets."""
        if db_session is None:
            pytest.skip("Database not available")

        PostgreSQLUserRepository(db_session)
        asset_repo = PostgreSQLDigitalAssetRepository(db_session)

        # Create user
        user_orm = UserORM(
            id=uuid4(),
            email="multi@example.com",
            password_hash="test_hash_multi",  # noqa: S106
            is_active=True,
            is_verified=False,
        )
        db_session.add(user_orm)
        await db_session.flush()

        # Create 2 assets for user
        for i in range(2):
            asset_orm = DigitalAssetORM(
                id=uuid4(),
                user_id=user_orm.id,
                asset_type=AssetType.URL,
                normalized_value=f"https://example{i}.com",
                sha256_hash=f"hash{i}",
            )
            db_session.add(asset_orm)
        await db_session.flush()

        # List user's assets
        assets, _total = await asset_repo.list_by_user(user_orm.id)
        assert len(assets) >= 2

    @pytest.mark.asyncio
    async def test_asset_can_have_multiple_analyses(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test that asset can have multiple analyses."""
        if db_session is None:
            pytest.skip("Database not available")

        PostgreSQLDigitalAssetRepository(db_session)
        analysis_repo = PostgreSQLAnalysisRepository(db_session)

        # Create asset
        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Create 2 analyses for asset with different analyzers
        for i in range(2):
            analysis_orm = AnalysisORM(
                id=uuid4(),
                digital_asset_id=asset_orm.id,
                analyzer_key=f"analyzer{i}",
                analyzer_version="1.0.0",
                status=AnalysisStatus.PENDING,
            )
            db_session.add(analysis_orm)
        await db_session.flush()

        # List asset's analyses
        analyses, _total = await analysis_repo.list_by_asset(asset_orm.id)
        assert len(analyses) >= 2


# ===========================================================================
# Pagination Tests (All Repositories)
# ===========================================================================


class TestAllRepositoriesPagination:
    """Pagination tests across all repositories."""

    @pytest.mark.asyncio
    async def test_user_list_pagination(self, db_session: AsyncSession | None) -> None:
        """Test pagination in user list."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLUserRepository(db_session)

        # Create 3 users
        for i in range(3):
            user_orm = UserORM(
                id=uuid4(),
                email=f"page_user{i}@example.com",
                password_hash="test_hash_page",  # noqa: S106
                is_active=True,
                is_verified=False,
            )
            db_session.add(user_orm)
        await db_session.flush()

        # Get first page
        page1, _total = await repo.list(skip=0, limit=1)
        # Get second page
        page2, _total2 = await repo.list(skip=1, limit=1)

        assert len(page1) == 1
        assert len(page2) == 1
        # No overlap
        page1_ids = {u.id for u in page1}
        page2_ids = {u.id for u in page2}
        assert len(page1_ids & page2_ids) == 0

    @pytest.mark.asyncio
    async def test_analysis_list_pagination(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test pagination in analysis list."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLAnalysisRepository(db_session)

        # Create asset
        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Create 3 analyses
        for i in range(3):
            analysis_orm = AnalysisORM(
                id=uuid4(),
                digital_asset_id=asset_orm.id,
                analyzer_key=f"analyzer{i}",
                analyzer_version="1.0.0",
                status=AnalysisStatus.PENDING,
            )
            db_session.add(analysis_orm)
        await db_session.flush()

        # Get first page
        page1, _total = await repo.list_by_asset(asset_orm.id, skip=0, limit=1)
        # Get second page
        page2, _total2 = await repo.list_by_asset(asset_orm.id, skip=1, limit=1)

        assert len(page1) == 1
        assert len(page2) == 1


# ===========================================================================
# Error Handling Tests (All Repositories)
# ===========================================================================


class TestAllRepositoriesErrorHandling:
    """Error handling tests across all repositories."""

    @pytest.mark.asyncio
    async def test_user_get_by_id_not_found(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test user get_by_id raises NotFound."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLUserRepository(db_session)
        with pytest.raises(NotFound):
            await repo.get_by_id(uuid4())

    @pytest.mark.asyncio
    async def test_upload_get_by_id_not_found(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test upload get_by_id raises NotFound."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLUploadRepository(db_session)
        with pytest.raises(NotFound):
            await repo.get_by_id(uuid4())

    @pytest.mark.asyncio
    async def test_asset_get_by_id_not_found(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test asset get_by_id raises NotFound."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLDigitalAssetRepository(db_session)
        with pytest.raises(NotFound):
            await repo.get_by_id(uuid4())

    @pytest.mark.asyncio
    async def test_analysis_get_by_id_not_found(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test analysis get_by_id raises NotFound."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLAnalysisRepository(db_session)
        with pytest.raises(NotFound):
            await repo.get_by_id(uuid4())
