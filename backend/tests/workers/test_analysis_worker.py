"""Unit tests for AnalysisWorker."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.analyzers.base.analyzer import Analyzer
from app.domain.entities.analysis import Analysis, AnalysisResult
from app.domain.entities.digital_asset import DigitalAsset
from app.domain.services.queue_adapter import Job
from app.workers.analysis_worker.worker import AnalysisWorker, AnalysisWorkerSettings


if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class MockAnalyzer(Analyzer):
    """Mock analyzer for testing."""

    @property
    def key(self) -> str:
        return "mock_analyzer"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def analyze(
        self,
        asset: DigitalAsset,
        content_stream: AsyncIterator[bytes],
    ) -> AnalysisResult:
        # Consume the stream to avoid resource leaks
        async for _ in content_stream:
            pass
        return AnalysisResult(
            verdict="safe",
            evidence={"test": "data"},
            confidence=1.0,
            recommendation="approve",
        )


class FailingAnalyzer(Analyzer):
    """Analyzer that always fails for testing error handling."""

    @property
    def key(self) -> str:
        return "failing_analyzer"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def analyze(
        self,
        asset: DigitalAsset,
        content_stream: AsyncIterator[bytes],
    ) -> AnalysisResult:
        async for _ in content_stream:
            pass
        raise ValueError("Simulated analyzer failure")


@pytest.fixture
def mock_queue():
    """Mock queue adapter."""
    queue = AsyncMock()
    queue.claim = AsyncMock()
    queue.ack = AsyncMock()
    queue.nack = AsyncMock()
    return queue


@pytest.fixture
def mock_analysis_repo():
    """Mock analysis repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_asset_repo():
    """Mock digital asset repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock()
    return repo


@pytest.fixture
def mock_storage():
    """Mock storage adapter."""
    storage = AsyncMock()
    storage.download_stream = MagicMock()
    return storage


@pytest.fixture
def mock_registry():
    """Mock analyzer registry."""
    registry = MagicMock()
    registry.get = MagicMock()
    return registry


@pytest.fixture
def sample_analysis():
    """Create a sample analysis entity."""
    return Analysis(
        id=uuid4(),
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="mock_analyzer",
        analyzer_version="1.0.0",
        status="pending",
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
def async_content_stream():
    """Create an async iterator for content streaming."""
    async def stream():
        yield b"test content"
    return stream()


@pytest.fixture
def worker(
    mock_queue,
    mock_analysis_repo,
    mock_asset_repo,
    mock_storage,
    mock_registry,
):
    """Create an AnalysisWorker instance with mocked dependencies."""
    return AnalysisWorker(
        queue=mock_queue,
        analysis_repo=mock_analysis_repo,
        asset_repo=mock_asset_repo,
        storage=mock_storage,
        registry=mock_registry,
        settings=AnalysisWorkerSettings(analysis_timeout_seconds=5.0, max_retries=2),
    )


@pytest.mark.asyncio
async def test_process_once_returns_false_when_queue_empty(worker, mock_queue):
    """Worker returns False when no jobs are available."""
    mock_queue.claim.return_value = None

    result = await worker.process_once()

    assert result is False
    mock_queue.claim.assert_called_once()


@pytest.mark.asyncio
async def test_process_once_claims_and_processes_successful_job(
    worker,
    mock_queue,
    mock_analysis_repo,
    mock_asset_repo,
    mock_storage,
    mock_registry,
    sample_analysis,
    sample_asset,
    async_content_stream,
):
    """Worker successfully processes a job from pending to completed."""
    job = Job(
        id=uuid4(),
        job_type="analysis.requested",
        payload={"analysis_id": str(sample_analysis.id)},
    )
    mock_queue.claim.return_value = job
    mock_analysis_repo.get_by_id.return_value = sample_analysis
    mock_asset_repo.get_by_id.return_value = sample_asset
    mock_storage.download_stream.return_value = async_content_stream
    mock_registry.get.return_value = MockAnalyzer()

    result = await worker.process_once()

    assert result is True
    mock_queue.claim.assert_called_once()
    mock_analysis_repo.get_by_id.assert_called_once_with(sample_analysis.id)
    mock_asset_repo.get_by_id.assert_called_once_with(sample_analysis.digital_asset_id)
    mock_registry.get.assert_called_once_with(sample_analysis.analyzer_key)
    mock_queue.ack.assert_called_once_with(job.id)


@pytest.mark.asyncio
async def test_process_once_handles_analysis_already_running(
    worker,
    mock_queue,
    mock_analysis_repo,
    mock_asset_repo,
    mock_storage,
    mock_registry,
    sample_analysis,
    sample_asset,
    async_content_stream,
):
    """Worker handles job that is already in running state."""
    running_analysis = sample_analysis.start()
    job = Job(
        id=uuid4(),
        job_type="analysis.requested",
        payload={"analysis_id": str(sample_analysis.id)},
    )
    mock_queue.claim.return_value = job
    mock_analysis_repo.get_by_id.return_value = running_analysis
    mock_asset_repo.get_by_id.return_value = sample_asset
    mock_storage.download_stream.return_value = async_content_stream
    mock_registry.get.return_value = MockAnalyzer()

    result = await worker.process_once()

    assert result is True
    # Should not try to start again, but should process
    mock_analysis_repo.update.assert_called()


@pytest.mark.asyncio
async def test_process_once_skips_terminal_state_analyses(
    worker,
    mock_queue,
    mock_analysis_repo,
    sample_analysis,
):
    """Worker skips analyses already in terminal state and acks the job."""
    running_analysis = sample_analysis.start()
    completed_analysis = running_analysis.complete(
        AnalysisResult(
            verdict="safe",
            evidence={},
            confidence=1.0,
            recommendation="approve",
        )
    )
    job = Job(
        id=uuid4(),
        job_type="analysis.requested",
        payload={"analysis_id": str(sample_analysis.id)},
    )
    mock_queue.claim.return_value = job
    mock_analysis_repo.get_by_id.return_value = completed_analysis

    result = await worker.process_once()

    assert result is True
    mock_queue.ack.assert_called_once_with(job.id)
    # Should not call update since analysis is already terminal
    mock_analysis_repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_process_once_handles_analyzer_failure_with_retry(
    worker,
    mock_queue,
    mock_analysis_repo,
    mock_asset_repo,
    mock_storage,
    mock_registry,
    sample_analysis,
    sample_asset,
    async_content_stream,
):
    """Worker retries analysis on analyzer failure within max_retries limit."""
    running_analysis = sample_analysis.start()
    running_analysis.retry_count = 1
    job = Job(
        id=uuid4(),
        job_type="analysis.requested",
        payload={"analysis_id": str(sample_analysis.id)},
    )
    mock_queue.claim.return_value = job
    mock_analysis_repo.get_by_id.return_value = running_analysis
    mock_asset_repo.get_by_id.return_value = sample_asset
    mock_storage.download_stream.return_value = async_content_stream
    mock_registry.get.return_value = FailingAnalyzer()

    result = await worker.process_once()

    assert result is True
    # Should nack for retry
    mock_queue.nack.assert_called_once_with(job.id)
    mock_queue.ack.assert_not_called()
    # Should update with retry count
    assert mock_analysis_repo.update.call_count >= 1


@pytest.mark.asyncio
async def test_process_once_permanently_fails_after_max_retries(
    worker,
    mock_queue,
    mock_analysis_repo,
    mock_asset_repo,
    mock_storage,
    mock_registry,
    sample_analysis,
    sample_asset,
    async_content_stream,
):
    """Worker permanently fails analysis after exceeding max_retries."""
    running_analysis = sample_analysis.start()
    running_analysis.retry_count = 2  # Already at max
    job = Job(
        id=uuid4(),
        job_type="analysis.requested",
        payload={"analysis_id": str(sample_analysis.id)},
    )
    mock_queue.claim.return_value = job
    mock_analysis_repo.get_by_id.return_value = running_analysis
    mock_asset_repo.get_by_id.return_value = sample_asset
    mock_storage.download_stream.return_value = async_content_stream
    mock_registry.get.return_value = FailingAnalyzer()

    result = await worker.process_once()

    assert result is True
    # Should ack (permanent failure, no retry)
    mock_queue.ack.assert_called_once_with(job.id)
    mock_queue.nack.assert_not_called()
    # Should update with failed status
    mock_analysis_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_process_once_handles_missing_analysis_gracefully(
    worker,
    mock_queue,
    mock_analysis_repo,
):
    """Worker handles case where analysis record cannot be loaded."""
    job = Job(
        id=uuid4(),
        job_type="analysis.requested",
        payload={"analysis_id": str(uuid4())},
    )
    mock_queue.claim.return_value = job
    mock_analysis_repo.get_by_id.return_value = None

    result = await worker.process_once()

    assert result is True
    mock_queue.ack.assert_called_once_with(job.id)
    mock_analysis_repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_process_once_handles_missing_storage_key(
    worker,
    mock_queue,
    mock_analysis_repo,
    mock_asset_repo,
    sample_analysis,
):
    """Worker handles asset without storage key by retrying."""
    asset_no_key = DigitalAsset.create_file(
        user_id=uuid4(),
        sha256_hash="a" * 64,
        mime_type="application/pdf",
        size_bytes=1024,
        raw_value="test.pdf",
        id=uuid4(),
        storage_key=None,  # No storage key
    )
    running_analysis = sample_analysis.start()
    job = Job(
        id=uuid4(),
        job_type="analysis.requested",
        payload={"analysis_id": str(sample_analysis.id)},
    )
    mock_queue.claim.return_value = job
    mock_analysis_repo.get_by_id.return_value = running_analysis
    mock_asset_repo.get_by_id.return_value = asset_no_key

    result = await worker.process_once()

    assert result is True
    # Should nack for retry (storage key might be populated later)
    mock_queue.nack.assert_called_once_with(job.id)
    mock_queue.ack.assert_not_called()


@pytest.mark.asyncio
async def test_process_once_handles_timeout(
    worker,
    mock_queue,
    mock_analysis_repo,
    mock_asset_repo,
    mock_storage,
    mock_registry,
    sample_analysis,
    sample_asset,
    async_content_stream,
):
    """Worker handles analyzer timeout by retrying."""
    class SlowAnalyzer(Analyzer):
        @property
        def key(self) -> str:
            return "slow_analyzer"

        @property
        def version(self) -> str:
            return "1.0.0"

        async def analyze(
            self,
            asset: DigitalAsset,
            content_stream: AsyncIterator[bytes],
        ) -> AnalysisResult:
            async for _ in content_stream:
                pass
            await asyncio.sleep(10)  # Longer than timeout
            return AnalysisResult(
                verdict="safe",
                evidence={},
                confidence=1.0,
                recommendation="approve",
            )

    running_analysis = sample_analysis.start()
    job = Job(
        id=uuid4(),
        job_type="analysis.requested",
        payload={"analysis_id": str(sample_analysis.id)},
    )
    mock_queue.claim.return_value = job
    mock_analysis_repo.get_by_id.return_value = running_analysis
    mock_asset_repo.get_by_id.return_value = sample_asset
    mock_storage.download_stream.return_value = async_content_stream
    mock_registry.get.return_value = SlowAnalyzer()

    # Set very short timeout
    worker.settings = AnalysisWorkerSettings(
        analysis_timeout_seconds=0.1,
        max_retries=2,
    )

    result = await worker.process_once()

    assert result is True
    # Should handle timeout as failure with retry
    mock_queue.nack.assert_called_once_with(job.id)
    mock_queue.ack.assert_not_called()


@pytest.mark.asyncio
async def test_process_once_validates_job_payload(worker, mock_queue):
    """Worker validates job payload contains required analysis_id."""
    job = Job(
        id=uuid4(),
        job_type="analysis.requested",
        payload={},  # Missing analysis_id
    )
    mock_queue.claim.return_value = job

    result = await worker.process_once()

    # Worker should handle the error gracefully and ack the job
    assert result is True
    mock_queue.ack.assert_called_once_with(job.id)


@pytest.mark.asyncio
async def test_run_processes_jobs_until_stop_event(
    worker,
    mock_queue,
):
    """Worker continues processing until stop event is set."""
    # First call returns a job, second returns None
    job = Job(
        id=uuid4(),
        job_type="analysis.requested",
        payload={"analysis_id": str(uuid4())},
    )
    mock_queue.claim.side_effect = [job, None]
    mock_analysis_repo = AsyncMock()
    mock_analysis_repo.get_by_id.return_value = None
    worker.analysis_repo = mock_analysis_repo

    stop_event = asyncio.Event()

    # Run worker in background
    task = asyncio.create_task(worker.run(stop_event))

    # Let it process one job
    await asyncio.sleep(0.1)

    # Stop the worker
    stop_event.set()

    # Wait for worker to stop
    await task

    # Should have claimed at least once
    assert mock_queue.claim.call_count >= 1


def test_worker_settings_defaults():
    """Worker settings have sensible defaults."""
    settings = AnalysisWorkerSettings()

    assert settings.analysis_timeout_seconds == 300.0
    assert settings.max_retries == 3


def test_worker_settings_custom():
    """Worker settings can be customized."""
    settings = AnalysisWorkerSettings(
        analysis_timeout_seconds=600.0,
        max_retries=5,
    )

    assert settings.analysis_timeout_seconds == 600.0
    assert settings.max_retries == 5
