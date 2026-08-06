"""
ReportRepository domain interface.

Defines the abstract contract for report-related CRUD and query operations.
Implementations must not leak infrastructure details (SQLAlchemy, ORM models)
to the Domain layer.

The ReportRepository interface is used by Application layer services to perform
report management operations (lookup, listing, creation, updates, soft-deletion).
The Domain layer depends on this interface, not on any concrete PostgreSQL
implementation.

Methods:
    - create(entity: Report) -> Report
    - get_by_id(entity_id: UUID) -> Report
    - list(skip, limit, sort_by, sort_order, **filters) -> (List[Report], int)
    - update(entity_id: UUID, updates: dict) -> Report
    - delete(entity_id: UUID) -> None
    - soft_delete(entity_id: UUID) -> Report
    - get_by_asset_id(asset_id: UUID) -> (List[Report], int)
      (report-specific query)
    - list_by_status(status: str, skip, limit) -> (List[Report], int)
      (report-specific query)

Soft-delete filtering is applied by default:
    - list() and get_by_id() automatically filter where deleted_at IS NULL
    - get_by_asset_id() automatically filters where deleted_at IS NULL
    - list_by_status() filters where deleted_at IS NULL

Exception Contract:
    - get_by_id() raises NotFound if report not found or is soft-deleted
    - get_by_asset_id() returns empty list if no active reports found
    - create() may raise ConstraintViolation if FK or data integrity issues
    - All methods may raise RepositoryException on unexpected errors

Traces to: E3.T10 Specification § Requirement R1 (Domain Interfaces)
Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
Traces to: 03-Architecture §4 (Domain layer)
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from app.domain.repositories.base import BaseRepository


if TYPE_CHECKING:
    from app.domain.entities.report import Report


class ReportRepository(BaseRepository["Report"]):
    """
    Abstract repository interface for Report entity CRUD and queries.

    Manages all report-related persistence operations for the Domain layer.
    Implementations handle database-specific details (SQLAlchemy async,
    PostgreSQL soft-delete filtering, etc.) transparently.

    Inherits CRUD methods from BaseRepository[Report]:
        - create(entity: Report) -> Report
        - get_by_id(entity_id: UUID) -> Report
        - list(skip, limit, sort_by, sort_order, **filters) -> (List[Report], int)
        - update(entity_id: UUID, updates: dict) -> Report
        - delete(entity_id: UUID) -> None

    Adds report-specific query methods:
        - soft_delete(entity_id: UUID) -> Report
        - get_by_asset_id(asset_id: UUID, include_deleted: bool = False)
          -> (List[Report], int)
        - list_by_status(status: str, skip, limit, include_deleted: bool = False)
          -> (List[Report], int)

    Soft-Delete Behavior:
        By default, all methods filter soft-deleted reports (deleted_at IS NULL).
        Soft-deleted reports are excluded from list() and get_by_id() operations.
        The include_deleted parameter in domain-specific queries allows admins
        to retrieve soft-deleted records when needed.

    Transaction Safety:
        - Methods do NOT commit/rollback transactions
        - Transaction lifecycle is managed by FastAPI dependency injection
        - All repository operations in a request are atomic

    Exception Contract:
        - get_by_id(id) raises NotFound if report not found or soft-deleted
        - get_by_asset_id(asset_id) returns empty list if no reports found
        - create(report) may raise ConstraintViolation if FK is invalid
        - update(id, updates) may raise NotFound, ConstraintViolation
        - delete(id) is idempotent (deleting non-existent report is no-op)
        - soft_delete(id) raises NotFound if report not found

    Example:
        ```python
        # Service depends on the interface, not implementation
        class ReportService:
            def __init__(self, report_repo: ReportRepository):
                self.report_repo = report_repo

            async def get_asset_reports(
                self, asset_id: UUID, page: int = 1
            ) -> (List[Report], int):
                skip = (page - 1) * 50
                return await self.report_repo.get_by_asset_id(
                    asset_id, skip=skip, limit=50
                )

            async def list_reports(self) -> (List[Report], int):
                return await self.report_repo.list(skip=0, limit=50)
        ```

    Traces to: E3.T10 Specification § Requirement R1 (Domain Interfaces)
    Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
    Traces to: E3.T10 Specification § Requirement R5 (Soft-Delete Semantics)
    Traces to: 03-Architecture §4 (Domain layer)
    """

    @abstractmethod
    async def soft_delete(self, entity_id: UUID) -> Report:
        """
        Soft-delete a report by setting deleted_at timestamp.

        Marks the report as deleted without removing the row from the database.
        This preserves audit history and enables recovery if needed. The report
        will be excluded from all list() and query() operations by default unless
        include_deleted=True is specified.

        Args:
            entity_id: UUID of the report to soft-delete

        Returns:
            The report entity with deleted_at timestamp populated

        Raises:
            NotFound: If report not found

        Example:
            ```python
            deleted_report = await report_repo.soft_delete(report_id)
            # report.deleted_at is now set to current timestamp
            # report is excluded from future list() calls
            ```

        Traces to: E3.T10 Specification § Requirement R5 (Soft-Delete)
        Traces to: 04-Database-Design §10 (Soft Delete Strategy)
        """
        pass

    @abstractmethod
    async def get_by_asset_id(
        self,
        asset_id: UUID,
        skip: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[Report], int]:
        """
        Retrieve reports for a specific digital asset, paginated.

        Fetches all reports associated with a particular asset. By default,
        soft-deleted reports are excluded. Use include_deleted=True to retrieve
        all reports including soft-deleted ones (admin use case).

        Args:
            asset_id: UUID of the DigitalAsset to retrieve reports for
            skip: Number of reports to skip (pagination offset), default 0
            limit: Maximum reports to return per page, default 20
            include_deleted: Whether to include soft-deleted reports, default False

        Returns:
            Tuple of (reports, total_count) where:
            - reports: List of Report entities for the asset
            - total_count: Total number of reports for asset (for pagination UI)

        Example:
            ```python
            results, total = await report_repo.get_by_asset_id(
                asset_id=asset_id,
                skip=0,
                limit=50
            )
            # results: list of 50 active reports for asset
            # total: total active reports for asset
            ```

        Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
        """
        pass

    @abstractmethod
    async def list_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[Report], int]:
        """
        List reports filtered by status, paginated.

        Retrieves a paginated list of all reports with the specified status.
        By default, soft-deleted reports are excluded.

        Args:
            status: Report status to filter by (e.g., 'draft', 'published', 'archived')
            skip: Number of reports to skip (pagination offset), default 0
            limit: Maximum reports to return per page, default 20
            include_deleted: Whether to include soft-deleted reports, default False

        Returns:
            Tuple of (reports, total_count) where:
            - reports: List of Report entities with specified status
            - total_count: Total number of reports with status (for pagination UI)

        Example:
            ```python
            results, total = await report_repo.list_by_status(
                status="published",
                skip=0,
                limit=50
            )
            # results: list of 50 published reports
            # total: total published reports
            ```

        Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
        """
        pass
