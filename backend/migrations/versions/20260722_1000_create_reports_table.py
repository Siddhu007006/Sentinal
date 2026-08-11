"""Add reports table for E3.T7

Revision ID: create_reports
Revises: a8f2b3c1
Create Date: 2026-07-22 10:00:00.000000

This migration creates the reports table, establishing the report entity
for summarizing analysis results and findings for digital assets.

The reports table records:
- UUID primary key (auto-generated)
- Foreign key to digital_assets (required)
- Foreign key to analyses (optional)
- Foreign key to users (required, created_by)
- Title and description
- Status (draft, published, archived)
- Content (report body)
- Standard timestamps (created_at, updated_at, deleted_at from BaseModel)

Constraints:
- Foreign key: asset_id -> digital_assets.id
- Foreign key: analysis_id -> analyses.id (nullable)
- Foreign key: created_by -> users.id
- Status values: draft, published, archived (CHECK constraint)

Indexes:
- (asset_id, created_at DESC): Query reports for an asset
- (status, created_at DESC): Filter by status
- (created_by, created_at DESC): Reports created by a user
- deleted_at: Soft-delete filtering

Traces to:
- 04-Database-Design §5.7 (Report table specification)
- 22-Engineering-Backlog E3.T7 (Report ORM model task)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "create_reports"
down_revision: str | Sequence[str] | None = "a8f2b3c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the reports table with all columns, constraints, and indexes."""
    # Create reports table
    op.create_table(
        "reports",
        sa.Column(
            "asset_id",
            sa.UUID(as_uuid=True),
            nullable=False,
            comment="FK to digital_assets.id, required",
        ),
        sa.Column(
            "analysis_id",
            sa.UUID(as_uuid=True),
            nullable=True,
            comment="FK to analyses.id, optional",
        ),
        sa.Column(
            "created_by",
            sa.UUID(as_uuid=True),
            nullable=False,
            comment="FK to users.id, user who created the report",
        ),
        sa.Column(
            "title",
            sa.String(255),
            nullable=False,
            comment="Report title, displayed in UI",
        ),
        sa.Column(
            "description",
            sa.String(1000),
            nullable=True,
            comment="Optional description or summary",
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="'draft'",
            comment="Report status: draft, published, archived",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=True,
            comment="Report body/content",
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
        sa.Column(
            "deleted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["digital_assets.id"],
            name="fk_reports_asset_id_digital_assets",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            name="fk_reports_analysis_id_analyses",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_reports_created_by_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reports"),
    )

    # Create check constraint for status
    op.create_check_constraint(
        "ck_reports_status_valid",
        "reports",
        "status IN ('draft', 'published', 'archived')",
    )

    # Create indexes
    op.create_index(
        "ix_reports_asset_created",
        "reports",
        ["asset_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )

    op.create_index(
        "ix_reports_status_created",
        "reports",
        ["status", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )

    op.create_index(
        "ix_reports_created_by",
        "reports",
        ["created_by", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )

    op.create_index(
        "ix_reports_deleted_at",
        "reports",
        ["deleted_at"],
    )


def downgrade() -> None:
    """Drop the reports table and all associated indexes."""
    op.drop_index("ix_reports_deleted_at", table_name="reports")
    op.drop_index("ix_reports_created_by", table_name="reports")
    op.drop_index("ix_reports_status_created", table_name="reports")
    op.drop_index("ix_reports_asset_created", table_name="reports")
    op.drop_constraint("ck_reports_status_valid", "reports")
    op.drop_table("reports")
