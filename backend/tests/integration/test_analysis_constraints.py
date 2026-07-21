"""
Integration tests for Analysis model database constraints.

Tests constraint enforcement at the database level: FK constraints,
CHECK constraints, and the partial unique index. These tests require
a real PostgreSQL database and verify that invalid operations are rejected.

**Validates: Requirements R5, R7, R10 (Referential Integrity, Idempotency, Lifecycle)**

Traces to: 22-Engineering-Backlog E3.T6 (Analysis ORM model task)
Traces to: 04-Database-Design §7 (Constraint strategy)
Traces to: 11-Testing-Strategy §6 (integration test patterns)
"""

import os
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis, AnalysisStatus
from app.models.digital_asset import AssetType, DigitalAsset
from app.models.user import User, UserRole


# ===========================================================================
# Test 1: FK Constraint — Invalid digital_asset_id Rejected
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_fk_constraint_rejects_invalid_digital_asset_id(
    db_session: AsyncSession | None,
) -> None:
    """Test: FK constraint rejects non-existent digital_asset_id.

    **Validates: R5 AC #1-3**

    Attempts to insert analysis with non-existent digital_asset_id
    and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user
    user = User(
        email="analysis-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Analysis Test User",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    # Create analysis with non-existent digital_asset_id
    analysis = Analysis(
        digital_asset_id=uuid4(),  # Non-existent asset
        requested_by=user.id,
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
    )

    db_session.add(analysis)

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
async def test_fk_constraint_accepts_valid_digital_asset_id(
    db_session: AsyncSession | None,
) -> None:
    """Test: FK constraint accepts valid digital_asset_id.

    **Validates: R5 AC #2**

    Creates asset and verifies that inserting analysis with valid
    digital_asset_id succeeds.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and asset
    user = User(
        email="valid-asset-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Valid Asset Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="example.com",
        normalized_value="example.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analysis with valid digital_asset_id
    analysis = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
    )

    db_session.add(analysis)

    # Should succeed
    await db_session.commit()

    # Verify analysis was created
    assert analysis.id is not None


# ===========================================================================
# Test 2: FK Constraint — Invalid requested_by Rejected
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_fk_constraint_rejects_invalid_requested_by(
    db_session: AsyncSession | None,
) -> None:
    """Test: FK constraint rejects non-existent requested_by (user).

    **Validates: R5 AC #1-3**

    Attempts to insert analysis with non-existent requested_by
    and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid asset
    user = User(
        email="owner@example.com",
        password_hash="$2b$12$hash",
        full_name="Owner",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="example.com",
        normalized_value="example.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analysis with non-existent requested_by
    analysis = Analysis(
        digital_asset_id=asset.id,
        requested_by=uuid4(),  # Non-existent user
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
    )

    db_session.add(analysis)

    # Should raise IntegrityError (FK constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    # Rollback to clean up
    await db_session.rollback()


# ===========================================================================
# Test 3: FK ON DELETE RESTRICT — Delete Asset with Analyses Blocked
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_fk_on_delete_restrict_prevents_asset_deletion(
    db_session: AsyncSession | None,
) -> None:
    """Test: FK ON DELETE RESTRICT prevents deletion of asset with analyses.

    **Validates: R5 AC #3 — ON DELETE RESTRICT**

    Creates asset with pending analysis, attempts to delete asset,
    and expects IntegrityError (deletion blocked).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create user, asset, and analysis
    user = User(
        email="restrict-test@example.com",
        password_hash="$2b$12$hash",
        full_name="Restrict Test",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="restrict.com",
        normalized_value="restrict.com",
    )
    db_session.add(asset)
    await db_session.flush()

    analysis = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.PENDING,
    )
    db_session.add(analysis)
    await db_session.commit()

    # Attempt to delete asset (should be blocked by FK ON DELETE RESTRICT)
    db_session.delete(asset)  # type: ignore[unused-coroutine]

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


