"""Unit tests for the S3StorageAdapter.

Mocks the aioboto3 session/client so no object storage is required.
Verifies the five adapter operations and the structured error
translation (botocore errors → domain Storage exceptions, never
leaking credentials).

Traces to: 22-Engineering-Backlog E5.T1 (Object Storage Adapter)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.settings import StorageSettings
from app.domain.exceptions import (
    StorageConnectionError,
    StorageError,
    StorageObjectNotFoundError,
)
from app.domain.services.storage_adapter import StorageAdapter
from app.infrastructure.storage.s3_adapter import S3StorageAdapter


if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
def settings() -> StorageSettings:
    """Storage settings pointing at a fake endpoint."""
    return StorageSettings(
        S3_ENDPOINT_URL="http://localhost:9000",
        S3_BUCKET_NAME="sentinel-assets",
        S3_ACCESS_KEY="test-access-key",
        S3_SECRET_KEY="test-secret-key",
    )


class _AsyncClientContext:
    """Async context manager yielding the mocked S3 client."""

    def __init__(self, client: AsyncMock) -> None:
        self._client = client

    async def __aenter__(self) -> AsyncMock:
        return self._client

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.fixture
def s3_client(
    settings: StorageSettings, monkeypatch: pytest.MonkeyPatch
) -> AsyncMock:
    """Patch aioboto3.Session to yield a mock S3 client (awaitable)."""
    client = AsyncMock()

    session = MagicMock()
    session.client.return_value = _AsyncClientContext(client)

    monkeypatch.setattr(
        "app.infrastructure.storage.s3_adapter.aioboto3.Session",
        lambda: session,
    )
    return client


def _client_error(code: str) -> ClientError:
    """Build a botocore ClientError with the given code."""
    return ClientError(
        {"Error": {"Code": code, "Message": "boom"}},
        "Operation",
    )


async def _chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


def _adapter(settings: StorageSettings) -> S3StorageAdapter:
    return S3StorageAdapter(settings)


class TestUploadStream:
    @pytest.mark.asyncio
    async def test_upload_small_stream_single_final_part(
        self, settings: StorageSettings, s3_client: AsyncMock
    ) -> None:
        """Small stream completes as one multipart part (< part size)."""
        s3_client.create_multipart_upload.return_value = {"UploadId": "mpu-1"}
        s3_client.upload_part.return_value = {"ETag": "etag-1"}

        adapter = _adapter(settings)
        key = await adapter.upload_stream(
            "k1", _chunks(b"ab", b"cd"), "application/pdf"
        )

        assert key == "k1"
        s3_client.create_multipart_upload.assert_awaited_once_with(
            Bucket="sentinel-assets",
            Key="k1",
            ContentType="application/pdf",
        )
        # Single final part carrying the joined payload
        s3_client.upload_part.assert_awaited_once_with(
            Bucket="sentinel-assets",
            Key="k1",
            UploadId="mpu-1",
            PartNumber=1,
            Body=b"abcd",
        )
        s3_client.complete_multipart_upload.assert_awaited_once_with(
            Bucket="sentinel-assets",
            Key="k1",
            UploadId="mpu-1",
            MultipartUpload={
                "Parts": [{"PartNumber": 1, "ETag": "etag-1"}]
            },
        )

    @pytest.mark.asyncio
    async def test_upload_flushes_parts_without_full_buffering(
        self,
        settings: StorageSettings,
        s3_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Stream larger than one part flushes parts at the boundary."""
        monkeypatch.setattr(
            "app.infrastructure.storage.s3_adapter._PART_SIZE", 4
        )
        s3_client.create_multipart_upload.return_value = {"UploadId": "mpu-2"}
        s3_client.upload_part.side_effect = [
            {"ETag": "etag-1"},
            {"ETag": "etag-2"},
        ]

        adapter = _adapter(settings)
        key = await adapter.upload_stream(
            "k1", _chunks(b"ab", b"cd", b"efg"), "text/plain"
        )

        assert key == "k1"
        # Part boundary at 4 bytes: "abcd" flushed mid-stream, "efg"
        # is the final part. Peak buffering = one part, not the whole
        # stream, and no trailing empty part is uploaded.
        assert s3_client.upload_part.await_count == 2
        calls = s3_client.upload_part.await_args_list
        assert [(c.kwargs["PartNumber"], c.kwargs["Body"]) for c in calls] == [
            (1, b"abcd"),
            (2, b"efg"),
        ]

        completed = s3_client.complete_multipart_upload.await_args.kwargs
        assert completed["MultipartUpload"]["Parts"] == [
            {"PartNumber": 1, "ETag": "etag-1"},
            {"PartNumber": 2, "ETag": "etag-2"},
        ]

    @pytest.mark.asyncio
    async def test_upload_zero_byte_stream_single_empty_part(
        self,
        settings: StorageSettings,
        s3_client: AsyncMock,
    ) -> None:
        """Empty stream completes as a single zero-byte part."""
        s3_client.create_multipart_upload.return_value = {"UploadId": "mpu-4"}
        s3_client.upload_part.return_value = {"ETag": "etag-1"}

        adapter = _adapter(settings)
        key = await adapter.upload_stream("k1", _chunks(), "text/plain")

        assert key == "k1"
        s3_client.upload_part.assert_awaited_once_with(
            Bucket="sentinel-assets",
            Key="k1",
            UploadId="mpu-4",
            PartNumber=1,
            Body=b"",
        )

    @pytest.mark.asyncio
    async def test_upload_failure_aborts_multipart(
        self,
        settings: StorageSettings,
        s3_client: AsyncMock,
    ) -> None:
        """Failure mid-upload aborts the multipart upload."""
        s3_client.create_multipart_upload.return_value = {"UploadId": "mpu-3"}
        s3_client.upload_part.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "boom"}},
            "UploadPart",
        )

        adapter = _adapter(settings)
        with pytest.raises(StorageError):
            await adapter.upload_stream("k1", _chunks(b"x"), "text/plain")

        s3_client.abort_multipart_upload.assert_awaited_once_with(
            Bucket="sentinel-assets",
            Key="k1",
            UploadId="mpu-3",
        )
        s3_client.complete_multipart_upload.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_connection_error_is_structured(
        self, settings: StorageSettings, s3_client: AsyncMock
    ) -> None:
        """EndpointConnectionError → StorageConnectionError, no secrets."""
        s3_client.create_multipart_upload.side_effect = EndpointConnectionError(
            endpoint_url="http://localhost:9000"
        )

        adapter = _adapter(settings)
        with pytest.raises(StorageConnectionError) as exc_info:
            await adapter.upload_stream("k1", _chunks(b"x"), "text/plain")

        # Structured: endpoint present, credentials absent
        assert "localhost:9000" in str(exc_info.value)
        assert "test-secret-key" not in str(exc_info.value)
        assert "test-access-key" not in str(exc_info.value)


