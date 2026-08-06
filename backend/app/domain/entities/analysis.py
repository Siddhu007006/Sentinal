"""
Analysis domain entity.

Represents a security analysis in the Sentinel system. This is a domain model
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
class Analysis:
    """Analysis domain entity."""

    id: UUID
    digital_asset_id: UUID
    requested_by: UUID
    analyzer_key: str
    analyzer_version: str
    status: str
    threat_score: float | None = None
    error_message: str | None = None
    error_code: str | None = None
    analyzer_slugs: str | None = None
    retry_count: int = 0
    celery_task_id: str | None = None
    confidence: float | None = None
    severity: str | None = None
    reasoning_payload: str | None = None
    enrichment_data: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
