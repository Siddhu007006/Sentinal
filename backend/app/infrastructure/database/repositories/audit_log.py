"""
PostgreSQL AuditLog repository implementation.

Immutable append-only audit trail persistence. AuditLog is never updated or
soft-deleted - only created and queried. delete() is a hard delete for cleanup
only, never called during normal application operation.

Traces to: E3.T11 Specification § Requirement R1-R9
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import and_, asc, func, select

from app.domain.repositories.audit_log import AuditLogRepository
from app.infrastructure.database.repositories.base import PostgreSQLRepository
from app.infrastructure.database.repositories.exceptions import map_db_exception
from app.models.audit_log import AuditLog as AuditLogORM


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.entities.audit_log import AuditLog as AuditLogEntity  # noqa: F401


class PostgreSQLAuditLogRepository(
    PostgreSQLRepository["AuditLogEntity"], AuditLogRepository
):
    """PostgreSQL repository for immutable AuditLog entity."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._model_class = AuditLogORM
        self._entity_name = "AuditLog"

    def _to_orm(self, entity: Any) -> AuditLogORM:  # noqa: ANN401
        """Convert domain entity to ORM model."""
        return AuditLogORM(
            id=entity.id,
            actor_id=entity.actor_id,
            actor_role=entity.actor_role,
            action=entity.action,
            resource_type=entity.resource_type,
            resource_id=entity.resource_id,
            before_state=entity.before_state,
            after_state=entity.after_state,
            ip_address=entity.ip_address,
            request_id=entity.request_id,
            user_agent=entity.user_agent,
            success=entity.success,
            failure_reason=entity.failure_reason,
            occurred_at=entity.occurred_at,
        )

    def _to_domain(self, orm_obj: AuditLogORM) -> Any:  # noqa: ANN401
        """Convert ORM model to domain entity."""
        from app.domain.entities.audit_log import AuditLog

        return AuditLog(
            id=orm_obj.id,
            actor_id=orm_obj.actor_id,
            actor_role=orm_obj.actor_role,
            action=orm_obj.action,
            resource_type=orm_obj.resource_type,
            resource_id=orm_obj.resource_id,
            before_state=orm_obj.before_state,
            after_state=orm_obj.after_state,
            ip_address=orm_obj.ip_address,
            request_id=orm_obj.request_id,
            user_agent=orm_obj.user_agent,
            success=orm_obj.success,
            failure_reason=orm_obj.failure_reason,
            created_at=orm_obj.created_at,
            occurred_at=orm_obj.occurred_at,
        )

    def _build_where_clauses(self, **filters: object) -> list[Any]:
        """Build WHERE clauses from filter arguments."""
        clauses: list[Any] = []
        if "actor_id" in filters:
            clauses.append(AuditLogORM.actor_id == filters["actor_id"])
        if "resource_type" in filters:
            clauses.append(AuditLogORM.resource_type == filters["resource_type"])
        if "resource_id" in filters:
            clauses.append(AuditLogORM.resource_id == filters["resource_id"])
        if "action" in filters:
            clauses.append(AuditLogORM.action == filters["action"])
        if "success" in filters:
            clauses.append(AuditLogORM.success == filters["success"])
        return clauses

    def _apply_eager_loading(self, stmt: Any) -> Any:  # noqa: ANN401
        """Apply eager loading for relationships (none for AuditLog)."""
        return stmt

    def _is_soft_delete_entity(self) -> bool:
        """AuditLog is not soft-deleted (immutable, append-only)."""
        return False

    async def list_by_actor(
        self,
        actor_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Any], int]:
        """Retrieve audit logs filtered by actor (WHO performed action)."""
        try:
            stmt = select(AuditLogORM).where(AuditLogORM.actor_id == actor_id)

            # Calculate total count
            count_stmt = select(func.count()).select_from(AuditLogORM).where(
                AuditLogORM.actor_id == actor_id
            )
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting (chronologically, oldest first)
            stmt = stmt.order_by(asc(AuditLogORM.occurred_at))
            stmt = stmt.offset(skip).limit(limit)

            results = await self.session.scalars(stmt)
            return ([self._to_domain(orm) for orm in results], total)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def list_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Any], int]:
        """Retrieve audit logs filtered by resource (WHAT was affected)."""
        try:
            stmt = select(AuditLogORM).where(
                and_(
                    AuditLogORM.resource_type == resource_type,
                    AuditLogORM.resource_id == resource_id,
                )
            )

            # Calculate total count
            count_stmt = (
                select(func.count())
                .select_from(AuditLogORM)
                .where(
                    and_(
                        AuditLogORM.resource_type == resource_type,
                        AuditLogORM.resource_id == resource_id,
                    )
                )
            )
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting (chronologically, oldest first for history)
            stmt = stmt.order_by(asc(AuditLogORM.occurred_at))
            stmt = stmt.offset(skip).limit(limit)

            results = await self.session.scalars(stmt)
            return ([self._to_domain(orm) for orm in results], total)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def query_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Any], int]:
        """Retrieve audit logs within a date range."""
        try:
            stmt = select(AuditLogORM).where(
                and_(
                    AuditLogORM.occurred_at >= start_date,
                    AuditLogORM.occurred_at <= end_date,
                )
            )

            # Calculate total count
            count_stmt = (
                select(func.count())
                .select_from(AuditLogORM)
                .where(
                    and_(
                        AuditLogORM.occurred_at >= start_date,
                        AuditLogORM.occurred_at <= end_date,
                    )
                )
            )
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting (chronologically, oldest first)
            stmt = stmt.order_by(asc(AuditLogORM.occurred_at))
            stmt = stmt.offset(skip).limit(limit)

            results = await self.session.scalars(stmt)
            return ([self._to_domain(orm) for orm in results], total)
        except Exception as exc:
            raise map_db_exception(exc) from exc