# ===========================================================================
# Test 4: FK ON DELETE RESTRICT — Delete User with Analyses Blocked
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_fk_on_delete_restrict_prevents_user_deletion(
    db_session: AsyncSession | None,
) -> None:
    """Test: FK ON DELETE RESTRICT prevents deletion of user with analyses.

    **Validates: R5 AC #3 — ON DELETE RESTRICT**

    Creates user who requested analysis, attempts to delete user,
    and expects IntegrityError (deletion blocked).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create user who requests analysis, separate user who owns asset
    requester = User(
        email="requester@example.com",
        password_hash="$2b$12$hash",
        full_name="Requester",
        role=UserRole.ANALYST.value,
    )
    owner = User(
        email="asset-owner@example.com",
        password_hash="$2b$12$hash",
        full_name="Asset Owner",
        role=UserRole.ANALYST.value,
    )
    db_session.add(requester)
    db_session.add(owner)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=owner.id,
        asset_type=AssetType.DOMAIN,
        raw_value="restrict.com",
        normalized_value="restrict.com",
    )
    db_session.add(asset)
    await db_session.flush()

    analysis = Analysis(
        digital_asset_id=asset.id,
        requested_by=requester.id,
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.RUNNING,
    )
    db_session.add(analysis)
    await db_session.commit()

    # Attempt to delete requester (should be blocked by FK ON DELETE RESTRICT)
    db_session.delete(requester)  # type: ignore[unused-coroutine]

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


# ===========================================================================
# Test 5: CHECK Constraint — Invalid Status Rejected
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_rejects_invalid_status(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint rejects invalid status value.

    **Validates: R10 AC #2 — Status Validation**

    Attempts to insert analysis with invalid status (not in enum)
    and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and asset
    user = User(
        email="invalid-status@example.com",
        password_hash="$2b$12$hash",
        full_name="Invalid Status",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="status-test.com",
        normalized_value="status-test.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analysis with invalid status (bypass enum)
    analysis = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
    )
    analysis.status = "invalid_status"  # type: ignore[assignment]

    db_session.add(analysis)

    # Should raise IntegrityError (CHECK constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


# ===========================================================================
# Test 6: CHECK Constraint — threat_score Range [0.0, 1.0]
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_rejects_threat_score_out_of_range(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint rejects threat_score outside [0.0, 1.0].

    **Validates: R10 AC #2 — Threat Score Range**

    Attempts to insert analysis with threat_score=1.5 (out of range)
    and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and asset
    user = User(
        email="threat-score@example.com",
        password_hash="$2b$12$hash",
        full_name="Threat Score",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="threat.com",
        normalized_value="threat.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analysis with invalid threat_score
    analysis = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.COMPLETED,
        threat_score=1.5,  # Out of range!
        confidence=0.9,
        severity="HIGH",
    )

    db_session.add(analysis)

    # Should raise IntegrityError (CHECK constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_rejects_negative_threat_score(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint rejects negative threat_score.

    **Validates: R10 AC #2 — Threat Score Range**

    Attempts to insert analysis with threat_score=-0.1 (negative)
    and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and asset
    user = User(
        email="negative-threat@example.com",
        password_hash="$2b$12$hash",
        full_name="Negative Threat",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="negative.com",
        normalized_value="negative.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analysis with negative threat_score
    analysis = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.COMPLETED,
        threat_score=-0.1,  # Negative!
        confidence=0.9,
        severity="HIGH",
    )

    db_session.add(analysis)

    # Should raise IntegrityError (CHECK constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


# ===========================================================================
# Test 7: CHECK Constraint — Confidence Range [0.0, 1.0]
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_rejects_confidence_out_of_range(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint rejects confidence outside [0.0, 1.0].

    **Validates: R10 AC #2 — Confidence Range**

    Attempts to insert analysis with confidence=1.5 (out of range)
    and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and asset
    user = User(
        email="confidence@example.com",
        password_hash="$2b$12$hash",
        full_name="Confidence",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="confidence.com",
        normalized_value="confidence.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analysis with invalid confidence
    analysis = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.COMPLETED,
        threat_score=0.8,
        confidence=1.5,  # Out of range!
        severity="HIGH",
    )

    db_session.add(analysis)

    # Should raise IntegrityError (CHECK constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


# ===========================================================================
# Test 8: CHECK Constraint — Severity Valid Values
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_rejects_invalid_severity(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint rejects invalid severity value.

    **Validates: R10 AC #2 — Severity Validation**

    Attempts to insert analysis with severity='UNKNOWN' (not valid)
    and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and asset
    user = User(
        email="severity@example.com",
        password_hash="$2b$12$hash",
        full_name="Severity",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="severity.com",
        normalized_value="severity.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analysis with invalid severity (bypass enum)
    analysis = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.COMPLETED,
        threat_score=0.8,
        confidence=0.9,
    )
    analysis.severity = "UNKNOWN"  # type: ignore[assignment]

    db_session.add(analysis)

    # Should raise IntegrityError (CHECK constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


# ===========================================================================
# Test 9: CHECK Constraint — retry_count Non-Negative
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_check_constraint_rejects_negative_retry_count(
    db_session: AsyncSession | None,
) -> None:
    """Test: CHECK constraint rejects negative retry_count.

    **Validates: R10 AC #2 — Retry Count Non-Negative**

    Attempts to insert analysis with retry_count=-1 (negative)
    and expects IntegrityError.
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and asset
    user = User(
        email="retry@example.com",
        password_hash="$2b$12$hash",
        full_name="Retry",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="retry.com",
        normalized_value="retry.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create analysis with negative retry_count (bypass validation)
    analysis = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
    )
    analysis.retry_count = -1  # type: ignore[assignment]

    db_session.add(analysis)

    # Should raise IntegrityError (CHECK constraint violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


