"""Unit tests for the UploadService pipeline (mocked infrastructure).

The central test is HASH AUTHORITY (locked 2026-08-23): the SHA-256 is
computed exclusively from the streamed bytes via the hashing tee — the
service accepts no client-declared hash parameter at all, and both
Upload.checksum_sha256 and DigitalAsset.sha256_hash come from
digest.hexdigest() of the received chunks.

Traces to: 22-Engineering-Backlog E5.T4 (Upload Service)
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.services.upload_service import (
    FileTooLargeError,
    UploadService,
)
from app.core.settings import UploadSettings
from app.domain.exceptions import NotFound, StorageConnectionError
from app.utils.file_validation import MimeTypeNotAllowedError


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.domain.entities.digital_asset import DigitalAsset
    from app.domain.entities.upload import Upload


# Textual payload: content is declared and validated as text/plain
_PAYLOAD = b"sentinel upload service test payload line\n" * 20
_PAYLOAD_HASH = hashlib.sha256(_PAYLOAD).hexdigest()

_ALLOWED = UploadSettings(
    UPLOAD_MAX_FILE_SIZE=1024 * 1024,
    UPLOAD_ALLOWED_MIME_TYPES=["application/pdf", "text/plain"],
)


def _settings() -> UploadSettings:
    return _ALLOWED


async def _stream(data: bytes, chunk_size: int = 7) -> AsyncIterator[bytes]:
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


def _consuming_storage() -> AsyncMock:
    """Storage mock that consumes the stream like the real adapter.

    The real multipart adapter iterates the hashing tee to completion;
    the mock must too, or the authoritative digest never accumulates.
    """
    storage = AsyncMock()

    async def _consume(key: str, stream: AsyncIterator[bytes], ct: str) -> str:
        async for _chunk in stream:
            pass
        return key

    storage.upload_stream.side_effect = _consume
    return storage


def _service(
    *,
    upload_repo: Any = None,
    asset_repo: Any = None,
    storage: Any = None,
    audit: Any = None,
) -> UploadService:
    return UploadService(
        upload_repo=upload_repo or AsyncMock(),
        asset_repo=asset_repo or AsyncMock(),
        storage=storage or _consuming_storage(),
        audit_service=audit or AsyncMock(),
        upload_settings=_settings(),
    )


def _passthrough_upload_repo() -> AsyncMock:
    """Upload repo mock that persists created entities by id."""
    repo = AsyncMock()
    store: dict = {}

    async def create(entity: Upload) -> Upload:
        store[entity.id] = entity
        return entity

    async def update(entity_id, updates: dict) -> Upload:
        from dataclasses import replace

        current = store[entity_id]
        store[entity_id] = replace(current, **updates)
        return store[entity_id]

    async def get_by_idempotency_key(user_id, key):
        for entity in store.values():
            if entity.user_id == user_id and entity.idempotency_key == key:
                return entity
        raise NotFound(f"no upload for key {key}")

    repo.create.side_effect = create
    repo.update.side_effect = update
    repo.get_by_idempotency_key.side_effect = get_by_idempotency_key
    repo.store = store
    return repo


def _dedup_asset_repo() -> AsyncMock:
    """Asset repo mock implementing get_by_hash/create over a dict."""
    repo = AsyncMock()
    by_hash: dict[str, DigitalAsset] = {}

    async def get_by_hash(sha256_hash: str) -> DigitalAsset:
        asset = by_hash.get(sha256_hash.lower())
        if asset is None:
            raise NotFound(f"no asset with hash {sha256_hash}")
        return asset

    async def create(entity: DigitalAsset) -> DigitalAsset:
        by_hash[entity.sha256_hash.lower()] = entity
        return entity

    repo.get_by_hash.side_effect = get_by_hash
    repo.create.side_effect = create
    repo.by_hash = by_hash
    return repo


class TestHashAuthority:
    @pytest.mark.asyncio
    async def test_hash_computed_from_streamed_bytes(self) -> None:
        """THE locked invariant: digest comes from the received chunks.

        The payload is hashed independently here and compared against
        what the service persisted — there is no hash input anywhere
        in the service call to trust instead.
        """
        uploads = _passthrough_upload_repo()
        assets = _dedup_asset_repo()
        service = _service(upload_repo=uploads, asset_repo=assets)

        result = await service.process_upload(
            user_id=uuid4(),
            original_filename="evidence.txt",
            content_type="text/plain",
            stream=_stream(_PAYLOAD),
        )

        # Authoritative digest == hashlib of exactly the streamed bytes
        assert result.checksum_sha256 == _PAYLOAD_HASH
        assert result.file_size_bytes == len(_PAYLOAD)
        assert result.upload_status == "completed"
        assert result.digital_asset_id is not None

        asset = assets.by_hash[_PAYLOAD_HASH]
        assert asset.sha256_hash == _PAYLOAD_HASH
        assert asset.size_bytes == len(_PAYLOAD)

    @pytest.mark.asyncio
    async def test_hash_changes_with_bytes_not_metadata(self) -> None:
        """Same declared metadata, different bytes → different hash."""
        assets = _dedup_asset_repo()
        service = _service(
            upload_repo=_passthrough_upload_repo(), asset_repo=assets
        )

        other = b"completely different content" * 10
        await service.process_upload(
            user_id=uuid4(),
            original_filename="evidence.txt",
            content_type="text/plain",
            stream=_stream(_PAYLOAD),
        )
        await service.process_upload(
            user_id=uuid4(),
            original_filename="evidence.txt",  # identical metadata
            content_type="text/plain",
            stream=_stream(other),
        )

        assert set(assets.by_hash) == {
            _PAYLOAD_HASH,
            hashlib.sha256(other).hexdigest(),
        }


class TestDeduplication:
    @pytest.mark.asyncio
    async def test_duplicate_content_resolves_existing_asset(self) -> None:
        """Second upload of identical bytes links to the SAME asset."""
        uploads = _passthrough_upload_repo()
        assets = _dedup_asset_repo()
        storage = _consuming_storage()
        service = _service(
            upload_repo=uploads, asset_repo=assets, storage=storage
        )
        user = uuid4()

        first = await service.process_upload(
            user_id=user,
            original_filename="a.txt",
            content_type="text/plain",
            stream=_stream(_PAYLOAD),
        )
        second = await service.process_upload(
            user_id=user,
            original_filename="b.txt",
            content_type="text/plain",
            stream=_stream(_PAYLOAD),
        )

        assert first.digital_asset_id == second.digital_asset_id
        assert len(assets.by_hash) == 1  # one asset for identical content

    @pytest.mark.asyncio
    async def test_duplicate_upload_cleans_redundant_object(self) -> None:
        """The redundant object streamed for a duplicate is deleted."""
        assets = _dedup_asset_repo()
        storage = _consuming_storage()
        service = _service(
            upload_repo=_passthrough_upload_repo(),
            asset_repo=assets,
            storage=storage,
        )
        user = uuid4()

        await service.process_upload(
            user_id=user,
            original_filename="a.txt",
            content_type="text/plain",
            stream=_stream(_PAYLOAD),
        )
        await service.process_upload(
            user_id=user,
            original_filename="b.txt",
            content_type="text/plain",
            stream=_stream(_PAYLOAD),
        )

        # Two streamed objects; exactly one delete for the redundant one
        assert storage.upload_stream.await_count == 2
        assert storage.delete.await_count == 1


class TestFailurePaths:
    @pytest.mark.asyncio
    async def test_storage_failure_fails_upload(self) -> None:
        """Storage error → upload persisted as failed, error re-raised."""
        uploads = _passthrough_upload_repo()
        storage = _consuming_storage()
        storage.upload_stream.side_effect = StorageConnectionError(
            "Could not connect to object storage at http://localhost:9000"
        )
        service = _service(upload_repo=uploads, storage=storage)

        with pytest.raises(StorageConnectionError):
            await service.process_upload(
                user_id=uuid4(),
                original_filename="x.txt",
                content_type="text/plain",
                stream=_stream(_PAYLOAD),
            )

        failed = next(iter(uploads.store.values()))
        assert failed.upload_status == "failed"
        assert failed.completed_at is not None
        assert failed.digital_asset_id is None

    @pytest.mark.asyncio
    async def test_oversize_rejected_at_stream_boundary(self) -> None:
        """Size limit enforced while streaming; no full buffering."""
        small = UploadSettings(
            UPLOAD_MAX_FILE_SIZE=16,
            UPLOAD_ALLOWED_MIME_TYPES=["text/plain"],
        )
        uploads = _passthrough_upload_repo()
        service = UploadService(
            upload_repo=uploads,
            asset_repo=_dedup_asset_repo(),
            storage=_consuming_storage(),
            audit_service=AsyncMock(),
            upload_settings=small,
        )

        with pytest.raises(FileTooLargeError):
            await service.process_upload(
                user_id=uuid4(),
                original_filename="big.txt",
                content_type="text/plain",
                stream=_stream(b"x" * 10_000, chunk_size=8),
            )

        failed = next(iter(uploads.store.values()))
        assert failed.upload_status == "failed"

    @pytest.mark.asyncio
    async def test_disallowed_mime_rejected_before_io(self) -> None:
        """Declared type outside the allow-list → no repo/storage calls."""
        uploads = AsyncMock()
        storage = _consuming_storage()
        service = _service(upload_repo=uploads, storage=storage)

        with pytest.raises(MimeTypeNotAllowedError):
            await service.process_upload(
                user_id=uuid4(),
                original_filename="evil.exe",
                content_type="application/x-msdownload",
                stream=_stream(b"MZ..."),
            )

        uploads.create.assert_not_awaited()
        storage.upload_stream.assert_not_awaited()


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_replay_returns_original_without_processing(self) -> None:
        """Same (user, key) → original upload returned; no re-upload."""
        uploads = _passthrough_upload_repo()
        storage = _consuming_storage()
        service = _service(
            upload_repo=uploads,
            asset_repo=_dedup_asset_repo(),
            storage=storage,
        )
        user = uuid4()

        first = await service.process_upload(
            user_id=user,
            original_filename="a.txt",
            content_type="text/plain",
            stream=_stream(_PAYLOAD),
            idempotency_key="req-001",
        )
        replay = await service.process_upload(
            user_id=user,
            original_filename="a.txt",
            content_type="text/plain",
            stream=_stream(_PAYLOAD),
            idempotency_key="req-001",
        )

        assert replay.id == first.id
        assert storage.upload_stream.await_count == 1

    @pytest.mark.asyncio
    async def test_same_key_different_users_independent(self) -> None:
        """Keys are scoped per user."""
        uploads = _passthrough_upload_repo()
        service = _service(
            upload_repo=uploads,
            asset_repo=_dedup_asset_repo(),
            storage=AsyncMock(),
        )

        a = await service.process_upload(
            user_id=uuid4(),
            original_filename="a.txt",
            content_type="text/plain",
            stream=_stream(_PAYLOAD),
            idempotency_key="shared-key",
        )
        b = await service.process_upload(
            user_id=uuid4(),
            original_filename="a.txt",
            content_type="text/plain",
            stream=_stream(_PAYLOAD),
            idempotency_key="shared-key",
        )

        assert a.id != b.id


class TestStorageKey:
    def test_filename_sanitized_into_key(self) -> None:
        """Path separators cannot escape the key prefix."""
        key = UploadService._derive_storage_key(
            uuid4(), "../../etc/passwd"
        )
        assert key.startswith("uploads/2")  # uploads/{y}/{m}/{d}/...
        assert ".." not in key
        # Traversal collapsed into a safe flat component
        assert "etc_passwd" in key.split("/")[-1]


class TestMagicByteValidation:
    @pytest.mark.asyncio
    async def test_magic_mismatch_rejected_before_storage(self) -> None:
        """E5.T5 wiring: spoofed content fails closed, never stored."""
        from app.utils.file_validation import MimeTypeMismatchError

        uploads = _passthrough_upload_repo()
        storage = _consuming_storage()
        service = _service(upload_repo=uploads, storage=storage)

        # Executable bytes wearing a PDF filename/declaration
        with pytest.raises(MimeTypeMismatchError):
            await service.process_upload(
                user_id=uuid4(),
                original_filename="report.pdf",
                content_type="application/pdf",
                stream=_stream(b"MZ\x90\x00\x03\x00\x00\x00\x04pdf?"),
            )

        # Nothing reached object storage; the upload is persisted failed
        storage.upload_stream.assert_not_awaited()
        failed = next(iter(uploads.store.values()))
        assert failed.upload_status == "failed"

    @pytest.mark.asyncio
    async def test_content_type_parameters_do_not_bypass(self) -> None:
        """Declared type with parameters still validates + normalizes."""
        uploads = _passthrough_upload_repo()
        service = _service(upload_repo=uploads)

        result = await service.process_upload(
            user_id=uuid4(),
            original_filename="notes.txt",
            content_type="text/plain; charset=utf-8",
            stream=_stream(b"parameterized but textual"),
        )
        assert result.upload_status == "completed"
