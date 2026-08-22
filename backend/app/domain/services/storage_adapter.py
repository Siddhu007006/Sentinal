"""
StorageAdapter domain interface.

Abstract contract for object storage operations. The Domain and
Application layers depend only on this interface; concrete
implementations (S3, MinIO, other S3-compatible stores) live in the
Infrastructure layer behind it.

This is the boundary required by 03-Architecture §4 (Infrastructure
adapters) and 00-Project-Context §6 ("files are never stored in
PostgreSQL"). Routes and services must never import the concrete
storage SDK (boto3/aioboto3) or this interface's implementations
directly.

Operations (22-Engineering-Backlog E5.T1):
    - upload_stream(key, stream, content_type) -> str
    - download_stream(key) -> AsyncIterator[bytes]
    - delete(key) -> None
    - generate_presigned_url(key, expiry) -> str
    - exists(key) -> bool

Exception contract (app.domain.exceptions):
    - StorageConnectionError: storage unreachable / request timed out
    - StorageObjectNotFoundError: key does not exist (where the
      operation requires existence)
    - StorageError: any other storage failure

Traces to: 22-Engineering-Backlog E5.T1 (Object Storage Adapter)
Traces to: 06-Repository-Structure § Infrastructure (storage/)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class StorageAdapter(ABC):
    """Abstract object storage adapter.

    Implementations persist and retrieve raw file bytes in an
    S3-compatible object store. Keys are opaque, unique identifiers
    assigned by the caller (the upload pipeline derives them from
    content hashes and identifiers).
    """

    @abstractmethod
    async def upload_stream(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        content_type: str,
    ) -> str:
        """Upload a stream of bytes as an object.

        Args:
            key: Object key (unique identifier within the bucket)
            stream: Async iterator of byte chunks
            content_type: MIME type of the content

        Returns:
            The key the object was stored under

        Raises:
            StorageConnectionError: If storage is unreachable
            StorageError: On any other storage failure
        """
        pass

    @abstractmethod
    def download_stream(self, key: str) -> AsyncIterator[bytes]:
        """Download an object as a stream of byte chunks.

        Args:
            key: Object key to download

        Returns:
            Async iterator yielding the object's bytes in chunks

        Raises:
            StorageObjectNotFoundError: If the key does not exist
            StorageConnectionError: If storage is unreachable
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete an object.

        Idempotent: deleting a non-existent key is a no-op.

        Args:
            key: Object key to delete

        Raises:
            StorageConnectionError: If storage is unreachable
            StorageError: On any other storage failure
        """
        pass

    @abstractmethod
    async def generate_presigned_url(
        self,
        key: str,
        expiry_seconds: int,
    ) -> str:
        """Generate a time-limited URL for downloading an object.

        Args:
            key: Object key to grant access to
            expiry_seconds: URL validity window in seconds

        Returns:
            Signed URL string that expires after expiry_seconds

        Raises:
            StorageError: If the URL cannot be generated
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check whether an object exists.

        Args:
            key: Object key to check

        Returns:
            True if the object exists, False otherwise

        Raises:
            StorageConnectionError: If storage is unreachable
        """
        pass
