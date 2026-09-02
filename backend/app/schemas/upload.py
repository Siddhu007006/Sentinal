"""
Upload request and response schemas.

Pydantic models for the upload API boundary:
- UploadResponse (for POST /uploads, GET /uploads/{uploadId})

Response shape follows the established codebase convention (flat
camelCase objects, as in auth/user routes). The internal storage_key
is deliberately NOT exposed. Status values are the implemented upload
state machine's: pending, processing, completed, failed (02-Domain-
Model §11 / E5.T3) — not the older asynchronous-flow names in
05-API-Specification §6.7 (see the E5.T6 divergence notes in
PROJECT_STATUS).

Traces to: 22-Engineering-Backlog E5.T6 (Upload Route Handlers)
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from pydantic import Field

from app.schemas.auth import PaginationInfo  # noqa: TC001
from app.schemas.base import BaseSchema


class UploadResponse(BaseSchema):
    """Upload detail response (POST /uploads, GET /uploads/{uploadId}).

    Does NOT include storage_key (internal object-storage layout) or
    the client's idempotency key (the client already knows it).
    """

    upload_id: UUID = Field(
        ...,
        alias="uploadId",
        examples=["b6f1c2e4-1a2b-4c3d-9e8f-7a6b5c4d3e2f"],
    )
    user_id: UUID = Field(
        ...,
        alias="userId",
        description="Owning user",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    original_filename: str = Field(
        ...,
        alias="originalFilename",
        examples=["quarterly-report.pdf"],
    )
    content_type: str = Field(
        ...,
        alias="contentType",
        examples=["application/pdf"],
    )
    file_size_bytes: int = Field(
        ...,
        alias="fileSizeBytes",
        examples=[2485760],
    )
    upload_status: str = Field(
        ...,
        alias="uploadStatus",
        description="pending, processing, completed, or failed",
        examples=["completed"],
    )
    checksum_sha256: str | None = Field(
        None,
        alias="checksumSha256",
        description="Server-computed content hash (set on completion)",
        examples=["a3f5c1d8e9f2b7c4a6d1e8f3b7c9d2e1..."],
    )
    digital_asset_id: UUID | None = Field(
        None,
        alias="digitalAssetId",
        description="Resolved DigitalAsset (set on completion)",
        examples=["9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c"],
    )
    completed_at: datetime | None = Field(
        None,
        alias="completedAt",
        examples=["2026-08-24T09:45:14.552000Z"],
    )
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        examples=["2026-08-24T09:45:10.001000Z"],
    )
    updated_at: datetime | None = Field(
        None,
        alias="updatedAt",
        examples=["2026-08-24T09:45:14.552000Z"],
    )


class UploadListResponse(BaseSchema):
    """Paginated list response for GET /uploads."""

    items: list[UploadResponse] = Field(
        ...,
        description="List of uploads for the current user",
    )
    pagination_info: PaginationInfo = Field(
        ...,
        alias="paginationInfo",
        description="Pagination metadata",
    )
