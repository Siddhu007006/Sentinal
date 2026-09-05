"""Analysis worker orchestration boundary."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities.analysis import RUNNING, Analysis, AnalysisResult


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.analyzers.registry.registry import AnalyzerRegistry
    from app.domain.entities.digital_asset import DigitalAsset
    from app.domain.repositories.analysis import AnalysisRepository
    from app.domain.repositories.digital_asset import DigitalAssetRepository
    from app.domain.services.queue_adapter import Job, QueueAdapter
    from app.domain.services.storage_adapter import StorageAdapter


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisWorkerSettings:
    """Runtime controls for one analysis worker."""

    analysis_timeout_seconds: float = 300.0
    max_retries: int = 3


class AnalysisWorker:
    """Claim and execute analysis jobs independently from the API process."""

    def __init__(
        self,
        queue: QueueAdapter,
        analysis_repo: AnalysisRepository,
        asset_repo: DigitalAssetRepository,
        storage: StorageAdapter,
        registry: AnalyzerRegistry,
        settings: AnalysisWorkerSettings | None = None,
    ) -> None:
        self.queue = queue
        self.analysis_repo = analysis_repo
        self.asset_repo = asset_repo
        self.storage = storage
        self.registry = registry
        self.settings = settings or AnalysisWorkerSettings()

    async def process_once(self) -> bool:
        """Process one claimed job and return whether a job was received."""
        job = await self.queue.claim()
        if job is None:
            return False

        analysis: Analysis | None = None
        try:
            analysis_id = self._analysis_id(job)
            analysis = await self.analysis_repo.get_by_id(analysis_id)
            if analysis.status not in ("pending", RUNNING):
                await self.queue.ack(job.id)
                return True

            running = analysis.start() if analysis.status == "pending" else analysis
            if running is not analysis:
                await self.analysis_repo.update(
                    running.id,
                    {
                        "status": running.status,
                        "started_at": running.started_at,
                        "updated_at": running.updated_at,
                    },
                )

            asset = await self.asset_repo.get_by_id(running.digital_asset_id)
            content_stream = self._content_stream(asset)
            analyzer = self.registry.get(running.analyzer_key)
            result = await asyncio.wait_for(
                analyzer.analyze(asset, content_stream),
                timeout=self.settings.analysis_timeout_seconds,
            )
            if result.verdict.lower() == "failed":
                failed = running.fail(
                    self._result_error_message(result),
                    "ANALYZER_FAILED",
                )
                await self.analysis_repo.update(
                    failed.id,
                    self._failed_result_updates(failed, result),
                )
            else:
                completed = running.complete(result)
                await self.analysis_repo.update(
                    completed.id,
                    self._completed_updates(completed, result),
                )

            await self.queue.ack(job.id)
            return True

        except Exception as exc:
            await self._handle_failure(job, analysis, exc)
            return True

    async def run(self, stop_event: asyncio.Event) -> None:
        """Process jobs until the supplied stop event is set."""
        while not stop_event.is_set():
            received = await self.process_once()
            if not received:
                await asyncio.sleep(0.1)

    async def _handle_failure(
        self,
        job: Job,
        analysis: Analysis | None,
        error: Exception,
    ) -> None:
        """Persist retry state, then nack transient failures for redelivery."""
        if analysis is None:
            await self.queue.ack(job.id)
            logger.exception("Analysis job could not be loaded", exc_info=error)
            return

        next_retry = analysis.retry_count + 1
        if next_retry <= self.settings.max_retries:
            await self.analysis_repo.update(
                analysis.id,
                {
                    "status": RUNNING,
                    "retry_count": next_retry,
                    "error_message": str(error),
                    "error_code": type(error).__name__,
                    "updated_at": datetime.now(tz=UTC),
                },
            )
            await self.queue.nack(job.id)
            return

        failed = analysis.fail(str(error), type(error).__name__)
        await self.analysis_repo.update(
            failed.id,
            {
                "status": failed.status,
                "retry_count": next_retry,
                "error_message": failed.error_message,
                "error_code": failed.error_code,
                "completed_at": failed.completed_at,
                "updated_at": failed.updated_at,
            },
        )
        await self.queue.ack(job.id)
        logger.error(
            "Analysis failed after retries",
            extra={"analysis_id": str(analysis.id), "retry_count": next_retry},
        )

    @staticmethod
    def _analysis_id(job: Job) -> UUID:
        value = job.payload.get("analysis_id")
        if value is None:
            raise ValueError("analysis_id is required in analysis queue payload")
        return UUID(str(value))

    def _content_stream(self, asset: DigitalAsset) -> AsyncIterator[bytes]:
        if not asset.storage_key:
            raise ValueError("digital asset has no storage key")
        return self.storage.download_stream(asset.storage_key)

    @staticmethod
    def _result_error_message(result: AnalysisResult) -> str:
        error = result.evidence.get("error")
        if isinstance(error, str) and error:
            return error
        return result.recommendation or "Analyzer reported a failed result"

    @staticmethod
    def _failed_result_updates(
        analysis: Analysis,
        result: AnalysisResult,
    ) -> dict[str, object]:
        return {
            "status": analysis.status,
            "confidence": result.confidence,
            "severity": None,
            "reasoning_payload": {
                "verdict": result.verdict,
                "evidence": result.evidence,
                "recommendation": result.recommendation,
            },
            "error_code": "ANALYZER_FAILED",
            "error_message": AnalysisWorker._result_error_message(result),
            "completed_at": analysis.completed_at,
            "updated_at": analysis.updated_at,
        }

    @staticmethod
    def _completed_updates(
        analysis: Analysis,
        result: AnalysisResult,
    ) -> dict[str, object]:
        verdict = result.verdict.upper()

        return {
            "status": analysis.status,
            "confidence": result.confidence,
            "severity": (
                verdict
                if verdict in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
                else None
            ),
            "reasoning_payload": {
                "verdict": verdict,
                "evidence": result.evidence,
                "recommendation": result.recommendation,
            },
            "completed_at": analysis.completed_at,
            "updated_at": analysis.updated_at,
        }
