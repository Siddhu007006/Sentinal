"""
AnalysisRepository domain interface.

Defines the abstract contract for analysis-related CRUD and query operations.
Implementations must not leak infrastructure details (SQLAlchemy, ORM models)
to the Domain layer.

The AnalysisRepository interface is used by Application layer services to manage
the complete analysis lifecycle: job submission, worker queue management, result
persistence, and query.

Methods:
    - create(entity: Analysis) -> Analysis
    - get_by_id(entity_id: UUID) -> Analysis
    - list(skip, limit, sort_by, sort_order, **filters)
      -> (List[Analysis], int)
    - update(entity_id: UUID, updates: dict) -> Analysis
    - delete(entity_id: UUID) -> None
    - get_completed_analysis(asset_id, analyzer_key, analyzer_version)
      -> Optional[Analysis] (idempotency)
    - list_by_asset(asset_id: UUID, skip, limit)
      -> (List[Analysis], int) (per-asset queries)
    - list_by_status(status: str, skip, limit)
      -> (List[Analysis], int) (status filtering)
    - list_pending_for_worker(limit: int) -> List[Analysis]
      (worker job queue, FIFO)

Soft-delete filtering:
    - list() and get_by_id() do NOT apply soft-delete filtering for Analysis
    - Analyses are hard-delete entities (no deleted_at field)
    - All analysis records are always queryable (audit trail via created_at)

Query Optimization:
    - All methods use eager loading strategy to prevent N+1 queries
    - Relationships (digital_asset, user) are loaded in same query via selectin
    - See E3.T7 Design § Section 5 (N+1 Prevention)

Exception Contract:
    - get_by_id() raises NotFound if analysis not found
    - get_completed_analysis() returns Optional (None if not found, no exception)
    - list_by_status() and other list methods return empty list if no matches
    - create() raises AlreadyExists if duplicate (not possible due to partial unique)
    - create() raises ConstraintViolation if FK references invalid entity
    - All methods may raise RepositoryException on unexpected errors

Traces to: E3.T7 Specification § Requirement R1 (Domain Interfaces)
Traces to: E3.T7 Specification § Requirement R4 (Domain-Specific Queries)
Traces to: E3.T7 Specification § Requirement R5 (N+1 Prevention)
Traces to: E3.T7 Design § Section 3.2 (AnalysisRepository interface)
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from app.domain.repositories.base import BaseRepository


if TYPE_CHECKING:
    from app.domain.entities.analysis import Analysis


class AnalysisRepository(BaseRepository["Analysis"]):
    """
    Abstract repository interface for Analysis entity CRUD and queries.

    Manages all analysis-related persistence operations for the Domain layer.
    Implementations handle database-specific details (SQLAlchemy async,
    query optimization via selectin loading, worker queue operations, etc.)
    transparently.

    Inherits CRUD methods from BaseRepository[Analysis]:
        - create(entity: Analysis) -> Analysis
        - get_by_id(entity_id: UUID) -> Analysis
        - list(skip, limit, sort_by, sort_order, **filters) -> (List[Analysis], int)
        - update(entity_id: UUID, updates: dict) -> Analysis
        - delete(entity_id: UUID) -> None

    Adds analysis-specific query methods:
        - get_completed_analysis(asset_id, analyzer_key, analyzer_version)
          -> Optional[Analysis]
        - list_by_asset(asset_id: UUID, skip, limit)
          -> (List[Analysis], int)
        - list_by_status(status: str, skip, limit)
          -> (List[Analysis], int)
        - list_pending_for_worker(limit: int) -> List[Analysis]

    Soft-Delete Behavior:
        Analysis entities do NOT have soft-delete support. All analyses are
        hard-deleted or preserved permanently. There is no deleted_at field
        on the Analysis ORM model. All analysis records are queryable and form
        part of the audit trail.

    N+1 Query Prevention:
        All repository methods use eager loading strategy (selectin loading) for
        relationships (digital_asset, user). This prevents N+1 queries when iterating
        over results and accessing related entities. See E3.T7 Design § Section 5.1.

    Transaction Safety:
        - Methods do NOT commit/rollback transactions
        - Transaction lifecycle is managed by FastAPI dependency injection
        - All repository operations in a request are atomic

    Exception Contract:
        - get_by_id(id) raises NotFound if analysis not found
        - get_completed_analysis(...) returns None if not found (no exception)
        - list_* methods return empty list if no matches (no exception)
        - create(analysis) may raise ConstraintViolation if FK is invalid
        - update(id, updates) may raise NotFound, ConstraintViolation
        - delete(id) is idempotent (deleting non-existent analysis is no-op)

    Example:
        ```python
        # Service depends on the interface, not implementation
        class AnalysisService:
            def __init__(self, analysis_repo: AnalysisRepository):
                self.analysis_repo = analysis_repo

            async def request_analysis(
                self,
                asset_id: UUID,
                analyzer_key: str,
                analyzer_version: str
            ) -> Analysis:
                # Idempotency: check if already completed
                existing = await self.analysis_repo.get_completed_analysis(
                    asset_id, analyzer_key, analyzer_version
                )
                if existing:
                    return existing

                # Create new analysis (pending status)
                analysis = await self.analysis_repo.create(
                    Analysis(
                        digital_asset_id=asset_id,
                        analyzer_key=analyzer_key,
                        analyzer_version=analyzer_version,
                        status="pending"
                    )
                )
                return analysis

            async def get_asset_analyses(
                self, asset_id: UUID, page: int = 1
            ) -> (List[Analysis], int):
                skip = (page - 1) * 50
                return await self.analysis_repo.list_by_asset(
                    asset_id, skip=skip, limit=50
                )

            async def get_next_job(self) -> Optional[Analysis]:
                # Worker picks up oldest pending analysis (FIFO)
                results = await self.analysis_repo.list_pending_for_worker(limit=1)
                return results[0] if results else None
        ```

    Traces to: E3.T7 Specification § Requirement R1 (Domain Interfaces)
    Traces to: E3.T7 Specification § Requirement R4.4 (AnalysisRepository queries)
    Traces to: E3.T7 Specification § Requirement R5 (N+1 Prevention)
    Traces to: E3.T7 Design § Section 3.2 (AnalysisRepository pattern)
    Traces to: 03-Architecture §4 (Domain layer)
    """

    @abstractmethod
    async def get_completed_analysis(
        self,
        asset_id: UUID,
        analyzer_key: str,
        analyzer_version: str,
    ) -> Analysis | None:
        """
        Retrieve completed analysis for idempotency check.

        Searches for an analysis with the specified (asset_id, analyzer_key,
        analyzer_version) triple that has reached the "completed" status.
        Used to implement idempotency: if the same analysis is requested
        twice, return the existing completed result instead of creating a
        duplicate.

        This method differs from get_by_id() in that it:
        1. Searches by domain identity (triple) instead of UUID
        2. Returns None instead of raising NotFound if not found
        3. Only matches "completed" status (not pending, running, or failed)

        The triple (asset_id, analyzer_key, analyzer_version) forms a partial
        unique index in the database (UNIQUE WHERE status='completed'), ensuring
        at most one completed analysis per triple.

        Args:
            asset_id: UUID of the DigitalAsset being analyzed
            analyzer_key: Analyzer module name (e.g., "virustotal_analyzer")
            analyzer_version: Analyzer version (e.g., "v2.1.0")

        Returns:
            Analysis entity if a completed analysis exists with this triple,
            or None if no completed analysis found

        Example:
            ```python
            # Check if analysis already completed
            existing = await analysis_repo.get_completed_analysis(
                asset_id=asset_id,
                analyzer_key="virustotal_analyzer",
                analyzer_version="v2.1.0"
            )
            if existing:
                # Return cached result
                return existing
            else:
                # Create new analysis (pending status)
                analysis = await analysis_repo.create(...)
            ```

        Traces to: E3.T7 Specification § Requirement R4.4
        Traces to: 02-Domain-Model § Analysis idempotency
        """
        pass

    @abstractmethod
    async def list_by_asset(
        self,
        asset_id: UUID,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Analysis], int]:
        """
        List all analyses for a specific digital asset, paginated.

        Retrieves a paginated list of all analyses associated with the specified asset.
        Results are ordered by default by most recent first (created_at DESC).

        **N+1 Query Prevention:** This method uses eager loading (selectin) to load
        related DigitalAsset and User entities in the same query. Iterating over
        results and accessing analysis.digital_asset or analysis.user does NOT
        trigger additional database queries. See E3.T7 Design § Section 5.1.

        This is the primary method for UI dashboards: "Show all analyses for
        this asset".

        Args:
            asset_id: UUID of the DigitalAsset to retrieve analyses for
            skip: Number of analyses to skip (pagination offset), default 0
            limit: Maximum analyses to return per page, default 100
            sort_by: Column to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")

        Returns:
            Tuple of (analyses, total_count) where:
            - analyses: List of Analysis entities for the asset
            - total_count: Total number of analyses for asset (for pagination UI)

        Example:
            ```python
            results, total = await analysis_repo.list_by_asset(
                asset_id=asset_id,
                skip=0,
                limit=50,
                sort_by="created_at",
                sort_order="desc"
            )
            # results: list of 50 most recent analyses for asset
            # total: total analyses for asset (for "Page 1 of X" UI)

            # N+1 prevention: accessing related objects does NOT cause extra queries
            for analysis in results:
                print(f"Asset: {analysis.digital_asset.normalized_value}")
                print(f"Requested by: {analysis.user.email}")
            ```

        Traces to: E3.T7 Specification § Requirement R4.4
        Traces to: E3.T7 Specification § Requirement R5 (N+1 Prevention)
        Traces to: 04-Database-Design § Analysis Index (ix_analyses_asset_latest)
        """
        pass

    @abstractmethod
    async def list_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Analysis], int]:
        """
        List analyses filtered by lifecycle status, paginated.

        Retrieves a paginated list of all analyses with the specified status.
        Used for admin dashboards, job queue monitoring, and analysis status reporting.

        Valid status values (from AnalysisStatus enum):
            - "pending": Analyses awaiting worker pickup
            - "running": Analyses currently being processed
            - "completed": Analyses that finished successfully
            - "failed": Analyses that failed with an error
            - "cancelled": Analyses that were cancelled

        Args:
            status: Analysis lifecycle status to filter by
            skip: Number of analyses to skip (pagination offset), default 0
            limit: Maximum analyses to return per page, default 100
            sort_by: Column to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")

        Returns:
            Tuple of (analyses, total_count) where:
            - analyses: List of Analysis entities with specified status
            - total_count: Total number of analyses with status (for pagination UI)

        Example:
            ```python
            results, total = await analysis_repo.list_by_status(
                status="failed",
                skip=0,
                limit=50
            )
            # results: list of 50 failed analyses
            # total: total failed analyses (for "Page 1 of X" UI)
            ```

        Traces to: E3.T7 Specification § Requirement R4.4
        Traces to: 02-Domain-Model § Analysis status lifecycle
        """
        pass

    @abstractmethod
    async def list_pending_for_worker(self, limit: int = 100) -> list[Analysis]:
        """
        Retrieve pending analyses for worker job queue (FIFO order).

        Retrieves up to `limit` analyses with status='pending', ordered oldest-first
        (created_at ASC). This is the worker job queue: Celery workers call this method
        to pick up the next analysis to process.

        Uses a partial index on (created_at) WHERE status='pending' for
        optimal performance. Returns results in FIFO (First-In-First-Out)
        order: the oldest pending analysis is processed first, ensuring fair
        scheduling.

        **No pagination:** This method does NOT return a total_count. Workers need only
        the next batch of jobs, not the total queue size. Returns empty list if no
        pending analyses.

        Args:
            limit: Maximum analyses to return for processing, default 100

        Returns:
            List of Analysis entities with status='pending', oldest first
            (up to `limit`)

        Example:
            ```python
            # Worker loop
            while True:
                pending = await analysis_repo.list_pending_for_worker(limit=10)
                if not pending:
                    # No jobs available, wait and retry
                    await asyncio.sleep(5)
                    continue

                for analysis in pending:
                    try:
                        result = await process_analysis(analysis)
                        await analysis_repo.update(
                            analysis.id,
                            {"status": "completed", "threat_score": result.score}
                        )
                    except Exception as e:
                        await analysis_repo.update(
                            analysis.id,
                            {
                                "status": "failed",
                                "error_message": str(e),
                                "error_code": type(e).__name__
                            }
                        )
            ```

        Traces to: E3.T7 Specification § Requirement R4.4
        Traces to: E3.T7 Design § Worker Job Queue pattern
        Traces to: 04-Database-Design § Analysis Index (ix_analyses_pending)
        """
        pass
