"""
Upload repository implementation.

Concrete PostgreSQL repository for Upload entity CRUD and queries.

This repository manages persistence of Upload entities (documents ingested by users).
Uploads track the lifecycle of file submissions from receipt (pending) through
processing (validation, hashing) to terminal state (completed/failed).

**Key Design Decisions:**

1. **Hard-Delete Entity:** Upload uses hard delete (_is_soft_delete_entity
   returns False). Uploads are immutable historical records and must be
   permanently preserved for audit trail. No deleted_at field on Upload ORM model.

2. **No Eager Loading:** Upload has no foreign key relationships of interest.
   The user_id FK is not eagerly loaded (stored as denormalized value).
   Database join already handled via ORM relationship definition.

3. **Immutable After Creation:** Uploads are not updated (except status state machine).
   Core fields (user_id, storage_key, content_type, file_size_bytes) never change.

4. **Query Methods:** Three domain-specific queries:
   - get_by_storage_key(storage_key): Unique immutable S3 key lookup
   - list_by_user(user_id): User's upload history (common for UI)
   - list_by_status(status): Admin dashboards, job queue monitoring

5. **Error Mapping:** All database operations wrapped in try/except that
   converts SQLAlchemy exceptions to domain exceptions.

**Soft-Delete Filtering:**
   Upload does NOT use soft-delete. All records are queryable.
   _is_soft_delete_entity() returns False.

**Pagination:**
   list_by_user() and list_by_status() return (results, total_count) for UI
   pagination controls.

**Transaction Safety:**
   Repositories do NOT commit/rollback. Transaction lifecycle managed by
   FastAPI dependency injection (per-request, atomic).

Traces to: E3.T7 Specification § Task T7 (UploadRepository implementation)
Traces to: E3.T7 Design § Section 4.3 (Repository Pattern)
Traces to: 04-Database-Design § Upload ORM (Storage Key UNIQUE, Status enum)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List  # noqa: UP035

from sqlalchemy import asc, desc, func, select

from app.domain.exceptions import NotFound
from app.domain.repositories.upload import UploadRepository
from app.infrastructure.database.repositories.base import PostgreSQLRepository
from app.infrastructure.database.repositories.exceptions import map_db_exception
from app.models.upload import Upload as UploadORM


if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.entities.upload import Upload


class PostgreSQLUploadRepository(PostgreSQLRepository["Upload"], UploadRepository):
    """
    PostgreSQL repository implementation for Upload entity.

    Implements the UploadRepository interface for persistence of Upload entities.
    Manages file upload records throughout their lifecycle (pending → processing →
    completed/failed).

    **Inheritance Chain:**
    ```
    UploadRepository (domain interface)
          ↑
          │ implements
          │
    PostgreSQLRepository[Upload] (base implementation)
          ↑
          │ inherits
          │
    PostgreSQLUploadRepository (concrete implementation)
    ```

    **CRUD Methods (from PostgreSQLRepository):**
    - create(entity: Upload) -> Upload
    - get_by_id(entity_id: UUID) -> Upload
    - list(skip, limit, sort_by, sort_order, **filters) -> (List[Upload], int)
    - update(entity_id: UUID, updates: dict) -> Upload
    - delete(entity_id: UUID) -> None

    **Upload-Specific Query Methods (from UploadRepository):**
    - get_by_storage_key(storage_key: str) -> Upload
    - list_by_user(user_id: UUID, skip, limit, sort_by, sort_order)
      -> (List[Upload], int)
    - list_by_status(status: str, skip, limit, sort_by, sort_order)
      -> (List[Upload], int)

    **Soft-Delete Behavior:**
    Upload does NOT use soft-delete (hard delete only).
    - _is_soft_delete_entity() returns False
    - delete() removes the row permanently (no deleted_at field)
    - list() and get_by_id() do NOT filter deleted_at

    **Error Mapping:**
    All database exceptions are caught and converted to domain exceptions:
    - IntegrityError with UNIQUE constraint → AlreadyExists (duplicate storage_key)
    - IntegrityError with FK constraint → ConstraintViolation (invalid user_id)
    - NoResultFound → NotFound (query returned no rows)

    Example:
        ```python
        from app.infrastructure.database.repositories.upload import (
            PostgreSQLUploadRepository
        )
        from app.models.upload import Upload
        from uuid import uuid4

        # Create repository (injected by FastAPI dependency)
        upload_repo = PostgreSQLUploadRepository(session)

        # Create upload
        new_upload = Upload(
            user_id=user_id,
            original_filename="report.pdf",
            storage_key="uploads/2025/07/19/uuid/report.pdf",
            content_type="application/pdf",
            file_size_bytes=1024,
            upload_status=UploadStatus.PENDING.value,
        )
        created = await upload_repo.create(new_upload)

        # Query by storage key (unique, immutable)
        upload = await upload_repo.get_by_storage_key(
            "uploads/2025/07/19/uuid/report.pdf"
        )

        # List user's uploads (most recent first)
        uploads, total = await upload_repo.list_by_user(
            user_id=user_id,
            skip=0,
            limit=50,
        )

        # List pending uploads (for job queue)
        pending, count = await upload_repo.list_by_status(
            status=UploadStatus.PENDING.value,
            skip=0,
            limit=100,
        )
        ```

    Traces to: E3.T7 Specification § Task T7 (UploadRepository)
    Traces to: E3.T7 Design § Section 4.3 (PostgreSQL Repository Pattern)
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with async session.

        Args:
            session: AsyncSession for database operations (request-scoped)
        """
        super().__init__(session)
        self._model_class = UploadORM
        self._entity_name = "Upload"

    def _to_orm(self, entity: Upload) -> UploadORM:
        """
        Convert domain Upload entity to ORM model.

        Args:
            entity: Domain Upload entity

        Returns:
            UploadORM model instance
        """
        return UploadORM(
            id=entity.id,
            user_id=entity.user_id,
            original_filename=entity.original_filename,
            storage_key=entity.storage_key,
            content_type=entity.content_type,
            file_size_bytes=entity.file_size_bytes,
            checksum_sha256=entity.checksum_sha256,
            upload_status=entity.upload_status,
            completed_at=entity.completed_at,
        )

    def _to_domain(self, orm_obj: UploadORM) -> Upload:
        """
        Convert ORM model to domain Upload entity.

        Args:
            orm_obj: UploadORM model instance

        Returns:
            Domain Upload entity
        """
        # Import here to avoid circular imports at module level
        from app.domain.entities.upload import Upload

        return Upload(
            id=orm_obj.id,
            user_id=orm_obj.user_id,
            original_filename=orm_obj.original_filename,
            storage_key=orm_obj.storage_key,
            content_type=orm_obj.content_type,
            file_size_bytes=orm_obj.file_size_bytes,
            checksum_sha256=orm_obj.checksum_sha256,
            upload_status=orm_obj.upload_status,
            completed_at=orm_obj.completed_at,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )

    def _build_where_clauses(self, **filters: object) -> List[Any]:  # noqa: UP006
        """
        Build WHERE clauses from filter arguments.

        Supported filters:
        - user_id: Filter by user (UUID)
        - status: Filter by upload_status (str)

        Args:
            **filters: Filter arguments

        Returns:
            List of WHERE clause expressions
        """
        clauses: list[Any] = []

        if "user_id" in filters:
            clauses.append(UploadORM.user_id == filters["user_id"])

        if "status" in filters:
            clauses.append(UploadORM.upload_status == filters["status"])

        return clauses

    def _apply_eager_loading(self, stmt: Any) -> Any:  # noqa: ANN401
        """
        Apply eager loading for relationships.

        Upload has no foreign key relationships of interest (user_id is already
        denormalized). Return statement unchanged.

        Args:
            stmt: SQLAlchemy Select statement

        Returns:
            Select statement (unchanged for Upload)
        """
        # No eager loading needed for Upload
        return stmt

    def _is_soft_delete_entity(self) -> bool:
        """
        Indicate if entity uses soft-delete.

        Upload does NOT use soft-delete. All uploads are hard-deleted or
        preserved permanently (no deleted_at field).

        Returns:
            False (Upload uses hard delete)
        """
        return False

    async def get_by_storage_key(self, storage_key: str) -> Upload:
        """
        Retrieve upload by storage key (immutable S3/MinIO object key).

        Performs a lookup of the upload by its immutable storage key (e.g.,
        uploads/2025/07/19/uuid/filename.pdf). The storage key is unique across
        all uploads and never changes. Used to retrieve an upload when you have
        the storage location but not the upload ID.

        Args:
            storage_key: The S3/MinIO object key (immutable, unique)

        Returns:
            Upload entity with the specified storage key

        Raises:
            NotFound: If no upload found with the specified storage key

        Example:
            >>> upload = await upload_repo.get_by_storage_key(
            ...     "uploads/2025/07/19/a1b2c3d4-e5f6-47g8/report.pdf"
            ... )

        Traces to: E3.T7 Specification § Requirement R4.2 (UploadRepository queries)
        Traces to: 04-Database-Design § Upload (storage_key UNIQUE, immutable)
        """
        try:
            stmt = select(UploadORM).where(UploadORM.storage_key == storage_key)
            orm_obj = await self.session.scalar(stmt)
            if not orm_obj:
                raise NotFound(
                    f"Upload with storage_key {storage_key} not found"
                )
            return self._to_domain(orm_obj)
        except NotFound:
            raise
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def list_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[List[Upload], int]:  # noqa: UP006
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
            >>> results, total = await upload_repo.list_by_user(
            ...     user_id=user_id,
            ...     skip=0,
            ...     limit=50,
            ... )
            >>> print(f"User has {total} uploads, showing page 1")

        Traces to: E3.T7 Specification § Requirement R4.2
        Traces to: 04-Database-Design § Upload Index (ix_uploads_user_created)
        """
        try:
            # Build WHERE clause for user_id
            stmt = select(UploadORM).where(UploadORM.user_id == user_id)

            # Count total
            count_stmt = (
                select(func.count())
                .select_from(UploadORM)
                .where(UploadORM.user_id == user_id)
            )
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting
            sort_column = getattr(UploadORM, sort_by)
            if sort_order.lower() == "desc":
                stmt = stmt.order_by(desc(sort_column))
            else:
                stmt = stmt.order_by(asc(sort_column))

            # Apply pagination
            stmt = stmt.offset(skip).limit(limit)

            # Execute query
            results = await self.session.scalars(stmt)
            domain_results = [self._to_domain(orm) for orm in results]

            return (domain_results, total)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def list_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[List[Upload], int]:  # noqa: UP006
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
            >>> pending, count = await upload_repo.list_by_status(
            ...     status=UploadStatus.PENDING.value,
            ...     skip=0,
            ...     limit=50,
            ... )
            >>> print(f"Found {count} pending uploads")

        Traces to: E3.T7 Specification § Requirement R4.2
        Traces to: 02-Domain-Model § Upload entity (status lifecycle)
        """
        try:
            # Build WHERE clause for status
            stmt = select(UploadORM).where(UploadORM.upload_status == status)

            # Count total
            count_stmt = (
                select(func.count())
                .select_from(UploadORM)
                .where(UploadORM.upload_status == status)
            )
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting
            sort_column = getattr(UploadORM, sort_by)
            if sort_order.lower() == "desc":
                stmt = stmt.order_by(desc(sort_column))
            else:
                stmt = stmt.order_by(asc(sort_column))

            # Apply pagination
            stmt = stmt.offset(skip).limit(limit)

            # Execute query
            results = await self.session.scalars(stmt)
            domain_results = [self._to_domain(orm) for orm in results]

            return (domain_results, total)
        except Exception as exc:
            raise map_db_exception(exc) from exc
