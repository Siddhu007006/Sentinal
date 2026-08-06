"""
Base PostgreSQL repository implementation.

Provides an abstract base class for all PostgreSQL repository implementations.
This base class implements common CRUD operations and query patterns, allowing
concrete repositories to focus on domain-specific query methods.

**Architecture:**

The PostgreSQLRepository[T] class:
1. Inherits from BaseRepository[T] (Domain interface)
2. Implements 5 common CRUD methods with error mapping and pagination
3. Defines 5 abstract methods for subclasses to customize behavior:
   - _to_orm(entity) -> Convert domain entity to ORM model
   - _to_domain(orm_obj) -> Convert ORM model to domain entity
   - _build_where_clauses(**filters) -> Build WHERE clauses from filters
   - _apply_eager_loading(stmt) -> Add eager loading for relationships
   - _is_soft_delete_entity() -> Indicate if entity uses soft-delete

**Key Features:**

1. **Error Mapping:** All database operations wrapped in try/except that
   converts SQLAlchemy exceptions to domain exceptions via map_db_exception()

2. **Soft-Delete Support:** Repositories can indicate if entity uses soft-delete.
   If enabled, list() and get_by_id() automatically filter deleted_at IS NULL

3. **Pagination:** list() returns (results, total_count) tuple for UI pagination

4. **Eager Loading Hook:** _apply_eager_loading() called in get_by_id() and
   list() to prevent N+1 queries via selectinload/joinedload

5. **Async/Await:** All methods are async-first, using AsyncSession from
   SQLAlchemy 2.0+

**Usage:**

Concrete repository subclasses implement abstract methods:

```python
class PostgreSQLUserRepository(PostgreSQLRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self._model_class = UserORM
        self._entity_name = "User"

    def _to_orm(self, entity: User) -> UserORM:
        return UserORM(
            id=entity.id,
            email=entity.email,
            password_hash=entity.password_hash,
            # ... other fields
        )

    def _to_domain(self, orm_obj: UserORM) -> User:
        return User(
            id=orm_obj.id,
            email=orm_obj.email,
            password_hash=orm_obj.password_hash,
            # ... other fields
        )

    def _build_where_clauses(self, **filters) -> List:
        clauses = []
        if 'email' in filters:
            clauses.append(UserORM.email == filters['email'].lower())
        if 'is_active' in filters:
            clauses.append(UserORM.is_active == filters['is_active'])
        return clauses

    def _apply_eager_loading(self, stmt):
        # No relationships to eager load for User
        return stmt

    def _is_soft_delete_entity(self) -> bool:
        return True  # User uses soft-delete

    async def get_by_email(self, email: str) -> User:
        stmt = select(UserORM).where(UserORM.email == email.lower())
        orm_obj = await self.session.scalar(stmt)
        if not orm_obj:
            raise NotFound(f"User with email {email} not found")
        return self._to_domain(orm_obj)
```

Traces to: E3.T7 Specification § R2 (PostgreSQL Implementations)
Traces to: E3.T7 Design § Section 4 (Implementation Patterns)
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Generic, List, TypeVar  # noqa: UP035

from sqlalchemy import and_, asc, desc, func, select

from app.domain.exceptions import NotFound
from app.domain.repositories.base import BaseRepository
from app.infrastructure.database.repositories.exceptions import map_db_exception


if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")  # Generic entity type


class PostgreSQLRepository(BaseRepository[T], Generic[T]):  # noqa: UP046
    """
    Abstract base PostgreSQL repository implementation.

    Provides common CRUD operations for all PostgreSQL repositories with
    error mapping, pagination, soft-delete support, and eager loading hooks.

    This class implements the BaseRepository[T] interface and leaves 5 abstract
    methods for subclasses to implement:
    - _to_orm(entity: T) -> ORM_Model
    - _to_domain(orm_obj: ORM_Model) -> T
    - _build_where_clauses(**filters) -> List[Clause]
    - _apply_eager_loading(stmt: Select) -> Select
    - _is_soft_delete_entity() -> bool

    Type Parameter:
        T: The domain entity type (e.g., User, Analysis)

    Attributes:
        session: AsyncSession for database operations
        _model_class: ORM model class (set by subclass)
        _entity_name: Human-readable entity name for error messages (set by subclass)

    All database operations:
    - Are wrapped in try/except with error mapping
    - Do NOT commit (transaction managed by caller)
    - Flush to get generated IDs where needed
    - Return domain entities, never ORM models
    - Raise domain exceptions, never SQLAlchemy exceptions

    Transaction Safety:
        Repositories do NOT manage transaction lifecycle. Transaction scope is
        managed by the FastAPI dependency system (per-request). All repository
        operations within a single request are atomic.

    Soft-Delete:
        If _is_soft_delete_entity() returns True, list() and get_by_id()
        automatically filter deleted_at IS NULL. delete() sets deleted_at
        instead of removing the row.

    Pagination:
        list() returns (results, total_count) tuple where total_count is the
        total number of entities matching filters (used for UI pagination).

    Eager Loading:
        _apply_eager_loading() is called in get_by_id() and list() to prevent
        N+1 queries. Subclasses override to add selectinload/joinedload for
        relationships.

    Example:
        See module docstring for full example.

    Traces to: E3.T7 Specification R2-R7, R9
    Traces to: E3.T7 Design § Section 4.1
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with async session.

        Args:
            session: AsyncSession for database operations (request-scoped,
                    managed by FastAPI dependency)
        """
        self.session = session
        # Subclasses MUST set these in __init__ after super().__init__()
        self._model_class: type = ...  # type: ignore[assignment]
        self._entity_name: str = ""

    async def create(self, entity: T) -> T:
        """
        Create a new entity in the repository.

        Converts domain entity to ORM model, adds to session, flushes to
        get generated ID, then returns domain entity with ID and timestamps
        populated.

        Args:
            entity: Domain entity to create (typically with id=None)

        Returns:
            Persisted domain entity with id and timestamps set

        Raises:
            AlreadyExists: If unique constraint violated
            ConstraintViolation: If FK or CHECK constraint violated
            ConflictError: If other data integrity violation occurs

        Transaction Behavior:
            Flushes within transaction (doesn't commit). Transaction committed
            by FastAPI dependency on request completion.

        Example:
            >>> user = User(email="jane@example.com", ...)
            >>> created_user = await user_repo.create(user)
            >>> assert created_user.id is not None

        Traces to: E3.T7 Specification § R3 (CRUD Operations)
        """
        try:
            orm_model = self._to_orm(entity)
            self.session.add(orm_model)
            await self.session.flush()
            return self._to_domain(orm_model)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def get_by_id(self, entity_id: UUID) -> T:
        """
        Retrieve a single entity by its ID.

        Queries the repository for an entity with the specified ID. If the
        entity uses soft-delete, automatically filters out soft-deleted
        records (deleted_at IS NULL).

        Args:
            entity_id: UUID primary key of entity to retrieve

        Returns:
            The domain entity with the specified ID

        Raises:
            NotFound: If entity doesn't exist or is soft-deleted

        Example:
            >>> user = await user_repo.get_by_id(user_id)
            >>> assert user.id == user_id

        Traces to: E3.T7 Specification R3 (CRUD Operations)
        """
        try:
            stmt: Any = select(self._model_class).where(
                self._model_class.id == entity_id  # type: ignore[attr-defined]
            )

            # Add soft-delete filtering if entity supports it
            if self._is_soft_delete_entity():
                stmt = stmt.where(self._model_class.deleted_at.is_(None))  # type: ignore[attr-defined]

            # Apply eager loading for relationships
            stmt = self._apply_eager_loading(stmt)

            orm_obj = await self.session.scalar(stmt)
            if not orm_obj:
                raise NotFound(
                    f"{self._entity_name} with id {entity_id} not found"
                )
            return self._to_domain(orm_obj)
        except NotFound:
            raise
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        **filters: object,
    ) -> tuple[List[T], int]:  # noqa: UP006
        """
        Retrieve a paginated list of entities.

        Returns a page of entities matching optional filters, along with the
        total count of all matching entities (for UI pagination controls).

        If entity uses soft-delete, automatically filters out soft-deleted
        records.

        Args:
            skip: Number of entities to skip (offset), default 0
            limit: Maximum entities to return per page, default 100
            sort_by: Column name to sort by (default "created_at")
            sort_order: "asc" or "desc" (default "desc")
            **filters: Repository-specific filter arguments
                      (implemented by _build_where_clauses)

        Returns:
            Tuple of (results, total_count) where:
            - results: List of domain entities
            - total_count: Total count of entities matching filters
                          (for "Page X of Y" UI)

        Example:
            >>> results, total = await user_repo.list(skip=0, limit=50)
            >>> print(f"Page 1 of {ceil(total / 50)}")

        Traces to: E3.T7 Specification R3, R6 (CRUD, Pagination)
        """
        try:
            # Build WHERE clause from filters
            stmt: Any = select(self._model_class)
            where_clauses = self._build_where_clauses(**filters)

            # Add soft-delete filtering if entity supports it
            if self._is_soft_delete_entity():
                where_clauses = list(where_clauses) if where_clauses else []
                where_clauses.append(self._model_class.deleted_at.is_(None))  # type: ignore[attr-defined]

            # Apply WHERE clauses
            if where_clauses:
                stmt = stmt.where(and_(*where_clauses))

            # Calculate total count with same filters
            count_stmt: Any = select(func.count()).select_from(self._model_class)
            if where_clauses:
                count_stmt = count_stmt.where(and_(*where_clauses))
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting
            sort_column = getattr(self._model_class, sort_by)
            if sort_order.lower() == "desc":
                stmt = stmt.order_by(desc(sort_column))
            else:
                stmt = stmt.order_by(asc(sort_column))

            # Apply pagination
            stmt = stmt.offset(skip).limit(limit)

            # Apply eager loading for relationships
            stmt = self._apply_eager_loading(stmt)

            # Execute query
            results = await self.session.scalars(stmt)
            domain_results = [self._to_domain(orm) for orm in results]

            return (domain_results, total)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def update(self, entity_id: UUID, updates: dict[str, object]) -> T:
        """
        Update an entity's fields.

        Updates specified fields of an entity identified by ID and returns
        the updated entity with all fields populated.

        Args:
            entity_id: UUID of entity to update
            updates: Dictionary of {field_name: new_value} to update

        Returns:
            Updated domain entity

        Raises:
            NotFound: If entity doesn't exist
            AlreadyExists: If update violates unique constraint
            ConstraintViolation: If update violates FK or CHECK constraint
            ConflictError: If other data integrity violation occurs

        Example:
            >>> updated = await user_repo.update(
            ...     user_id,
            ...     {"full_name": "New Name", "is_active": False}
            ... )

        Traces to: E3.T7 Specification R3 (CRUD Operations)
        """
        try:
            # Fetch existing entity
            stmt: Any = select(self._model_class).where(
                self._model_class.id == entity_id  # type: ignore[attr-defined]
            )
            orm_obj = await self.session.scalar(stmt)
            if not orm_obj:
                raise NotFound(f"{self._entity_name} with id {entity_id} not found")

            # Update fields
            for key, value in updates.items():
                if hasattr(orm_obj, key):
                    setattr(orm_obj, key, value)

            await self.session.flush()
            return self._to_domain(orm_obj)
        except NotFound:
            raise
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def delete(self, entity_id: UUID) -> None:
        """
        Delete an entity from the repository.

        For soft-delete entities, sets deleted_at timestamp. For hard-delete
        entities, removes row entirely. This operation is idempotent: deleting
        a non-existent entity is a no-op.

        Args:
            entity_id: UUID of entity to delete

        Returns:
            None (no return value)

        Example:
            >>> await user_repo.delete(user_id)
            >>> # User is soft-deleted (deleted_at set)

        Traces to: E3.T7 Specification R3, R7 (CRUD, Soft-Delete)
        """
        try:
            # Fetch entity
            orm_obj: Any = await self.session.get(self._model_class, entity_id)
            if orm_obj is None:
                # Idempotent: deleting non-existent entity is no-op
                return

            # Soft-delete or hard-delete based on entity type
            if self._is_soft_delete_entity():
                orm_obj.deleted_at = datetime.now(tz=UTC)
            else:
                await self.session.delete(orm_obj)

            await self.session.flush()
        except Exception as exc:
            raise map_db_exception(exc) from exc

    # =========================================================================
    # ABSTRACT METHODS FOR SUBCLASSES
    # =========================================================================

    @abstractmethod
    def _to_orm(self, entity: T) -> Any:  # noqa: ANN401
        """
        Convert domain entity to ORM model.

        Subclasses implement to transform a domain entity (e.g., User) into
        an ORM model (e.g., UserORM) for database persistence.

        Args:
            entity: Domain entity to convert

        Returns:
            ORM model instance ready for database operations

        Example:
            >>> def _to_orm(self, user: User) -> UserORM:
            ...     return UserORM(
            ...         id=user.id,
            ...         email=user.email,
            ...         password_hash=user.password_hash,
            ...         full_name=user.full_name,
            ...         role=user.role,
            ...         is_active=user.is_active,
            ...     )
        """
        ...

    @abstractmethod
    def _to_domain(self, orm_obj: Any) -> T:  # noqa: ANN401
        """
        Convert ORM model to domain entity.

        Subclasses implement to transform an ORM model (e.g., UserORM) into
        a domain entity (e.g., User) for use by Application/Domain layers.

        Args:
            orm_obj: ORM model instance from database

        Returns:
            Domain entity instance

        Example:
            >>> def _to_domain(self, orm_obj: UserORM) -> User:
            ...     return User(
            ...         id=orm_obj.id,
            ...         email=orm_obj.email,
            ...         password_hash=orm_obj.password_hash,
            ...         full_name=orm_obj.full_name,
            ...         role=orm_obj.role,
            ...         is_active=orm_obj.is_active,
            ...     )
        """
        ...

    @abstractmethod
    def _build_where_clauses(self, **filters: object) -> List[Any]:  # noqa: UP006
        """
        Build WHERE clauses from filter arguments.

        Subclasses implement to define how filter arguments are converted to
        WHERE clauses. Each repository defines its own supported filters.

        Args:
            **filters: Filter arguments (varies by repository)

        Returns:
            List of SQLAlchemy WHERE clauses (e.g., [UserORM.is_active == True])

        Example:
            >>> def _build_where_clauses(self, **filters) -> list[Any]:
            ...     clauses: list[Any] = []
            ...     if 'is_active' in filters:
            ...         clauses.append(UserORM.is_active == filters['is_active'])
            ...     if 'email' in filters:
            ...         clauses.append(UserORM.email == filters['email'].lower())
            ...     return clauses
        """
        ...

    @abstractmethod
    def _apply_eager_loading(self, stmt: Any) -> Any:  # noqa: ANN401
        """
        Apply eager loading for relationships.

        Subclasses override to add selectinload/joinedload for relationships
        to prevent N+1 queries. Called in get_by_id() and list().

        Args:
            stmt: SQLAlchemy Select statement

        Returns:
            Select statement with eager loading applied

        Example:
            >>> def _apply_eager_loading(self, stmt):
            ...     # Analysis loads DigitalAsset via selectin (separate query)
            ...     return stmt.options(selectinload(AnalysisORM.digital_asset))

        See: E3.T7 Design § Section 5 (Query Optimization)
        """
        ...

    @abstractmethod
    def _is_soft_delete_entity(self) -> bool:
        """
        Indicate if this entity uses soft-delete.

        Subclasses implement to return True if entity uses soft-delete (e.g.,
        User, DigitalAsset) or False if entity uses hard-delete (e.g., AuditLog).

        When True:
        - list() and get_by_id() automatically filter deleted_at IS NULL
        - delete() sets deleted_at instead of removing row

        Returns:
            True if entity supports soft-delete, False for hard-delete

        Example:
            >>> def _is_soft_delete_entity(self) -> bool:
            ...     return True  # User uses soft-delete

        See: E3.T7 Design § Section 6 (Soft-Delete Implementation)
        """
        ...
