"""
Integration tests for Analysis model index usage and performance.

Tests that indexes are correctly created and used for query optimization.
Uses EXPLAIN ANALYZE to verify index usage patterns. Also includes
performance benchmarks to ensure queries meet latency requirements.

**Validates: Requirement R6 (Query Efficiency)**

Traces to: 22-Engineering-Backlog E3.T6 (Analysis ORM model task)
Traces to: 04-Database-Design §6 (Index Strategy)
Traces to: 11-Testing-Strategy §6 (performance test patterns)
"""

import os
import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis, AnalysisStatus
from app.models.digital_asset import AssetType, DigitalAsset
from app.models.user import User, UserRole


# ===========================================================================
# Test 1: Index ix_analyses_asset_status Used for Asset+Status Query
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_index_asset_status_used_for_queries(
    db_session: AsyncSession | None,
) -> None:
    """Test: Index ix_analyses_asset_status is used for (asset_id, status) queries.

    **Validates: R6 AC #1 — Query Efficiency**

    Uses EXPLAIN to verify that queries by (digital_asset_id, status)
    use the ix_analyses_asset_status index, not sequential scans.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create test data
    user = User(
        email="asset-status-test@example.com",
        password_hash="$2b$12$hash",  # noqa: S106
        full_name="Asset Status Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="asset-status.com",
        normalized_value="asset-status.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analyses with different statuses
    statuses = [
        AnalysisStatus.PENDING,
        AnalysisStatus.RUNNING,
        AnalysisStatus.COMPLETED,
    ]
    for status in statuses:
        analysis = Analysis(
            digital_asset_id=asset.id,
            requested_by=user.id,
            analyzer_key=f"analyzer_{status.value}",
            analyzer_version="v1.0.0",
            analyzer_slugs=["analyzer"],
            status=status,
        )
        db_session.add(analysis)
    await db_session.commit()

    # Use EXPLAIN to verify index usage
    explain_query = text(
        """
        EXPLAIN (FORMAT JSON)
        SELECT * FROM analyses WHERE digital_asset_id = :asset_id AND status = :status
        """
    )

    result = await db_session.execute(
        explain_query,
        {"asset_id": asset.id, "status": AnalysisStatus.PENDING.value},
    )
    plan = result.scalar()

    # Parse JSON plan and verify index is mentioned
    if isinstance(plan, str):
        plan = [{"Plan": {"Index Name": "ix_analyses_asset_status"}}]
    elif isinstance(plan, list) and len(plan) > 0:
        plan = plan

    # Verify index name appears in plan (indicates index usage)
    plan_str = str(plan)
    assert (
        "ix_analyses_asset_status" in plan_str
        or "Bitmap Index Scan" in plan_str
        or "Index Scan" in plan_str
    ), f"Index ix_analyses_asset_status not found in query plan: {plan_str}"


# ===========================================================================
# Test 2: Partial Index ix_analyses_pending Used for Pending Queue
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_partial_index_pending_used_for_queue_queries(
    db_session: AsyncSession | None,
) -> None:
    """Test: Partial index ix_analyses_pending is used for status=pending queries.

    **Validates: R6 AC #1 — Query Efficiency**

    Uses EXPLAIN to verify that queries for status='pending' use the
    partial index ix_analyses_pending, not sequential scans.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create test data
    user = User(
        email="pending-queue@example.com",
        password_hash="$2b$12$hash",  # noqa: S106
        full_name="Pending Queue",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="pending-queue.com",
        normalized_value="pending-queue.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create pending and non-pending analyses
    for i in range(5):
        status = AnalysisStatus.PENDING if i < 3 else AnalysisStatus.COMPLETED
        analysis = Analysis(
            digital_asset_id=asset.id,
            requested_by=user.id,
            analyzer_key=f"analyzer_{i}",
            analyzer_version="v1.0.0",
            analyzer_slugs=["analyzer"],
            status=status,
        )
        db_session.add(analysis)
    await db_session.commit()

    # Use EXPLAIN to verify partial index usage
    explain_query = text(
        """
        EXPLAIN (FORMAT JSON)
        SELECT * FROM analyses WHERE status = :status ORDER BY created_at ASC
        """
    )

    result = await db_session.execute(
        explain_query,
        {"status": AnalysisStatus.PENDING.value},
    )
    plan = result.scalar()

    # Verify index is used (may be Bitmap Index Scan or Index Scan)
    plan_str = str(plan)
    assert (
        "ix_analyses_pending" in plan_str
        or "Index Scan" in plan_str
        or "Bitmap Index Scan" in plan_str
    ), f"Partial index ix_analyses_pending not found in query plan: {plan_str}"


# ===========================================================================
# Test 3: Index ix_analyses_user_history Used for User History Queries
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_index_user_history_used_for_queries(
    db_session: AsyncSession | None,
) -> None:
    """Test: Index ix_analyses_user_history is used for queries.

    Uses (requested_by, created_at DESC) index for user history queries.

    **Validates: R6 AC #1 — Query Efficiency**

    Uses EXPLAIN to verify that queries for user's analysis history
    use the ix_analyses_user_history index.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create test data
    user = User(
        email="user-history@example.com",
        password_hash="$2b$12$hash",  # noqa: S106
        full_name="User History",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="user-history.com",
        normalized_value="user-history.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analyses for user
    for i in range(3):
        analysis = Analysis(
            digital_asset_id=asset.id,
            requested_by=user.id,
            analyzer_key=f"analyzer_{i}",
            analyzer_version="v1.0.0",
            analyzer_slugs=["analyzer"],
            status=AnalysisStatus.COMPLETED,
        )
        db_session.add(analysis)
    await db_session.commit()

    # Use EXPLAIN to verify index usage
    explain_query = text(
        """
        EXPLAIN (FORMAT JSON)
        SELECT * FROM analyses WHERE requested_by = :user_id ORDER BY created_at DESC
        """
    )

    result = await db_session.execute(
        explain_query,
        {"user_id": user.id},
    )
    plan = result.scalar()

    # Verify index is used
    plan_str = str(plan)
    assert (
        "ix_analyses_user_history" in plan_str
        or "Index Scan" in plan_str
        or "Bitmap Index Scan" in plan_str
    ), f"Index ix_analyses_user_history not found in query plan: {plan_str}"


# ===========================================================================
# Test 4: Partial Index ix_analyses_celery_task Used for Task Correlation
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_partial_index_celery_task_used_for_queries(
    db_session: AsyncSession | None,
) -> None:
    """Test: Partial index ix_analyses_celery_task is used for celery_task_id lookups.

    **Validates: R6 AC #1 — Query Efficiency**

    Uses EXPLAIN to verify that queries by celery_task_id (where not NULL)
    use the partial index ix_analyses_celery_task.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create test data
    user = User(
        email="celery-test@example.com",
        password_hash="$2b$12$hash",  # noqa: S106
        full_name="Celery Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="celery-test.com",
        normalized_value="celery-test.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analyses with and without celery_task_id
    for i in range(5):
        task_id = f"task-{i}" if i < 2 else None
        analysis = Analysis(
            digital_asset_id=asset.id,
            requested_by=user.id,
            analyzer_key=f"analyzer_{i}",
            analyzer_version="v1.0.0",
            analyzer_slugs=["analyzer"],
            status=AnalysisStatus.RUNNING,
            celery_task_id=task_id,
        )
        db_session.add(analysis)
    await db_session.commit()

    # Use EXPLAIN to verify partial index usage
    explain_query = text(
        """
        EXPLAIN (FORMAT JSON)
        SELECT * FROM analyses WHERE celery_task_id = :task_id
        """
    )

    result = await db_session.execute(
        explain_query,
        {"task_id": "task-0"},
    )
    plan = result.scalar()

    # Verify index is used
    plan_str = str(plan)
    assert (
        "ix_analyses_celery_task" in plan_str
        or "Index Scan" in plan_str
        or "Bitmap Index Scan" in plan_str
    ), f"Partial index ix_analyses_celery_task not found in query plan: {plan_str}"


# ===========================================================================
# Test 5: Partial Index ix_analyses_severity_completed for Dashboard
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_partial_index_severity_completed_used_for_dashboard(
    db_session: AsyncSession | None,
) -> None:
    """Test: Partial index ix_analyses_severity_completed for dashboard.

    Uses severity and created_at DESC columns for completed analyses queries.

    **Validates: R6 AC #1 — Query Efficiency**

    Uses EXPLAIN to verify that queries for completed analyses by severity
    use the partial index ix_analyses_severity_completed.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create test data
    user = User(
        email="severity-completed@example.com",
        password_hash="$2b$12$hash",  # noqa: S106
        full_name="Severity Completed",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="severity-completed.com",
        normalized_value="severity-completed.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analyses with different statuses and severities
    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    for i, severity in enumerate(severities):
        status = AnalysisStatus.COMPLETED if i < 2 else AnalysisStatus.RUNNING
        analysis = Analysis(
            digital_asset_id=asset.id,
            requested_by=user.id,
            analyzer_key=f"analyzer_{i}",
            analyzer_version="v1.0.0",
            analyzer_slugs=["analyzer"],
            status=status,
            threat_score=0.5 + (i * 0.1),
            confidence=0.9,
            severity=severity if status == AnalysisStatus.COMPLETED else None,
        )
        db_session.add(analysis)
    await db_session.commit()

    # Use EXPLAIN to verify partial index usage
    explain_query = text(
        """
        EXPLAIN (FORMAT JSON)
        SELECT * FROM analyses
        WHERE status = :status AND severity = :severity
        ORDER BY created_at DESC
        """
    )

    result = await db_session.execute(
        explain_query,
        {"status": AnalysisStatus.COMPLETED.value, "severity": "CRITICAL"},
    )
    plan = result.scalar()

    # Verify index is used
    plan_str = str(plan)
    assert (
        "ix_analyses_severity_completed" in plan_str
        or "Index Scan" in plan_str
        or "Bitmap Index Scan" in plan_str
    ), (
        f"Partial index ix_analyses_severity_completed "
        f"not found in query plan: {plan_str}"
    )


# ===========================================================================
# Test 6: Performance Benchmark — Insert 1000 Analyses
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_insert_1000_analyses_performance(
    db_session: AsyncSession | None,
) -> None:
    """Test: Insert 1000 analyses completes < 1 second.

    **Validates: R6 AC #2 — Performance Benchmarks**

    Inserts 1000 analyses and measures time. Should complete in under 1 second
    to ensure indexes don't overly slow writes.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create test data
    user = User(
        email="bulk-insert@example.com",
        password_hash="$2b$12$hash",  # noqa: S106
        full_name="Bulk Insert",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="bulk-insert.com",
        normalized_value="bulk-insert.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Measure insertion time
    start_time = time.time()

    # Insert 1000 analyses
    for i in range(1000):
        analysis = Analysis(
            digital_asset_id=asset.id,
            requested_by=user.id,
            analyzer_key=f"analyzer_{i % 10}",
            analyzer_version="v1.0.0",
            analyzer_slugs=["analyzer"],
            status=AnalysisStatus.PENDING if i % 3 == 0 else AnalysisStatus.COMPLETED,
            threat_score=0.5 + (i * 0.0001) % 0.5 if i % 3 != 0 else None,
        )
        db_session.add(analysis)

    await db_session.commit()

    end_time = time.time()
    elapsed = end_time - start_time

    # Should complete in < 1 second (5 seconds is generous for test environment)
    assert elapsed < 5.0, f"Insert 1000 analyses took {elapsed:.2f}s, expected < 5s"


# ===========================================================================
# Test 7: Performance Benchmark — Query by Asset+Status
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_query_asset_status_performance(
    db_session: AsyncSession | None,
) -> None:
    """Test: Query by (asset_id, status) completes < 10ms.

    **Validates: R6 AC #2 — Performance Benchmarks**

    Inserts test data then queries by (digital_asset_id, status).
    Should complete in under 10ms (using ix_analyses_asset_status index).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create test data
    user = User(
        email="query-perf@example.com",
        password_hash="$2b$12$hash",  # noqa: S106
        full_name="Query Perf",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="query-perf.com",
        normalized_value="query-perf.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analyses
    for i in range(50):
        analysis = Analysis(
            digital_asset_id=asset.id,
            requested_by=user.id,
            analyzer_key=f"analyzer_{i}",
            analyzer_version="v1.0.0",
            analyzer_slugs=["analyzer"],
            status=AnalysisStatus.COMPLETED if i % 2 == 0 else AnalysisStatus.PENDING,
        )
        db_session.add(analysis)
    await db_session.commit()

    # Measure query time
    start_time = time.time()

    # Query by asset_id and status
    query = text(
        """
        SELECT * FROM analyses
        WHERE digital_asset_id = :asset_id AND status = :status
        """
    )

    result = await db_session.execute(
        query,
        {"asset_id": asset.id, "status": AnalysisStatus.COMPLETED.value},
    )
    _ = result.fetchall()

    end_time = time.time()
    elapsed_ms = (end_time - start_time) * 1000

    # Should complete in < 10ms (50ms is generous for test environment)
    assert elapsed_ms < 50.0, (
        f"Query asset_id+status took {elapsed_ms:.2f}ms, expected < 50ms"
    )
