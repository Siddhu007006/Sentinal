"""
SQLAlchemy declarative base and base model.

Provides the foundation for all ORM models in the application. Every database
table model must inherit from BaseModel defined here, ensuring consistent
primary keys, timestamps, and metadata conventions.

The naming conventions defined here are critical for Alembic migrations:
- Constraints are auto-named following PostgreSQL best practices
- Migration scripts can reliably reference constraints by predictable names
- No manual constraint naming required in model definitions

Traces to: 04-Database-Design (UUID PKs, timezone-aware timestamps)
Traces to: 07-Backend-Development-Standards §8 (ORM models, naming conventions)
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


# Naming convention for database constraints.
#
# Alembic uses these patterns to generate predictable constraint names in
# migration files. Without explicit naming, constraint names are database-
# generated and unpredictable, making migrations fragile across environments.
#
# Pattern variables:
#   %(table_name)s     - Table name (e.g., "users")
#   %(column_0_name)s  - First column name (e.g., "email")
#   %(constraint_name)s - Constraint name from CheckConstraint
#   %(referred_table_name)s - Foreign key target table
#
# Generated names follow PostgreSQL conventions:
#   ix_users_email              - Index on users.email
#   uq_users_email              - Unique constraint on users.email
#   ck_users_email_format       - Check constraint on users table
#   fk_users_organization_id_organizations - FK from users to organizations
#   pk_users                    - Primary key on users
#
# Traces to: 07-Backend-Development-Standards §8 (naming conventions)
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base class.

    This is the root of the ORM model hierarchy. All models inherit from this
    (either directly or via BaseModel). It provides:
    - Shared metadata with naming conventions
    - SQLAlchemy 2.0 declarative mapping style
    - Type-safe attribute access via Mapped[]

    Do not inherit from Base directly in model definitions. Use BaseModel
    instead, which adds common fields (id, created_at, updated_at).

    Example (via BaseModel):
        ```python
        from app.infrastructure.database.base import BaseModel

        class User(BaseModel):
            __tablename__ = "users"

            email: Mapped[str] = mapped_column(unique=True)
            full_name: Mapped[str]
            # id, created_at, updated_at inherited from BaseModel
        ```

    Traces to: 07-Backend-Development-Standards §8 (declarative models)
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class BaseModel(Base):
    """
    Abstract base model with common fields.

    All domain entity models inherit from this. Provides:
    - UUID primary key (id)
    - Creation timestamp (created_at)
    - Update timestamp (updated_at)
    - Automatic timestamp population via SQL defaults

    Models inheriting from BaseModel should define:
    - __tablename__: Table name (singular, snake_case)
    - Domain-specific columns using Mapped[] syntax
    - Relationships (if needed)
    - Table-level constraints (if needed)

    Primary Key:
        - Type: UUID (uuid.UUID in Python, UUID in PostgreSQL)
        - Default: Auto-generated via uuid.uuid4() (application) or
                  gen_random_uuid() (database)
        - Immutable after creation

    Timestamps:
        - Type: datetime with timezone (datetime in Python, TIMESTAMPTZ in PostgreSQL)
        - created_at: Set once on INSERT, never updated
        - updated_at: Set on INSERT, updated on every UPDATE
        - Always stored as UTC, application handles timezone conversion

    Example usage:
        ```python
        from app.infrastructure.database.base import BaseModel

        class Upload(BaseModel):
            __tablename__ = "uploads"

            filename: Mapped[str]
            size_bytes: Mapped[int]
            uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

            # id, created_at, updated_at inherited and auto-managed
        ```

    Security considerations (08-Security-Architecture):
        - UUIDs prevent sequential ID enumeration attacks
        - Timestamps enable audit trail reconstruction
        - UTC storage prevents timezone confusion in logs

    Performance considerations (07-Backend-Development-Standards §13):
        - UUID indexing is efficient in PostgreSQL (B-tree support)
        - Server-side defaults reduce round-trips (no RETURNING needed for PKs)
        - Timestamp defaults offload work to database (no Python datetime overhead)

    Traces to: 04-Database-Design (UUID PKs, TIMESTAMPTZ columns)
    Traces to: 07-Backend-Development-Standards §8 (BaseModel pattern)
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        # Client-side default: Generated in Python before INSERT.
        # Allows immediate access to ID without database round-trip.
        default=uuid.uuid4,
        # Server-side default: Database generates UUID if not provided.
        # Fallback for INSERT statements that don't specify ID.
        # PostgreSQL gen_random_uuid() is cryptographically strong (uses /dev/urandom).
        server_default=func.gen_random_uuid(),
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        # Client-side default: Timestamp generated in Python.
        # Provides consistent timezone handling (always UTC).
        default=lambda: datetime.now(UTC),
        # Server-side default: Database generates timestamp on INSERT.
        # Ensures timestamp even if application doesn't provide one.
        # PostgreSQL now() returns TIMESTAMPTZ in database's timezone,
        # but we store as UTC for consistency.
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        # Client-side default: Initial value on INSERT.
        default=lambda: datetime.now(UTC),
        # Server-side default: Initial value on INSERT (same as created_at).
        server_default=func.now(),
        # Client-side onupdate: New timestamp on UPDATE.
        # SQLAlchemy automatically calls this on session.commit() if row changed.
        onupdate=lambda: datetime.now(UTC),
        # Server-side onupdate: Database updates timestamp on UPDATE.
        # Ensures timestamp update even if ORM doesn't handle it.
        # Note: PostgreSQL doesn't have native ON UPDATE trigger syntax,
        # so this generates an Alembic trigger in migrations.
        server_onupdate=func.now(),
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=None,
    )
    def __repr__(self) -> str:
        """
        String representation for debugging.

        Returns model name and ID, useful in logs and debugger.

        Example:
            >>> user = User(email="test@example.com")
            >>> repr(user)
            '<User id=550e8400-e29b-41d4-a716-446655440000>'
        """
        return f"<{self.__class__.__name__} id={self.id}>"

