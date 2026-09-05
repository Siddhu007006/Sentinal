"""Analysis Service - High-level analysis orchestration.

AnalysisService implements the core analysis flows:
- Request analysis (idempotent check, job creation, queue publishing)
- Cancel analysis (state transition from pending/running to cancelled)
- Get analysis (retrieve by ID)
- List analyses (paginated, filtered)

Per 22-Engineering-Backlog E6.T6:
- request_analysis(): Idempotent check, create pending analysis, publish queue job
- cancel_analysis(): Transition pending/running to cancelled
- get_analysis(): Retrieve analysis by ID
- list_analyses(): Paginated list with filters
- All operations create AuditLog entries
- Audit failure does not block analysis operations

Traces to: 22-Engineering-Backlog E6.T6 (Analysis Service)
Traces to: 02-Domain-Model (Analysis entity invariants)
Traces to: 03-Architecture §5 (async pipeline)
"""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.analyzers.registry.registry import AnalyzerRegistryError
from app.domain.entities.analysis import Analysis
from app.domain.exceptions import NotFound


if TYPE_CHECKING:
    from app.analyzers.registry.registry import AnalyzerRegistry
    from app.domain.entities.user import UserRole
    from app.domain.repositories.analysis import AnalysisRepository
    from app.domain.repositories.digital_asset import DigitalAssetRepository
    from app.domain.services.audit_service import AuditService
    from app.domain.services.queue_adapter import QueueAdapter


logger = logging.getLogger(__name__)


class AnalysisNotFoundError(Exception):
    """Raised when an analysis cannot be found by ID."""

    pass


class AnalyzerNotFoundError(Exception):
    """Raised when requesting analysis with non-existent analyzer."""

    pass


class InvalidAnalysisStateError(Exception):
    """Raised when attempting to cancel an analysis in invalid state."""

    pass


class QueuePublicationError(Exception):
    """Raised when publishing the analysis job to the queue fails.

    If the pending analysis row was already persisted, the service
    performs a best-effort cleanup before raising this error so no
    unprocessable pending analysis is left stranded in the database.
    """

    pass


