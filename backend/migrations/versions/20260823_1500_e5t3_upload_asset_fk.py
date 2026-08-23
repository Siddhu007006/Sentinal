"""E5.T3: move the upload↔asset FK to uploads.digital_asset_id

Implements the 02-Domain-Model ERD relationship
("DIGITAL_ASSET ||--|{ UPLOAD : matched by") that was deliberately
deferred during the DigitalAsset reconciliation (2026-08-23):

- uploads.digital_asset_id UUID NULL, FK → digital_assets.id
  ON DELETE RESTRICT, indexed. NULL until upload_status = 'completed'
  (CHECK ck_uploads_digital_asset_completed).
- digital_assets.upload_id dropped together with its
  ck_digital_assets_file_upload_invariant CHECK — the linkage now
  lives on the Upload side, where one asset is matched by many
  uploads (content deduplication).

Best-effort backfill (upgrade): existing digital_assets.upload_id
values are copied into uploads.digital_asset_id where unambiguous
(deterministic MIN(id) when an upload had multiple assets). Dev/test
databases are truncated, so this is normally a no-op.

Runs as schema_owner via DATABASE_MIGRATION_URL.

Revision ID: e5t3_upload_asset_fk
Revises: reconcile_digital_assets
Create Date: 2026-08-23 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5t3_upload_asset_fk"
down_revision: str | Sequence[str] | None = "reconcile_digital_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Move the upload↔asset FK to the uploads side."""
    op.add_column(
        "uploads",
        sa.Column(
            "digital_asset_id",
            sa.UUID(),
            nullable=True,
            comment=(
                "Resolved DigitalAsset; NULL until upload_status="
                "'completed' (content deduplication target)"
            ),
        ),
    )

    # Backfill from the old column (deterministic when an upload was
    # referenced by multiple assets; PostgreSQL has no MIN(uuid)).
    op.execute(
        """
        UPDATE uploads
        SET digital_asset_id = (
            SELECT da.id FROM digital_assets da
            WHERE da.upload_id = uploads.id
            ORDER BY da.created_at, da.id
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM digital_assets da WHERE da.upload_id = uploads.id
        )
        """
    )

    op.create_foreign_key(
        "fk_uploads_digital_asset_id_digital_assets",
        "uploads",
        "digital_assets",
        ["digital_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_uploads_digital_asset_id",
        "uploads",
        ["digital_asset_id"],
    )
    # Bare name: the naming convention prefixes it with the table name,
    # producing ck_uploads_digital_asset_completed as declared in the
    # ORM __table_args__.
    op.create_check_constraint(
        "digital_asset_completed",
        "uploads",
        "digital_asset_id IS NULL OR upload_status = 'completed'",
    )

    # Drop the old asset→upload linkage.
    op.drop_constraint(
        "ck_digital_assets_file_upload_invariant",
        "digital_assets",
        type_="check",
    )
    op.drop_constraint(
        "fk_digital_assets_upload_id_uploads",
        "digital_assets",
        type_="foreignkey",
    )
    op.drop_column("digital_assets", "upload_id")


def downgrade() -> None:
    """Restore the asset→upload FK direction."""
    op.add_column(
        "digital_assets",
        sa.Column(
            "upload_id",
            sa.UUID(),
            nullable=True,
            comment="FK to uploads.id; only non-NULL for 'file' asset type",
        ),
    )

    # Reverse backfill (deterministic when an asset matched many uploads).
    op.execute(
        """
        UPDATE digital_assets
        SET upload_id = (
            SELECT u.id FROM uploads u
            WHERE u.digital_asset_id = digital_assets.id
            ORDER BY u.created_at, u.id
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM uploads u
            WHERE u.digital_asset_id = digital_assets.id
        )
        """
    )

    op.create_foreign_key(
        "fk_digital_assets_upload_id_uploads",
        "digital_assets",
        "uploads",
        ["upload_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Full name passed on purpose: the naming convention wraps it again,
    # reproducing the doubly-prefixed name the original 20260720
    # create_table migration left in the database.
    op.create_check_constraint(
        "ck_digital_assets_file_upload_invariant",
        "digital_assets",
        "(asset_type = 'file') = (upload_id IS NOT NULL)",
    )

    op.drop_constraint(
        "digital_asset_completed", "uploads", type_="check"
    )
    op.drop_index("ix_uploads_digital_asset_id", table_name="uploads")
    op.drop_constraint(
        "fk_uploads_digital_asset_id_digital_assets",
        "uploads",
        type_="foreignkey",
    )
    op.drop_column("uploads", "digital_asset_id")
