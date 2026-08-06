"""
DigitalAsset repository implementation.

Concrete PostgreSQL repository for DigitalAsset entity CRUD and queries.

This repository manages persistence of DigitalAsset entities (digital artifacts
submitted for security analysis: URLs, domains, IPs, file hashes, uploaded files).
DigitalAssets are the central entity around which all analysis, verdicts, and
reports revolve.

**Key Design Decisions:**

1. **Soft-Delete Entity:** DigitalAsset uses soft delete
   (_is_soft_delete_entity returns True). Assets are archived (deleted) by users
   but preserved for audit trail. All queries automatically filter deleted_at IS NULL.

2. **No Eager Loading:** DigitalAsset has relationships (user, analyses) but does
   not eagerly load them by default. User relationship is handled by ORM lazy
   loading. Analyses collection is not eagerly loaded (may be large).

3. **Immutable After Creation:** DigitalAssets are not updated (except is_active
   flag for user control). Core fields (asset_type, raw_value, normalized_value,
   upload_id, metadata) never change. This preserves the historical record.

4. **Query Methods:** Three domain-specific queries:
   - get_by_hash(sha256_hash): File hash lookup (for file_hash asset type)
   - list_by_user(user_id): User's assets (common for UI)
   - get_by_normalized_value(asset_type, normalized_value): Deduplication check
     (supports idempotency: submitting same asset twice returns existing)

5. **Error Mapping:** All database operations wrapped in try/except that
   converts SQLAlchemy exceptions to domain exceptions.

**Soft-Delete Filtering:**
   DigitalAsset USES soft-delete. _is_soft_delete_entity() returns True.
   All methods automatically filter deleted_at IS NULL:
   - get_by_id(): Excludes soft-deleted assets
   - list(): Excludes soft-deleted assets
   - get_by_hash(): Excludes soft-deleted assets
   - list_by_user(): Excludes soft-deleted assets
   - get_by_normalized_value(): Excludes soft-deleted assets

**Pagination:**
   list_by_user() returns (results, total_count) for UI pagination controls.
   Counts only non-deleted assets.

**Transaction Safety:**
   Repositories do NOT commit/rollback. Transaction lifecycle managed by
   FastAPI dependency injection (per-request, atomic).

Traces to: E3.T7 Specification § Task T7 (DigitalAssetRepository implementation)
Traces to: E3.T7 Design § Section 4.3 (Repository Pattern), Section 6 (Soft-Delete)
Traces to: 04-Database-Design § DigitalAsset ORM (Soft-Delete, UNIQUE constraints)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List  # noqa: UP035

from sqlalchemy import and_, asc, desc, func, select

from app.domain.exceptions import NotFound
from app.domain.repositories.digital_asset import DigitalAssetRepository
from app.infrastructure.database.repositories.base import PostgreSQLRepository
from app.infrastructure.database.repositories.exceptions import map_db_exception
from app.models.digital_asset import DigitalAsset as DigitalAssetORM


if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.entities.digital_asset import DigitalAsset


class PostgreSQLDigitalAssetRepository(
    PostgreSQLRepository["DigitalAsset"], DigitalAssetRepository
):
    """
    PostgreSQL repository implementation for DigitalAsset entity.

    Implements the DigitalAssetRepository interface for persistence of DigitalAsset
    entities. Manages digital artifacts (URLs, domains, IPs, file hashes, files)
    submitted for security analysis.

    **Inheritance Chain:**
    ```
    DigitalAssetRepository (domain interface)
          ↑
          │ implements
          │
    PostgreSQLRepository[DigitalAsset] (base implementation)
          ↑
          │ inherits
          │
    PostgreSQLDigitalAssetRepository (concrete implementation)
    ```

    **CRUD Methods (from PostgreSQLRepository):**
    - create(entity: DigitalAsset) -> DigitalAsset
    - get_by_id(entity_id: UUID) -> DigitalAsset
    - list(skip, limit, sort_by, sort_order, **filters) -> (List[DigitalAsset], int)
    - update(entity_id: UUID, updates: dict) -> DigitalAsset
    - delete(entity_id: UUID) -> None

    **DigitalAsset-Specific Query Methods (from DigitalAssetRepository):**
    - get_by_hash(sha256_hash: str) -> DigitalAsset
    - list_by_user(user_id: UUID, skip, limit, sort_by, sort_order)
      -> (List[DigitalAsset], int)
    - get_by_normalized_value(asset_type: str, normalized_value: str) -> DigitalAsset

    **Soft-Delete Behavior:**
    DigitalAsset USES soft-delete (with deleted_at field).
    - _is_soft_delete_entity() returns True
    - delete() sets deleted_at = now() (soft delete)
    - get_by_id() filters deleted_at IS NULL
    - list() filters deleted_at IS NULL
    - All query methods automatically apply soft-delete filtering

    **Error Mapping:**
    All database exceptions are caught and converted to domain exceptions:
    - IntegrityError with UNIQUE constraint → AlreadyExists (duplicate identity)
    - IntegrityError with FK constraint → ConstraintViolation (invalid refs)
    - NoResultFound → NotFound (query returned no rows)

    Example:
        ```python
        from app.infrastructure.database.repositories.digital_asset import (
            PostgreSQLDigitalAssetRepository
        )
        from app.models.digital_asset import DigitalAsset, AssetType
        from uuid import uuid4

        # Create repository (injected by FastAPI dependency)
        asset_repo = PostgreSQLDigitalAssetRepository(session)

        # Create asset
        new_asset = DigitalAsset(
            user_id=user_id,
            asset_type=AssetType.DOMAIN.value,
            raw_value="Evil.COM",
            normalized_value="evil.com",
            display_label="Suspect C2",
            metadata_json={"tld": "com"},
            is_active=True,
        )
        created = await asset_repo.create(new_asset)

        # Idempotency check: does user already have this asset?
        try:
            existing = await asset_repo.get_by_normalized_value(
                asset_type=AssetType.DOMAIN.value,
                normalized_value="evil.com"
            )
            # Asset exists, use existing
        except NotFound:
            # Create new asset
            pass

        # Query by hash (for file_hash type)
        asset = await asset_repo.get_by_hash(
            "a3f5c1d8e9f2b7c4a6d1e8f3b7c9d2e1"
        )

        # List user's assets (most recent first, excluding deleted)
        assets, total = await asset_repo.list_by_user(
            user_id=user_id,
            skip=0,
            limit=50,
        )

        # Soft delete asset (preserved for audit trail, excluded from queries)
        await asset_repo.delete(asset_id)
        ```

    Traces to: E3.T7 Specification § Task T7 (DigitalAssetRepository)
    Traces to: E3.T7 Design § Section 4.3 (PostgreSQL Repository Pattern)
    Traces to: E3.T7 Design § Section 6 (Soft-Delete Implementation)
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with async session.

        Args:
            session: AsyncSession for database operations (request-scoped)
        """
        super().__init__(session)
        self._model_class = DigitalAssetORM
        self._entity_name = "DigitalAsset"

    def _to_orm(self, entity: DigitalAsset) -> DigitalAssetORM:
        """
        Convert domain DigitalAsset entity to ORM model.

        Args:
            entity: Domain DigitalAsset entity

        Returns:
            DigitalAssetORM model instance
        """
        import json

        return DigitalAssetORM(
            id=entity.id,
            user_id=entity.user_id,
            upload_id=entity.upload_id,
            asset_type=entity.asset_type,
            raw_value=entity.raw_value,
            normalized_value=entity.normalized_value,
            display_label=entity.display_label,
            metadata_json=(
                json.loads(entity.metadata_json)
                if entity.metadata_json
                else None
            ),
            is_active=entity.is_active,
            deleted_at=entity.deleted_at,
        )

    def _to_domain(self, orm_obj: DigitalAssetORM) -> DigitalAsset:
        """
        Convert ORM model to domain DigitalAsset entity.

        Args:
            orm_obj: DigitalAssetORM model instance

        Returns:
            Domain DigitalAsset entity
        """
        # Import here to avoid circular imports at module level
        import json

        from app.domain.entities.digital_asset import DigitalAsset

        return DigitalAsset(
            id=orm_obj.id,
            user_id=orm_obj.user_id,
            upload_id=orm_obj.upload_id,
            asset_type=orm_obj.asset_type,
            raw_value=orm_obj.raw_value,
            normalized_value=orm_obj.normalized_value,
            display_label=orm_obj.display_label,
            metadata_json=(
                json.dumps(orm_obj.metadata_json)
                if orm_obj.metadata_json
                else None
            ),
            is_active=orm_obj.is_active,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
            deleted_at=orm_obj.deleted_at,
        )

    def _build_where_clauses(self, **filters: object) -> List[Any]:  # noqa: UP006
        """
        Build WHERE clauses from filter arguments.

        Supported filters:
        - user_id: Filter by user (UUID)
        - asset_type: Filter by asset type (str)
        - is_active: Filter by active status (bool)

        Args:
            **filters: Filter arguments

        Returns:
            List of WHERE clause expressions
        """
        clauses: list[Any] = []

        if "user_id" in filters:
            clauses.append(DigitalAssetORM.user_id == filters["user_id"])

        if "asset_type" in filters:
            clauses.append(DigitalAssetORM.asset_type == filters["asset_type"])

        if "is_active" in filters:
            clauses.append(DigitalAssetORM.is_active == filters["is_active"])

        return clauses

    def _apply_eager_loading(self, stmt: Any) -> Any:  # noqa: ANN401
        """
        Apply eager loading for relationships.

        DigitalAsset has relationships (user, analyses) but does not eagerly load
        them by default. User relationship is handled by ORM lazy loading strategy.
        Analyses collection is not eagerly loaded (may grow large over time).

        Return statement unchanged (no selectinload/joinedload).

        Args:
            stmt: SQLAlchemy Select statement

        Returns:
            Select statement (unchanged for DigitalAsset)
        """
        # No eager loading needed for DigitalAsset
        return stmt

    def _is_soft_delete_entity(self) -> bool:
        """
        Indicate if entity uses soft-delete.

        DigitalAsset USES soft-delete. Assets can be archived/deleted by users
        but are preserved in the database for audit trail.

        Returns:
            True (DigitalAsset uses soft delete)
        """
        return True

    async def get_by_hash(self, sha256_hash: str) -> DigitalAsset:
        """
        Retrieve asset by SHA-256 hash (for file_hash asset type).

        Performs a lookup of the asset by its SHA-256 content hash. This is used
        when a file's hash (not the file itself) is submitted for analysis.
        Returns the first asset with the matching hash (case-insensitive hex
        comparison).

        Soft-delete filtering is applied: soft-deleted assets (deleted_at IS NOT NULL)
        are excluded from the search result.

        Args:
            sha256_hash: SHA-256 hash in hex format (64 characters)

        Returns:
            DigitalAsset entity with the specified hash

        Raises:
            NotFound: If no asset found with the specified hash, or if asset is
                     soft-deleted (deleted_at IS NOT NULL)

        Example:
            >>> asset = await asset_repo.get_by_hash(
            ...     "a3f5c1d8e9f2b7c4a6d1e8f3b7c9d2e1"
            ... )

        Traces to: E3.T7 Specification § Requirement R4.3 (DigitalAssetRepository)
        Traces to: 02-Domain-Model § Asset Type (FILE_HASH)
        """
        try:
            stmt = (
                select(DigitalAssetORM)
                .where(
                    and_(
                        DigitalAssetORM.metadata_json["sha256_hash"].astext
                        == sha256_hash,
                        DigitalAssetORM.deleted_at.is_(None),
                    )
                )
            )
            orm_obj = await self.session.scalar(stmt)
            if not orm_obj:
                raise NotFound(
                    f"DigitalAsset with hash {sha256_hash} not found"
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
    ) -> tuple[List[DigitalAsset], int]:  # noqa: UP006
        """
        List assets belonging to a specific user, paginated.

        Retrieves a paginated list of all digital assets submitted by the specified
        user. Results are ordered by default by most recent first (created_at DESC).
        Soft-deleted assets are excluded (deleted_at IS NULL applied automatically).
        This is the primary method for UI pages showing "My Assets".

        Args:
            user_id: UUID of the user whose assets to retrieve
            skip: Number of assets to skip (pagination offset), default 0
            limit: Maximum assets to return per page, default 100
            sort_by: Column to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")

        Returns:
            Tuple of (assets, total_count) where:
            - assets: List of DigitalAsset entities belonging to user (not deleted)
            - total_count: Total number of non-deleted assets by user
              (for pagination UI)

        Example:
            >>> results, total = await asset_repo.list_by_user(
            ...     user_id=user_id,
            ...     skip=0,
            ...     limit=50,
            ... )
            >>> print(f"User has {total} assets, showing page 1")

        Traces to: E3.T7 Specification § Requirement R4.3
        Traces to: 04-Database-Design § DigitalAsset Index
                   (ix_digital_assets_user_created)
        """
        try:
            # Build WHERE clause for user_id and soft-delete filter
            stmt = (
                select(DigitalAssetORM)
                .where(
                    and_(
                        DigitalAssetORM.user_id == user_id,
                        DigitalAssetORM.deleted_at.is_(None),
                    )
                )
            )

            # Count total (non-deleted assets by user)
            count_stmt = (
                select(func.count())
                .select_from(DigitalAssetORM)
                .where(
                    and_(
                        DigitalAssetORM.user_id == user_id,
                        DigitalAssetORM.deleted_at.is_(None),
                    )
                )
            )
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting
            sort_column = getattr(DigitalAssetORM, sort_by)
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

    async def get_by_normalized_value(
        self,
        asset_type: str,
        normalized_value: str,
    ) -> DigitalAsset:
        """
        Retrieve asset by domain identity (normalized_value + asset_type).

        Performs a lookup of the asset using the domain identity: the combination of
        asset_type and normalized_value. This is the deduplication key used for
        idempotency: submitting the same asset twice returns the existing asset
        (no duplicate created).

        The domain identity is unique per user (enforced by UNIQUE constraint):
        a user cannot have two assets with the same asset_type + normalized_value pair.
        However, different users can have the same domain identity (they reference
        the same threat/resource).

        Soft-delete filtering is applied: soft-deleted assets (deleted_at IS NOT NULL)
        are excluded from the search result.

        Args:
            asset_type: Asset classification (url, domain, ip_address, file_hash, file)
            normalized_value: Canonicalized form (lowercased domain, defanged URL, etc.)

        Returns:
            DigitalAsset entity with the specified domain identity

        Raises:
            NotFound: If no asset found with the specified type and value, or if
                     asset is soft-deleted (deleted_at IS NOT NULL)

        Example:
            ```python
            # Check if user already has this asset (idempotency)
            try:
                asset = await asset_repo.get_by_normalized_value(
                    asset_type="domain",
                    normalized_value="evil.com"
                )
                # Asset already exists, use existing
            except NotFound:
                # Create new asset
                asset = await asset_repo.create(...)
            ```

        Traces to: E3.T7 Specification § Requirement R4.3
        Traces to: 02-Domain-Model § Asset deduplication (domain identity)
        Traces to: 04-Database-Design § DigitalAsset UNIQUE constraint
        """
        try:
            stmt = (
                select(DigitalAssetORM)
                .where(
                    and_(
                        DigitalAssetORM.normalized_value == normalized_value,
                        DigitalAssetORM.asset_type == asset_type,
                        DigitalAssetORM.deleted_at.is_(None),
                    )
                )
            )
            orm_obj = await self.session.scalar(stmt)
            if not orm_obj:
                raise NotFound(
                    f"DigitalAsset with type {asset_type} and value "
                    f"{normalized_value} not found"
                )
            return self._to_domain(orm_obj)
        except NotFound:
            raise
        except Exception as exc:
            raise map_db_exception(exc) from exc
