"""
User domain entity.

Represents a user in the Sentinel system. This is a domain model (business logic),
not an ORM model. It contains no SQLAlchemy imports or database-specific code.

Per design.md § User Domain Entity:
- User is deliberately mutable (unlike other domain entities)
- Immutable: id, email, created_at
- Mutable: full_name, role, is_active, updated_at, deleted_at
- Email and role validation enforced in validate() method
- password_hash is never plaintext (verified via hashing algorithm only)
- Soft-delete via deactivate() sets is_active=False and deleted_at=<now>
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from uuid import UUID


class UserRole(StrEnum):
    """Three roles defined in 02-Domain-Model.md §3."""

    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


@dataclass
class User:
    """
    User domain entity with mutable profile fields.

    Invariants:
    - id is immutable UUID
    - email is unique and immutable after creation
    - password_hash is never plaintext
      (verified via hashing algorithm, never substring match)
    - role is one of: admin, analyst, viewer
    - is_active controls authentication eligibility
    - created_at is immutable, set at creation
    - updated_at tracks last profile change
    - deleted_at marks soft-delete timestamp
    """

    id: UUID
    email: str  # Unique, immutable
    password_hash: str  # Non-reversible hash, never plaintext
    role: UserRole  # Mutable (admin-only change)
    is_active: bool  # Mutable (soft-delete when False)
    created_at: datetime  # Immutable
    full_name: str | None = None  # Mutable
    updated_at: datetime | None = None  # Updated on profile changes
    deleted_at: datetime | None = None  # Soft-delete timestamp

    def validate(self) -> None:
        """
        Validate all invariants.

        Raises:
            ValueError: If any invariant is violated
        """
        # Email is required and must be non-empty
        if not self.email or not isinstance(self.email, str):
            raise ValueError("Email is required and must be a string")

        # Email format validation (RFC 5322 simplified):
        # must contain @ with non-empty parts
        email_parts = self.email.split("@")
        if (
            len(email_parts) != 2
            or not email_parts[0]
            or not email_parts[1]
        ):
            msg = (
                "Invalid email format: "
                "must contain @ with non-empty local and domain parts"
            )
            raise ValueError(msg)

        # Role must be one of the enum values
        if not isinstance(self.role, UserRole):
            msg = (
                f"Invalid role. Must be one of: "
                f"{', '.join([r.value for r in UserRole])}"
            )
            raise ValueError(msg)

        # password_hash should never be empty
        # (set by hashing service only)
        if not self.password_hash or not isinstance(
            self.password_hash, str
        ):
            msg = (
                "Password hash is required and must be a non-empty string"
            )
            raise ValueError(msg)

    def deactivate(self) -> User:
        """
        Soft-delete by marking inactive.

        Returns:
            New User instance with is_active=False and deleted_at=<now>
        """
        return User(
            id=self.id,
            email=self.email,
            password_hash=self.password_hash,
            role=self.role,
            is_active=False,
            created_at=self.created_at,
            full_name=self.full_name,
            updated_at=datetime.now(tz=UTC),
            deleted_at=datetime.now(tz=UTC),
        )

    def update_profile(self, full_name: str | None) -> User:
        """
        Update mutable profile fields (non-admin operation).

        Args:
            full_name: New full name (or None to keep existing)

        Returns:
            New User instance with updated profile
        """
        return User(
            id=self.id,
            email=self.email,
            password_hash=self.password_hash,
            role=self.role,
            is_active=self.is_active,
            created_at=self.created_at,
            full_name=full_name if full_name is not None else self.full_name,
            updated_at=datetime.now(tz=UTC),
            deleted_at=self.deleted_at,
        )

    def update_role(self, new_role: UserRole) -> User:
        """
        Update role (admin-only operation).

        Entity doesn't enforce authorization boundary.

        Args:
            new_role: New role from UserRole enum

        Returns:
            New User instance with updated role
        """
        return User(
            id=self.id,
            email=self.email,
            password_hash=self.password_hash,
            role=new_role,
            is_active=self.is_active,
            created_at=self.created_at,
            full_name=self.full_name,
            updated_at=datetime.now(tz=UTC),
            deleted_at=self.deleted_at,
        )
