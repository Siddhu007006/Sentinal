"""
UserRepository domain interface.

Defines the abstract contract for user-related CRUD and query operations.
Implementations must not leak infrastructure details (SQLAlchemy, ORM models)
to the Domain layer.

The UserRepository interface is used by Application layer services to perform
user management operations (lookup, listing, creation, updates). The Domain layer
depends on this interface, not on any concrete PostgreSQL implementation.

Methods:
    - create(entity: User) -> User
    - get_by_id(entity_id: UUID) -> User
    - list(skip, limit, sort_by, sort_order, **filters) -> (List[User], int)
    - update(entity_id: UUID, updates: dict) -> User
    - delete(entity_id: UUID) -> None
    - get_by_email(email: str) -> User (user-specific query)
    - list_active_users(skip, limit) -> (List[User], int) (user-specific query)

Soft-delete filtering is applied by default:
    - list() and get_by_id() automatically filter where deleted_at IS NULL
    - get_by_email() automatically filters where deleted_at IS NULL
    - list_active_users() filters where is_active=true AND deleted_at IS NULL

Exception Contract:
    - get_by_id() raises NotFound if user not found or is soft-deleted
    - get_by_email() raises NotFound if user not found or is soft-deleted
    - create() raises AlreadyExists if email already exists (case-insensitive)
    - create() raises ConstraintViolation if role is invalid
    - All methods may raise RepositoryException on unexpected errors

Traces to: E3.T7 Specification § Requirement R1 (Domain Interfaces)
Traces to: E3.T7 Specification § Requirement R4 (Domain-Specific Queries)
Traces to: E3.T7 Design § Section 3.2 (UserRepository interface)
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from app.domain.repositories.base import BaseRepository


if TYPE_CHECKING:
    from app.domain.entities.user import User


class UserRepository(BaseRepository["User"]):
    """
    Abstract repository interface for User entity CRUD and queries.

    Manages all user-related persistence operations for the Domain layer.
    Implementations handle database-specific details (SQLAlchemy async,
    PostgreSQL soft-delete filtering, etc.) transparently.

    Inherits CRUD methods from BaseRepository[User]:
        - create(entity: User) -> User
        - get_by_id(entity_id: UUID) -> User
        - list(skip, limit, sort_by, sort_order, **filters) -> (List[User], int)
        - update(entity_id: UUID, updates: dict) -> User
        - delete(entity_id: UUID) -> None

    Adds user-specific query methods:
        - get_by_email(email: str) -> User
        - list_active_users(skip, limit) -> (List[User], int)

    Soft-Delete Behavior:
        By default, all methods filter soft-deleted users (deleted_at IS NULL).
        Soft-deleted users are excluded from list() and get_by_id() operations.
        To retrieve soft-deleted users, a separate method would be needed
        (e.g., list_all_including_deleted()) — not in Phase A scope.

    Transaction Safety:
        - Methods do NOT commit/rollback transactions
        - Transaction lifecycle is managed by FastAPI dependency injection
        - All repository operations in a request are atomic

    Exception Contract:
        - get_by_id(id) raises NotFound if user not found or soft-deleted
        - get_by_email(email) raises NotFound if user not found or soft-deleted
        - create(user) raises AlreadyExists if email already exists
        - create(user) raises ConstraintViolation if role is invalid
        - update(id, updates) may raise NotFound, AlreadyExists, ConstraintViolation
        - delete(id) is idempotent (deleting non-existent user is no-op)

    Example:
        ```python
        # Service depends on the interface, not implementation
        class UserService:
            def __init__(self, user_repo: UserRepository):
                self.user_repo = user_repo

            async def get_user_by_email(self, email: str) -> User:
                # Service doesn't know or care about SQLAlchemy
                return await self.user_repo.get_by_email(email)

            async def list_users(self, page: int = 1) -> (List[User], int):
                skip = (page - 1) * 50
                return await self.user_repo.list(skip=skip, limit=50)
        ```

    Traces to: E3.T7 Specification § Requirement R1 (Domain Interfaces)
    Traces to: E3.T7 Specification § Requirement R4.1 (UserRepository queries)
    Traces to: E3.T7 Design § Section 3.2 (UserRepository pattern)
    Traces to: 03-Architecture §4 (Domain layer)
    """

    @abstractmethod
    async def get_by_email(self, email: str) -> User:
        """
        Retrieve user by email address (case-insensitive).

        Performs a case-insensitive lookup of the user by email. Email addresses
        are normalized to lowercase before comparison. This is the primary user
        lookup method for authentication and password recovery workflows.

        Soft-delete filtering is applied: soft-deleted users (deleted_at IS NOT NULL)
        are excluded from the search result.

        Args:
            email: Email address to search for (will be normalized to lowercase)

        Returns:
            User entity with the specified email

        Raises:
            NotFound: If no user found with the specified email, or if user is
                     soft-deleted (deleted_at IS NOT NULL)

        Example:
            ```python
            user = await user_repo.get_by_email("jane@example.com")
            # Searches for user with normalized email 'jane@example.com'
            # Case-insensitive: "Jane@Example.COM" also returns same user
            # Raises NotFound if no such user or user is deleted
            ```

        Traces to: E3.T7 Specification § Requirement R4.1
        Traces to: 08-Security-Architecture § Authentication (email login)
        """
        pass

    @abstractmethod
    async def list_active_users(
        self,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[User], int]:
        """
        List active users (is_active=true, not soft-deleted).

        Retrieves a paginated list of users filtered to only include active users
        (is_active=true AND deleted_at IS NULL). Useful for admin dashboards,
        user management interfaces, and reports of active system users.

        The distinction between is_active (administrative deactivation) and
        deleted_at (soft delete) is intentional:
            - is_active=false: User deactivated by admin (login rejected,
              data preserved)
            - deleted_at IS NOT NULL: User deleted (soft-deleted, excluded
              from all queries)

        This method returns only users where both are true for "active" status.

        Args:
            skip: Number of users to skip (pagination offset), default 0
            limit: Maximum users to return per page, default 100
            sort_by: Column to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")

        Returns:
            Tuple of (users, total_count) where:
            - users: List of active User entities matching pagination
            - total_count: Total number of active users (for pagination UI)

        Example:
            ```python
            results, total = await user_repo.list_active_users(
                skip=0,
                limit=50,
                sort_by="email",
                sort_order="asc"
            )
            # results: list of 50 active users, sorted by email ascending
            # total: total number of active users (for "Page 1 of X" UI)
            ```

        Traces to: E3.T7 Specification § Requirement R4.1
        Traces to: 08-Security-Architecture § User Management
        """
        pass
