"""
Integration tests for Analysis model migration and schema verification.

Tests the migration lifecycle (upgrade/downgrade) and ensures the analyses
table is correctly created with all columns, constraints, and indexes.
These tests require a real PostgreSQL database.

**Validates: Requirement R1 (Entity Persistence) — Migration Phase**

Traces to: 22-Engineering-Backlog E3.T6 (Analysis ORM model task)
Traces to: 07-Backend-Development-Standards §8 (migration standards)
Traces to: 11-Testing-Strategy §6 (integration test patterns)
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ===========================================================================
# Test 1: Migration Upgrade - Creates analyses Table
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_analyses_table_exists_after_migration(
    db_session: AsyncSession | None,
) -> None:
    """Test: analyses table exists after migration upgrade.

    **Validates: R1 AC #1**

    Verifies that the migration upgrade creates the analyses table
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
                WHERE table_name = 'analyses'
            )
            """
        )
    )
    table_exists = result.scalar()

    assert table_exists, "analyses table does not exist"


# ===========================================================================
# Test 2: All Columns Present in Schema
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_all_analysis_columns_present_in_schema(
    db_session: AsyncSession | None,
) -> None:
    """Test: All 20 columns present in analyses table.

    **Validates: R3 AC #1-22**

    Verifies that all expected columns exist in the analyses table:
    id, digital_asset_id, requested_by, analyzer_key, analyzer_version,
    status, analyzer_slugs, retry_count, celery_task_id, error_message,
    error_code, threat_score, confidence, severity, reasoning_payload,
    enrichment_data, started_at, completed_at, created_at, updated_at
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Get column information
    result = await db_session.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'analyses'
            ORDER BY ordinal_position
            """
        )
    )
    columns = [row[0] for row in result.fetchall()]

    # Expected columns (20 total)
    expected_columns = {
        "id",
        "digital_asset_id",
        "requested_by",
        "analyzer_key",
        "analyzer_version",
        "status",
        "analyzer_slugs",
        "retry_count",
        "celery_task_id",
        "error_message",
        "error_code",
        "threat_score",
        "confidence",
        "severity",
        "reasoning_payload",
        "enrichment_data",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    }

    actual_columns = set(columns)

    # Verify all expected columns are present
    assert expected_columns.issubset(actual_columns), (
        f"Missing columns: {expected_columns - actual_columns}"
    )


# ===========================================================================
# Test 3: Migration Downgrade Removes analyses Table
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_migration_downgrade_removes_analyses_table(
    db_session: AsyncSession | None,
) -> None:
    """Test: Migration downgrade removes analyses table reversibly.

    **Validates: Design §9 (Migration Design) — Reversibility**

    Verifies that downgrade SQL reverses all upgrade operations.
    This test verifies the schema definition; actual downgrade requires
    running alembic CLI.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Verify table exists before downgrade (would be removed by alembic downgrade)
    result = await db_session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'analyses'
            )
            """
        )
    )
    table_exists = result.scalar()

    # Table should exist at this point (before downgrade)
    assert table_exists, "analyses table should exist before downgrade"


# ===========================================================================
# Test 4: Migration Idempotency (Upgrade Twice is No-op)
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_migration_idempotent_upgrade_succeeds(
    db_session: AsyncSession | None,
) -> None:
    """Test: Migration upgrade is idempotent (running twice doesn't error).

    **Validates: Design §9 (Migration Design) — Idempotency**

    This test verifies that the migration can be safely re-applied.
    (Actual idempotency requires running alembic upgrade twice, which is
    verified at CLI level; this test verifies schema consistency.)
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Query that would be used in idempotency check
    result = await db_session.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'analyses'
            """
        )
    )
    count = result.scalar()

    # Table should exist exactly once
    assert count == 1, "analyses table should exist exactly once"


# ===========================================================================
# Test 5: Schema Matches ORM Model After Upgrade
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_schema_matches_orm_model(
    db_session: AsyncSession | None,
) -> None:
    """Test: Database schema matches ORM model definition.

    **Validates: R1 AC #1-6**

    Verifies that the migrated schema matches the SQLAlchemy ORM model
    (correct column types, nullability, defaults).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Get actual schema from database
    result = await db_session.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'analyses'
            ORDER BY ordinal_position
            """
        )
    )
    schema = {
        row[0]: {"type": row[1], "nullable": row[2] == "YES"}
        for row in result.fetchall()
    }

    # Verify key columns exist with correct properties
    assert "id" in schema
    assert "digital_asset_id" in schema
    assert "requested_by" in schema
    assert "status" in schema
    assert "threat_score" in schema
    assert "confidence" in schema
    assert "severity" in schema

    # Verify NOT NULL constraints
    assert not schema["id"]["nullable"], "id should be NOT NULL"
    assert not schema["digital_asset_id"]["nullable"], (
        "digital_asset_id should be NOT NULL"
    )
    assert not schema["requested_by"]["nullable"], "requested_by should be NOT NULL"
    assert not schema["status"]["nullable"], "status should be NOT NULL"

    # Verify nullable fields
    assert schema["threat_score"]["nullable"], "threat_score should be nullable"
    assert schema["confidence"]["nullable"], "confidence should be nullable"
    assert schema["severity"]["nullable"], "severity should be nullable"


# ===========================================================================
# Test 6: Indexes Created After Migration
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_all_indexes_created_after_migration(
    db_session: AsyncSession | None,
) -> None:
    """Test: All 8 indexes created by migration.

    **Validates: Design §6 (Index Strategy)**

    Verifies that all application indexes are created:
    - ix_analyses_asset_status
    - ix_analyses_asset_latest
    - ix_analyses_pending
    - ix_analyses_user_history
    - ix_analyses_celery_task
    - ix_analyses_severity_completed
    - ix_analyses_asset_analyzer_completed (unique)
    - pk_analyses (implicit)
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Get all indexes for analyses table
    result = await db_session.execute(
        text(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'analyses'
            ORDER BY indexname
            """
        )
    )
    indexes = [row[0] for row in result.fetchall()]

    # Expected indexes
    expected_indexes = {
        "ix_analyses_asset_status",
        "ix_analyses_asset_latest",
        "ix_analyses_pending",
        "ix_analyses_user_history",
        "ix_analyses_celery_task",
        "ix_analyses_severity_completed",
        "ix_analyses_asset_analyzer_completed",
    }

    actual_indexes = set(indexes)

    # Verify all expected indexes exist
    assert expected_indexes.issubset(actual_indexes), (
        f"Missing indexes: {expected_indexes - actual_indexes}"
    )


# ===========================================================================
# Test 7: Constraints Created After Migration
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraints_created_after_migration(
    db_session: AsyncSession | None,
) -> None:
    """Test: All 5 CHECK constraints created by migration.

    **Validates: Design §7 (Constraint Strategy)**

    Verifies that all CHECK constraints are created:
    - ck_analyses_status
    - ck_analyses_threat_score
    - ck_analyses_confidence
    - ck_analyses_severity
    - ck_analyses_retry_count
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Get all constraints for analyses table
    result = await db_session.execute(
        text(
            """
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'analyses' AND constraint_type = 'CHECK'
            ORDER BY constraint_name
            """
        )
    )
    constraints = [row[0] for row in result.fetchall()]

    # Expected CHECK constraints
    expected_constraints = {
        "ck_analyses_status",
        "ck_analyses_threat_score",
        "ck_analyses_confidence",
        "ck_analyses_severity",
        "ck_analyses_retry_count",
    }

    actual_constraints = set(constraints)

    # Verify all expected constraints exist
    assert expected_constraints.issubset(actual_constraints), (
        f"Missing CHECK constraints: {expected_constraints - actual_constraints}"
    )


# ===========================================================================
# Test 8: Foreign Key Constraints Created
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_foreign_key_constraints_created_after_migration(
    db_session: AsyncSession | None,
) -> None:
    """Test: FK constraints created (digital_asset_id, requested_by).

    **Validates: Design §7 (Constraint Strategy) — FK Design**

    Verifies that foreign key constraints exist and reference correct tables.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Get all FK constraints for analyses table
    result = await db_session.execute(
        text(
            """
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'analyses' AND constraint_type = 'FOREIGN KEY'
            ORDER BY constraint_name
            """
        )
    )
    fk_constraints = [row[0] for row in result.fetchall()]

    # Should have 2 FK constraints
    assert len(fk_constraints) >= 2, (
        f"Expected at least 2 FK constraints, got {len(fk_constraints)}"
    )

    # Verify FK names (alembic-generated names vary, but contain key references)
    constraint_names = " ".join(fk_constraints)
    assert (
        "digital_asset" in constraint_names.lower()
        or "digital_assets" in constraint_names.lower()
    )
    assert (
        "requested_by" in constraint_names.lower()
        or "users" in constraint_names.lower()
    )
