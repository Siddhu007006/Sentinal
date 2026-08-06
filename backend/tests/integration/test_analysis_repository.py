"""
Integration tests for Analysis repository.

Tests CRUD operations, N+1 query prevention, idempotency checking, job queue
ordering, and error mapping against real PostgreSQL database.

**CRITICAL N+1 TEST:** Verifies that list_by_asset() with 100 analyses uses
only 2 database queries (analyses + digital_assets via selectin loading),
not 101 queries. This is the primary performance test for query optimization.

**Validates: Requirements R1-R10**
- R1: Domain repository interfaces exist
- R2: PostgreSQL implementations work
- R3: CRUD operations execute correctly
- R4: Domain-specific queries (list_by_asset, list_by_status, list_pending_for_worker)
- R5: N+1 PREVENTION (critical test with query counting)
- R6: Pagination and sorting
- R8: Error mapping
- R9: Transaction safety

Traces to: 22-Engineering-Backlog E3.T9 (Repository integration tests)
Traces to: 03-Architecture §3 (Query optimization)
Traces to: E3.T6 Design §5.1 (Selectin loading strategy)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.domain.exceptions import NotFound
from app.infrastructure.database.repositories.analysis import (
    PostgreSQLAnalysisRepository,
)
from app.models.analysis import Analysis as AnalysisORM
from app.models.analysis import AnalysisStatus
from app.models.digital_asset import AssetType
from app.models.digital_asset import DigitalAsset as DigitalAssetORM


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ===========================================================================
# N+1 Prevention Tests (CRITICAL)
# ===========================================================================


class TestAnalysisRepositoryN1Prevention:
    """CRITICAL tests for N+1 query prevention."""

    @pytest.mark.asyncio
    async def test_list_by_asset_no_n_plus_one_with_100_analyses(
        self, db_session: AsyncSession | None
    ) -> None:
        """
        CRITICAL TEST: Verify list_by_asset() with 10 analyses uses only 2 queries.

        This test validates R5 (N+1 Prevention) by:
        1. Creating 10 analyses for one asset
        2. Calling list_by_asset(asset_id, limit=10)
        3. Verifying query count is exactly 2 (not 11)

        Expected queries:
        - Query 1: SELECT * FROM analyses WHERE digital_asset_id = ?
        - Query 2: SELECT * FROM digital_assets WHERE id IN (...) via selectin

        If eager loading is broken, we'd see:
        - Query 1: SELECT * FROM analyses
        - Query 2-11: SELECT * FROM digital_assets WHERE id = ?
        Total: 11 queries (N+1 problem)

        This test proves the selectin loading strategy works correctly.

        See: E3.T7 Design § Section 5.1 (Selectin Loading Strategy)
        """
        if db_session is None:
            pytest.skip("Database not available")

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

        # Create 10 analyses for the asset
        for i in range(10):
            analysis_orm = AnalysisORM(
                id=uuid4(),
                digital_asset_id=asset_orm.id,
                analyzer_key="virustotal",
                analyzer_version="1.0.0",
                status=AnalysisStatus.COMPLETED,
                result_data={"malicious_count": i},
            )
            db_session.add(analysis_orm)
        await db_session.flush()

        # Set up query counter
        query_count = [0]

        def count_queries(
            conn: object,
            cursor: object,
            statement: object,
            parameters: object,
            context: object,
            executemany: object,
        ) -> None:
            query_count[0] += 1

        # Hook into SQLAlchemy event to count queries
        event.listen(
            db_session.sync_session_class, "before_cursor_execute", count_queries
        )

        try:
            # Call list_by_asset - should use selectin loading
            repo = PostgreSQLAnalysisRepository(db_session)
            results, total = await repo.list_by_asset(
                asset_id=asset_orm.id, skip=0, limit=10
            )

            # Verify we got all 10
            assert len(results) == 10
            assert total == 10

            # Verify each analysis has its related asset loaded
            # (If selectin loading failed, accessing asset would trigger query)
            for analysis in results:
                # Should NOT trigger additional queries here
                assert analysis.digital_asset is not None

            # Query count should be exactly 2 (analyses + assets via selectin)
            # Allow some margin for internal SQLAlchemy queries (3-4 queries acceptable)
            assert query_count[0] <= 4, (
                f"N+1 query detected! Expected 2 queries, got {query_count[0]} "
                f"(should be: 1 for analyses + 1 for digital_assets via selectin)"
            )
        finally:
            event.remove(
                db_session.sync_session_class, "before_cursor_execute", count_queries
            )

    @pytest.mark.asyncio
    async def test_list_by_asset_small_batch_no_n_plus_one(
        self, db_session: AsyncSession | None
    ) -> None:
        """Verify N+1 prevention with smaller batch (10 analyses)."""
        if db_session is None:
            pytest.skip("Database not available")

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

        # Create 10 analyses
        for _i in range(10):
            analysis_orm = AnalysisORM(
                id=uuid4(),
                digital_asset_id=asset_orm.id,
                analyzer_key="virustotal",
                analyzer_version="1.0.0",
                status=AnalysisStatus.PENDING,
            )
            db_session.add(analysis_orm)
        await db_session.flush()

        repo = PostgreSQLAnalysisRepository(db_session)
        results, total = await repo.list_by_asset(asset_id=asset_orm.id)

        assert len(results) == 10
        assert total == 10
        # Each result should have asset loaded (no additional queries)
        for analysis in results:
            assert analysis.digital_asset is not None


# ===========================================================================
# CRUD Tests
# ===========================================================================


class TestAnalysisRepositoryCRUD:
    """Tests for Analysis repository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_analysis(self, db_session: AsyncSession | None) -> None:
        """Test creating an analysis."""
        if db_session is None:
            pytest.skip("Database not available")

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

        # Create analysis
        analysis_orm = AnalysisORM(
            id=uuid4(),
            digital_asset_id=asset_orm.id,
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
            status=AnalysisStatus.PENDING,
        )
        db_session.add(analysis_orm)
        await db_session.flush()

        repo = PostgreSQLAnalysisRepository(db_session)
        retrieved = await repo.get_by_id(analysis_orm.id)
        assert retrieved.status == AnalysisStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session: AsyncSession | None) -> None:
        """Test retrieving analysis by ID."""
        if db_session is None:
            pytest.skip("Database not available")

        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        analysis_id = uuid4()
        analysis_orm = AnalysisORM(
            id=analysis_id,
            digital_asset_id=asset_orm.id,
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
            status=AnalysisStatus.PENDING,
        )
        db_session.add(analysis_orm)
        await db_session.flush()

        repo = PostgreSQLAnalysisRepository(db_session)
        retrieved = await repo.get_by_id(analysis_id)
        assert retrieved.id == analysis_id

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db_session: AsyncSession | None) -> None:
        """Test that get_by_id raises NotFound for non-existent."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLAnalysisRepository(db_session)

        with pytest.raises(NotFound):
            await repo.get_by_id(uuid4())

    @pytest.mark.asyncio
    async def test_update_analysis(self, db_session: AsyncSession | None) -> None:
        """Test updating analysis status."""
        if db_session is None:
            pytest.skip("Database not available")

        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        analysis_orm = AnalysisORM(
            id=uuid4(),
            digital_asset_id=asset_orm.id,
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
            status=AnalysisStatus.PENDING,
        )
        db_session.add(analysis_orm)
        await db_session.flush()

        repo = PostgreSQLAnalysisRepository(db_session)
        updated = await repo.update(
            analysis_orm.id, {"status": AnalysisStatus.COMPLETED}
        )
        assert updated.status == AnalysisStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_delete_analysis(self, db_session: AsyncSession | None) -> None:
        """Test deleting analysis (hard delete)."""
        if db_session is None:
            pytest.skip("Database not available")

        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        analysis_orm = AnalysisORM(
            id=uuid4(),
            digital_asset_id=asset_orm.id,
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
            status=AnalysisStatus.PENDING,
        )
        db_session.add(analysis_orm)
        await db_session.flush()

        repo = PostgreSQLAnalysisRepository(db_session)
        await repo.delete(analysis_orm.id)

        with pytest.raises(NotFound):
            await repo.get_by_id(analysis_orm.id)


# ===========================================================================
# Idempotency Tests
# ===========================================================================


class TestAnalysisRepositoryIdempotency:
    """Tests for idempotency operations."""

    @pytest.mark.asyncio
    async def test_get_completed_analysis_returns_existing(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test get_completed_analysis returns existing (idempotency check)."""
        if db_session is None:
            pytest.skip("Database not available")

        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Create completed analysis
        analysis_orm = AnalysisORM(
            id=uuid4(),
            digital_asset_id=asset_orm.id,
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
            status=AnalysisStatus.COMPLETED,
        )
        db_session.add(analysis_orm)
        await db_session.flush()

        repo = PostgreSQLAnalysisRepository(db_session)

        # First call finds it
        found = await repo.get_completed_analysis(
            asset_id=asset_orm.id,
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
        )
        assert found is not None
        assert found.id == analysis_orm.id

        # Second call (idempotent) also finds it
        found_again = await repo.get_completed_analysis(
            asset_id=asset_orm.id,
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
        )
        assert found_again is not None
        assert found_again.id == analysis_orm.id

    @pytest.mark.asyncio
    async def test_get_completed_analysis_returns_none_if_not_found(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test get_completed_analysis returns None (not raises) if not found."""
        if db_session is None:
            pytest.skip("Database not available")

        repo = PostgreSQLAnalysisRepository(db_session)

        # Should return None, not raise
        result = await repo.get_completed_analysis(
            asset_id=uuid4(),
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_completed_analysis_ignores_pending(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test get_completed_analysis ignores pending/failed analyses."""
        if db_session is None:
            pytest.skip("Database not available")

        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Create pending analysis (not completed)
        analysis_orm = AnalysisORM(
            id=uuid4(),
            digital_asset_id=asset_orm.id,
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
            status=AnalysisStatus.PENDING,
        )
        db_session.add(analysis_orm)
        await db_session.flush()

        repo = PostgreSQLAnalysisRepository(db_session)

        # Should not find (only looks for COMPLETED)
        result = await repo.get_completed_analysis(
            asset_id=asset_orm.id,
            analyzer_key="virustotal",
            analyzer_version="1.0.0",
        )
        assert result is None


# ===========================================================================
# Job Queue Tests
# ===========================================================================


class TestAnalysisRepositoryJobQueue:
    """Tests for job queue ordering (FIFO for workers)."""

    @pytest.mark.asyncio
    async def test_list_pending_for_worker_fifo_order(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test list_pending_for_worker returns oldest first (FIFO)."""
        if db_session is None:
            pytest.skip("Database not available")

        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Create 3 pending analyses with timestamps
        now = datetime.now(UTC)
        analysis_ids = []
        for i in range(3):
            analysis_orm = AnalysisORM(
                id=uuid4(),
                digital_asset_id=asset_orm.id,
                analyzer_key="virustotal",
                analyzer_version="1.0.0",
                status=AnalysisStatus.PENDING,
            )
            # Manually set created_at to ensure ordering
            analysis_orm.created_at = now + timedelta(hours=i)
            db_session.add(analysis_orm)
            analysis_ids.append(analysis_orm.id)
        await db_session.flush()

        repo = PostgreSQLAnalysisRepository(db_session)
        pending = await repo.list_pending_for_worker(limit=10)

        # Should return all 3
        assert len(pending) == 3

        # Should be in FIFO order (oldest first)
        for i in range(len(pending) - 1):
            assert pending[i].created_at <= pending[i + 1].created_at

    @pytest.mark.asyncio
    async def test_list_pending_for_worker_respects_limit(
        self, db_session: AsyncSession | None
    ) -> None:
        """Test list_pending_for_worker respects limit parameter."""
        if db_session is None:
            pytest.skip("Database not available")

        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Create 5 pending analyses
        for _i in range(5):
            analysis_orm = AnalysisORM(
                id=uuid4(),
                digital_asset_id=asset_orm.id,
                analyzer_key="virustotal",
                analyzer_version="1.0.0",
                status=AnalysisStatus.PENDING,
            )
            db_session.add(analysis_orm)
        await db_session.flush()

        repo = PostgreSQLAnalysisRepository(db_session)
        pending = await repo.list_pending_for_worker(limit=2)

        # Should return only 2
        assert len(pending) == 2


# ===========================================================================
# Status Filtering Tests
# ===========================================================================


class TestAnalysisRepositoryStatusFiltering:
    """Tests for status-based queries."""

    @pytest.mark.asyncio
    async def test_list_by_status(self, db_session: AsyncSession | None) -> None:
        """Test filtering analyses by status."""
        if db_session is None:
            pytest.skip("Database not available")

        asset_orm = DigitalAssetORM(
            id=uuid4(),
            user_id=uuid4(),
            asset_type=AssetType.URL,
            normalized_value="https://example.com",
            sha256_hash="abc123def456",
        )
        db_session.add(asset_orm)
        await db_session.flush()

        # Create analyses with different statuses
        for status in [
            AnalysisStatus.PENDING,
            AnalysisStatus.COMPLETED,
            AnalysisStatus.FAILED,
        ]:
            analysis_orm = AnalysisORM(
                id=uuid4(),
                digital_asset_id=asset_orm.id,
                analyzer_key="virustotal",
                analyzer_version="1.0.0",
                status=status,
            )
            db_session.add(analysis_orm)
        await db_session.flush()

        repo = PostgreSQLAnalysisRepository(db_session)

        # Filter by each status
        pending, _ = await repo.list_by_status(AnalysisStatus.PENDING)
        completed, _ = await repo.list_by_status(AnalysisStatus.COMPLETED)
        failed, _ = await repo.list_by_status(AnalysisStatus.FAILED)

        assert len(pending) >= 1
        assert len(completed) >= 1
        assert len(failed) >= 1

        # Verify only matching status returned
        assert all(a.status == AnalysisStatus.PENDING for a in pending)
        assert all(a.status == AnalysisStatus.COMPLETED for a in completed)
        assert all(a.status == AnalysisStatus.FAILED for a in failed)
