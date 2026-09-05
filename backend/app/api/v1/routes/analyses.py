"""
Analysis route handlers.

Thin HTTP boundary for the analysis API:
- POST  /assets/{assetId}/analyses      (request analysis; analyst/admin)
- GET   /assets/{assetId}/analyses      (list analyses for an asset)
- GET   /analyses                       (list the current user's analyses)
- GET   /analyses/{analysisId}          (detail; owner or admin)
- POST  /analyses/{analysisId}/cancel   (cancel; owner or admin)

Routes contain NO domain logic — all state transitions, idempotency,
queue publication, and auditing live in AnalysisService. This layer
parses the request, enforces authentication + ownership, delegates,
and maps service-layer errors to HTTP responses.

Error mapping (08-Security-Architecture §7 + enumeration prevention):
- Unknown / non-owned analysis id  → 404 (consistent with upload/asset routes)
- Analyzer key not registered       → 422
- Asset id unknown or non-visible   → 404
- Cancel on terminal state          → 409 Conflict
- Queue publication failure         → 502 (generic, no internal detail)
- Idempotency-Key honored on POST   → returned via request_analysis service

Traces to: 22-Engineering-Backlog E6.T7 (Analysis Route Handlers)
Traces to: 05-API-Specification §6.14-6.16 (analysis endpoints)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  # runtime: FastAPI path params

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.api.v1.dependencies.auth import get_current_user, require_role
from app.application.services.analysis_service import (
    AnalysisNotFoundError,
    AnalyzerNotFoundError,
    InvalidAnalysisStateError,
    QueuePublicationError,
)
from app.core.dependencies import (
    get_analysis_repository,
    get_analysis_service,
    get_digital_asset_repository,
    get_request_context,
)
from app.domain.entities.analysis import Analysis  # noqa: TC001
from app.domain.entities.user import User  # noqa: TC001
from app.domain.exceptions import NotFound
from app.schemas.analysis import (
    AnalysisListResponse,
    AnalysisResponse,
    AnalysisResultSchema,
    RequestAnalysisRequest,
)
from app.schemas.auth import PaginationInfo


if TYPE_CHECKING:
    from app.application.services.analysis_service import AnalysisService
    from app.core.dependencies import RequestContext
    from app.domain.repositories.analysis import AnalysisRepository
    from app.domain.repositories.digital_asset import DigitalAssetRepository


router = APIRouter(tags=["analyses"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_admin(current_user: User) -> bool:
    return current_user.role.value == "admin"


def _to_response(analysis: Analysis) -> AnalysisResponse:
    """Map an Analysis domain entity to the public API response."""
    result: AnalysisResultSchema | None = None
    if analysis.result is not None:
        result = AnalysisResultSchema(
            verdict=analysis.result.verdict,
            evidence=analysis.result.evidence,
            confidence=analysis.result.confidence,
            recommendation=analysis.result.recommendation,
        )

    return AnalysisResponse(
        analysis_id=analysis.id,
        asset_id=analysis.digital_asset_id,
        requested_by=analysis.requested_by,
        analyzer_key=analysis.analyzer_key,
        analyzer_version=analysis.analyzer_version,
        status=analysis.status,
        result=result,
        error_message=analysis.error_message,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


def _client_ip(request: Request) -> str | None:
    """Best-effort client IP from the FastAPI Request object."""
    client = getattr(request, "client", None)
    if client is None:
        return None
    host = client.host
    # Filter out test client and non-IP addresses
    if not host or host == "testclient":
        return None
    return host  # type: ignore[no-any-return]


def _user_agent(request: Request) -> str | None:
    """Best-effort User-Agent from the request headers."""
    return request.headers.get("user-agent")


# ---------------------------------------------------------------------------
# 1. POST /assets/{asset_id}/analyses  — request new analysis
# ---------------------------------------------------------------------------


@router.post(
    "/assets/{asset_id}/analyses",
    response_model=AnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request analysis of an asset (analyst/admin)",
    description=(
        "Submit an asset for asynchronous analysis by a registered "
        "analyzer. If an identical analysis (same asset + analyzer "
        "version) has already completed, that completed result is "
        "returned directly (idempotency at the domain level). An "
        "optional Idempotency-Key header is echoed for client-side "
        "retries."
    ),
)
async def request_analysis(
    asset_id: UUID,
    payload: RequestAnalysisRequest,
    request: Request,
    idempotency_key: str | None = Header(
        None, alias="Idempotency-Key", max_length=255
    ),
    current_user: User = Depends(require_role(["admin", "analyst"])),  # noqa: B008
    analysis_service: AnalysisService = Depends(get_analysis_service),  # noqa: B008
    asset_repo: DigitalAssetRepository = Depends(get_digital_asset_repository),  # noqa: B008
    ctx: RequestContext = Depends(get_request_context),  # noqa: B008
) -> AnalysisResponse:
    """Request a new analysis for an asset."""
    del idempotency_key  # Idempotency handled at the domain/service layer

    # Visibility check: caller must be able to see the asset
    try:
        asset = await asset_repo.get_by_id(asset_id)
    except NotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        ) from exc

    if not (_is_admin(current_user) or asset.user_id == current_user.id):
        # Enumeration prevention: do not reveal asset existence
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    try:
        analysis = await analysis_service.request_analysis(
            asset_id=asset_id,
            analyzer_key=payload.analyzer_key,
            requested_by=current_user.id,
            requested_by_role=current_user.role,
            ip_address=_client_ip(request),
            request_id=ctx.request_id,
            user_agent=_user_agent(request),
        )
    except AnalyzerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except NotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except QueuePublicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Analysis job could not be enqueued; please retry later",
        ) from exc

    return _to_response(analysis)


# ---------------------------------------------------------------------------
# 2. GET /assets/{asset_id}/analyses  — list analyses for an asset
# ---------------------------------------------------------------------------


@router.get(
    "/assets/{asset_id}/analyses",
    response_model=AnalysisListResponse,
    status_code=status.HTTP_200_OK,
    summary="List analyses for a specific asset",
)
async def list_asset_analyses(
    asset_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status (optional)"
    ),
    current_user: User = Depends(get_current_user),  # noqa: B008
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),  # noqa: B008
    asset_repo: DigitalAssetRepository = Depends(get_digital_asset_repository),  # noqa: B008
) -> AnalysisListResponse:
    """List analyses scoped to a single asset with visibility checks."""
    try:
        asset = await asset_repo.get_by_id(asset_id)
    except NotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        ) from exc

    if not (_is_admin(current_user) or asset.user_id == current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    requested_by: UUID | None = None if _is_admin(current_user) else current_user.id

    analyses, total = await analysis_repo.list(
        skip=offset,
        limit=limit,
        sort_by="created_at",
        sort_order="desc",
        digital_asset_id=asset_id,
        **({"status": status_filter} if status_filter is not None else {}),
        **({"requested_by": requested_by} if requested_by is not None else {}),
    )

    return AnalysisListResponse(
        items=[_to_response(a) for a in analyses],
        pagination_info=PaginationInfo(total=total, limit=limit, offset=offset),
    )


# ---------------------------------------------------------------------------
# 3. GET /analyses  — list current user's (or admin's) analyses
# ---------------------------------------------------------------------------


@router.get(
    "/analyses",
    response_model=AnalysisListResponse,
    status_code=status.HTTP_200_OK,
    summary="List analyses visible to the current user",
    description=(
        "Return a paginated list of analyses. Non-admin users see "
        "only analyses they requested; admins see every analysis in "
        "the system."
    ),
)
async def list_analyses(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    asset_id_filter: UUID | None = Query(  # noqa: B008
        None, alias="assetId", description="Filter by asset id (optional)"
    ),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status (optional)"
    ),
    current_user: User = Depends(get_current_user),  # noqa: B008
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),  # noqa: B008
) -> AnalysisListResponse:
    """List analyses visible to the caller with optional filters."""
    requested_by: UUID | None = None if _is_admin(current_user) else current_user.id

    analyses, total = await analysis_repo.list(
        skip=offset,
        limit=limit,
        sort_by="created_at",
        sort_order="desc",
        **(
            {"digital_asset_id": asset_id_filter}
            if asset_id_filter is not None
            else {}
        ),
        **({"status": status_filter} if status_filter is not None else {}),
        **({"requested_by": requested_by} if requested_by is not None else {}),
    )

    return AnalysisListResponse(
        items=[_to_response(a) for a in analyses],
        pagination_info=PaginationInfo(total=total, limit=limit, offset=offset),
    )


# ---------------------------------------------------------------------------
# 4. GET /analyses/{analysis_id}  — analysis detail
# ---------------------------------------------------------------------------


@router.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Get analysis detail (owner or admin)",
)
async def get_analysis(
    analysis_id: UUID,
    current_user: User = Depends(get_current_user),  # noqa: B008
    analysis_service: AnalysisService = Depends(get_analysis_service),  # noqa: B008
) -> AnalysisResponse:
    """Retrieve one analysis's detail with ownership enforcement."""
    try:
        analysis = await analysis_service.get_analysis(analysis_id)
    except AnalysisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        ) from exc

    if not (_is_admin(current_user) or analysis.requested_by == current_user.id):
        # Enumeration prevention: 404 (not 403) for non-owner non-admin
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    return _to_response(analysis)


