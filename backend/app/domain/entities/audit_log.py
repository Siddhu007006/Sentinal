"""
AuditLog domain entity.

Represents an immutable audit log entry. This is a domain model (business logic),
not an ORM model. It contains no SQLAlchemy imports or database-specific code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass
class AuditLog:
    """AuditLog domain entity (immutable)."""

    id: UUID
    actor_id: UUID | None
    actor_role: str
    action: str
    resource_type: str
    resource_id: UUID
    before_state: dict[str, object] | None
    after_state: dict[str, object] | None
    ip_address: str | None
    request_id: str | None
    user_agent: str | None
    success: bool
    failure_reason: str | None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime
