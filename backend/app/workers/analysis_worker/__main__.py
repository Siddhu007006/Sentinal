"""Entry point for running the analysis worker as a standalone process."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from contextlib import suppress
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analyzers.metadata_analyzer.analyzer import MetadataAnalyzer
from app.analyzers.registry.registry import AnalyzerRegistry
from app.core.dependencies import get_settings
from app.infrastructure.database.repositories.analysis import (
    PostgreSQLAnalysisRepository,
)
from app.infrastructure.database.repositories.digital_asset import (
    PostgreSQLDigitalAssetRepository,
)
from app.infrastructure.database.session import _engine
from app.infrastructure.queue.redis_queue import CeleryRedisQueueAdapter
from app.infrastructure.storage.s3_adapter import S3StorageAdapter
from app.workers.analysis_worker.worker import (
    AnalysisWorker,
    AnalysisWorkerSettings,
)


if TYPE_CHECKING:
    from app.domain.services.queue_adapter import QueueAdapter
    from app.domain.services.storage_adapter import StorageAdapter

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure worker process logging from application settings."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.logging.level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def create_analyzer_registry() -> AnalyzerRegistry:
    """Create and populate the analyzer registry."""
    registry = AnalyzerRegistry()
    registry.register(MetadataAnalyzer())
    logger.info(
        "Registered %d analyzers: %s",
        len(registry.list()),
        [analyzer.key for analyzer in registry.list()],
    )
    return registry


def create_queue_adapter() -> QueueAdapter:
    """Create the queue adapter used by analysis workers."""
    settings = get_settings()
    queue = CeleryRedisQueueAdapter(
        broker_url=settings.queue.broker_url,
        queue_name="sentinel-analysis",
        claim_timeout_seconds=1,
    )
    logger.info("Created queue adapter")
    return queue


def create_storage_adapter() -> StorageAdapter:
    """Create the storage adapter used by analysis workers."""
    settings = get_settings()
    storage = S3StorageAdapter(settings.storage)
    logger.info(
        "Created storage adapter for bucket %s",
        settings.storage.bucket_name,
    )
    return storage


def create_worker_settings() -> AnalysisWorkerSettings:
    """Create worker settings from environment variables."""
    return AnalysisWorkerSettings(
        analysis_timeout_seconds=float(
            os.getenv("WORKER_ANALYSIS_TIMEOUT_SECONDS", "300")
        ),
        max_retries=int(os.getenv("WORKER_MAX_RETRIES", "3")),
    )



async def run_worker() -> None:
    """Run the analysis worker until shutdown is requested."""
    setup_logging()
    logger.info("Starting Analysis Worker")

    engine = _engine
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    queue = create_queue_adapter()
    storage = create_storage_adapter()
    registry = create_analyzer_registry()
    worker_settings = create_worker_settings()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_shutdown() -> None:
        logger.info("Shutdown requested")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, request_shutdown)

    try:
        while not stop_event.is_set():
            async with session_factory() as session:
                analysis_repo = PostgreSQLAnalysisRepository(session)
                asset_repo = PostgreSQLDigitalAssetRepository(session)

                worker = AnalysisWorker(
                    queue=queue,
                    analysis_repo=analysis_repo,
                    asset_repo=asset_repo,
                    storage=storage,
                    registry=registry,
                    settings=worker_settings,
                )

                received = await worker.process_once()

                if received:
                    await session.commit()
                else:
                    await session.rollback()

            if not received:
                await asyncio.sleep(0.1)
    finally:
        if engine is not None:
            await engine.dispose()
        logger.info("Analysis Worker stopped")


def main() -> None:
    """Entry point for the worker process."""
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        sys.exit(0)
    except Exception as exc:
        logger.exception("Worker terminated with error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
