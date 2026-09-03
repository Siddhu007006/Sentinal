from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.entities.upload import PENDING, Upload
from app.workers.scheduled.upload_cleanup import cleanup_abandoned_uploads


class FakeUploadRepository:
    def __init__(self, uploads: list[Upload]) -> None:
        self.uploads = uploads
        self.updated: list[tuple[object, dict[str, object]]] = []

    async def list_pending_before(
        self,
        cutoff: datetime,
        limit: int = 1000,
    ) -> list[Upload]:
        return [
            upload
            for upload in self.uploads
            if upload.upload_status == PENDING
            and upload.created_at < cutoff
        ][:limit]

    async def update(self, upload_id: object, updates: dict[str, object]) -> Upload:
        self.updated.append((upload_id, updates))
        return next(upload for upload in self.uploads if upload.id == upload_id)


def _pending_upload(created_at: datetime, storage_key: str) -> Upload:
    return Upload.create(
        id=uuid4(),
        user_id=uuid4(),
        original_filename="abandoned.pdf",
        storage_key=storage_key,
        content_type="application/pdf",
        file_size_bytes=0,
        created_at=created_at,
    )


@pytest.mark.asyncio
async def test_cleanup_fails_stale_uploads_deletes_objects_and_logs_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    stale = _pending_upload(now - timedelta(hours=25), "uploads/stale")
    recent = _pending_upload(now - timedelta(hours=23), "uploads/recent")
    repository = FakeUploadRepository([stale, recent])
    storage = AsyncMock()

    with caplog.at_level("INFO"):
        cleaned = await cleanup_abandoned_uploads(repository, storage, now=now)

    assert cleaned == 1
    assert [upload_id for upload_id, _ in repository.updated] == [
        stale.id,
    ]
    assert all(
        updates["upload_status"] == "failed"
        for _, updates in repository.updated
    )
    assert all(updates["completed_at"] == now for _, updates in repository.updated)
    storage.delete.assert_awaited_once_with("uploads/stale")
    assert caplog.records[-1].cleaned_uploads == 1


@pytest.mark.asyncio
async def test_cleanup_does_not_select_upload_exactly_at_cutoff() -> None:
    now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    at_cutoff = _pending_upload(now - timedelta(hours=24), "uploads/boundary")
    repository = FakeUploadRepository([at_cutoff])

    cleaned = await cleanup_abandoned_uploads(
        repository,
        AsyncMock(),
        now=now,
    )

    assert cleaned == 0
    assert repository.updated == []
