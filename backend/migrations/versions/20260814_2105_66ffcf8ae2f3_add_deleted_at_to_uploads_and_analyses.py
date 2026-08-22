"""add deleted_at to uploads and analyses

Revision ID: 66ffcf8ae2f3
Revises: make_full_name_optional
Create Date: 2026-08-14 21:05:04.705751

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "66ffcf8ae2f3"
down_revision: str | Sequence[str] | None = "make_full_name_optional"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add soft-delete timestamps to uploads and analyses."""
    op.add_column(
        "uploads",
        sa.Column(
            "deleted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Soft delete timestamp; NULL for active records",
        ),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "deleted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Soft delete timestamp; NULL for active records",
        ),
    )


def downgrade() -> None:
    """Remove soft-delete timestamps from uploads and analyses."""
    op.drop_column("analyses", "deleted_at")
    op.drop_column("uploads", "deleted_at")