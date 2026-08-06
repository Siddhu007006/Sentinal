"""
DigitalAsset domain entity.

Represents a digital asset (URL, domain, IP, file hash, file) in the Sentinel system.
This is a domain model (business logic), not an ORM model. It contains no SQLAlchemy
imports or database-specific code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass
class DigitalAsset:
    """DigitalAsset domain entity."""

    id: UUID
    user_id: UUID
    asset_type: str
    normalized_value: str
    raw_value: str
    upload_id: UUID | None
    display_label: str | None
    metadata_json: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
