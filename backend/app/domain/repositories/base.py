"""
Base repository interface.

Defines the abstract repository interface that all concrete repositories
implement. This is the contract between the Domain/Application layers and
the Infrastructure layer.

The BaseRepository[T] ABC defines five core CRUD methods:
- create(entity) -> T: Insert a new entity, return with generated ID
- get_by_id(id) -> T: Retrieve entity by ID, raise NotFound if missing
- list(skip, limit, **filters) -> (List[T], int): Paginated list with total count
- update(id, updates) -> T: Update fields, return updated entity
- delete(id) -> None: Delete entity (soft or hard per entity type)

All methods:
- Use async/await
- Return domain entities (never ORM models)
- Raise domain exceptions (NotFound, AlreadyExists, etc.)
- Never import SQLAlchemy or infrastructure code

This interface is implemented by PostgreSQLRepository and its subclasses.

Traces to: E3.T7 Specification § Requirement R1 (Domain Interfaces)
Traces to: E3.T7 Design § Section 3 (Domain Interfaces)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from uuid import UUID  # noqa: TC003


T = TypeVar("T")  # Generic entity type parameter


class BaseRepository(ABC, Generic[T]):  # noqa: UP046
    """
    Abstract base repository interface for CRUD operations on entities.

    Defines the contract that all repository implementations must follow.
    This interface has no SQLAlchemy imports and is pure Python, allowing
    the Domain layer to depend on it without any infrastructure knowledge.

    Type Parameter:
        T: The domain entity type this repository manages (e.g., User, Analysis)

    Methods:
        - create(entity: T) -> T
        - get_by_id(entity_id: UUID) -> T
        - list(skip, limit, sort_by, sort_order, **filters) -> tuple[List[T], int]
        - update(entity_id: UUID, updates: dict) -> T
        - delete(entity_id: UUID) -> None

    Exception Contract:
        - create() may raise AlreadyExists or ConstraintViolation
        - get_by_id() raises NotFound if entity not found
        - update() may raise NotFound, AlreadyExists, or ConstraintViolation
        - delete() is idempotent (deleting non-existent entity is no-op)

    Transaction Safety:
        - Repositories do NOT commit or rollback transactions
        - Transaction lifecycle is managed by the FastAPI dependency system
        - All repository operations within a single request are atomic

    Example:
        Services depend on repository interfaces, not implementations:

        ```python
        class AnalysisService:
            def __init__(
                self,
                analysis_repo: AnalysisRepository,
                asset_repo: DigitalAssetRepository
            ):
                self.analysis_repo = analysis_repo
                self.asset_repo = asset_repo

            async def request_analysis(
                self,
                asset_id: UUID,
                analyzer_key: str
            ) -> Analysis:
                # Services use repository interfaces
                asset = await self.asset_repo.get_by_id(asset_id)
                analysis = await self.analysis_repo.create(
                    Analysis(digital_asset_id=asset.id, ...)
                )
                return analysis
        ```

    Traces to: E3.T7 Specification § R1 (Domain Repository Interfaces)
    Traces to: 03-Architecture §4 (Domain layer design)
    """

    @abstractmethod
    async def create(self, entity: T) -> T:
        """
        Create a new entity in the repository.

        Inserts the entity into the database and returns it with generated
        ID and timestamps (created_at, updated_at) populated.

        Args:
            entity: The domain entity to create (typically with id=None)

        Returns:
            The persisted entity with id and timestamps set

        Raises:
            AlreadyExists: If unique constraint violated (e.g., duplicate email)
            ConstraintViolation: If foreign key or check constraint violated
            ConflictError: If other data integrity violation occurs

        Transaction Behavior:
            - Flushes the entity to get generated ID (within transaction)
            - Does NOT commit (caller manages transaction lifecycle)

        Example:
            ```python
            user = User(
                email="jane@example.com",
                full_name="Jane Doe",
                password_hash=...
            )
            created_user = await user_repo.create(user)
            # created_user.id is now set (UUID)
            # created_user.created_at is set to current time
            ```
        """
        pass

    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> T:
        """
        Retrieve a single entity by its ID.

        Queries the repository for an entity with the specified ID.
        For soft-delete repositories (User, DigitalAsset), automatically
        filters out soft-deleted records (deleted_at IS NULL).

        Args:
            entity_id: The UUID primary key of the entity

        Returns:
            The entity with the specified ID

        Raises:
            NotFound: If entity not found or entity is soft-deleted

        Example:
            ```python
            user = await user_repo.get_by_id(user_id)
            # Raises NotFound if user doesn't exist or is deleted
            ```
        """
        pass

    @abstractmethod
    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        **filters: object,
    ) -> tuple[list[T], int]:
        """
        Retrieve a paginated list of entities.

        Returns a page of entities matching optional filters, along with
        the total count of all matching entities (for pagination UI).

        For soft-delete repositories, automatically filters out soft-deleted
        records by default.

        Args:
            skip: Number of entities to skip (offset), default 0
            limit: Maximum entities to return per page, default 100
            sort_by: Column to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")
            **filters: Repository-specific filter arguments
                      (e.g., is_active=True, status="pending")

        Returns:
            Tuple of (results, total_count) where:
            - results: List of T entities matching filters and pagination
            - total_count: Total number of entities matching filters
                          (used for UI pagination controls)

        Example:
            ```python
            results, total = await user_repo.list(
                skip=0,
                limit=50,
                sort_by="email",
                sort_order="asc"
            )
            # results: list of 50 User entities
            # total: total count of all users (for "Page 1 of X" UI)
            ```
        """
        pass

    @abstractmethod
    async def update(self, entity_id: UUID, updates: dict[str, object]) -> T:
        """
        Update an entity's fields.

        Updates the specified fields of an entity and returns the updated entity.

        Args:
            entity_id: UUID of the entity to update
            updates: Dictionary of field name -> value to update
                    (e.g., {"is_active": False, "email": "new@example.com"})

        Returns:
            The updated entity

        Raises:
            NotFound: If entity doesn't exist
            AlreadyExists: If update violates unique constraint
            ConstraintViolation: If update violates FK or check constraint
            ConflictError: If other data integrity issue occurs

        Example:
            ```python
            updated_user = await user_repo.update(
                user_id,
                {"full_name": "New Name", "is_active": False}
            )
            ```
        """
        pass

    @abstractmethod
    async def delete(self, entity_id: UUID) -> None:
        """
        Delete an entity from the repository.

        For soft-delete entities (User, DigitalAsset), sets deleted_at timestamp.
        For hard-delete entities (AuditLog), removes row entirely.

        This operation is idempotent: deleting a non-existent entity is a no-op
        (no exception raised).

        Args:
            entity_id: UUID of the entity to delete

        Returns:
            None (no return value)

        Example:
            ```python
            await user_repo.delete(user_id)
            # For User: sets deleted_at timestamp
            # For AuditLog: removes row entirely
            # No error if user_id doesn't exist (idempotent)
            ```
        """
        pass
