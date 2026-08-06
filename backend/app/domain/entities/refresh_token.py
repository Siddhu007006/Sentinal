"""
RefreshToken domain entity.

Represents a server-side refresh token for session management. This is a domain
model (business logic), not an ORM model. It contains no SQLAlchemy imports or
database-specific code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass
class RefreshToken:
    """RefreshToken domain entity (immutable after creation)."""

    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    is_revoked: bool
    revoked_at: datetime | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    updated_at: datetime
