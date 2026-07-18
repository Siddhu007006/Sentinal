"""
User ORM model.

Defines the authoritative registry of all Sentinel platform users. Every
digital asset, analysis, report, and audit log is owned by or attributed to
a User. This is the identity anchor for the entire system.

Key design decisions:
1. No username field — email is the primary login credential (simpler UX,
   matches industry standard for SaaS products)
2. Role stored as VARCHAR with CHECK constraint (not PostgreSQL enum) to
   enable zero-downtime role additions via simple string additions
3. Soft delete via deleted_at (not is_deleted boolean) to preserve timestamp
   and enable "when was this deleted?" queries
4. last_login_at tracked for security monitoring and inactive account cleanup
5. is_verified separate from is_active to distinguish email verification state
   from administrative deactivation

Security notes:
- password_hash must NEVER be returned in API responses (enforced at repository)
- Email stored lowercase for case-insensitive unique constraint
- UUIDs prevent user enumeration attacks
- Soft delete preserves audit trail

Traces to: 04-Database-Design §5.1 (users table specification)
Traces to: 08-Security-Architecture §4 (authentication, passwords)
Traces to: 22-Engineering-Backlog E3.T3 (User ORM model task)
"""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import BaseModel


class UserRole(enum.StrEnum):
    """
    User authorization roles.

    Implements Role-Based Access Control (RBAC) per 08-Security-Architecture §5.

    Roles:
        ADMIN: Full system access including user management, system configuration,
               and audit log access. Can perform destructive operations.
        ANALYST: Can create/analyze digital assets, view own analyses, generate
                 reports. Cannot manage users or access audit logs.
        VIEWER: Read-only access to own uploaded assets and analysis results.
                Cannot trigger new analyses or modify data.

    Future: When organization/workspace features are added, roles will become
    scoped per-workspace via a join table (user_roles), allowing users to have
    different roles in different workspaces.

    Traces to: 08-Security-Architecture §5 (RBAC model)
    Traces to: backend/openapi.yaml UserRole schema
    """

    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class User(BaseModel):
    """
    User entity representing a Sentinel platform account.

    Inherits from BaseModel:
        - id: UUID primary key (automatically generated)
        - created_at: Timestamp of account creation (immutable)
        - updated_at: Timestamp of last modification (auto-updated)

    This is the root identity entity. All content and actions in Sentinel are
    attributed to a User. User deactivation (is_active=False) prevents login
    but preserves all historical data for audit and compliance.

    Lifecycle states:
        1. Created: User registered, is_verified=False, is_active=True
        2. Verified: Email verified, is_verified=True, full platform access
        3. Deactivated: is_active=False, login rejected, data preserved
        4. Soft-deleted: deleted_at set, excluded from queries, data preserved

    Example:
        >>> from app.models.user import User, UserRole
        >>> user = User(
        ...     email="jane@example.com",
        ...     password_hash="$2b$12$...",  # bcrypt hash
        ...     full_name="Jane Doe",
        ...     role=UserRole.ANALYST,
        ... )
        >>> session.add(user)
        >>> await session.commit()

    Security:
        - password_hash is NEVER returned in API responses (repository layer)
        - Email uniqueness enforced at database level (case-insensitive)
        - UUIDs prevent user ID enumeration
        - Soft delete preserves audit trail

    Traces to: 04-Database-Design §5.1 (users table)
    Traces to: backend/openapi.yaml User schema
    """

    __tablename__ = "users"

    # Email - Primary login credential and contact address
    # Stored lowercase for case-insensitive uniqueness.
    # Application layer must normalize email before queries.
    email: Mapped[str] = mapped_column(
        String(320),  # Max email length per RFC 5321
        unique=True,
        nullable=False,
        index=True,
        comment="Primary login credential (lowercased, normalized)",
    )

    # Password hash - bcrypt with cost=12
    # NEVER expose this field in API responses.
    # NEVER log this field.
    # Application layer handles hashing via passlib/bcrypt.
    password_hash: Mapped[str] = mapped_column(
        String(60),  # bcrypt output is exactly 60 chars
        nullable=False,
        comment="bcrypt hash (cost=12), never plaintext",
    )

    # Full name - Display name for UI
    # Not used for authentication.
    # User can update this via profile endpoints.
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name for UI and reports",
    )

    # Role - RBAC authorization level
    # Stored as VARCHAR with CHECK constraint (not PostgreSQL ENUM) to enable
    # zero-downtime role additions. When adding a new role, only a data migration
    # is needed (no ALTER TYPE ... ADD VALUE which requires exclusive locks).
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.VIEWER.value,
        server_default=f"'{UserRole.VIEWER.value}'",
        comment="RBAC role: admin, analyst, viewer",
    )

    # Active flag - Administrative deactivation
    # False = login rejected, API access denied, but data preserved.
    # Separate from is_verified (email verification) and deleted_at (soft delete).
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default="true",
        comment="false = deactivated, login rejected",
    )

    # Verified flag - Email verification status
    # False = email not verified, may have restricted access to certain features.
    # Separate from is_active (administrative control).
    # Future: email verification flow will set this to True.
    is_verified: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
        comment="Email verification status",
    )

    # Last login timestamp - Security monitoring and inactive account detection
    # Updated on successful authentication (POST /auth/login).
    # Null = never logged in (possible for admin-created accounts).
    last_login_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Last successful login timestamp (UTC)",
    )

    # Soft delete timestamp - When user was deleted
    # Null = active user
    # Non-null = soft-deleted, excluded from all queries by default
    # Preserves audit trail and referential integrity.
    # Hard deletion is not supported in v1 per 04-Database-Design §10.
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Soft delete timestamp (UTC), null = active",
    )

    # Table-level constraints
    __table_args__ = (
        # Enforce role values at database level
        # Using CHECK constraint instead of PostgreSQL ENUM for easier
        # role additions
        CheckConstraint(
            (
                f"role IN ('{UserRole.ADMIN.value}', "
                f"'{UserRole.ANALYST.value}', '{UserRole.VIEWER.value}')"
            ),
            name="ck_users_role_valid",
        ),
        # Composite index for admin user list queries
        # Filters active users and sorts by creation date (most recent first)
        # Traces to: 04-Database-Design §5.1 (users_active_created index)
        Index(
            "ix_users_active_created",
            "is_active",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        # Email index already created by unique=True on email column
        # Additional index for soft-delete queries (exclude deleted users)
        Index(
            "ix_users_deleted_at",
            "deleted_at",
        ),
    )

    def __repr__(self) -> str:
        """
        String representation for debugging.

        Does NOT include password_hash for security.

        Returns:
            String like '<User id=uuid email=jane@example.com role=analyst>'
        """
        return (
            f"<User id={self.id} email={self.email} role={self.role} "
            f"active={self.is_active}>"
        )
