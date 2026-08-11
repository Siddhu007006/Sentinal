"""PostgreSQL User repository implementation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, List  # noqa: UP035

from sqlalchemy import and_, asc, desc, func, select

from app.domain.entities.user import User
from app.domain.exceptions import NotFound
from app.domain.repositories.user import UserRepository
from app.infrastructure.database.repositories.base import PostgreSQLRepository
from app.infrastructure.database.repositories.exceptions import map_db_exception
from app.models.user import User as UserORM


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PostgreSQLUserRepository(PostgreSQLRepository[User], UserRepository):
    """PostgreSQL repository for User entity with soft-delete and query optimization."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._model_class = UserORM
        self._entity_name = "User"

    def _to_orm(self, entity: User) -> UserORM:
        """
        Convert domain User entity to ORM model.

        Args:
            entity: Domain User entity

        Returns:
            UserORM model instance
        """
        return UserORM(
            id=entity.id,
            email=entity.email,
            password_hash=entity.password_hash,
            full_name=entity.full_name,
            role=entity.role.value,  # Convert enum to string value
            is_active=entity.is_active,
            is_verified=entity.is_verified,
            deleted_at=entity.deleted_at,
        )

    def _to_domain(self, orm_obj: UserORM) -> User:
        """
        Convert ORM model to domain User entity.

        Args:
            orm_obj: UserORM model instance

        Returns:
            Domain User entity
        """
        from app.domain.entities.user import UserRole

        return User(
            id=orm_obj.id,
            email=orm_obj.email,
            password_hash=orm_obj.password_hash,
            full_name=orm_obj.full_name,
            role=UserRole(orm_obj.role),  # Convert string to enum
            is_active=orm_obj.is_active,
            is_verified=orm_obj.is_verified,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
            deleted_at=orm_obj.deleted_at,
        )

    def _build_where_clauses(self, **filters: object) -> List[Any]:  # noqa: UP006
        clauses: list[Any] = []
        if "email" in filters:
            clauses.append(UserORM.email == str(filters["email"]).lower())
        if "is_active" in filters:
            clauses.append(UserORM.is_active == filters["is_active"])
        if "is_verified" in filters:
            clauses.append(UserORM.is_verified == filters["is_verified"])
        if "role" in filters:
            clauses.append(UserORM.role == filters["role"])
        if "deleted_at" in filters:
            clauses.append(UserORM.deleted_at == filters["deleted_at"])
        return clauses

    def _apply_eager_loading(self, stmt: Any) -> Any:  # noqa: ANN401
        return stmt

    def _is_soft_delete_entity(self) -> bool:
        return True

    async def get_by_email(self, email: str) -> User:
        """Retrieve user by email (case-insensitive, soft-delete filtering applied)."""
        try:
            stmt = select(UserORM).where(
                and_(
                    UserORM.email == email.lower(),
                    UserORM.deleted_at.is_(None),
                )
            )
            stmt = self._apply_eager_loading(stmt)
            orm_obj = await self.session.scalar(stmt)
            if not orm_obj:
                raise NotFound(f"User with email {email.lower()} not found")
            return self._to_domain(orm_obj)
        except NotFound:
            raise
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def list_active_users(
        self,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[List[User], int]:  # noqa: UP006
        """List active users (is_active=true AND deleted_at IS NULL)."""
        try:
            stmt = select(UserORM).where(
                and_(
                    UserORM.is_active == True,  # noqa: E712
                    UserORM.deleted_at.is_(None),
                )
            )
            count_stmt = select(func.count()).select_from(UserORM).where(
                and_(
                    UserORM.is_active == True,  # noqa: E712
                    UserORM.deleted_at.is_(None),
                )
            )
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0
            sort_column = getattr(UserORM, sort_by)
            if sort_order.lower() == "desc":
                stmt = stmt.order_by(desc(sort_column))
            else:
                stmt = stmt.order_by(asc(sort_column))
            stmt = stmt.offset(skip).limit(limit)
            stmt = self._apply_eager_loading(stmt)
            results = await self.session.scalars(stmt)
            return ([self._to_domain(orm) for orm in results], total)
        except Exception as exc:
            raise map_db_exception(exc) from exc