# ===========================================================================
# Test 10: Partial Unique Index — Completed Status Idempotency
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_unique_index_enforces_completed_idempotency(
    db_session: AsyncSession | None,
) -> None:
    """Test: Partial unique index prevents duplicate completed analyses.

    **Validates: R7 AC #1-2 — Idempotency Guarantee**

    Inserts first completed analysis with (asset_id, analyzer_key, analyzer_version),
    then attempts duplicate and expects IntegrityError (idempotency enforced).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and asset
    user = User(
        email="idempotency@example.com",
        password_hash="$2b$12$hash",
        full_name="Idempotency",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="idempotent.com",
        normalized_value="idempotent.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create first completed analysis
    analysis1 = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
        status=AnalysisStatus.COMPLETED,
        threat_score=0.8,
        confidence=0.9,
        severity="HIGH",
    )
    db_session.add(analysis1)
    await db_session.commit()

    # Attempt to create second completed analysis with same triple
    # (asset, analyzer_key, analyzer_version)
    analysis2 = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="virustotal_analyzer",  # Same!
        analyzer_version="v2.1.0",  # Same!
        analyzer_slugs=["virustotal"],
        status=AnalysisStatus.COMPLETED,  # Same status!
        threat_score=0.85,
        confidence=0.95,
        severity="HIGH",
    )
    db_session.add(analysis2)

    # Should raise IntegrityError (unique index violation)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


# ===========================================================================
# Test 11: Partial Unique Index — Pending Allows Duplicates
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_partial_unique_index_allows_pending_duplicates(
    db_session: AsyncSession | None,
) -> None:
    """Test: Partial unique index allows multiple pending with same triple.

    **Validates: R7 AC #3 — Partial Unique Allows Retries**

    Inserts first pending analysis, then inserts second pending with same
    (asset_id, analyzer_key, analyzer_version) and expects SUCCESS (retries allowed).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and asset
    user = User(
        email="pending-retry@example.com",
        password_hash="$2b$12$hash",
        full_name="Pending Retry",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="pending.com",
        normalized_value="pending.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create first pending analysis
    analysis1 = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
        status=AnalysisStatus.PENDING,
    )
    db_session.add(analysis1)
    await db_session.commit()

    # Create second pending analysis with same (asset, analyzer_key, analyzer_version)
    analysis2 = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="virustotal_analyzer",  # Same!
        analyzer_version="v2.1.0",  # Same!
        analyzer_slugs=["virustotal"],
        status=AnalysisStatus.PENDING,  # Different status (pending, not completed)!
    )
    db_session.add(analysis2)

    # Should succeed (partial unique index only checks completed status)
    await db_session.commit()

    # Verify both were created
    assert analysis1.id is not None
    assert analysis2.id is not None
    assert analysis1.id != analysis2.id


# ===========================================================================
# Test 12: Partial Unique Index — Failed Allows Duplicates
# ===========================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_MIGRATION_URL"),
    reason="DATABASE_MIGRATION_URL not configured",
)
@pytest.mark.asyncio
async def test_partial_unique_index_allows_failed_duplicates(
    db_session: AsyncSession | None,
) -> None:
    """Test: Partial unique index allows multiple failed with same triple.

    **Validates: R7 AC #3 — Partial Unique Allows Retries**

    Inserts first failed analysis, then inserts second failed with same
    (asset_id, analyzer_key, analyzer_version) and expects SUCCESS (retries allowed).
    """
    if db_session is None:
        pytest.skip("Database not available")

    # Create valid user and asset
    user = User(
        email="failed-retry@example.com",
        password_hash="$2b$12$hash",
        full_name="Failed Retry",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()

    asset = DigitalAsset(
        user_id=user.id,
        asset_type=AssetType.DOMAIN,
        raw_value="failed.com",
        normalized_value="failed.com",
    )
    db_session.add(asset)
    await db_session.flush()

    # Create first failed analysis
    analysis1 = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
        status=AnalysisStatus.FAILED,
        error_message="Timeout",
        error_code="ENRICHMENT_TIMEOUT",
    )
    db_session.add(analysis1)
    await db_session.commit()

    # Create second failed analysis with same (asset, analyzer_key, analyzer_version)
    analysis2 = Analysis(
        digital_asset_id=asset.id,
        requested_by=user.id,
        analyzer_key="virustotal_analyzer",  # Same!
        analyzer_version="v2.1.0",  # Same!
        analyzer_slugs=["virustotal"],
        status=AnalysisStatus.FAILED,  # Different status (failed, not completed)!
        error_message="Retry timeout",
        error_code="ENRICHMENT_TIMEOUT",
    )
    db_session.add(analysis2)

    # Should succeed (partial unique index only checks completed status)
    await db_session.commit()

    # Verify both were created
    assert analysis1.id is not None
    assert analysis2.id is not None
    assert analysis1.id != analysis2.id
