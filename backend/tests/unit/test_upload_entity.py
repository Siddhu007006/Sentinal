"""Unit tests for the Upload domain entity state machine.

Validates the E5.T3 acceptance criteria: the pending → processing →
completed/failed state machine with valid paths only, digital_asset_id
NULL until completed, terminal-state immutability, and per-user
ownership.

Traces to: 22-Engineering-Backlog E5.T3 (Upload Domain Entity)
Traces to: 02-Domain-Model §11 (upload state machine)
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.upload import (
    COMPLETED,
    FAILED,
    PENDING,
    PROCESSING,
    Upload,
    UploadTransitionError,
)


_HASH = "a3f5c1d8e9f2b7c4a6d1e8f3b7c9d2e1" * 2  # 64 lowercase hex


def _pending_upload() -> Upload:
    return Upload.create(
        id=uuid4(),
        user_id=uuid4(),
        original_filename="report.pdf",
        storage_key="uploads/2026/08/23/x/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
    )


def _processing_upload() -> Upload:
    return _pending_upload().start_processing()


class TestFactory:
    def test_create_starts_pending(self) -> None:
        upload = _pending_upload()

        assert upload.upload_status == PENDING
        assert upload.checksum_sha256 is None
        assert upload.digital_asset_id is None
        assert upload.completed_at is None

    def test_create_rejects_negative_size(self) -> None:
        with pytest.raises(ValueError, match="file_size_bytes"):
            Upload.create(
                id=uuid4(),
                user_id=uuid4(),
                original_filename="x",
                storage_key="uploads/x",
                content_type="text/plain",
                file_size_bytes=-1,
            )

    def test_create_requires_user(self) -> None:
        with pytest.raises(ValueError, match="user_id"):
            Upload.create(
                id=uuid4(),
                user_id=None,  # type: ignore[arg-type]
                original_filename="x",
                storage_key="uploads/x",
                content_type="text/plain",
                file_size_bytes=1,
            )


class TestValidTransitions:
    def test_pending_to_processing(self) -> None:
        upload = _pending_upload().start_processing()

        assert upload.upload_status == PROCESSING
        assert upload.checksum_sha256 is None
        assert upload.digital_asset_id is None
        assert upload.completed_at is None

    def test_processing_to_completed(self) -> None:
        asset_id = uuid4()
        upload = _processing_upload().complete(
            digital_asset_id=asset_id,
            checksum_sha256=_HASH,
        )

        assert upload.upload_status == COMPLETED
        assert upload.checksum_sha256 == _HASH
        assert upload.digital_asset_id == asset_id
        assert upload.completed_at is not None

    def test_processing_to_failed(self) -> None:
        upload = _processing_upload().fail()

        assert upload.upload_status == FAILED
        assert upload.completed_at is not None
        assert upload.digital_asset_id is None

    def test_pending_to_failed_allowed_for_cleanup(self) -> None:
        """E5.T8: abandoned pending uploads (never processed) fail."""
        upload = _pending_upload().fail()

        assert upload.upload_status == FAILED
        assert upload.completed_at is not None


class TestInvalidTransitions:
    def test_pending_cannot_complete_directly(self) -> None:
        with pytest.raises(UploadTransitionError, match="complete"):
            _pending_upload().complete(
                digital_asset_id=uuid4(),
                checksum_sha256=_HASH,
            )

    def test_processing_cannot_restart(self) -> None:
        with pytest.raises(UploadTransitionError, match="start"):
            _processing_upload().start_processing()

    def test_completed_is_terminal(self) -> None:
        completed = _processing_upload().complete(
            digital_asset_id=uuid4(),
            checksum_sha256=_HASH,
        )

        with pytest.raises(UploadTransitionError, match="terminal"):
            completed.start_processing()
        with pytest.raises(UploadTransitionError, match="terminal"):
            completed.complete(
                digital_asset_id=uuid4(), checksum_sha256=_HASH
            )
        with pytest.raises(UploadTransitionError, match="terminal"):
            completed.fail()

    def test_failed_is_terminal(self) -> None:
        failed = _processing_upload().fail()

        with pytest.raises(UploadTransitionError, match="terminal"):
            failed.start_processing()
        with pytest.raises(UploadTransitionError, match="terminal"):
            failed.complete(
                digital_asset_id=uuid4(), checksum_sha256=_HASH
            )
        with pytest.raises(UploadTransitionError, match="terminal"):
            failed.fail()


class TestInvariants:
    def test_digital_asset_id_requires_completed(self) -> None:
        """digital_asset_id is NULL until completed."""
        with pytest.raises(ValueError, match="digital_asset_id"):
            Upload(
                id=uuid4(),
                user_id=uuid4(),
                original_filename="x",
                storage_key="uploads/x",
                content_type="text/plain",
                file_size_bytes=1,
                upload_status=PROCESSING,
                created_at=datetime.now(tz=UTC),
                digital_asset_id=uuid4(),
            )

    def test_terminal_requires_completed_at(self) -> None:
        from datetime import UTC, datetime

        with pytest.raises(ValueError, match="completed_at"):
            Upload(
                id=uuid4(),
                user_id=uuid4(),
                original_filename="x",
                storage_key="uploads/x",
                content_type="text/plain",
                file_size_bytes=1,
                upload_status=FAILED,
                created_at=datetime.now(tz=UTC),
                completed_at=None,
            )

    def test_non_terminal_rejects_completed_at(self) -> None:
        from datetime import UTC, datetime

        with pytest.raises(ValueError, match="completed_at"):
            Upload(
                id=uuid4(),
                user_id=uuid4(),
                original_filename="x",
                storage_key="uploads/x",
                content_type="text/plain",
                file_size_bytes=1,
                upload_status=PENDING,
                created_at=datetime.now(tz=UTC),
                completed_at=datetime.now(tz=UTC),
            )

    def test_checksum_format_validated(self) -> None:
        with pytest.raises(ValueError, match="checksum_sha256"):
            _processing_upload().complete(
                digital_asset_id=uuid4(),
                checksum_sha256="NOT_A_HASH",
            )

    def test_invalid_status_rejected(self) -> None:
        from datetime import UTC, datetime

        with pytest.raises(ValueError, match="upload_status"):
            Upload(
                id=uuid4(),
                user_id=uuid4(),
                original_filename="x",
                storage_key="uploads/x",
                content_type="text/plain",
                file_size_bytes=1,
                upload_status="cancelled",
                created_at=datetime.now(tz=UTC),
            )

    def test_transitions_preserve_identity_fields(self) -> None:
        original = _pending_upload()
        completed = original.start_processing().complete(
            digital_asset_id=uuid4(),
            checksum_sha256=_HASH,
        )

        assert completed.id == original.id
        assert completed.user_id == original.user_id
        assert completed.storage_key == original.storage_key
        assert completed.original_filename == original.original_filename

        # Source instance is untouched (transitions return new states)
        assert original.upload_status == PENDING