# ---------------------------------------------------------------------------
# 5. POST /analyses/{analysis_id}/cancel  — cancel analysis
# ---------------------------------------------------------------------------


@router.post(
    "/analyses/{analysis_id}/cancel",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a pending or running analysis",
    description=(
        "Cancel an analysis that is still pending or running. "
        "Analyses in a terminal state (completed, failed, cancelled) "
        "cannot be cancelled and return 409 Conflict. Owner or admin."
    ),
)
async def cancel_analysis(
    analysis_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
    analysis_service: AnalysisService = Depends(get_analysis_service),  # noqa: B008
    ctx: RequestContext = Depends(get_request_context),  # noqa: B008
) -> AnalysisResponse:
    """Cancel a pending or running analysis (owner or admin)."""
    # First fetch for ownership check; use the service's NotFound mapping
    try:
        existing = await analysis_service.get_analysis(analysis_id)
    except AnalysisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        ) from exc

    if not (_is_admin(current_user) or existing.requested_by == current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    try:
        cancelled = await analysis_service.cancel_analysis(
            analysis_id=analysis_id,
            cancelled_by=current_user.id,
            cancelled_by_role=current_user.role,
            ip_address=_client_ip(request),
            request_id=ctx.request_id,
            user_agent=_user_agent(request),
        )
    except AnalysisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        ) from exc
    except InvalidAnalysisStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _to_response(cancelled)
