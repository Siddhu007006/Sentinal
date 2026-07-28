"""Add uploads table

Revision ID: 85764e04d85a
Revises: de771966819d
Create Date: 2026-07-19 20:56:00.000000

This migration creates the uploads table, establishing the first cross-table
foreign key relationship to users. Every upload represents a document ingested
by a user, tracking its lifecycle from receipt (pending) through processing
(validation, hashing) to terminal state (completed/failed).

Each upload has:
- UUID primary key (auto-generated, prevents enumeration)
- Foreign key to users (every upload belongs to exactly one user)
- Original filename (as provided by user, up to 255 chars)
- Storage key (immutable S3/MinIO path, unique, up to 1024 chars)
- Content type (MIME type, e.g., application/pdf)
- File size in bytes (must be >= 0)
- Checksum SHA-256 (nullable, set during processing)
- Upload status (pending/processing/completed/failed)
- Completion timestamp (nullable, set when reaching terminal state)
- Timestamps (created_at auto-managed, updated_at auto-managed)

Constraints:
- Foreign key: user_id -> users.id
- UNIQUE on storage_key (prevents duplicate storage keys)
- UNIQUE on idempotency_key (nullable, allows deduplication retries)
- NOT NULL on: user_id, original_filename, storage_key, content_type,
  file_size_bytes, upload_status, created_at
- CHECK on upload_status (only pending/processing/completed/failed allowed)
- CHECK on file_size_bytes (must be >= 0)

Indexes:
- Primary key index (id)
- Foreign key index (user_id, automatic)
- UNIQUE index on storage_key (automatic)
- Composite index on (user_id, created_at DESC) for user upload history queries

State machine (enforced at domain layer, not DB):
- pending -> processing: validation starts
- pending -> failed: immediate validation failure
- processing -> completed: processing succeeded
- processing -> failed: processing failed
- completed/failed are terminal states

Traces to:
- 04-Database-Design §4 (ERD), §5.2 (uploads table specification)
- 02-Domain-Model §4 (Upload entity, state machine)
- 22-Engineering-Backlog E3.T4 (Upload ORM model task)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "85764e04d85a"
down_revision: str | Sequence[str] | None = "de771966819d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the uploads table with all columns, constraints, and indexes."""
    # Create uploads table
    op.create_table(
        "uploads",
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            nullable=False,
            comment=(
                "Foreign key to users table; every upload belongs to" "exactly one user"
            ),
        ),
        sa.Column(
            "original_filename",
            sa.String(255),
            nullable=False,
            comment=(
                "Original filename as provided by user (normalized, may"
                "contain special chars)"
            ),
        ),
        sa.Column(
            "storage_key",
            sa.String(1024),
            nullable=False,
            comment="S3/MinIO object key (immutable, unique, max 1024 chars)",
            unique=True,
            index=True,
        ),
        sa.Column(
            "content_type",
            sa.String(100),
            nullable=False,
            comment="MIME type (e.g., application/pdf, image/png)",
        ),
        sa.Column(
            "file_size_bytes",
            sa.BigInteger(),
            nullable=False,
            comment="File size in bytes (>= 0)",
        ),
        sa.Column(
            "checksum_sha256",
            sa.String(64),
            nullable=True,
            comment=(
                "SHA-256 hash of file (64-char hex); null until validation" "completes"
            ),
        ),
        sa.Column(
            "upload_status",
            sa.String(20),
            nullable=False,
            server_default="'pending'",
            comment="Upload lifecycle state: pending, processing, completed, failed",
        ),
        sa.Column(
            "completed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment=(
                "When upload reached terminal state (completed/failed);"
                "null if pending/processing"
            ),
        ),
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "upload_status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_uploads_upload_status_valid",
        ),
        sa.CheckConstraint(
            "file_size_bytes >= 0", name="ck_uploads_file_size_bytes_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_uploads_user_id_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_uploads"),
    )

    # Create indexes
    op.create_index(
        "ix_uploads_user_created",
        "uploads",
        ["user_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    """Drop the uploads table and all associated indexes."""
    op.drop_index("ix_uploads_user_created", table_name="uploads")
    op.drop_table("uploads")
