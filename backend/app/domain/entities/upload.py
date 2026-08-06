"""
Upload domain entity.

Represents a file upload in the Sentinel system. This is a domain model
(business logic), not an ORM model. It contains no SQLAlchemy imports or
database-specific code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass
class Upload:
    """Upload domain entity."""

    id: UUID
    user_id: UUID
    original_filename: str
    storage_key: str
    content_type: str
    file_size_bytes: int
    checksum_sha256: str | None
    upload_status: str
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
