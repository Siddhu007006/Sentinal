"""
DigitalAssetRepository domain interface.

Defines the abstract contract for digital asset-related CRUD and query operations.
Implementations must not leak infrastructure details (SQLAlchemy, ORM models)
to the Domain layer.

The DigitalAssetRepository interface is used by Application layer services to manage
digital assets (URLs, domains, IPs, file hashes, files) submitted for security analysis.

Methods:
    - create(entity: DigitalAsset) -> DigitalAsset
    - get_by_id(entity_id: UUID) -> DigitalAsset
    - list(skip, limit, sort_by, sort_order, **filters)
      -> (List[DigitalAsset], int)
    - update(entity_id: UUID, updates: dict) -> DigitalAsset
    - delete(entity_id: UUID) -> None
    - get_by_hash(sha256_hash: str) -> DigitalAsset (asset-specific query)
    - list_by_user(user_id: UUID, skip, limit)
      -> (List[DigitalAsset], int) (asset-specific query)
    - get_by_normalized_value(asset_type: str, value: str) -> DigitalAsset
      (deduplication query)

Soft-delete filtering is applied by default:
    - list() and get_by_id() automatically filter where deleted_at IS NULL
    - get_by_hash() automatically filters where deleted_at IS NULL
    - list_by_user() automatically filters where deleted_at IS NULL
    - get_by_normalized_value() automatically filters where deleted_at IS NULL

Exception Contract:
    - get_by_id() raises NotFound if asset not found or is soft-deleted
    - get_by_hash() raises NotFound if asset not found or is soft-deleted
    - get_by_normalized_value() raises NotFound if asset not found or is soft-deleted
    - create() raises AlreadyExists if (normalized_value, asset_type) already exists
    - create() raises ConstraintViolation if FK or CHECK constraint violated
    - All methods may raise RepositoryException on unexpected errors

Traces to: E3.T7 Specification § Requirement R1 (Domain Interfaces)
Traces to: E3.T7 Specification § Requirement R4 (Domain-Specific Queries)
Traces to: E3.T7 Design § Section 3.2 (DigitalAssetRepository interface)
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from app.domain.repositories.base import BaseRepository


if TYPE_CHECKING:
    from app.domain.entities.digital_asset import DigitalAsset


class DigitalAssetRepository(BaseRepository["DigitalAsset"]):
    """
    Abstract repository interface for DigitalAsset entity CRUD and queries.

    Manages all digital asset-related persistence operations for the Domain layer.
    Implementations handle database-specific details (SQLAlchemy async,
    PostgreSQL soft-delete filtering, deduplication constraints, etc.) transparently.

    Inherits CRUD methods from BaseRepository[DigitalAsset]:
        - create(entity: DigitalAsset) -> DigitalAsset
        - get_by_id(entity_id: UUID) -> DigitalAsset
        - list(skip, limit, sort_by, sort_order, **filters) -> (List[DigitalAsset], int)
        - update(entity_id: UUID, updates: dict) -> DigitalAsset
        - delete(entity_id: UUID) -> None

    Adds asset-specific query methods:
        - get_by_hash(sha256_hash: str) -> DigitalAsset
        - list_by_user(user_id: UUID, skip, limit) -> (List[DigitalAsset], int)
        - get_by_normalized_value(asset_type: str, value: str) -> DigitalAsset

    Soft-Delete Behavior:
        By default, all methods filter soft-deleted assets (deleted_at IS NULL).
        Soft-deleted assets are excluded from list() and get_by_id() operations.
        To retrieve soft-deleted assets, a separate method would be needed
        (e.g., list_all_including_deleted()) — not in Phase A scope.

    Deduplication via Domain Identity:
        Each asset has a domain identity: (normalized_value, asset_type) pair.
        A user cannot have two assets with the same domain identity.
        get_by_normalized_value() supports idempotency checks: submitting the
        same asset twice returns the existing asset (no duplicate created).

    Transaction Safety:
        - Methods do NOT commit/rollback transactions
        - Transaction lifecycle is managed by FastAPI dependency injection
        - All repository operations in a request are atomic

    Exception Contract:
        - get_by_id(id) raises NotFound if asset not found or soft-deleted
        - get_by_hash(hash) raises NotFound if no asset with that hash
        - get_by_normalized_value(type, value) raises NotFound if not found
        - create(asset) raises AlreadyExists if (normalized_value, asset_type) exists
        - create(asset) raises ConstraintViolation if FK or CHECK constraint violated
        - update(id, updates) may raise NotFound, AlreadyExists, ConstraintViolation
        - delete(id) is idempotent (deleting non-existent asset is no-op)

    Example:
        ```python
        # Service depends on the interface, not implementation
        class DigitalAssetService:
            def __init__(self, asset_repo: DigitalAssetRepository):
                self.asset_repo = asset_repo

            async def get_or_create_asset(
                self,
                user_id: UUID,
                asset_type: str,
                normalized_value: str,
                raw_value: str
            ) -> DigitalAsset:
                # Idempotency: check if asset exists
                try:
                    existing = await self.asset_repo.get_by_normalized_value(
                        asset_type, normalized_value
                    )
                    return existing
                except NotFound:
                    # Create new asset
                    return await self.asset_repo.create(
                        DigitalAsset(
                            user_id=user_id,
                            asset_type=asset_type,
                            normalized_value=normalized_value,
                            raw_value=raw_value
                        )
                    )
        ```

    Traces to: E3.T7 Specification § Requirement R1 (Domain Interfaces)
    Traces to: E3.T7 Specification § Requirement R4.3 (DigitalAssetRepository queries)
    Traces to: E3.T7 Design § Section 3.2 (DigitalAssetRepository pattern)
    Traces to: 03-Architecture §4 (Domain layer)
    """

    @abstractmethod
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
            ```python
            asset = await asset_repo.get_by_hash(
                "a3f5c1d8e9f2b7c4a6d1e8f3b7c9d2e1a3f5c1d8e9f2b7c4a6d1e8f3b7c9d2e1"
            )
            # Retrieves asset with file_hash type and matching checksum
            ```

        Traces to: E3.T7 Specification § Requirement R4.3
        Traces to: 02-Domain-Model § Asset Type (FILE_HASH)
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
    ) -> tuple[list[DigitalAsset], int]:
        """
        List assets belonging to a specific user, paginated.

        Retrieves a paginated list of all digital assets submitted by the
        specified user. Results are ordered by default by most recent first
        (created_at DESC). Soft-deleted assets are excluded (deleted_at IS NULL
        applied automatically). This is the primary method for UI pages showing
        "My Assets".

        Args:
            user_id: UUID of the user whose assets to retrieve
            skip: Number of assets to skip (pagination offset), default 0
            limit: Maximum assets to return per page, default 100
            sort_by: Column to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")

        Returns:
            Tuple of (assets, total_count) where:
            - assets: List of DigitalAsset entities belonging to user
              (not deleted)
            - total_count: Total number of non-deleted assets by user
              (for pagination UI)

        Example:
            ```python
            results, total = await asset_repo.list_by_user(
                user_id=user_id,
                skip=0,
                limit=50,
                sort_by="created_at",
                sort_order="desc"
            )
            # results: list of 50 most recent assets by user
            # total: total non-deleted assets by user (for "Page 1 of X" UI)
            ```

        Traces to: E3.T7 Specification § Requirement R4.3
        Traces to: 04-Database-Design § DigitalAsset Index
                   (ix_digital_assets_user_created)
        """
        pass

    @abstractmethod
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

        The domain identity is unique per user: different users can have the same
        normalized_value + asset_type pair (they reference the same threat/resource).

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
        pass
