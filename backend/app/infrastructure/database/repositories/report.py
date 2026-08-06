"""
PostgreSQL Report repository implementation.

Report entity persistence with soft-delete support.

NOTE: This module references an Report ORM model that may not yet exist.
It will raise an ImportError if the model is not available.

Traces to: E3.T11 Specification § Requirement R1-R9
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import desc, func, select

from app.domain.exceptions import NotFound
from app.domain.repositories.report import ReportRepository
from app.infrastructure.database.repositories.base import PostgreSQLRepository
from app.infrastructure.database.repositories.exceptions import map_db_exception


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.entities.report import Report as ReportEntity  # noqa: F401

# Import Report ORM model - will fail with ImportError if model doesn't exist
try:
    from app.models.report import Report as ReportORM
except ImportError as e:
    raise ImportError(
        "Report ORM model not found. E3.T4 (Report ORM + Migration) must be "
        "completed before this repository can be used."
    ) from e


class PostgreSQLReportRepository(
    PostgreSQLRepository["ReportEntity"], ReportRepository
):
    """PostgreSQL repository for Report entity with soft-delete support."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._model_class = ReportORM
        self._entity_name = "Report"

    def _to_orm(self, entity: Any) -> ReportORM:  # noqa: ANN401
        """Convert domain entity to ORM model."""
        return ReportORM(
            id=entity.id,
            asset_id=entity.asset_id,
            analysis_id=entity.analysis_id,
            title=entity.title,
            description=entity.description,
            status=entity.status,
            content=entity.content,
            created_by=entity.created_by,
        )

    def _to_domain(self, orm_obj: ReportORM) -> Any:  # noqa: ANN401
        """Convert ORM model to domain entity."""
        from app.domain.entities.report import Report

        return Report(
            id=orm_obj.id,
            asset_id=orm_obj.asset_id,
            analysis_id=orm_obj.analysis_id,
            title=orm_obj.title,
            description=orm_obj.description,
            status=orm_obj.status,
            content=orm_obj.content,
            created_by=orm_obj.created_by,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
            deleted_at=orm_obj.deleted_at,
        )

    def _build_where_clauses(self, **filters: object) -> list[Any]:
        """Build WHERE clauses from filter arguments."""
        clauses: list[Any] = []
        if "status" in filters:
            clauses.append(ReportORM.status == filters["status"])
        if "asset_id" in filters:
            clauses.append(ReportORM.asset_id == filters["asset_id"])
        return clauses

    def _apply_eager_loading(self, stmt: Any) -> Any:  # noqa: ANN401
        """Apply eager loading for relationships."""
        return stmt

    def _is_soft_delete_entity(self) -> bool:
        """Report uses soft-delete."""
        return True

    async def soft_delete(self, entity_id: UUID) -> Any:  # noqa: ANN401
        """Soft-delete a report (set deleted_at)."""
        try:
            orm_obj = await self.session.get(ReportORM, entity_id)
            if orm_obj is None:
                raise NotFound(f"Report with id {entity_id} not found")

            orm_obj.deleted_at = datetime.now(tz=UTC)
            await self.session.flush()

            return self._to_domain(orm_obj)
        except NotFound:
            raise
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def get_by_asset_id(
        self,
        asset_id: UUID,
        skip: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[Any], int]:
        """Retrieve reports for a specific asset."""
        try:
            stmt = select(ReportORM).where(ReportORM.asset_id == asset_id)

            if not include_deleted:
                stmt = stmt.where(ReportORM.deleted_at.is_(None))

            # Calculate total count
            count_stmt = (
                select(func.count())
                .select_from(ReportORM)
                .where(ReportORM.asset_id == asset_id)
            )
            if not include_deleted:
                count_stmt = count_stmt.where(ReportORM.deleted_at.is_(None))

            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting (most recent first)
            stmt = stmt.order_by(desc(ReportORM.created_at))
            stmt = stmt.offset(skip).limit(limit)

            results = await self.session.scalars(stmt)
            return ([self._to_domain(orm) for orm in results], total)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def list_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[Any], int]:
        """Retrieve reports filtered by status."""
        try:
            stmt = select(ReportORM).where(ReportORM.status == status)

            if not include_deleted:
                stmt = stmt.where(ReportORM.deleted_at.is_(None))

            # Calculate total count
            count_stmt = (
                select(func.count())
                .select_from(ReportORM)
                .where(ReportORM.status == status)
            )
            if not include_deleted:
                count_stmt = count_stmt.where(ReportORM.deleted_at.is_(None))

            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting (most recent first)
            stmt = stmt.order_by(desc(ReportORM.created_at))
            stmt = stmt.offset(skip).limit(limit)

            results = await self.session.scalars(stmt)
            return ([self._to_domain(orm) for orm in results], total)
        except Exception as exc:
            raise map_db_exception(exc) from exc
