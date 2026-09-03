"""Scheduled cleanup for abandoned uploads."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.domain.entities.upload import FAILED


if TYPE_CHECKING:
    from app.domain.repositories.upload import UploadRepository
    from app.domain.services.storage_adapter import StorageAdapter


logger = logging.getLogger(__name__)


async def cleanup_abandoned_uploads(
    upload_repo: UploadRepository,
    storage: StorageAdapter,
    *,
    now: datetime | None = None,
    max_batch_size: int = 1000,
) -> int:
    """Fail stale pending uploads and remove their partial storage objects.

    The caller owns the repository transaction. A missing storage key is valid
    for an upload that failed before object storage was started.
    """
    cleanup_time = now or datetime.now(tz=UTC)
    cutoff = cleanup_time - timedelta(hours=24)
    uploads = await upload_repo.list_pending_before(
        cutoff,
        limit=max_batch_size,
    )
    cleaned_count = 0

    for upload in uploads:
        await upload_repo.update(
            upload.id,
            {
                "upload_status": FAILED,
                "completed_at": cleanup_time,
                "updated_at": cleanup_time,
            },
        )
        if upload.storage_key:
            await storage.delete(upload.storage_key)
        cleaned_count += 1

    logger.info(
        "Abandoned upload cleanup completed",
        extra={
            "cleaned_uploads": cleaned_count,
            "cutoff": cutoff.isoformat(),
        },
    )
    return cleaned_count
