"""Digital asset API response schemas."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from pydantic import Field

from app.schemas.auth import PaginationInfo  # noqa: TC001
from app.schemas.base import BaseSchema


class DigitalAssetResponse(BaseSchema):
    """Public digital asset detail response."""

    asset_id: UUID = Field(..., alias="assetId")
    user_id: UUID = Field(..., alias="userId")
    asset_type: str = Field(..., alias="assetType")
    raw_value: str = Field(..., alias="rawValue")
    normalized_value: str = Field(..., alias="normalizedValue")
    display_label: str | None = Field(None, alias="displayLabel")
    metadata: dict[str, object] | None = None
    is_active: bool = Field(..., alias="isActive")
    sha256_hash: str | None = Field(None, alias="sha256Hash")
    mime_type: str | None = Field(None, alias="mimeType")
    size_bytes: int | None = Field(None, alias="sizeBytes")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")


class DigitalAssetListResponse(BaseSchema):
    """Paginated list response for the current user's active assets."""

    items: list[DigitalAssetResponse]
    pagination_info: PaginationInfo = Field(..., alias="paginationInfo")
