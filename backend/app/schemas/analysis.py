"""
Analysis request and response schemas.

Pydantic models for the analysis API boundary:
- RequestAnalysisRequest (POST /assets/{assetId}/analyses)
- AnalysisResultSchema (verdict, evidence, confidence, recommendation)
- AnalysisResponse (GET /analyses/{analysisId}, etc.)
- AnalysisListResponse (GET /analyses, GET /assets/{assetId}/analyses)

Response shape follows the established codebase convention (flat
camelCase objects matching upload/asset/auth routes). The internal
worker-facing fields (celery_task_id, retry_count, etc.) are
deliberately NOT exposed.

Traces to: 22-Engineering-Backlog E6.T7 (Analysis Route Handlers)
Traces to: 05-API-Specification §6.14-6.16 (analysis endpoints)
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any
from uuid import UUID  # noqa: TC003

from pydantic import Field

from app.schemas.auth import PaginationInfo  # noqa: TC001
from app.schemas.base import BaseSchema


class RequestAnalysisRequest(BaseSchema):
    """Request body for POST /assets/{assetId}/analyses.

    Specifies which registered analyzer should run against the asset.
    The analyzer_key must match a key registered in AnalyzerRegistry.
    """

    analyzer_key: str = Field(
        ...,
        alias="analyzerKey",
        description="Registered analyzer key (e.g., 'metadata')",
        examples=["metadata"],
    )


class AnalysisResultSchema(BaseSchema):
    """Structured result returned by a completed analysis.

    Every analyzer must populate all four fields; the domain entity
    enforces this via AnalysisResult.__post_init__.
    """

    verdict: str = Field(
        ...,
        description="Top-level outcome (e.g., 'safe', 'suspicious')",
        examples=["informational"],
    )
    evidence: Any = Field(
        ...,
        description="Structured evidence produced by the analyzer",
        examples=[{"fileType": "application/pdf", "pageCount": 12}],
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Analyzer-reported confidence (0.0-1.0)",
        examples=[1.0],
    )
    recommendation: str = Field(
        ...,
        description="Human-readable action suggested by the analyzer",
        examples=["No action required; metadata extracted successfully."],
    )


class AnalysisResponse(BaseSchema):
    """Analysis detail response.

    Returned by POST /assets/{assetId}/analyses, GET /analyses/{id},
    and as list items. `result` is populated only when status is
    `completed`; `errorMessage` is populated only when status is
    `failed`.
    """

    analysis_id: UUID = Field(
        ...,
        alias="analysisId",
        examples=["d2e4f6a8-1b3c-4d5e-9f0a-2b4c6d8e0f1a"],
    )
    asset_id: UUID = Field(
        ...,
        alias="assetId",
        description="Analyzed digital asset",
        examples=["9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c"],
    )
    requested_by: UUID = Field(
        ...,
        alias="requestedBy",
        description="User who triggered the analysis",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    analyzer_key: str = Field(
        ...,
        alias="analyzerKey",
        examples=["metadata"],
    )
    analyzer_version: str = Field(
        ...,
        alias="analyzerVersion",
        examples=["1.0.0"],
    )
    status: str = Field(
        ...,
        description="pending, running, completed, failed, or cancelled",
        examples=["pending"],
    )
    result: AnalysisResultSchema | None = Field(
        None,
        description="Populated only when status is 'completed'",
    )
    error_message: str | None = Field(
        None,
        alias="errorMessage",
        description="Populated only when status is 'failed'",
        examples=[None],
    )
    started_at: datetime | None = Field(
        None,
        alias="startedAt",
        examples=[None],
    )
    completed_at: datetime | None = Field(
        None,
        alias="completedAt",
        examples=[None],
    )
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        examples=["2026-08-24T09:45:10.001000Z"],
    )
    updated_at: datetime | None = Field(
        None,
        alias="updatedAt",
        examples=[None],
    )


class AnalysisListResponse(BaseSchema):
    """Paginated list response for analysis listings."""

    items: list[AnalysisResponse] = Field(
        ...,
        description="List of analyses matching the filters",
    )
    pagination_info: PaginationInfo = Field(
        ...,
        alias="paginationInfo",
        description="Pagination metadata",
    )
