"""Integration tests for the UploadService pipeline (real MinIO + PostgreSQL).

Exercises the E5.T4 acceptance criteria end-to-end:
- Stream to object storage while computing SHA-256 concurrently
  (authoritative server-side hash from the received bytes)
- Duplicate hash resolves to the existing DigitalAsset
- Idempotency key prevents duplicate uploads
- 100 MB upload without buffering (payload generated chunk-by-chunk;
  the expected digest is computed incrementally alongside the stream)
- Oversized files rejected at the stream boundary

Skips when PostgreSQL or MinIO is unavailable.

Traces to: 22-Engineering-Backlog E5.T4 (Upload Service)
"""

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.services.upload_service import (
    FileTooLargeError,
    UploadService,
)
from app.core.settings import Settings, UploadSettings
from app.domain.services.audit_service import AuditService
from app.infrastructure.database.repositories.digital_asset import (
    PostgreSQLDigitalAssetRepository,
)
from app.infrastructure.database.repositories.upload import (
    PostgreSQLUploadRepository,
)
from app.infrastructure.storage.s3_adapter import S3StorageAdapter


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession


async def _minio_adapter_or_skip() -> S3StorageAdapter:
    """Adapter for the composed MinIO instance; skip when unreachable."""
    try:
        settings = Settings().storage
    except Exception:
        pytest.skip("storage settings unavailable")

    adapter = S3StorageAdapter(settings)

    from botocore.exceptions import BotoCoreError, ClientError

    try:
        async with adapter._client() as client:  # test reaches the SDK client
            await client.head_bucket(Bucket=settings.bucket_name)
    except (ClientError, BotoCoreError, OSError):
        pytest.skip("MinIO not available at configured endpoint")
    return adapter


def _upload_settings(max_bytes: int = 104857600) -> UploadSettings:
    return UploadSettings(
        UPLOAD_MAX_FILE_SIZE=max_bytes,
        UPLOAD_ALLOWED_MIME_TYPES=["application/pdf", "text/plain"],
    )


