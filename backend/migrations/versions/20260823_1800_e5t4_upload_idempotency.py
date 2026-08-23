"""E5.T4: uploads.idempotency_key for idempotent POST /uploads retries

Adds a nullable client-supplied idempotency key with a per-user partial
unique index: one upload per (user_id, idempotency_key) where the key
is present. Retrying POST /uploads with the same key returns the
original upload instead of re-processing (22-Engineering-Backlog E5.T4
acceptance criterion: "Idempotency key prevents duplicate uploads").
Uploads without a key are unrestricted.

Runs as schema_owner via DATABASE_MIGRATION_URL.

Revision ID: e5t4_upload_idempotency
Revises: e5t3_upload_asset_fk
Create Date: 2026-08-23 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5t4_upload_idempotency"
down_revision: str | Sequence[str] | None = "e5t3_upload_asset_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add idempotency_key column with per-user partial unique index."""
    op.add_column(
        "uploads",
        sa.Column(
            "idempotency_key",
            sa.String(255),
            nullable=True,
            comment=(
                "Client idempotency key; one upload per user+key "
                "(unique where not null)"
            ),
        ),
    )
    op.create_index(
        "uq_uploads_user_idempotency_key",
        "uploads",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove the idempotency_key column and its index."""
    op.drop_index(
        "uq_uploads_user_idempotency_key",
        table_name="uploads",
    )
    op.drop_column("uploads", "idempotency_key")