class TestDownloadStream:
    @pytest.mark.asyncio
    async def test_download_yields_chunks(
        self, settings: StorageSettings, s3_client: MagicMock
    ) -> None:
        """download_stream yields the object's chunks in order."""
        body = MagicMock()

        def iter_chunks(_size: int) -> AsyncIterator[bytes]:
            async def gen() -> AsyncIterator[bytes]:
                yield b"ab"
                yield b"cd"

            return gen()

        body.iter_chunks = iter_chunks
        s3_client.get_object.return_value = {"Body": body}

        adapter = _adapter(settings)
        collected = [chunk async for chunk in adapter.download_stream("k1")]

        assert collected == [b"ab", b"cd"]
        s3_client.get_object.assert_awaited_once_with(
            Bucket="sentinel-assets", Key="k1"
        )

    @pytest.mark.asyncio
    async def test_missing_key_raises_not_found(
        self, settings: StorageSettings, s3_client: MagicMock
    ) -> None:
        """ClientError 404 → StorageObjectNotFoundError."""
        s3_client.get_object.side_effect = _client_error("NoSuchKey")

        adapter = _adapter(settings)
        with pytest.raises(StorageObjectNotFoundError):
            async for _chunk in adapter.download_stream("missing"):
                pass


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_calls_delete_object(
        self, settings: StorageSettings, s3_client: MagicMock
    ) -> None:
        """delete issues delete_object for the key."""
        adapter = _adapter(settings)
        await adapter.delete("k1")

        s3_client.delete_object.assert_awaited_once_with(
            Bucket="sentinel-assets", Key="k1"
        )

    @pytest.mark.asyncio
    async def test_delete_connection_error(
        self, settings: StorageSettings, s3_client: MagicMock
    ) -> None:
        """Connection failure during delete → StorageConnectionError."""
        s3_client.delete_object.side_effect = EndpointConnectionError(
            endpoint_url="http://localhost:9000"
        )

        adapter = _adapter(settings)
        with pytest.raises(StorageConnectionError):
            await adapter.delete("k1")


class TestPresignedUrl:
    @pytest.mark.asyncio
    async def test_returns_signed_url(
        self, settings: StorageSettings, s3_client: MagicMock
    ) -> None:
        """generate_presigned_url returns the client's signed URL."""
        s3_client.generate_presigned_url.return_value = (
            "http://localhost:9000/sentinel-assets/k1?X-Amz-Signature=abc"
        )

        adapter = _adapter(settings)
        url = await adapter.generate_presigned_url("k1", 300)

        assert "X-Amz-Signature" in url
        s3_client.generate_presigned_url.assert_awaited_once_with(
            "get_object",
            Params={"Bucket": "sentinel-assets", "Key": "k1"},
            ExpiresIn=300,
        )


class TestExists:
    @pytest.mark.asyncio
    async def test_exists_true_when_head_succeeds(
        self, settings: StorageSettings, s3_client: MagicMock
    ) -> None:
        adapter = _adapter(settings)
        assert await adapter.exists("k1") is True
        s3_client.head_object.assert_awaited_once_with(
            Bucket="sentinel-assets", Key="k1"
        )

    @pytest.mark.asyncio
    async def test_exists_false_on_404(
        self, settings: StorageSettings, s3_client: MagicMock
    ) -> None:
        s3_client.head_object.side_effect = _client_error("404")

        adapter = _adapter(settings)
        assert await adapter.exists("missing") is False

    @pytest.mark.asyncio
    async def test_exists_other_client_error_raises_storage_error(
        self, settings: StorageSettings, s3_client: MagicMock
    ) -> None:
        s3_client.head_object.side_effect = _client_error("403")

        adapter = _adapter(settings)
        with pytest.raises(StorageError):
            await adapter.exists("forbidden")

    @pytest.mark.asyncio
    async def test_exists_connection_error(
        self, settings: StorageSettings, s3_client: MagicMock
    ) -> None:
        s3_client.head_object.side_effect = EndpointConnectionError(
            endpoint_url="http://localhost:9000"
        )

        adapter = _adapter(settings)
        with pytest.raises(StorageConnectionError):
            await adapter.exists("k1")


def test_adapter_implements_interface(settings: StorageSettings) -> None:
    """S3StorageAdapter satisfies the domain StorageAdapter contract."""
    assert isinstance(_adapter(settings), StorageAdapter)