async def _user(db_session: AsyncSession) -> object:
    from app.models.user import User, UserRole

    user = User(
        email=f"upload-pipeline-{uuid4()}@example.com",
        password_hash="$2b$12$hash",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    await db_session.flush()
    return user


def _pattern_stream(
    block: bytes, repeat: int, chunk_size: int = 256 * 1024
) -> tuple[AsyncIterator[bytes], str, int]:
    """Build a bounded-memory stream of block*repeat and its digest.

    Returns (stream, expected_sha256, total_size). The expected digest
    is computed EAGERLY (hashing the block `repeat` times == hashing
    the concatenation), and the stream slices the virtual concatenation
    chunk by chunk — the full payload is never materialized, mirroring
    the service's bounded-memory contract.
    """
    total = len(block) * repeat
    digest = hashlib.sha256()
    for _ in range(repeat):
        digest.update(block)
    expected = digest.hexdigest()

    async def stream() -> AsyncIterator[bytes]:
        pos = 0
        while pos < total:
            end = min(pos + chunk_size, total)
            parts: list[bytes] = []
            i = pos
            while i < end:
                blk_start = i % len(block)
                take = min(end - i, len(block) - blk_start)
                parts.append(block[blk_start : blk_start + take])
                i += take
            yield b"".join(parts)
            pos = end

    return stream(), expected, total


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_upload_completes_with_server_computed_hash(
        self, db_session: AsyncSession | None
    ) -> None:
        """Pipeline end-to-end: hash authoritative from streamed bytes."""
        if db_session is None:
            pytest.skip("Database not available")
        adapter = await _minio_adapter_or_skip()

        user = await _user(db_session)
        service = UploadService(
            upload_repo=PostgreSQLUploadRepository(db_session),
            asset_repo=PostgreSQLDigitalAssetRepository(db_session),
            storage=adapter,
            audit_service=AsyncMockAudit(),
            upload_settings=_upload_settings(),
        )

        block = os.urandom(64 * 1024)
        stream, expected_hash, total = _pattern_stream(block, repeat=3)

        result = await service.process_upload(
            user_id=user.id,  # type: ignore[attr-defined]
            original_filename="evidence.bin.pdf",
            content_type="application/pdf",
            stream=stream,
        )
        await db_session.commit()

        assert result.upload_status == "completed"
        assert result.checksum_sha256 == expected_hash  # server-side truth
        assert result.file_size_bytes == total
        assert result.digital_asset_id is not None

        # The asset is content-addressed by the same authoritative hash
        asset = await PostgreSQLDigitalAssetRepository(
            db_session
        ).get_by_hash(expected_hash)
        assert asset.id == result.digital_asset_id
        assert asset.size_bytes == total

    @pytest.mark.asyncio
    async def test_duplicate_content_dedups_to_single_asset(
        self, db_session: AsyncSession | None
    ) -> None:
        """Two uploads of identical bytes → one asset, both completed."""
        if db_session is None:
            pytest.skip("Database not available")
        adapter = await _minio_adapter_or_skip()

        user = await _user(db_session)
        service = UploadService(
            upload_repo=PostgreSQLUploadRepository(db_session),
            asset_repo=PostgreSQLDigitalAssetRepository(db_session),
            storage=adapter,
            audit_service=AsyncMockAudit(),
            upload_settings=_upload_settings(),
        )

        block = os.urandom(32 * 1024)
        stream_a, expected_hash, _total = _pattern_stream(block, repeat=2)
        first = await service.process_upload(
            user_id=user.id,  # type: ignore[attr-defined]
            original_filename="first.pdf",
            content_type="application/pdf",
            stream=stream_a,
        )
        stream_b, hash_b, _ = _pattern_stream(block, repeat=2)
        second = await service.process_upload(
            user_id=user.id,  # type: ignore[attr-defined]
            original_filename="second.pdf",
            content_type="application/pdf",
            stream=stream_b,
        )
        await db_session.commit()

        assert hash_b == expected_hash
        assert first.digital_asset_id == second.digital_asset_id

        # Exactly one asset exists for this content
        from sqlalchemy import func, select

        from app.models.digital_asset import DigitalAsset as AssetORM

        count = (
            await db_session.execute(
                select(func.count()).select_from(AssetORM).where(
                    AssetORM.sha256_hash == expected_hash
                )
            )
        ).scalar_one()
        assert count == 1

    @pytest.mark.asyncio
    async def test_idempotency_key_prevents_duplicate_processing(
        self, db_session: AsyncSession | None
    ) -> None:
        """Same (user, key) replay returns the original upload."""
        if db_session is None:
            pytest.skip("Database not available")
        adapter = await _minio_adapter_or_skip()

        user = await _user(db_session)
        service = UploadService(
            upload_repo=PostgreSQLUploadRepository(db_session),
            asset_repo=PostgreSQLDigitalAssetRepository(db_session),
            storage=adapter,
            audit_service=AsyncMockAudit(),
            upload_settings=_upload_settings(),
        )

        stream_a, _h, _t = _pattern_stream(b"idempotent-block", repeat=4)
        first = await service.process_upload(
            user_id=user.id,  # type: ignore[attr-defined]
            original_filename="once.pdf",
            content_type="application/pdf",
            stream=stream_a,
            idempotency_key="req-integration-001",
        )
        stream_b, _h2, _t2 = _pattern_stream(b"idempotent-block", repeat=4)
        replay = await service.process_upload(
            user_id=user.id,  # type: ignore[attr-defined]
            original_filename="once.pdf",
            content_type="application/pdf",
            stream=stream_b,
            idempotency_key="req-integration-001",
        )
        await db_session.commit()

        assert replay.id == first.id  # original returned, not reprocessed


class TestLargeStream:
    @pytest.mark.asyncio
    async def test_100mb_upload_streams_without_materializing(
        self, db_session: AsyncSession | None
    ) -> None:
        """100 MB through the pipeline with chunk-generated payload.

        The payload never exists as a single bytes object: the stream
        yields 256 KiB chunks of a repeating 1 MiB random block, and
        the expected digest accumulates incrementally — mirroring the
        service's own bounded-memory contract.
        """
        if db_session is None:
            pytest.skip("Database not available")
        adapter = await _minio_adapter_or_skip()

        user = await _user(db_session)
        service = UploadService(
            upload_repo=PostgreSQLUploadRepository(db_session),
            asset_repo=PostgreSQLDigitalAssetRepository(db_session),
            storage=adapter,
            audit_service=AsyncMockAudit(),
            upload_settings=_upload_settings(),
        )

        block = os.urandom(1024 * 1024)  # 1 MiB random block
        stream, expected_hash, total = _pattern_stream(
            block, repeat=100  # 100 MiB
        )
        assert total == 100 * 1024 * 1024

        result = await service.process_upload(
            user_id=user.id,  # type: ignore[attr-defined]
            original_filename="large-evidence.pdf",
            content_type="application/pdf",
            stream=stream,
        )
        await db_session.commit()

        assert result.upload_status == "completed"
        assert result.file_size_bytes == total
        assert result.checksum_sha256 == expected_hash

    @pytest.mark.asyncio
    async def test_oversize_rejected_and_failed(
        self, db_session: AsyncSession | None
    ) -> None:
        """Stream above the limit is rejected mid-flight, upload failed."""
        if db_session is None:
            pytest.skip("Database not available")
        adapter = await _minio_adapter_or_skip()

        user = await _user(db_session)
        service = UploadService(
            upload_repo=PostgreSQLUploadRepository(db_session),
            asset_repo=PostgreSQLDigitalAssetRepository(db_session),
            storage=adapter,
            audit_service=AsyncMockAudit(),
            upload_settings=_upload_settings(max_bytes=1024 * 1024),
        )

        block = os.urandom(256 * 1024)
        stream, _h, _t = _pattern_stream(block, repeat=16)  # 4 MiB > 1 MiB

        with pytest.raises(FileTooLargeError):
            await service.process_upload(
                user_id=user.id,  # type: ignore[attr-defined]
                original_filename="too-big.pdf",
                content_type="application/pdf",
                stream=stream,
            )
        await db_session.commit()

        from sqlalchemy import select

        from app.models.upload import Upload as UploadORM

        rows = (
            await db_session.execute(
                select(UploadORM).where(
                    UploadORM.user_id == user.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].upload_status == "failed"


class AsyncMockAudit(AuditService):
    """Audit stand-in for pipeline tests (no audit repo wiring here).

    The fail-safe audit path is unit-tested elsewhere; these tests
    exercise the upload pipeline itself.
    """

    def __init__(self) -> None:
        pass

    async def log_upload_completed(self, **_kwargs: object) -> None:
        return None
