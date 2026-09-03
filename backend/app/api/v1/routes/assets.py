"""Digital asset route handlers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.dependencies.auth import get_current_user
from app.core.dependencies import get_digital_asset_repository
from app.domain.entities.digital_asset import DigitalAsset  # noqa: TC001
from app.domain.entities.user import User  # noqa: TC001
from app.domain.exceptions import NotFound
from app.schemas.auth import PaginationInfo
from app.schemas.digital_asset import (
    DigitalAssetListResponse,
    DigitalAssetResponse,
)


if TYPE_CHECKING:
    from app.domain.repositories.digital_asset import DigitalAssetRepository


router = APIRouter(tags=["assets"])


def _to_response(asset: DigitalAsset) -> DigitalAssetResponse:
    """Map a DigitalAsset domain entity to the public API response."""
    metadata: dict[str, object] | None = None
    if asset.metadata_json:
        metadata = json.loads(asset.metadata_json)

    return DigitalAssetResponse(
        asset_id=asset.id,
        user_id=asset.user_id,
        asset_type=asset.asset_type,
        raw_value=asset.raw_value,
        normalized_value=asset.normalized_value,
        display_label=asset.display_label,
        metadata=metadata,
        is_active=asset.is_active,
        sha256_hash=asset.sha256_hash,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _is_admin(current_user: User) -> bool:
    return current_user.role.value == "admin"


@router.get(
    "",
    response_model=DigitalAssetListResponse,
    status_code=status.HTTP_200_OK,
    summary="List active assets for the current user",
)
async def list_assets(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),  # noqa: B008
    asset_repo: DigitalAssetRepository = Depends(get_digital_asset_repository),  # noqa: B008
) -> DigitalAssetListResponse:
    """Return active, non-deleted assets belonging to the current user."""
    assets, total = await asset_repo.list_by_user(
        current_user.id,
        skip=offset,
        limit=limit,
        sort_by="created_at",
        sort_order="desc",
    )
    return DigitalAssetListResponse(
        items=[_to_response(asset) for asset in assets],
        pagination_info=PaginationInfo(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/{asset_id}",
    response_model=DigitalAssetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get asset detail",
)
async def get_asset(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),  # noqa: B008
    asset_repo: DigitalAssetRepository = Depends(get_digital_asset_repository),  # noqa: B008
) -> DigitalAssetResponse:
    """Return an asset to its owner or an administrator."""
    try:
        asset = await asset_repo.get_by_id(asset_id)
    except NotFound as exc:
        raise HTTPException(404, detail="Asset not found") from exc

    if not (_is_admin(current_user) or asset.user_id == current_user.id):
        raise HTTPException(404, detail="Asset not found")
    return _to_response(asset)


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an asset",
)
async def delete_asset(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),  # noqa: B008
    asset_repo: DigitalAssetRepository = Depends(get_digital_asset_repository),  # noqa: B008
) -> None:
    """Soft-delete an asset for its owner or an administrator."""
    try:
        asset = await asset_repo.get_by_id(asset_id)
    except NotFound as exc:
        raise HTTPException(404, detail="Asset not found") from exc

    if not (_is_admin(current_user) or asset.user_id == current_user.id):
        raise HTTPException(404, detail="Asset not found")

    await asset_repo.delete(asset_id)
