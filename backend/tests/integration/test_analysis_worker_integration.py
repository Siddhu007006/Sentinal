"""Integration tests for AnalysisWorker with real infrastructure."""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import suppress
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.analyzers.metadata_analyzer.analyzer import MetadataAnalyzer
from app.analyzers.registry.registry import AnalyzerRegistry
from app.domain.entities.analysis import Analysis
from app.domain.entities.digital_asset import DigitalAsset
from app.domain.repositories.analysis import AnalysisRepository
from app.domain.repositories.digital_asset import DigitalAssetRepository
from app.infrastructure.queue.redis_queue import CeleryRedisQueueAdapter
from app.workers.analysis_worker.worker import AnalysisWorker, AnalysisWorkerSettings


if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.domain.repositories.analysis import AnalysisRepository
    from app.domain.repositories.digital_asset import DigitalAssetRepository


def _valid_pdf_content() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << >> /Contents 4 0 R >>"
        ),
        b"<< /Length 0 >>\nstream\n\nendstream",
    ]

    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode())
        content.extend(obj)
        content.extend(b"\nendobj\n")

    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode())
    content.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(content)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_worker_processes_job_end_to_end(
    redis_client: Redis,
    analysis_repo: AnalysisRepository,
    asset_repo: DigitalAssetRepository,
    storage_adapter,
    user,
):
    """Test worker processes a complete job from queue to completion."""
    # Skip if Redis unavailable
    try:
        await redis_client.ping()
    except Exception as exc:
        pytest.skip(f"Redis unavailable: {exc}")

    # Setup
    queue_name = f"test:worker:{uuid4()}"
    queue = CeleryRedisQueueAdapter(
        "redis://localhost:6379/15",
        queue_name=queue_name,
    )
    registry = AnalyzerRegistry([MetadataAnalyzer()])
    worker = AnalysisWorker(
        queue=queue,
        analysis_repo=analysis_repo,
        asset_repo=asset_repo,
        storage=storage_adapter,
        registry=registry,
        settings=AnalysisWorkerSettings(analysis_timeout_seconds=10.0, max_retries=2),
    )

    try:
        # Create valid one-page PDF content
        content = _valid_pdf_content()
        content_hash = hashlib.sha256(content).hexdigest()


        # Create test asset
        asset = DigitalAsset.create_file(
            user_id=user.id,
            sha256_hash=content_hash,
            mime_type="application/pdf",
            size_bytes=len(content),
            raw_value="test.pdf",
            id=uuid4(),
            storage_key="test/key.pdf",
        )
        await asset_repo.create(asset)

        # Upload test content
        async def content_stream():
            yield content

        await storage_adapter.upload_stream(
            asset.storage_key,
            content_stream(),
            "application/pdf",
        )

        # Create pending analysis
        analysis = Analysis(
            id=uuid4(),
            digital_asset_id=asset.id,
            requested_by=asset.user_id,
            analyzer_key="metadata",
            analyzer_version="1.0.0",
            status="pending",
        )
        await analysis_repo.create(analysis)

        # Publish job to queue
        await queue.publish(
            "analysis.requested",
            {"analysis_id": str(analysis.id)},
        )

        # Process the job
        result = await worker.process_once()

        assert result is True

        # Verify analysis completed
        completed_analysis = await analysis_repo.get_by_id(analysis.id)
        assert completed_analysis.status == "completed"
        assert completed_analysis.result is not None
        assert completed_analysis.completed_at is not None

    finally:
        await redis_client.delete(queue_name)
        # Cleanup test data
        with suppress(Exception):
            await storage_adapter.delete(asset.storage_key)
        with suppress(Exception):
            await analysis_repo.delete(analysis.id)
        with suppress(Exception):
            await asset_repo.delete(asset.id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_worker_handles_timeout_with_real_infrastructure(
    redis_client: Redis,
    analysis_repo: AnalysisRepository,
    asset_repo: DigitalAssetRepository,
    storage_adapter,
    user,
):
    """Test worker timeout handling with real storage and database."""
    try:
        await redis_client.ping()
    except Exception as exc:
        pytest.skip(f"Redis unavailable: {exc}")

    queue_name = f"test:worker:timeout:{uuid4()}"
    queue = CeleryRedisQueueAdapter(
        "redis://localhost:6379/15",
        queue_name=queue_name,
    )

    # Create a slow analyzer for testing
    class SlowAnalyzer(MetadataAnalyzer):
        async def analyze(self, asset, content_stream):
            # Consume stream slowly
            async for _chunk in content_stream:
                await asyncio.sleep(0.1)
            # Add delay to exceed timeout
            await asyncio.sleep(2.0)
            async def empty_stream():
                yield b""

            return await super().analyze(asset, empty_stream())

    registry = AnalyzerRegistry([SlowAnalyzer()])
    worker = AnalysisWorker(
        queue=queue,
        analysis_repo=analysis_repo,
        asset_repo=asset_repo,
        storage=storage_adapter,
        registry=registry,
        settings=AnalysisWorkerSettings(analysis_timeout_seconds=0.5, max_retries=1),
    )

    try:
        # Create test asset
        asset = DigitalAsset.create_file(
            user_id=user.id,
            sha256_hash="b" * 64,
            mime_type="application/pdf",
            size_bytes=1024,
            raw_value="slow.pdf",
            id=uuid4(),
            storage_key="test/slow.pdf",
        )
        await asset_repo.create(asset)

        # Upload content
        async def content_stream():
            yield b"%PDF-1.4\n%%EOF"

        await storage_adapter.upload_stream(
            asset.storage_key,
            content_stream(),
            "application/pdf",
        )

        # Create and start analysis
        analysis = Analysis(
            id=uuid4(),
            digital_asset_id=asset.id,
            requested_by=asset.user_id,
            analyzer_key="metadata",
            analyzer_version="1.0.0",
            status="pending",
        )
        await analysis_repo.create(analysis)
        running_analysis = analysis.start()
        await analysis_repo.update(analysis.id, {
            "status": running_analysis.status,
            "started_at": running_analysis.started_at,
        })

        # Publish job
        await queue.publish(
            "analysis.requested",
            {"analysis_id": str(analysis.id)},
        )

        # Process with timeout
        result = await worker.process_once()

        assert result is True

        # Verify analysis was marked for retry due to timeout
        updated_analysis = await analysis_repo.get_by_id(analysis.id)
        assert updated_analysis.retry_count > 0

    finally:
        await redis_client.delete(queue_name)
        with suppress(Exception):
            await storage_adapter.delete(asset.storage_key)
        with suppress(Exception):
            await analysis_repo.delete(analysis.id)
        with suppress(Exception):
            await asset_repo.delete(asset.id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_workers_dont_duplicate_processing(
    redis_client: Redis,
    analysis_repo: AnalysisRepository,
    asset_repo: DigitalAssetRepository,
    storage_adapter,
    user,
):
    """Test that multiple workers don't process the same job."""
    try:
        await redis_client.ping()
    except Exception as exc:
        pytest.skip(f"Redis unavailable: {exc}")

    queue_name = f"test:worker:concurrent:{uuid4()}"

    # Create two workers with same queue
    queue1 = CeleryRedisQueueAdapter(
        "redis://localhost:6379/15",
        queue_name=queue_name,
    )
    queue2 = CeleryRedisQueueAdapter(
        "redis://localhost:6379/15",
        queue_name=queue_name,
    )

    registry = AnalyzerRegistry([MetadataAnalyzer()])
    worker1 = AnalysisWorker(
        queue=queue1,
        analysis_repo=analysis_repo,
        asset_repo=asset_repo,
        storage=storage_adapter,
        registry=registry,
        settings=AnalysisWorkerSettings(analysis_timeout_seconds=10.0, max_retries=2),
    )
    worker2 = AnalysisWorker(
        queue=queue2,
        analysis_repo=analysis_repo,
        asset_repo=asset_repo,
        storage=storage_adapter,
        registry=registry,
        settings=AnalysisWorkerSettings(analysis_timeout_seconds=10.0, max_retries=2),
    )

    try:
        # Create valid one-page PDF content
        content = _valid_pdf_content()
        content_hash = hashlib.sha256(content).hexdigest()



        # Create test asset
        asset = DigitalAsset.create_file(
            user_id=user.id,
            sha256_hash=content_hash,
            mime_type="application/pdf",
            size_bytes=len(content),
            raw_value="concurrent.pdf",
            id=uuid4(),
            storage_key="test/concurrent.pdf",
        )
        await asset_repo.create(asset)

        # Upload content
        async def content_stream():
            yield content

        await storage_adapter.upload_stream(
            asset.storage_key,
            content_stream(),
            "application/pdf",
        )

        # Create analysis
        analysis = Analysis(
            id=uuid4(),
            digital_asset_id=asset.id,
            requested_by=asset.user_id,
            analyzer_key="metadata",
            analyzer_version="1.0.0",
            status="pending",
        )
        await analysis_repo.create(analysis)

        # Publish single job
        await queue1.publish(
            "analysis.requested",
            {"analysis_id": str(analysis.id)},
        )

        # Both workers try to claim simultaneously
        results = await asyncio.gather(
            worker1.process_once(),
            worker2.process_once(),
        )

        # Only one should have processed the job
        processed_count = sum(1 for r in results if r)
        assert processed_count == 1, "Only one worker should process the job"

        # Verify analysis completed once
        completed_analysis = await analysis_repo.get_by_id(analysis.id)
        assert completed_analysis.status == "completed"

    finally:
        await redis_client.delete(queue_name)
        with suppress(Exception):
            await storage_adapter.delete(asset.storage_key)
        with suppress(Exception):
            await analysis_repo.delete(analysis.id)
        with suppress(Exception):
            await asset_repo.delete(asset.id)
