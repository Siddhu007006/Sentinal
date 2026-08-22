"""
S3-compatible object storage adapter.

Concrete StorageAdapter implementation using aioboto3 against any
S3-compatible API (MinIO in development, AWS/R2 in production).
Configured entirely from StorageSettings (endpoint, bucket,
credentials).

This is the ONLY module outside of tests that imports the storage SDK.
Routes and services depend on the StorageAdapter interface in the
Domain layer; swapping the object store means swapping this adapter.

Error translation:
    botocore EndpointConnectionError / timeouts
        → StorageConnectionError (structured, no credentials in message)
    ClientError 404 / NoSuchKey / NotFound
        → StorageObjectNotFoundError
    other ClientError / BotoCoreError
        → StorageError

Traces to: 22-Engineering-Backlog E5.T1 (Object Storage Adapter)
Traces to: 06-Repository-Structure § Infrastructure (storage/)
Traces to: 09-Deployment-Architecture §8 (object storage persistence)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

from app.domain.exceptions import (
    StorageConnectionError,
    StorageError,
    StorageObjectNotFoundError,
)
from app.domain.services.storage_adapter import StorageAdapter


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.core.settings import StorageSettings

_CONNECTION_ERROR_TYPES: tuple[type[Exception], ...] = (
    EndpointConnectionError,
    ConnectionError,
    TimeoutError,
)


class S3StorageAdapter(StorageAdapter):
    """Async S3-compatible StorageAdapter backed by aioboto3.

    A short-lived client is created per operation via the aioboto3
    session; connection pooling is handled by the underlying aiohttp
    session inside each context manager.
    """

    def __init__(self, settings: StorageSettings) -> None:
        """Initialize the adapter from storage settings.

        Args:
            settings: Object storage configuration (endpoint, bucket,
                credentials)
        """
        self._settings = settings
        self._session = aioboto3.Session()

    def _client_kwargs(self) -> dict[str, Any]:
        """Build boto3 client kwargs from settings (secrets stay wrapped)."""
        return {
            "endpoint_url": self._settings.endpoint_url,
            "aws_access_key_id": self._settings.access_key_id.get_secret_value(),
            "aws_secret_access_key": (
                self._settings.secret_access_key.get_secret_value()
            ),
        }

    def _client(self) -> Any:  # noqa: ANN401  # aioboto3 client is untyped
        """Create an async S3 client context manager."""
        return self._session.client("s3", **self._client_kwargs())

    async def upload_stream(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        content_type: str,
    ) -> str:
        """Upload a stream of bytes to the bucket.

        Buffers the stream and issues a single PUT. Streaming/multipart
        upload without full in-memory buffering is deferred to the
        upload pipeline (E5.T4), which computes the content hash during
        streaming.

        Args:
            key: Object key
            stream: Async iterator of byte chunks
            content_type: MIME type of the content

        Returns:
            The key the object was stored under

        Raises:
            StorageConnectionError: If storage is unreachable
            StorageError: On any other storage failure
        """
        chunks: list[bytes] = []
        async for chunk in stream:
            chunks.append(chunk)

        try:
            async with self._client() as client:
                await client.put_object(
                    Bucket=self._settings.bucket_name,
                    Key=key,
                    Body=b"".join(chunks),
                    ContentType=content_type,
                )
        except _CONNECTION_ERROR_TYPES as exc:
            raise StorageConnectionError(
                f"Could not connect to object storage at "
                f"{self._settings.endpoint_url}: {exc}"
            ) from exc
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"Upload failed for key {key!r}: {exc}") from exc

        return key

    async def download_stream(self, key: str) -> AsyncIterator[bytes]:
        """Download an object as a stream of chunks.

        Args:
            key: Object key to download

        Yields:
            Byte chunks of the object body

        Raises:
            StorageObjectNotFoundError: If the key does not exist
            StorageConnectionError: If storage is unreachable
        """
        try:
            async with self._client() as client:
                response = await client.get_object(
                    Bucket=self._settings.bucket_name,
                    Key=key,
                )
                async for chunk in response["Body"].iter_chunks(64 * 1024):
                    yield chunk
        except _CONNECTION_ERROR_TYPES as exc:
            raise StorageConnectionError(
                f"Could not connect to object storage at "
                f"{self._settings.endpoint_url}: {exc}"
            ) from exc
        except ClientError as exc:
            if _is_not_found(exc):
                raise StorageObjectNotFoundError(
                    f"Object {key!r} not found in bucket "
                    f"{self._settings.bucket_name!r}"
                ) from exc
            raise StorageError(f"Download failed for key {key!r}: {exc}") from exc
        except BotoCoreError as exc:
            raise StorageError(f"Download failed for key {key!r}: {exc}") from exc

    async def delete(self, key: str) -> None:
        """Delete an object (idempotent for missing keys).

        Args:
            key: Object key to delete

        Raises:
            StorageConnectionError: If storage is unreachable
            StorageError: On any other storage failure
        """
        try:
            async with self._client() as client:
                await client.delete_object(
                    Bucket=self._settings.bucket_name,
                    Key=key,
                )
        except _CONNECTION_ERROR_TYPES as exc:
            raise StorageConnectionError(
                f"Could not connect to object storage at "
                f"{self._settings.endpoint_url}: {exc}"
            ) from exc
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"Delete failed for key {key!r}: {exc}") from exc

    async def generate_presigned_url(
        self,
        key: str,
        expiry_seconds: int,
    ) -> str:
        """Generate a time-limited download URL for an object.

        Args:
            key: Object key to grant access to
            expiry_seconds: URL validity window in seconds

        Returns:
            Signed URL string

        Raises:
            StorageError: If the URL cannot be generated
        """
        try:
            async with self._client() as client:
                url: str = await client.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": self._settings.bucket_name,
                        "Key": key,
                    },
                    ExpiresIn=expiry_seconds,
                )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(
                f"Presigned URL generation failed for key {key!r}: {exc}"
            ) from exc

        return url

    async def exists(self, key: str) -> bool:
        """Check whether an object exists via HEAD.

        Args:
            key: Object key to check

        Returns:
            True if the object exists, False otherwise

        Raises:
            StorageConnectionError: If storage is unreachable
        """
        try:
            async with self._client() as client:
                await client.head_object(
                    Bucket=self._settings.bucket_name,
                    Key=key,
                )
            return True
        except ClientError as exc:
            if _is_not_found(exc):
                return False
            raise StorageError(
                f"Existence check failed for key {key!r}: {exc}"
            ) from exc
        except _CONNECTION_ERROR_TYPES as exc:
            raise StorageConnectionError(
                f"Could not connect to object storage at "
                f"{self._settings.endpoint_url}: {exc}"
            ) from exc
        except BotoCoreError as exc:
            raise StorageError(
                f"Existence check failed for key {key!r}: {exc}"
            ) from exc


def _is_not_found(exc: ClientError) -> bool:
    """Whether a ClientError represents a missing object/bucket."""
    error_code = exc.response.get("Error", {}).get("Code", "")
    return error_code in {"404", "NoSuchKey", "NotFound"}
