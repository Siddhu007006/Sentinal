"""Analyzer route handlers (E6.T8).

Provides read-only endpoints for listing and inspecting registered analyzers.
Analyzers are registered in code, not via API — these endpoints expose
metadata about available analyzers for client discovery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status

from app.analyzers.registry.registry import AnalyzerRegistry, AnalyzerRegistryError
from app.core.dependencies import get_analyzer_registry
from app.schemas.analyzer import AnalyzerListResponse, AnalyzerSchema


if TYPE_CHECKING:
    from app.analyzers.base.analyzer import Analyzer


router = APIRouter(prefix="/analyzers", tags=["analyzers"])


def _analyzer_to_schema(analyzer: Analyzer) -> AnalyzerSchema:
    """Convert domain Analyzer to API response schema."""
    return AnalyzerSchema(
        key=analyzer.key,
        version=analyzer.version,
        description=_get_analyzer_description(analyzer.key),
    )


def _get_analyzer_description(key: str) -> str:
    """Return human-readable description for an analyzer key."""
    descriptions: dict[str, str] = {
        "metadata": (
            "Extract file metadata (MIME type, dimensions, page count) "
            "without external services"
        ),
    }
    return descriptions.get(key, f"Analyzer: {key}")


# ---------------------------------------------------------------------------
# 1. GET /analyzers  — list all registered analyzers
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=AnalyzerListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all registered analyzers",
    description="Returns metadata for all analyzers registered in the system. "
    "Analyzers are registered in code, not via API.",
)
async def list_analyzers(
    analyzer_registry: AnalyzerRegistry = Depends(get_analyzer_registry),  # noqa: B008
) -> AnalyzerListResponse:
    """List all registered analyzers with their metadata."""
    analyzers = analyzer_registry.list()
    analyzer_schemas = [_analyzer_to_schema(analyzer) for analyzer in analyzers]
    return AnalyzerListResponse(analyzers=analyzer_schemas, total=len(analyzer_schemas))


# ---------------------------------------------------------------------------
# 2. GET /analyzers/{analyzerId}  — get analyzer details
# ---------------------------------------------------------------------------


@router.get(
    "/{analyzer_id}",
    response_model=AnalyzerSchema,
    status_code=status.HTTP_200_OK,
    summary="Get analyzer details",
    description="Returns detailed metadata for a specific analyzer by its key.",
)
async def get_analyzer(
    analyzer_id: str,
    analyzer_registry: AnalyzerRegistry = Depends(get_analyzer_registry),  # noqa: B008
) -> AnalyzerSchema:
    """Get detailed metadata for a specific analyzer."""
    try:
        analyzer = analyzer_registry.get(analyzer_id)
    except AnalyzerRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analyzer '{analyzer_id}' not found",
        ) from exc

    return _analyzer_to_schema(analyzer)