class AnalysisService:
    """High-level analysis service.

    Orchestrates analysis request, cancellation, retrieval, and listing operations.
    Integrates with analyzer registry, repositories, queue, and audit service.

    All analysis operations are atomic: either the operation succeeds with audit logged,
    or it fails. Audit logging failures do not block analysis operations (fail-safe).

    Attributes:
        analysis_repo: AnalysisRepository for analysis persistence
        asset_repo: DigitalAssetRepository for asset validation
        analyzer_registry: AnalyzerRegistry for analyzer resolution
        queue: QueueAdapter for job publishing
        audit_service: AuditService for immutable audit logging
    """

    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        asset_repo: DigitalAssetRepository,
        analyzer_registry: AnalyzerRegistry,
        queue: QueueAdapter,
        audit_service: AuditService,
    ) -> None:
        """Initialize AnalysisService with dependencies.

        Args:
            analysis_repo: AnalysisRepository for analysis persistence
            asset_repo: DigitalAssetRepository for asset validation
            analyzer_registry: AnalyzerRegistry for analyzer resolution
            queue: QueueAdapter for job publishing
            audit_service: AuditService for audit logging
        """
        self.analysis_repo = analysis_repo
        self.asset_repo = asset_repo
        self.analyzer_registry = analyzer_registry
        self.queue = queue
        self.audit_service = audit_service

    async def request_analysis(
        self,
        asset_id: UUID,
        analyzer_key: str,
        requested_by: UUID,
        requested_by_role: UserRole,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> Analysis:
        """Request analysis of an asset with a specific analyzer.

        Implements idempotency: if a completed analysis exists for the same
        (asset_id, analyzer_key, analyzer_version) triple, return the existing
        analysis instead of creating a new one.

        Core behavior:
        1. Resolve analyzer and version from registry
        2. Check for existing completed analysis (idempotency)
        3. If exists → return existing
        4. Otherwise → create pending Analysis
        5. Publish job to queue for worker processing
        6. Audit the request

        Args:
            asset_id: UUID of the digital asset to analyze
            analyzer_key: Key of the analyzer to run
            requested_by: UUID of the user requesting analysis
            requested_by_role: Role of the user requesting analysis
            ip_address: Client IP address (optional, for audit)
            request_id: Request correlation ID (optional, for audit)
            user_agent: Client User-Agent (optional, for audit)

        Returns:
            Analysis entity (existing completed or newly created pending)

        Raises:
            AnalyzerNotFoundError: If analyzer_key not registered
            NotFound: If asset_id does not exist
            RepositoryException: If database error occurs

        Example:
            ```python
            analysis = await analysis_service.request_analysis(
                asset_id=asset_uuid,
                analyzer_key="metadata",
                requested_by=user_uuid,
                requested_by_role=UserRole.ANALYST,
            )
            # If existing completed analysis exists, returns it
            # Otherwise creates pending analysis and publishes to queue
            ```
        """
        # Resolve analyzer from registry
        try:
            analyzer = self.analyzer_registry.get(analyzer_key)
        except AnalyzerRegistryError as exc:
            raise AnalyzerNotFoundError(
                f"Analyzer not registered: {analyzer_key}"
            ) from exc

        analyzer_version = analyzer.version

        # Validate asset exists
        try:
            await self.asset_repo.get_by_id(asset_id)
        except NotFound as exc:
            raise NotFound(f"Asset not found: {asset_id}") from exc

        # Idempotency check: return existing completed analysis if exists
        existing = await self.analysis_repo.get_completed_analysis(
            asset_id=asset_id,
            analyzer_key=analyzer_key,
            analyzer_version=analyzer_version,
        )
        if existing is not None:
            logger.info(
                f"Returning existing completed analysis {existing.id} "
                f"for asset {asset_id} with analyzer {analyzer_key}"
            )
            # Audit the idempotent return (fail-safe: audit failure never blocks)
            try:
                await self.audit_service.log_analysis_request(
                    analysis_id=existing.id,
                    asset_id=asset_id,
                    analyzer_key=analyzer_key,
                    analyzer_version=analyzer_version,
                    requested_by=requested_by,
                    requested_by_role=requested_by_role,
                    is_idempotent=True,
                    ip_address=ip_address,
                    request_id=request_id,
                    user_agent=user_agent,
                )
            except Exception as e:
                logger.exception(
                    "Audit log creation failed (non-blocking)",
                    extra={
                        "analysis_id": str(existing.id),
                        "action": "ANALYSIS_REQUEST_IDEMPOTENT",
                        "error": str(e),
                        "request_id": request_id,
                    },
                )
            return existing

        # Create new pending analysis
        analysis = Analysis(
            id=uuid4(),
            digital_asset_id=asset_id,
            requested_by=requested_by,
            analyzer_key=analyzer_key,
            analyzer_version=analyzer_version,
            status="pending",
            created_at=datetime.now(tz=UTC),
        )

        # Persist analysis
        created_analysis = await self.analysis_repo.create(analysis)

        # Publish job to queue. If publication fails, clean up the pending
        # analysis so the DB cannot silently hold an unprocessable record.
        try:
            job = await self.queue.publish(
                "analysis.requested",
                {"analysis_id": str(created_analysis.id)},
            )
        except Exception as pub_exc:
            with suppress(Exception):
                await self.analysis_repo.delete(created_analysis.id)
            logger.exception(
                "Failed to publish analysis job; pending analysis removed",
                extra={
                    "analysis_id": str(created_analysis.id),
                    "asset_id": str(asset_id),
                    "analyzer_key": analyzer_key,
                    "analyzer_version": analyzer_version,
                    "error": str(pub_exc),
                    "request_id": request_id,
                },
                )
            raise QueuePublicationError(
                f"Failed to publish analysis job for {created_analysis.id}"
            ) from pub_exc

        logger.info(
            f"Created analysis {created_analysis.id} and published job {job.id} "
            f"for asset {asset_id} with analyzer {analyzer_key}"
        )

        # Audit the creation (fail-safe: audit failure never blocks)
        try:
            await self.audit_service.log_analysis_request(
                analysis_id=created_analysis.id,
                asset_id=asset_id,
                analyzer_key=analyzer_key,
                analyzer_version=analyzer_version,
                requested_by=requested_by,
                requested_by_role=requested_by_role,
                is_idempotent=False,
                ip_address=ip_address,
                request_id=request_id,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.exception(
                "Audit log creation failed (non-blocking)",
                extra={
                    "analysis_id": str(created_analysis.id),
                    "action": "ANALYSIS_REQUEST_CREATED",
                    "error": str(e),
                    "request_id": request_id,
                },
            )

        return created_analysis

    async def cancel_analysis(
        self,
        analysis_id: UUID,
        cancelled_by: UUID,
        cancelled_by_role: UserRole,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> Analysis:
        """Cancel a pending or running analysis.

        Transitions analysis from pending or running state to cancelled.
        Analyses in terminal states (completed, failed, cancelled) cannot be cancelled.

        Args:
            analysis_id: UUID of the analysis to cancel
            cancelled_by: UUID of the user cancelling the analysis
            cancelled_by_role: Role of the user cancelling the analysis
            ip_address: Client IP address (optional, for audit)
            request_id: Request correlation ID (optional, for audit)
            user_agent: Client User-Agent (optional, for audit)

        Returns:
            Updated Analysis entity with status="cancelled"

        Raises:
            AnalysisNotFoundError: If analysis_id does not exist
            InvalidAnalysisStateError: If analysis is in terminal state

        Example:
            ```python
            cancelled = await analysis_service.cancel_analysis(
                analysis_id=analysis_uuid,
                cancelled_by=user_uuid,
                cancelled_by_role=UserRole.ANALYST,
            )
            # cancelled.status == "cancelled"
            ```
        """
        # Load analysis
        try:
            analysis = await self.analysis_repo.get_by_id(analysis_id)
        except NotFound as exc:
            raise AnalysisNotFoundError(f"Analysis not found: {analysis_id}") from exc

        # Check if cancellation is allowed
        if analysis.status not in ("pending", "running"):
            raise InvalidAnalysisStateError(
                f"Cannot cancel analysis in {analysis.status} state. "
                "Only pending and running analyses can be cancelled."
            )

        # Transition to cancelled
        cancelled_analysis = analysis.cancel()

        # Persist update
        updated_analysis = await self.analysis_repo.update(
            analysis_id,
            {
                "status": cancelled_analysis.status,
                "completed_at": cancelled_analysis.completed_at,
                "updated_at": cancelled_analysis.updated_at,
            },
        )

        logger.info(f"Cancelled analysis {analysis_id}")

        # Audit the cancellation (fail-safe: audit failure never blocks)
        try:
            await self.audit_service.log_analysis_cancellation(
                analysis_id=analysis_id,
                cancelled_by=cancelled_by,
                cancelled_by_role=cancelled_by_role,
                previous_status=analysis.status,
                ip_address=ip_address,
                request_id=request_id,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.exception(
                "Audit log creation failed (non-blocking)",
                extra={
                    "analysis_id": str(analysis_id),
                    "action": "ANALYSIS_CANCELLED",
                    "previous_status": analysis.status,
                    "error": str(e),
                    "request_id": request_id,
                },
            )

        return updated_analysis

    async def get_analysis(
        self,
        analysis_id: UUID,
    ) -> Analysis:
        """Retrieve an analysis by ID.

        Args:
            analysis_id: UUID of the analysis to retrieve

        Returns:
            Analysis entity

        Raises:
            AnalysisNotFoundError: If analysis_id does not exist

        Example:
            ```python
            analysis = await analysis_service.get_analysis(analysis_uuid)
            ```
        """
        try:
            return await self.analysis_repo.get_by_id(analysis_id)
        except NotFound as exc:
            raise AnalysisNotFoundError(f"Analysis not found: {analysis_id}") from exc

    async def list_analyses(
        self,
        skip: int = 0,
        limit: int = 100,
        asset_id: UUID | None = None,
        status: str | None = None,
        requested_by: UUID | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Analysis], int]:
        """List analyses with optional filtering and pagination.

        Args:
            skip: Number of analyses to skip (pagination offset)
            limit: Maximum analyses to return per page
            asset_id: Filter by asset ID (optional)
            status: Filter by status (optional)
            requested_by: Filter by requesting user (optional)
            sort_by: Column to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")

        Returns:
            Tuple of (analyses, total_count) where:
            - analyses: List of Analysis entities matching filters
            - total_count: Total number of analyses matching filters

        Example:
            ```python
            analyses, total = await analysis_service.list_analyses(
                skip=0,
                limit=50,
                status="pending",
            )
            ```
        """
        # Build filter dictionary
        filters: dict[str, object] = {}
        if asset_id is not None:
            filters["digital_asset_id"] = asset_id
        if status is not None:
            filters["status"] = status
        if requested_by is not None:
            filters["requested_by"] = requested_by

        # Use base repository list method
        return await self.analysis_repo.list(
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            **filters,
        )
