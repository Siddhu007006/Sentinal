"""
Upload application service.

Orchestrates the upload pipeline per openapi.yaml and 02-Domain-Model
(22-Engineering-Backlog E5.T4 + E5.T5):

    1. Idempotency: a retried (user, idempotency_key) returns the
       original upload without re-processing.
    2. Declared MIME allow-list check (cheap, before any I/O).
    3. Create the Upload row (pending), transition to processing.
    4. Magic-byte validation of the actual content against the declared
       type (fail closed, BEFORE any storage write — E5.T5); the
       validator returns a replay stream of the same bytes.
    5. Stream the bytes to object storage via multipart while computing
       the SHA-256 digest concurrently — a hashing tee feeds every chunk
       to hashlib; memory stays bounded to one storage part.
    6. Resolve the DigitalAsset by content hash (deduplication):
       existing asset reused, otherwise a new content-addressed asset.
    7. complete() the upload with the authoritative hash + asset.
    8. Audit (fail-safe: audit failures never fail the upload).

HASH AUTHORITY (non-negotiable domain invariant, locked 2026-08-23):
the SHA-256 is authoritative ONLY from the streamed bytes — every chunk
passes through hashlib.sha256().update() on its way to storage, and
digest.hexdigest() after the stream ends is the sole source for BOTH
Upload.checksum_sha256 and DigitalAsset.sha256_hash. This service
accepts no client-declared hash parameter at all (02-Domain-Model:
"always computed server-side from the actual received bytes").

Traces to: 22-Engineering-Backlog E5.T4 (Upload Service)
Traces to: 02-Domain-Model § Upload / § Digital Asset
Traces to: 08-Security-Architecture §6 (upload constraints)
"""

from __future__ import annotations

import hashlib
import logging
import re
from contextlib import suppress
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.domain.entities.digital_asset import DigitalAsset
from app.domain.entities.upload import Upload
from app.domain.exceptions import NotFound, StorageError
from app.utils.file_validation import (
    FileValidationError,
    validate_declared_mime_type,
    validate_upload_stream,
)


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.core.settings import UploadSettings
    from app.domain.repositories.digital_asset import DigitalAssetRepository
    from app.domain.repositories.upload import UploadRepository
    from app.domain.services.audit_service import AuditService
    from app.domain.services.storage_adapter import StorageAdapter

logger = logging.getLogger(__name__)

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class FileTooLargeError(Exception):
    """Stream exceeded the configured maximum upload size.

    Raised at the stream boundary: the check happens while chunks are
    consumed, so oversized inputs are rejected without buffering the
    whole body.
    """

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"Upload of {size_bytes} bytes exceeds the maximum "
            f"allowed size of {max_bytes} bytes"
        )


class _HashingTee:
    """Pass-through async stream wrapper computing the authoritative digest.

    Every chunk flows to the consumer (the storage adapter) unchanged
    while ALSO being fed to hashlib and counted — the server-side SHA-256
    of the exact received bytes. Enforces the size limit at the stream
    boundary: as soon as the running total exceeds max_bytes, iteration
    raises FileTooLargeError (no further chunks are buffered).
    """

    def __init__(self, source: AsyncIterator[bytes], max_bytes: int) -> None:
        self._source = source
        self._digest = hashlib.sha256()
        self._max_bytes = max_bytes
        self.size_bytes = 0

    def __aiter__(self) -> _HashingTee:
        return self

    async def __anext__(self) -> bytes:
        chunk = await self._source.__anext__()
        self._digest.update(chunk)
        self.size_bytes += len(chunk)
        if self.size_bytes > self._max_bytes:
            raise FileTooLargeError(self.size_bytes, self._max_bytes)
        return chunk

    def hexdigest(self) -> str:
        """Authoritative SHA-256 of the received bytes (after stream end)."""
        return self._digest.hexdigest()


