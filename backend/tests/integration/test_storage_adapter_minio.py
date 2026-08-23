"""Integration tests for the S3StorageAdapter against MinIO.

Verifies the E5.T1 acceptance criteria against the real object store
from docker-compose (MinIO on localhost:9000, bucket sentinel-assets):
- Upload to MinIO succeeds
- Download returns the same bytes
- Delete removes the object
- Presigned URL is valid and time-limited
- Connection failure raises a structured exception

Skips when MinIO is not reachable (e.g. compose stack not running).

Traces to: 22-Engineering-Backlog E5.T1 (Object Storage Adapter)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
import pytest

from app.core.settings import Settings, StorageSettings
from app.domain.exceptions import (
    StorageConnectionError,
    StorageObjectNotFoundError,
)
from app.infrastructure.storage.s3_adapter import S3StorageAdapter


if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _live_storage_settings() -> StorageSettings:
    """Storage settings for the composed MinIO instance."""
    try:
        return Settings().storage
    except Exception:
        # Settings unavailable (e.g. env not loaded); fall back to the
        # composed MinIO defaults from docker-compose.yml.
        return StorageSettings(
            S3_ENDPOINT_URL="http://localhost:9000",
            S3_BUCKET_NAME="sentinel-assets",
            S3_ACCESS_KEY="minioadmin",
            S3_SECRET_KEY="minioadmin",
        )


async def _minio_ready(settings: StorageSettings) -> bool:
    """Probe MinIO connectivity and ensure the bucket exists."""
    from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

    adapter = S3StorageAdapter(settings)
    try:
        async with adapter._client() as client:  # test reaches the SDK client
            try:
                await client.head_bucket(Bucket=settings.bucket_name)
            except ClientError:
                # Bucket missing (or ambiguous 404): create it. The
                # composed minio-init should have done this already.
                await client.create_bucket(Bucket=settings.bucket_name)
    except EndpointConnectionError:
        return False
    except (ClientError, BotoCoreError, OSError):
        return False
    return True


@pytest.fixture
def storage_settings() -> StorageSettings:
    settings = _live_storage_settings()
    import asyncio

    if not asyncio.run(_minio_ready(settings)):
        pytest.skip("MinIO not available at configured endpoint")
    return settings


@pytest.fixture
def adapter(storage_settings: StorageSettings) -> S3StorageAdapter:
    return S3StorageAdapter(storage_settings)


async def _stream_of(data: bytes, chunk_size: int = 4) -> AsyncIterator[bytes]:
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


class TestUploadDownloadDelete:
    @pytest.mark.asyncio
    async def test_upload_download_roundtrip(self, adapter: S3StorageAdapter) -> None:
        """Upload to MinIO succeeds; download returns the same bytes."""
        key = f"e5t1-test/roundtrip/{uuid4()}"
        payload = b"sentinel-e5t1-roundtrip-payload" * 10

        stored_key = await adapter.upload_stream(
            key, _stream_of(payload), "application/octet-stream"
        )
        assert stored_key == key
        assert await adapter.exists(key) is True

        downloaded = b"".join(
            [chunk async for chunk in adapter.download_stream(key)]
        )
        assert downloaded == payload

        await adapter.delete(key)

    @pytest.mark.asyncio
    async def test_multipart_upload_large_file_roundtrip(
        self, adapter: S3StorageAdapter
    ) -> None:
        """Payload larger than one 8 MiB part round-trips via multipart.

        Proves the true multipart path (>1 part) against real MinIO:
        memory stays bounded to one part while the object reassembles
        byte-identically.
        """
        import secrets

        key = f"e5t1-test/multipart/{uuid4()}"
        # 12 MiB of random data: guarantees at least two parts
        # (one 8 MiB flushed part + 4 MiB final part).
        payload = secrets.token_bytes(12 * 1024 * 1024)

        await adapter.upload_stream(
            key,
            _stream_of(payload, chunk_size=256 * 1024),
            "application/octet-stream",
        )
        assert await adapter.exists(key) is True

        downloaded = b"".join(
            [chunk async for chunk in adapter.download_stream(key)]
        )
        assert downloaded == payload
        assert len(downloaded) == 12 * 1024 * 1024

        await adapter.delete(key)
        assert await adapter.exists(key) is False

    @pytest.mark.asyncio
    async def test_delete_removes_object(self, adapter: S3StorageAdapter) -> None:
        """Delete removes the object; it no longer exists."""
        key = f"e5t1-test/delete/{uuid4()}"

        await adapter.upload_stream(key, _stream_of(b"bye"), "text/plain")
        assert await adapter.exists(key) is True

        await adapter.delete(key)

        assert await adapter.exists(key) is False
        with pytest.raises(StorageObjectNotFoundError):
            async for _chunk in adapter.download_stream(key):
                pass

    @pytest.mark.asyncio
    async def test_download_missing_key_raises(
        self, adapter: S3StorageAdapter
    ) -> None:
        """Downloading a non-existent key raises StorageObjectNotFoundError."""
        with pytest.raises(StorageObjectNotFoundError):
            async for _chunk in adapter.download_stream(f"e5t1-test/missing/{uuid4()}"):
                pass

    @pytest.mark.asyncio
    async def test_delete_missing_key_is_noop(
        self, adapter: S3StorageAdapter
    ) -> None:
        """Deleting a non-existent key does not raise."""
        await adapter.delete(f"e5t1-test/never-existed/{uuid4()}")


class TestPresignedUrl:
    @pytest.mark.asyncio
    async def test_presigned_url_valid_and_time_limited(
        self, adapter: S3StorageAdapter, storage_settings: StorageSettings
    ) -> None:
        """Presigned URL downloads the object and carries an expiry."""
        key = f"e5t1-test/presign/{uuid4()}"
        payload = b"presigned-content"

        await adapter.upload_stream(key, _stream_of(payload), "text/plain")

        url = await adapter.generate_presigned_url(key, 60)

        # Time-limited: signed URL carries an expiry parameter
        assert "Expires" in url or "X-Amz-Expires" in url

        # Valid: an unauthenticated GET returns the object bytes
        async with httpx.AsyncClient() as http:
            response = await http.get(url)
        assert response.status_code == 200
        assert response.content == payload

        await adapter.delete(key)


class TestConnectionFailure:
    @pytest.mark.asyncio
    async def test_unreachable_endpoint_raises_structured_error(self) -> None:
        """Connection failure raises StorageConnectionError, not an SDK error."""
        dead_settings = StorageSettings(
            S3_ENDPOINT_URL="http://localhost:59999",  # nothing listens here
            S3_BUCKET_NAME="sentinel-assets",
            S3_ACCESS_KEY="minioadmin",
            S3_SECRET_KEY="minioadmin",
        )
        dead_adapter = S3StorageAdapter(dead_settings)

        with pytest.raises(StorageConnectionError) as exc_info:
            await dead_adapter.exists(f"e5t1-test/dead/{uuid4()}")

        # Structured message names the endpoint, hides credentials
        assert "59999" in str(exc_info.value)
        assert "minioadmin" not in str(exc_info.value)
