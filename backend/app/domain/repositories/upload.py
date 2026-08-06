"""
UploadRepository domain interface.

Defines the abstract contract for upload-related CRUD and query operations.
Implementations must not leak infrastructure details (SQLAlchemy, ORM models)
to the Domain layer.

The UploadRepository interface is used by Application layer services to track
file uploads throughout their lifecycle (pending → processing → completed/failed).

Methods:
    - create(entity: Upload) -> Upload
    - get_by_id(entity_id: UUID) -> Upload
    - list(skip, limit, sort_by, sort_order, **filters)
      -> (List[Upload], int)
    - update(entity_id: UUID, updates: dict) -> Upload
    - delete(entity_id: UUID) -> None
    - get_by_storage_key(storage_key: str) -> Upload (upload-specific query)
    - list_by_user(user_id: UUID, skip, limit)
      -> (List[Upload], int) (upload-specific query)
    - list_by_status(status: str, skip, limit)
      -> (List[Upload], int) (upload-specific query)

Soft-delete filtering:
    - list() and get_by_id() do NOT apply soft-delete filtering for Upload
    - Uploads are hard-delete entities (no deleted_at field)
    - All upload records are always queryable (audit trail via created_at)

Exception Contract:
    - get_by_id() raises NotFound if upload not found
    - get_by_storage_key() raises NotFound if upload not found
    - create() raises AlreadyExists if storage_key already exists (UNIQUE constraint)
    - create() raises ConstraintViolation if user_id references non-existent user
    - All methods may raise RepositoryException on unexpected errors

Traces to: E3.T7 Specification § Requirement R1 (Domain Interfaces)
Traces to: E3.T7 Specification § Requirement R4 (Domain-Specific Queries)
Traces to: E3.T7 Design § Section 3.2 (UploadRepository interface)
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from app.domain.repositories.base import BaseRepository


if TYPE_CHECKING:
    from app.domain.entities.upload import Upload


class UploadRepository(BaseRepository["Upload"]):
    """
    Abstract repository interface for Upload entity CRUD and queries.

    Manages all upload-related persistence operations for the Domain layer.
    Implementations handle database-specific details (SQLAlchemy async,
    PostgreSQL constraints, etc.) transparently.

    Inherits CRUD methods from BaseRepository[Upload]:
        - create(entity: Upload) -> Upload
        - get_by_id(entity_id: UUID) -> Upload
        - list(skip, limit, sort_by, sort_order, **filters) -> (List[Upload], int)
        - update(entity_id: UUID, updates: dict) -> Upload
        - delete(entity_id: UUID) -> None

    Adds upload-specific query methods:
        - get_by_storage_key(storage_key: str) -> Upload
        - list_by_user(user_id: UUID, skip, limit) -> (List[Upload], int)
        - list_by_status(status: str, skip, limit) -> (List[Upload], int)

    Soft-Delete Behavior:
        Upload entities do NOT have soft-delete support. All uploads are hard-deleted
        or preserved permanently. There is no deleted_at field on the Upload ORM model.
        All upload records are queryable and form part of the audit trail.

    Transaction Safety:
        - Methods do NOT commit/rollback transactions
        - Transaction lifecycle is managed by FastAPI dependency injection
        - All repository operations in a request are atomic

    Exception Contract:
        - get_by_id(id) raises NotFound if upload not found
        - get_by_storage_key(key) raises NotFound if no upload with that storage key
        - create(upload) raises AlreadyExists if storage_key already exists
        - create(upload) raises ConstraintViolation if user_id is invalid
        - update(id, updates) may raise NotFound, AlreadyExists, ConstraintViolation
        - delete(id) is idempotent (deleting non-existent upload is no-op)

    Example:
        ```python
        # Service depends on the interface, not implementation
        class UploadService:
            def __init__(self, upload_repo: UploadRepository):
                self.upload_repo = upload_repo

            async def get_user_uploads(
                self, user_id: UUID, page: int = 1
            ) -> (List[Upload], int):
                skip = (page - 1) * 50
                return await self.upload_repo.list_by_user(
                    user_id, skip=skip, limit=50
                )

            async def get_upload_by_key(self, storage_key: str) -> Upload:
                return await self.upload_repo.get_by_storage_key(storage_key)
        ```

    Traces to: E3.T7 Specification § Requirement R1 (Domain Interfaces)
    Traces to: E3.T7 Specification § Requirement R4.2 (UploadRepository queries)
    Traces to: E3.T7 Design § Section 3.2 (UploadRepository pattern)
    Traces to: 03-Architecture §4 (Domain layer)
    """

    @abstractmethod
    async def get_by_storage_key(self, storage_key: str) -> Upload:
        """
        Retrieve upload by storage key (immutable S3/MinIO object key).

        Performs a lookup of the upload by its immutable storage key. The storage key
        is the S3/MinIO object identifier (e.g., uploads/2025/07/19/uuid/filename.pdf)
        and is unique across all uploads. This method is used to retrieve an upload
        when you have the storage location but not the upload ID.

        Args:
            storage_key: The S3/MinIO object key (immutable, unique across uploads)

        Returns:
            Upload entity with the specified storage key

        Raises:
            NotFound: If no upload found with the specified storage key

        Example:
            ```python
            upload = await upload_repo.get_by_storage_key(
                "uploads/2025/07/19/a1b2c3d4-e5f6-47g8-h9i0/report.pdf"
            )
            ```

        Traces to: E3.T7 Specification § Requirement R4.2
        Traces to: 04-Database-Design § Upload Entity (storage_key field)
        """
        pass

    @abstractmethod
    async def list_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Upload], int]:
        """
        List uploads belonging to a specific user, paginated.

        Retrieves a paginated list of all uploads submitted by the specified user.
        Results are ordered by default by most recent first (created_at DESC).
        This is the primary method for UI pages showing "My Uploads".

        Args:
            user_id: UUID of the user whose uploads to retrieve
            skip: Number of uploads to skip (pagination offset), default 0
            limit: Maximum uploads to return per page, default 100
            sort_by: Column to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")

        Returns:
            Tuple of (uploads, total_count) where:
            - uploads: List of Upload entities belonging to user
            - total_count: Total number of uploads by user (for pagination UI)

        Example:
            ```python
            results, total = await upload_repo.list_by_user(
                user_id=user_id,
                skip=0,
                limit=50,
                sort_by="created_at",
                sort_order="desc"
            )
            # results: list of 50 most recent uploads by user
            # total: total uploads by user (for "Page 1 of X" UI)
            ```

        Traces to: E3.T7 Specification § Requirement R4.2
        Traces to: 04-Database-Design § Upload Index (ix_uploads_user_created)
        """
        pass

    @abstractmethod
    async def list_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Upload], int]:
        """
        List uploads filtered by lifecycle status, paginated.

        Retrieves a paginated list of all uploads with the specified status
        (pending, processing, completed, or failed). Used for admin dashboards,
        job queue monitoring, and upload status reporting.

        Valid status values (from UploadStatus enum):
            - "pending": Uploads awaiting processing
            - "processing": Uploads currently being validated/hashed
            - "completed": Uploads successfully processed
            - "failed": Uploads that failed processing

        Args:
            status: Upload lifecycle status to filter by
            skip: Number of uploads to skip (pagination offset), default 0
            limit: Maximum uploads to return per page, default 100
            sort_by: Column to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")

        Returns:
            Tuple of (uploads, total_count) where:
            - uploads: List of Upload entities with specified status
            - total_count: Total number of uploads with status (for pagination UI)

        Example:
            ```python
            results, total = await upload_repo.list_by_status(
                status="pending",
                skip=0,
                limit=50
            )
            # results: list of 50 pending uploads (oldest first)
            # total: total pending uploads
            ```

        Traces to: E3.T7 Specification § Requirement R4.2
        Traces to: 02-Domain-Model § Upload entity (status lifecycle)
        """
        pass