class UploadService:
    """Application service orchestrating the upload pipeline."""

    def __init__(
        self,
        upload_repo: UploadRepository,
        asset_repo: DigitalAssetRepository,
        storage: StorageAdapter,
        audit_service: AuditService,
        upload_settings: UploadSettings,
    ) -> None:
        """Initialize UploadService with its dependencies.

        Args:
            upload_repo: UploadRepository for upload persistence
            asset_repo: DigitalAssetRepository for dedup resolution
            storage: StorageAdapter (object storage; SDK stays behind it)
            audit_service: AuditService for upload events (fail-safe)
            upload_settings: Size limit + MIME allow-list configuration
        """
        self.upload_repo = upload_repo
        self.asset_repo = asset_repo
        self.storage = storage
        self.audit_service = audit_service
        self._settings = upload_settings

    async def process_upload(
        self,
        *,
        user_id: UUID,
        original_filename: str,
        content_type: str,
        stream: AsyncIterator[bytes],
        idempotency_key: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> Upload:
        """Run the full upload pipeline and return the terminal Upload.

        There is deliberately NO hash parameter: the authoritative
        SHA-256 is computed from `stream` while it is written to object
        storage, never taken from request metadata.

        Args:
            user_id: Owning user (exactly one per upload)
            original_filename: Filename as submitted
            content_type: Declared MIME type (allow-listed here;
                magic-byte verification is E5.T5)
            stream: Async iterator of the file's bytes
            idempotency_key: Optional client key; a retry with the same
                key returns the original upload unchanged
            ip_address: Client IP (audit context)
            request_id: Correlation ID (audit context)
            user_agent: Client user agent (audit context)

        Returns:
            The completed Upload (linked to its DigitalAsset), or the
            original Upload when an idempotent replay occurred.

        Raises:
            FileTooLargeError: Stream exceeded the size limit
            MimeTypeNotAllowedError: Declared type not allow-listed
            StorageError: Object storage failed (upload marked failed)
        """
        # 1. Idempotent replay: return the original upload untouched.
        if idempotency_key is not None:
            with suppress(NotFound):
                return await self.upload_repo.get_by_idempotency_key(
                    user_id, idempotency_key
                )

        # 2. Declared MIME allow-list — cheap rejection before any I/O
        #    (normalizes parameters/case; 08-Security §6 reject-early).
        normalized_type = validate_declared_mime_type(
            content_type, self._settings.allowed_mime_types
        )

        # 3. Create the pending upload and start processing.
        upload = Upload.create(
            id=uuid4(),
            user_id=user_id,
            original_filename=original_filename,
            storage_key=self._derive_storage_key(
                uuid4(), original_filename
            ),
            content_type=normalized_type,
            # Real size arrives from the stream; 0 is the honest intake
            # value for a stream of unknown length (CHECK: >= 0).
            file_size_bytes=0,
            idempotency_key=idempotency_key,
        )
        persisted = await self.upload_repo.create(upload)
        processing = persisted.start_processing()
        await self.upload_repo.update(
            persisted.id, {"upload_status": processing.upload_status}
        )

        # 4. Magic-byte validation (E5.T5, 08-Security §6): sniff the
        #    minimum prefix and fail closed BEFORE any storage write —
        #    invalid content is rejected outright, never stored. The
        #    validator returns a replay of the same bytes so the
        #    pipeline stays single-pass and bounded-memory.
        try:
            replay = await validate_upload_stream(
                stream,
                declared_content_type=normalized_type,
                allowed_mime_types=self._settings.allowed_mime_types,
            )
        except FileValidationError as exc:
            await self._fail_upload(processing, reason=str(exc))
            raise

        # 5. Stream to storage while hashing — the tee is consumed by
        #    the adapter's multipart upload; the digest accumulates
        #    server-side from the same bytes that reach storage.
        tee = _HashingTee(replay, self._settings.max_file_size)
        try:
            await self.storage.upload_stream(
                processing.storage_key, tee, normalized_type
            )
        except (StorageError, FileTooLargeError) as exc:
            await self._fail_upload(processing, reason=str(exc))
            raise

        # AUTHORITATIVE hash: from the received bytes only.
        checksum = tee.hexdigest()

        # 5. Resolve the asset by content hash (global deduplication).
        asset = await self._resolve_asset(
            processing=processing,
            checksum=checksum,
            content_type=normalized_type,
            size_bytes=tee.size_bytes,
            original_filename=original_filename,
            user_id=user_id,
        )

        # 6. Complete the upload with the authoritative facts.
        completed = processing.complete(
            digital_asset_id=asset.id,
            checksum_sha256=checksum,
        )
        from dataclasses import replace

        final = replace(completed, file_size_bytes=tee.size_bytes)
        await self.upload_repo.update(
            processing.id,
            {
                "upload_status": final.upload_status,
                "checksum_sha256": checksum,
                "digital_asset_id": asset.id,
                "file_size_bytes": tee.size_bytes,
                "completed_at": final.completed_at,
                "updated_at": final.updated_at,
            },
        )

        # 7. Audit (fail-safe).
        try:
            await self.audit_service.log_upload_completed(
                user_id=user_id,
                upload_id=final.id,
                asset_id=asset.id,
                ip_address=ip_address,
                request_id=request_id,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.exception(
                "Audit log creation failed (non-blocking)",
                extra={
                    "user_id": user_id,
                    "action": "UPLOAD_COMPLETED",
                    "error": str(e),
                },
            )

        return final

    async def _resolve_asset(
        self,
        *,
        processing: Upload,
        checksum: str,
        content_type: str,
        size_bytes: int,
        original_filename: str,
        user_id: UUID,
    ) -> DigitalAsset:
        """Deduplicate by content hash; create the asset when new.

        On a dedup hit the object just written is redundant (the
        original asset already owns its storage object) and is removed
        best-effort — failure to clean up never fails the upload.
        """
        existing: DigitalAsset | None
        try:
            existing = await self.asset_repo.get_by_hash(checksum)
        except NotFound:
            existing = None

        if existing is None:
            asset = DigitalAsset.create_file(
                user_id=user_id,
                sha256_hash=checksum,
                mime_type=content_type,
                size_bytes=size_bytes,
                raw_value=original_filename,
                id=uuid4(),
                storage_key=processing.storage_key,
            )
            return await self.asset_repo.create(asset)

        # Duplicate content: the existing asset is authoritative; drop
        # the redundant object we just streamed (best-effort — cleanup
        # failure never fails the upload).
        with suppress(Exception):
            try:
                await self.storage.delete(processing.storage_key)
            except StorageError as e:
                logger.warning(
                    "Redundant object cleanup failed (non-blocking)",
                    extra={
                        "storage_key": processing.storage_key,
                        "error": str(e),
                    },
                )
        return existing

    async def _fail_upload(self, processing: Upload, *, reason: str) -> None:
        """Persist the failed terminal state (best-effort)."""
        failed = processing.fail()
        try:
            await self.upload_repo.update(
                processing.id,
                {
                    "upload_status": failed.upload_status,
                    "completed_at": failed.completed_at,
                    "updated_at": failed.updated_at,
                },
            )
        except Exception:
            logger.exception(
                "Failed to persist failed upload state",
                extra={"upload_id": processing.id, "reason": reason},
            )

    @staticmethod
    def _derive_storage_key(upload_id: UUID, original_filename: str) -> str:
        """Derive the object key: uploads/{y}/{m}/{d}/{upload_id}/{name}.

        The filename is sanitized (unusual characters collapsed, dot
        runs broken, leading dots stripped) so the key cannot escape
        its prefix.
        """
        from datetime import UTC, datetime

        now = datetime.now(tz=UTC)
        safe_name = _UNSAFE_FILENAME_CHARS.sub("_", original_filename)
        safe_name = re.sub(r"\.{2,}", ".", safe_name).lstrip(".")
        return f"uploads/{now:%Y/%m/%d}/{upload_id}/{safe_name}"
