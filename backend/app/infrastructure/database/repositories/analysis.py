"""
Analysis repository implementation.

Concrete PostgreSQL repository for Analysis entity CRUD and queries.

This repository manages persistence of Analysis entities (security analysis jobs)
with critical query optimization for N+1 prevention. Each Analysis represents one
invocation of one or more analyzers against one digital asset.

**Key Design Decisions:**

1. **Hard-Delete Entity:** Analysis uses hard delete (_is_soft_delete_entity returns
   False). Analyses are not soft-deleted; they form part of the audit trail and are
   preserved permanently. There is no deleted_at field on Analysis.

2. **N+1 Prevention via Selectin Loading:** CRITICAL REQUIREMENT. The
   _apply_eager_loading method uses selectinload() for the digital_asset
   relationship. When querying 100 analyses, this prevents 101 queries (1 for list
   + 100 for each asset). With selectin: only 2 queries (1 for analyses + 1 for
   assets via IN clause). See E3.T7 Design § Section 5.1 (Query Optimization).

3. **Idempotency Support:** get_completed_analysis() returns Optional[Analysis]
   (None if not found, no exception). This differs from get_by_id() which raises
   NotFound. Used to implement idempotency: re-running same analyzer returns
   existing completed result.

4. **Worker Job Queue:** list_pending_for_worker() returns List[Analysis] (no
   total_count). Returns oldest pending analyses first (FIFO), used by Celery
   workers to pick up next job. No pagination needed (workers are throttled by
   available resources).

5. **Query Methods:** Four domain-specific queries:
   - get_completed_analysis(asset_id, analyzer_key, analyzer_version): Idempotency
   - list_by_asset(asset_id): Per-asset analysis list
   - list_by_status(status): Status filtering
   - list_pending_for_worker(limit): Worker job queue (FIFO)

6. **Error Mapping:** All database operations wrapped in try/except that converts
   SQLAlchemy exceptions to domain exceptions.

**N+1 Query Prevention (CRITICAL):**
   When calling list_by_asset() to retrieve 100 analyses:
   - Without optimization: 101 queries (1 for analyses list + 100 for each
     analysis.digital_asset)
   - With selectin: 2 queries (1 for analyses + 1 for digital_assets via IN clause)
   - Implementation: _apply_eager_loading() returns stmt.options(
     selectinload(Analysis.digital_asset))

**No Soft-Delete:**
   Analysis DOES NOT use soft-delete. _is_soft_delete_entity() returns False.
   All analyses are hard-deleted (DELETE) and permanent. Analysis records form
   part of the immutable audit trail.

**Pagination:**
   list_by_asset() and list_by_status() return (results, total_count) for UI pagination.
   list_pending_for_worker() returns just List[Analysis] (no total_count).

**Transaction Safety:**
   Repositories do NOT commit/rollback. Transaction lifecycle managed by FastAPI
   dependency injection (per-request, atomic).

Traces to: E3.T7 Specification § Task T6 (AnalysisRepository implementation)
Traces to: E3.T7 Design § Section 4.3 (Repository Pattern), Section 5.1 (N+1 Prevention)
Traces to: 04-Database-Design § Analysis ORM (N+1 indexes, partial unique)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List  # noqa: UP035

from sqlalchemy import and_, asc, desc, func, select
from sqlalchemy.orm import selectinload

from app.domain.repositories.analysis import AnalysisRepository
from app.infrastructure.database.repositories.base import PostgreSQLRepository
from app.infrastructure.database.repositories.exceptions import map_db_exception
from app.models.analysis import Analysis as AnalysisORM


if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.entities.analysis import Analysis


class PostgreSQLAnalysisRepository(
    PostgreSQLRepository["Analysis"], AnalysisRepository
):
    """
    PostgreSQL repository implementation for Analysis entity.

    Implements the AnalysisRepository interface for persistence of Analysis
    entities (security analysis jobs). Manages complete analysis lifecycle:
    job submission, worker queue, result persistence, and query.

    **CRITICAL: N+1 Query Prevention**
    This repository uses selectin loading for the digital_asset relationship.
    When querying 100 analyses and accessing analysis.digital_asset:
    - Without optimization: 101 database queries
    - With selectin (implemented here): 2 queries only
    This prevents N+1 query problems at scale.

    **Inheritance Chain:**
    ```
    AnalysisRepository (domain interface)
          ↑
          │ implements
          │
    PostgreSQLRepository[Analysis] (base implementation)
          ↑
          │ inherits
          │
    PostgreSQLAnalysisRepository (concrete implementation)
    ```

    **CRUD Methods (from PostgreSQLRepository):**
    - create(entity: Analysis) -> Analysis
    - get_by_id(entity_id: UUID) -> Analysis
    - list(skip, limit, sort_by, sort_order, **filters) -> (List[Analysis], int)
    - update(entity_id: UUID, updates: dict) -> Analysis
    - delete(entity_id: UUID) -> None

    **Analysis-Specific Query Methods (from AnalysisRepository):**
    - get_completed_analysis(asset_id: UUID, analyzer_key: str, analyzer_version: str)
      -> Optional[Analysis] (idempotency check, returns None if not found)
    - list_by_asset(asset_id: UUID, skip, limit, sort_by, sort_order)
      -> (List[Analysis], int) (per-asset queries with N+1 prevention)
    - list_by_status(status: str, skip, limit, sort_by, sort_order)
      -> (List[Analysis], int) (status filtering)
    - list_pending_for_worker(limit: int) -> List[Analysis]
      (worker job queue, FIFO order, no pagination)

    **Hard-Delete Behavior (NO Soft-Delete):**
    Analysis does NOT use soft-delete.
    - _is_soft_delete_entity() returns False
    - delete() performs hard delete (DELETE from database)
    - Analyses are permanent and form part of the audit trail
    - No deleted_at field on Analysis ORM model

    **N+1 Prevention via Selectin Loading:**
    _apply_eager_loading() adds selectinload for digital_asset relationship.
    All query methods use this to prevent N+1 queries:
    - Querying 100 analyses loads their digital_assets in separate SELECT IN query
    - Not 100 separate SELECT queries (traditional lazy loading)
    - Result: 2 total queries (analyses + digital_assets) instead of 101

    **Idempotency Support:**
    get_completed_analysis() returns Optional[Analysis]:
    - Returns existing completed analysis if found
    - Returns None if not found (no exception raised)
    - Differs from get_by_id() which raises NotFound
    - Used by services to prevent duplicate analyses

    **Worker Job Queue:**
    list_pending_for_worker() returns List[Analysis] (no total_count):
    - Returns oldest pending analyses first (FIFO order)
    - Used by Celery workers to pick up next job
    - No pagination (workers throttled by resources)
    - Returns empty list if no pending analyses

    **Error Mapping:**
    All database exceptions caught and converted to domain exceptions:
    - IntegrityError with UNIQUE constraint → AlreadyExists
    - IntegrityError with FK constraint → ConstraintViolation
    - NoResultFound → NotFound

    Example:
        ```python
        from app.infrastructure.database.repositories.analysis import (
            PostgreSQLAnalysisRepository
        )
        from app.models.analysis import Analysis

        # Create repository (injected by FastAPI dependency)
        analysis_repo = PostgreSQLAnalysisRepository(session)

        # Service use case: Idempotent analysis request
        existing = await analysis_repo.get_completed_analysis(
            asset_id=asset_id,
            analyzer_key="virustotal_analyzer",
            analyzer_version="v2.1.0"
        )
        if existing:
            return existing  # Return cached result

        # Create new analysis (pending status)
        analysis = await analysis_repo.create(Analysis(...))

        # List all analyses for an asset (N+1 prevention via selectin)
        analyses, total = await analysis_repo.list_by_asset(
            asset_id=asset_id,
            skip=0,
            limit=100
        )
        # Accessing analysis.digital_asset does NOT trigger additional queries
        for analysis in analyses:
            print(f"Asset: {analysis.digital_asset.normalized_value}")

        # Worker job queue (FIFO)
        pending = await analysis_repo.list_pending_for_worker(limit=10)
        for job in pending:
            try:
                result = await process_analysis(job)
                await analysis_repo.update(job.id, {"status": "completed", ...})
            except Exception as e:
                await analysis_repo.update(job.id, {"status": "failed", ...})
        ```

    Traces to: E3.T7 Specification § Task T6 (AnalysisRepository)
    Traces to: E3.T7 Design § Section 4.3 (PostgreSQL Repository Pattern)
    Traces to: E3.T7 Design § Section 5.1 (N+1 Prevention via Selectin)
    Traces to: E3.T7 Design § Section 6 (Hard-Delete Implementation)
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with async session.

        Args:
            session: AsyncSession for database operations (request-scoped)
        """
        super().__init__(session)
        self._model_class = AnalysisORM
        self._entity_name = "Analysis"

    def _to_orm(self, entity: Analysis) -> AnalysisORM:
        """
        Convert domain Analysis entity to ORM model.

        Args:
            entity: Domain Analysis entity

        Returns:
            AnalysisORM model instance
        """
        import json

        return AnalysisORM(
            id=entity.id,
            digital_asset_id=entity.digital_asset_id,
            requested_by=entity.requested_by,
            analyzer_key=entity.analyzer_key,
            analyzer_version=entity.analyzer_version,
            status=entity.status,
            analyzer_slugs=(
                entity.analyzer_slugs.split(",")
                if entity.analyzer_slugs
                else []
            ),
            retry_count=entity.retry_count,
            celery_task_id=entity.celery_task_id,
            error_message=entity.error_message,
            error_code=entity.error_code,
            threat_score=entity.threat_score,
            confidence=entity.confidence,
            severity=entity.severity,
            reasoning_payload=(
                json.loads(entity.reasoning_payload)
                if entity.reasoning_payload
                else None
            ),
            enrichment_data=(
                json.loads(entity.enrichment_data)
                if entity.enrichment_data
                else None
            ),
            started_at=entity.started_at,
            completed_at=entity.completed_at,
        )

    def _to_domain(self, orm_obj: AnalysisORM) -> Analysis:
        """
        Convert ORM model to domain Analysis entity.

        Args:
            orm_obj: AnalysisORM model instance

        Returns:
            Domain Analysis entity
        """
        # Import here to avoid circular imports at module level
        import json

        from app.domain.entities.analysis import Analysis

        return Analysis(
            id=orm_obj.id,
            digital_asset_id=orm_obj.digital_asset_id,
            requested_by=orm_obj.requested_by,
            analyzer_key=orm_obj.analyzer_key,
            analyzer_version=orm_obj.analyzer_version,
            status=orm_obj.status,
            analyzer_slugs=(
                ",".join(orm_obj.analyzer_slugs)
                if orm_obj.analyzer_slugs
                else None
            ),
            retry_count=orm_obj.retry_count,
            celery_task_id=orm_obj.celery_task_id,
            error_message=orm_obj.error_message,
            error_code=orm_obj.error_code,
            threat_score=orm_obj.threat_score,
            confidence=orm_obj.confidence,
            severity=orm_obj.severity,
            reasoning_payload=(
                json.dumps(orm_obj.reasoning_payload)
                if orm_obj.reasoning_payload
                else None
            ),
            enrichment_data=(
                json.dumps(orm_obj.enrichment_data)
                if orm_obj.enrichment_data
                else None
            ),
            started_at=orm_obj.started_at,
            completed_at=orm_obj.completed_at,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )

    def _build_where_clauses(self, **filters: object) -> List[Any]:  # noqa: UP006
        """
        Build WHERE clauses from filter arguments.

        Supported filters:
        - status: Filter by lifecycle status (str)
        - digital_asset_id: Filter by asset (UUID)
        - requested_by: Filter by requester user (UUID)
        - analyzer_key: Filter by analyzer (str)

        Args:
            **filters: Filter arguments

        Returns:
            List of WHERE clause expressions
        """
        clauses: list[Any] = []

        if "status" in filters:
            clauses.append(AnalysisORM.status == filters["status"])

        if "digital_asset_id" in filters:
            clauses.append(AnalysisORM.digital_asset_id == filters["digital_asset_id"])

        if "requested_by" in filters:
            clauses.append(AnalysisORM.requested_by == filters["requested_by"])

        if "analyzer_key" in filters:
            clauses.append(AnalysisORM.analyzer_key == filters["analyzer_key"])

        return clauses

    def _apply_eager_loading(self, stmt: Any) -> Any:  # noqa: ANN401
        """
        Apply eager loading for relationships.

        CRITICAL: This method implements N+1 query prevention via selectin loading.

        The Analysis entity has a relationship to DigitalAsset. Without eager loading,
        querying 100 analyses and accessing analysis.digital_asset triggers 101 queries:
        1 for the analyses list + 100 individual queries for each digital_asset.

        With selectin loading (implemented here), only 2 queries are executed:
        1. SELECT * FROM analyses WHERE ...
        2. SELECT * FROM digital_assets WHERE id IN (asset_id_1, asset_id_2, ...)

        This prevents N+1 queries at scale (10M+ rows) and is more efficient than
        JOIN which would cause Cartesian product with reverse relationships.

        Args:
            stmt: SQLAlchemy Select statement

        Returns:
            Select statement with selectinload for digital_asset relationship

        Example:
            ```python
            # Without eager loading (SLOW - N+1 queries):
            results = await session.scalars(select(AnalysisORM))
            for analysis in results:
                # Each access triggers a database query for the related asset
                print(analysis.digital_asset.normalized_value)  # 1 query per analysis

            # With eager loading (FAST - 2 queries total):
            stmt = select(AnalysisORM).options(
                selectinload(AnalysisORM.digital_asset)
            )
            results = await session.scalars(stmt)
            for analysis in results:
                # Related asset already loaded, no additional query
                print(analysis.digital_asset.normalized_value)  # No query
            ```

        Traces to: E3.T7 Specification § Requirement R5 (N+1 Prevention)
        Traces to: E3.T7 Design § Section 5.1 (Selectin Loading Strategy)
        """
        return stmt.options(selectinload(AnalysisORM.digital_asset))

    def _is_soft_delete_entity(self) -> bool:
        """
        Indicate if entity uses soft-delete.

        Analysis does NOT use soft-delete. Analyses are hard-deleted (permanently
        removed from database) and do not have a deleted_at field. All analysis
        records form part of the permanent audit trail.

        Returns:
            False (Analysis uses hard delete, not soft-delete)
        """
        return False

    async def get_completed_analysis(
        self,
        asset_id: UUID,
        analyzer_key: str,
        analyzer_version: str,
    ) -> Analysis | None:
        """
        Retrieve completed analysis for idempotency check.

        Searches for an analysis with the specified (asset_id, analyzer_key,
        analyzer_version) triple that has reached "completed" status. This is
        used by services to implement idempotency: if the same analysis is
        requested twice, return the existing completed result instead of creating
        a duplicate.

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

        Raises:
            No exceptions raised (returns None on not found)

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

        Traces to: E3.T7 Specification § Requirement R4.4 (AnalysisRepository)
        Traces to: 02-Domain-Model § Analysis idempotency (partial unique index)
        """
        try:
            stmt = select(AnalysisORM).where(
                and_(
                    AnalysisORM.digital_asset_id == asset_id,
                    AnalysisORM.analyzer_key == analyzer_key,
                    AnalysisORM.analyzer_version == analyzer_version,
                    AnalysisORM.status == "completed",
                )
            )
            stmt = self._apply_eager_loading(stmt)
            orm_obj = await self.session.scalar(stmt)
            return self._to_domain(orm_obj) if orm_obj else None
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def list_by_asset(
        self,
        asset_id: UUID,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[List[Analysis], int]:  # noqa: UP006
        """
        List all analyses for a specific digital asset, paginated.

        Retrieves a paginated list of all analyses associated with the specified
        asset. Results are ordered by default by most recent first (created_at DESC).

        **N+1 Query Prevention:** This method uses eager loading (selectin) to load
        related DigitalAsset entities in the same query. Iterating over results and
        accessing analysis.digital_asset does NOT trigger additional database
        queries. With 100 analyses: 2 queries total (analyses + digital_assets via
        IN clause), not 101 queries. See E3.T7 Design § Section 5.1 (Query
        Optimization).

        This is the primary method for UI dashboards: "Show all analyses for this
        asset".

        Args:
            asset_id: UUID of the DigitalAsset to retrieve analyses for
            skip: Number of analyses to skip (pagination offset), default 0
            limit: Maximum analyses to return per page, default 100
            sort_by: Column to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")

        Returns:
            Tuple of (analyses, total_count) where:
            - analyses: List of Analysis entities for the asset (eager-loaded)
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
                # digital_asset is already loaded via selectin (no additional query)
                print(f"Asset: {analysis.digital_asset.normalized_value}")
            ```

        Traces to: E3.T7 Specification § Requirement R4.4 (AnalysisRepository)
        Traces to: E3.T7 Specification § Requirement R5 (N+1 Prevention)
        Traces to: E3.T7 Design § Section 5.1 (Selectin Loading Strategy)
        """
        try:
            # Build WHERE clause for asset_id
            stmt = select(AnalysisORM).where(
                AnalysisORM.digital_asset_id == asset_id
            )

            # Count total analyses for asset
            count_stmt = select(func.count()).select_from(AnalysisORM).where(
                AnalysisORM.digital_asset_id == asset_id
            )
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting
            sort_column = getattr(AnalysisORM, sort_by)
            if sort_order.lower() == "desc":
                stmt = stmt.order_by(desc(sort_column))
            else:
                stmt = stmt.order_by(asc(sort_column))

            # Apply pagination
            stmt = stmt.offset(skip).limit(limit)

            # Apply eager loading for N+1 prevention
            stmt = self._apply_eager_loading(stmt)

            # Execute query
            results = await self.session.scalars(stmt)
            domain_results = [self._to_domain(orm) for orm in results]

            return (domain_results, total)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def list_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[List[Analysis], int]:  # noqa: UP006
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

        Traces to: E3.T7 Specification § Requirement R4.4 (AnalysisRepository)
        Traces to: 02-Domain-Model § Analysis status lifecycle
        """
        try:
            # Build WHERE clause for status
            stmt = select(AnalysisORM).where(AnalysisORM.status == status)

            # Count total analyses with status
            count_stmt = select(func.count()).select_from(AnalysisORM).where(
                AnalysisORM.status == status
            )
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting
            sort_column = getattr(AnalysisORM, sort_by)
            if sort_order.lower() == "desc":
                stmt = stmt.order_by(desc(sort_column))
            else:
                stmt = stmt.order_by(asc(sort_column))

            # Apply pagination
            stmt = stmt.offset(skip).limit(limit)

            # Apply eager loading for N+1 prevention
            stmt = self._apply_eager_loading(stmt)

            # Execute query
            results = await self.session.scalars(stmt)
            domain_results = [self._to_domain(orm) for orm in results]

            return (domain_results, total)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def list_pending_for_worker(self, limit: int = 100) -> List[Analysis]:  # noqa: UP006
        """
        Retrieve pending analyses for worker job queue (FIFO order).

        Retrieves up to `limit` analyses with status='pending', ordered oldest-first
        (created_at ASC). This is the worker job queue: Celery workers call this method
        to pick up the next analysis to process.

        Uses a partial index on (created_at) WHERE status='pending' for optimal
        performance. Returns results in FIFO (First-In-First-Out) order: the oldest
        pending analysis is processed first, ensuring fair scheduling.

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

        Traces to: E3.T7 Specification § Requirement R4.4 (AnalysisRepository)
        Traces to: E3.T7 Design § Worker Job Queue pattern
        Traces to: 04-Database-Design § Analysis Index (ix_analyses_pending)
        """
        try:
            # Query pending analyses, oldest first (FIFO)
            stmt = (
                select(AnalysisORM)
                .where(AnalysisORM.status == "pending")
                .order_by(asc(AnalysisORM.created_at))
                .limit(limit)
            )

            # Apply eager loading for N+1 prevention
            stmt = self._apply_eager_loading(stmt)

            # Execute query
            results = await self.session.scalars(stmt)
            domain_results = [self._to_domain(orm) for orm in results]

            return domain_results
        except Exception as exc:
            raise map_db_exception(exc) from exc
