"""Unit tests for AnalysisService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.analyzers.metadata_analyzer.analyzer import MetadataAnalyzer
from app.analyzers.registry.registry import AnalyzerRegistryError
from app.application.services.analysis_service import (
    AnalysisNotFoundError,
    AnalysisService,
    AnalyzerNotFoundError,
    InvalidAnalysisStateError,
    QueuePublicationError,
)
from app.domain.entities.analysis import Analysis, AnalysisResult
from app.domain.entities.digital_asset import DigitalAsset
from app.domain.entities.user import UserRole
from app.domain.exceptions import NotFound


@pytest.fixture
def mock_analysis_repo():
    """Mock AnalysisRepository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_completed_analysis = AsyncMock()
    repo.list = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_asset_repo():
    """Mock DigitalAssetRepository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock()
    return repo


@pytest.fixture
def mock_analyzer_registry():
    """Mock AnalyzerRegistry with MetadataAnalyzer."""
    registry = MagicMock()
    registry.get = MagicMock()
    registry.get.return_value = MetadataAnalyzer()
    return registry


@pytest.fixture
def mock_queue():
    """Mock QueueAdapter."""
    queue = AsyncMock(spec_set=["publish", "claim", "ack", "nack"])
    job = MagicMock(id=uuid4())
    queue.publish = AsyncMock(return_value=job)
    queue.claim = AsyncMock(return_value=None)
    queue.ack = AsyncMock()
    queue.nack = AsyncMock()
    return queue


@pytest.fixture
def mock_audit_service():
    """Mock AuditService."""
    audit = AsyncMock()
    audit.log_analysis_request = AsyncMock()
    audit.log_analysis_cancellation = AsyncMock()
    audit.audit_repo = AsyncMock()
    audit.audit_repo.create = AsyncMock()
    return audit


@pytest.fixture
def analysis_service(
    mock_analysis_repo,
    mock_asset_repo,
    mock_analyzer_registry,
    mock_queue,
    mock_audit_service,
):
    """Create AnalysisService instance with mocked dependencies."""
    return AnalysisService(
        analysis_repo=mock_analysis_repo,
        asset_repo=mock_asset_repo,
        analyzer_registry=mock_analyzer_registry,
        queue=mock_queue,
        audit_service=mock_audit_service,
    )


@pytest.fixture
def sample_asset():
    """Create a sample digital asset."""
    return DigitalAsset.create_file(
        user_id=uuid4(),
        sha256_hash="a" * 64,
        mime_type="application/pdf",
        size_bytes=1024,
        raw_value="test.pdf",
        id=uuid4(),
        storage_key="test/key.pdf",
    )


@pytest.fixture
def sample_analysis(sample_asset):
    """Create a sample analysis."""
    return Analysis(
        id=uuid4(),
        digital_asset_id=sample_asset.id,
        requested_by=sample_asset.user_id,
        analyzer_key="metadata",
        analyzer_version="1.0.0",
        status="pending",
    )


@pytest.mark.asyncio
async def test_request_analysis_returns_existing_completed_analysis(
    analysis_service,
    mock_analysis_repo,
    mock_asset_repo,
    mock_queue,
    mock_audit_service,
    sample_asset,
    sample_analysis,
):
    """Test that duplicate analysis request returns existing completed analysis."""
    user_id = uuid4()

    # Mock asset exists
    mock_asset_repo.get_by_id.return_value = sample_asset

    # Mock existing completed analysis (need to start() before complete())
    running_analysis = sample_analysis.start()
    completed_analysis = running_analysis.complete(
        AnalysisResult(
            verdict="safe",
            evidence={},
            confidence=1.0,
            recommendation="approve",
        )
    )
    mock_analysis_repo.get_completed_analysis.return_value = completed_analysis

    # Request analysis
    result = await analysis_service.request_analysis(
        asset_id=sample_asset.id,
        analyzer_key="metadata",
        requested_by=user_id,
        requested_by_role=UserRole.ANALYST,
    )

    # Should return existing analysis
    assert result == completed_analysis
    assert result.status == "completed"

    # Should not create new analysis or publish job
    mock_analysis_repo.create.assert_not_called()
    mock_queue.publish.assert_not_called()

    # Should audit the idempotent return
    mock_audit_service.log_analysis_request.assert_called_once()
    call_kwargs = mock_audit_service.log_analysis_request.call_args.kwargs
    assert call_kwargs["is_idempotent"] is True


@pytest.mark.asyncio
async def test_request_analysis_queue_publish_failure_cleans_up_pending_analysis(
    analysis_service,
    mock_analysis_repo,
    mock_asset_repo,
    mock_queue,
    mock_audit_service,
    sample_asset,
):
    """If queue.publish fails, delete the pending analysis and raise
    QueuePublicationError so no stranded unprocessable row is left."""
    user_id = uuid4()
    pending_analysis = Analysis(
        id=uuid4(),
        digital_asset_id=sample_asset.id,
        requested_by=user_id,
        analyzer_key="metadata",
        analyzer_version="1.0.0",
        status="pending",
    )

    mock_asset_repo.get_by_id.return_value = sample_asset
    mock_analysis_repo.get_completed_analysis.return_value = None
    mock_analysis_repo.create.return_value = pending_analysis
    mock_queue.publish.side_effect = ConnectionError("queue unavailable")

    with pytest.raises(QueuePublicationError) as exc_info:
        await analysis_service.request_analysis(
            asset_id=sample_asset.id,
            analyzer_key="metadata",
            requested_by=user_id,
            requested_by_role=UserRole.ANALYST,
        )

    # Pending analysis must have been removed so no orphan is left stranded
    mock_analysis_repo.delete.assert_called_once_with(pending_analysis.id)
    assert "Failed to publish analysis job" in str(exc_info.value)


@pytest.mark.asyncio
async def test_request_analysis_audit_failure_does_not_block_primary_operation(
    analysis_service,
    mock_analysis_repo,
    mock_asset_repo,
    mock_queue,
    mock_audit_service,
    sample_asset,
):
    """If the audit call fails, the request must still succeed (fail-safe audit)."""
    user_id = uuid4()
    pending_analysis = Analysis(
        id=uuid4(),
        digital_asset_id=sample_asset.id,
        requested_by=user_id,
        analyzer_key="metadata",
        analyzer_version="1.0.0",
        status="pending",
    )

    mock_asset_repo.get_by_id.return_value = sample_asset
    mock_analysis_repo.get_completed_analysis.return_value = None
    mock_analysis_repo.create.return_value = pending_analysis
    mock_audit_service.log_analysis_request.side_effect = RuntimeError(
        "audit db down"
    )

    result = await analysis_service.request_analysis(
        asset_id=sample_asset.id,
        analyzer_key="metadata",
        requested_by=user_id,
        requested_by_role=UserRole.ANALYST,
    )

    # Primary operation succeeds: analysis returned, job published
    assert result == pending_analysis
    mock_queue.publish.assert_called_once()
    mock_analysis_repo.delete.assert_not_called()


@pytest.mark.asyncio
async def test_request_analysis_idempotent_return_audit_failure_does_not_block(
    analysis_service,
    mock_analysis_repo,
    mock_asset_repo,
    mock_queue,
    mock_audit_service,
    sample_asset,
    sample_analysis,
):
    """Idempotent return path also tolerates audit failure."""
    user_id = uuid4()

    mock_asset_repo.get_by_id.return_value = sample_asset
    completed = sample_analysis.start().complete(
        AnalysisResult(
            verdict="safe",
            evidence={},
            confidence=1.0,
            recommendation="approve",
        )
    )
    mock_analysis_repo.get_completed_analysis.return_value = completed
    mock_audit_service.log_analysis_request.side_effect = RuntimeError(
        "audit db down"
    )

    result = await analysis_service.request_analysis(
        asset_id=sample_asset.id,
        analyzer_key="metadata",
        requested_by=user_id,
        requested_by_role=UserRole.ANALYST,
    )

    assert result == completed
    mock_analysis_repo.create.assert_not_called()
    mock_queue.publish.assert_not_called()


@pytest.mark.asyncio
async def test_request_analysis_creates_new_pending_analysis(
    analysis_service,
    mock_analysis_repo,
    mock_asset_repo,
    mock_queue,
    mock_audit_service,
    sample_asset,
):
    """Test that new analysis request creates pending analysis and publishes job."""
    user_id = uuid4()

    # Mock asset exists
    mock_asset_repo.get_by_id.return_value = sample_asset

    # Mock no existing completed analysis
    mock_analysis_repo.get_completed_analysis.return_value = None

    # Mock create returns analysis
    mock_analysis_repo.create.return_value = Analysis(
        id=uuid4(),
        digital_asset_id=sample_asset.id,
        requested_by=user_id,
        analyzer_key="metadata",
        analyzer_version="1.0.0",
        status="pending",
    )

    # Request analysis
    await analysis_service.request_analysis(
        asset_id=sample_asset.id,
        analyzer_key="metadata",
        requested_by=user_id,
        requested_by_role=UserRole.ANALYST,
    )

    # Should create new analysis
    mock_analysis_repo.create.assert_called_once()

    # Should publish job to queue
    mock_queue.publish.assert_called_once()
    publish_call = mock_queue.publish.call_args
    assert publish_call[0][0] == "analysis.requested"
    assert "analysis_id" in publish_call[0][1]

    # Should audit the creation
    mock_audit_service.log_analysis_request.assert_called_once()
    call_kwargs = mock_audit_service.log_analysis_request.call_args.kwargs
    assert call_kwargs["is_idempotent"] is False


@pytest.mark.asyncio
async def test_request_analysis_raises_for_unknown_analyzer(
    analysis_service,
    mock_analyzer_registry,
    sample_asset,
):
    """Test that requesting analysis with unknown analyzer raises error."""
    user_id = uuid4()

    # Mock analyzer not found - simulate actual registry exception
    mock_analyzer_registry.get.side_effect = AnalyzerRegistryError(
        "Analyzer key 'unknown_analyzer' is not registered"
    )

    # Mock asset exists
    analysis_service.asset_repo.get_by_id.return_value = sample_asset

    # Request analysis with unknown analyzer
    with pytest.raises(AnalyzerNotFoundError, match="Analyzer not registered"):
        await analysis_service.request_analysis(
            asset_id=sample_asset.id,
            analyzer_key="unknown_analyzer",
            requested_by=user_id,
            requested_by_role=UserRole.ANALYST,
        )


@pytest.mark.asyncio
async def test_request_analysis_raises_for_unknown_asset(
    analysis_service,
    mock_asset_repo,
):
    """Test that requesting analysis for unknown asset raises error."""
    user_id = uuid4()
    asset_id = uuid4()

    # Mock asset not found
    mock_asset_repo.get_by_id.side_effect = NotFound("Asset not found")

    # Request analysis for unknown asset
    with pytest.raises(NotFound, match="Asset not found"):
        await analysis_service.request_analysis(
            asset_id=asset_id,
            analyzer_key="metadata",
            requested_by=user_id,
            requested_by_role=UserRole.ANALYST,
        )


@pytest.mark.asyncio
async def test_cancel_analysis_from_pending_state(
    analysis_service,
    mock_analysis_repo,
    mock_audit_service,
    sample_analysis,
):
    """Test cancelling analysis from pending state."""
    user_id = uuid4()

    # Mock analysis exists in pending state
    mock_analysis_repo.get_by_id.return_value = sample_analysis

    # Mock update returns cancelled analysis
    cancelled_analysis = sample_analysis.cancel()
    mock_analysis_repo.update.return_value = cancelled_analysis

    # Cancel analysis
    await analysis_service.cancel_analysis(
        analysis_id=sample_analysis.id,
        cancelled_by=user_id,
        cancelled_by_role=UserRole.ANALYST,
    )

    # Should update analysis to cancelled
    mock_analysis_repo.update.assert_called_once()
    update_call = mock_analysis_repo.update.call_args
    assert update_call[0][1]["status"] == "cancelled"

    # Should audit the cancellation
    mock_audit_service.log_analysis_cancellation.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_analysis_from_running_state(
    analysis_service,
    mock_analysis_repo,
    mock_audit_service,
    sample_analysis,
):
    """Test cancelling analysis from running state."""
    user_id = uuid4()

    # Mock analysis exists in running state
    running_analysis = sample_analysis.start()
    mock_analysis_repo.get_by_id.return_value = running_analysis

    # Mock update returns cancelled analysis
    cancelled_analysis = running_analysis.cancel()
    mock_analysis_repo.update.return_value = cancelled_analysis

    # Cancel analysis
    await analysis_service.cancel_analysis(
        analysis_id=sample_analysis.id,
        cancelled_by=user_id,
        cancelled_by_role=UserRole.ANALYST,
    )

    # Should update analysis to cancelled
    mock_analysis_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_analysis_raises_for_terminal_state(
    analysis_service,
    mock_analysis_repo,
    sample_analysis,
):
    """Test that cancelling analysis in terminal state raises error."""
    user_id = uuid4()

    # Mock analysis in completed state (terminal)
    running_analysis = sample_analysis.start()
    completed_analysis = running_analysis.complete(
        AnalysisResult(
            verdict="safe",
            evidence={},
            confidence=1.0,
            recommendation="approve",
        )
    )
    mock_analysis_repo.get_by_id.return_value = completed_analysis

    # Attempt to cancel
    with pytest.raises(InvalidAnalysisStateError, match="Cannot cancel analysis"):
        await analysis_service.cancel_analysis(
            analysis_id=sample_analysis.id,
            cancelled_by=user_id,
            cancelled_by_role=UserRole.ANALYST,
        )


@pytest.mark.asyncio
async def test_cancel_analysis_raises_for_unknown_analysis(
    analysis_service,
    mock_analysis_repo,
):
    """Test that cancelling unknown analysis raises error."""
    user_id = uuid4()
    analysis_id = uuid4()

    # Mock analysis not found
    mock_analysis_repo.get_by_id.side_effect = NotFound("Analysis not found")

    # Attempt to cancel - should raise AnalysisNotFoundError
    with pytest.raises(AnalysisNotFoundError):
        await analysis_service.cancel_analysis(
            analysis_id=analysis_id,
            cancelled_by=user_id,
            cancelled_by_role=UserRole.ANALYST,
        )


@pytest.mark.asyncio
async def test_cancel_analysis_audit_failure_does_not_block_primary_operation(
    analysis_service,
    mock_analysis_repo,
    mock_audit_service,
    sample_analysis,
):
    """If cancellation audit log fails, the cancel still succeeds (fail-safe audit)."""
    user_id = uuid4()

    cancelled = sample_analysis.cancel()
    mock_analysis_repo.get_by_id.return_value = sample_analysis
    mock_analysis_repo.update.return_value = cancelled
    mock_audit_service.log_analysis_cancellation.side_effect = RuntimeError(
        "audit db down"
    )

    result = await analysis_service.cancel_analysis(
        analysis_id=sample_analysis.id,
        cancelled_by=user_id,
        cancelled_by_role=UserRole.ANALYST,
    )

    # Primary operation: cancelled state persisted
    assert result == cancelled
    mock_analysis_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_get_analysis_returns_analysis(
    analysis_service,
    mock_analysis_repo,
    sample_analysis,
):
    """Test getting analysis by ID."""
    # Mock analysis exists
    mock_analysis_repo.get_by_id.return_value = sample_analysis

    # Get analysis
    result = await analysis_service.get_analysis(sample_analysis.id)

    # Should return analysis
    assert result == sample_analysis
    mock_analysis_repo.get_by_id.assert_called_once_with(sample_analysis.id)


@pytest.mark.asyncio
async def test_get_analysis_raises_for_unknown_analysis(
    analysis_service,
    mock_analysis_repo,
):
    """Test that getting unknown analysis raises error."""
    analysis_id = uuid4()

    # Mock analysis not found
    mock_analysis_repo.get_by_id.side_effect = NotFound("Analysis not found")

    # Attempt to get - should raise AnalysisNotFoundError
    with pytest.raises(AnalysisNotFoundError):
        await analysis_service.get_analysis(analysis_id)


@pytest.mark.asyncio
async def test_list_analyses_with_filters(
    analysis_service,
    mock_analysis_repo,
    sample_analysis,
):
    """Test listing analyses with filters."""
    # Mock list returns results
    mock_analysis_repo.list.return_value = ([sample_analysis], 1)

    # List with filters
    analyses, total = await analysis_service.list_analyses(
        skip=0,
        limit=10,
        asset_id=sample_analysis.digital_asset_id,
        status="pending",
    )

    # Should call list with filters
    mock_analysis_repo.list.assert_called_once()
    call_kwargs = mock_analysis_repo.list.call_args.kwargs
    assert call_kwargs["skip"] == 0
    assert call_kwargs["limit"] == 10
    assert call_kwargs["digital_asset_id"] == sample_analysis.digital_asset_id
    assert call_kwargs["status"] == "pending"

    # Should return results
    assert analyses == [sample_analysis]
    assert total == 1


@pytest.mark.asyncio
async def test_list_analyses_without_filters(
    analysis_service,
    mock_analysis_repo,
    sample_analysis,
):
    """Test listing analyses without filters."""
    # Mock list returns results
    mock_analysis_repo.list.return_value = ([sample_analysis], 1)

    # List without filters
    _analyses, _total = await analysis_service.list_analyses(
        skip=0,
        limit=10,
    )

    # Should call list without specific filters
    mock_analysis_repo.list.assert_called_once()
    call_kwargs = mock_analysis_repo.list.call_args.kwargs
    assert "digital_asset_id" not in call_kwargs
    assert "status" not in call_kwargs
    assert "requested_by" not in call_kwargs


@pytest.mark.asyncio
async def test_list_analyses_with_requested_by_filter(
    analysis_service,
    mock_analysis_repo,
    sample_analysis,
):
    """Test listing analyses filtered by requesting user (requester)."""
    requested_by_uuid = uuid4()

    # Mock list returns results
    mock_analysis_repo.list.return_value = ([sample_analysis], 1)

    # List with requested_by filter only
    analyses, total = await analysis_service.list_analyses(
        skip=0,
        limit=10,
        requested_by=requested_by_uuid,
    )

    # Should call list with requested_by filter and no asset/status filters
    mock_analysis_repo.list.assert_called_once()
    call_kwargs = mock_analysis_repo.list.call_args.kwargs
    assert call_kwargs["skip"] == 0
    assert call_kwargs["limit"] == 10
    assert call_kwargs["requested_by"] == requested_by_uuid
    assert "digital_asset_id" not in call_kwargs
    assert "status" not in call_kwargs

    # Should return results
    assert analyses == [sample_analysis]
    assert total == 1
