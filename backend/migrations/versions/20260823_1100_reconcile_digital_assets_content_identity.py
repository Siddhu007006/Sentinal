"""reconcile digital_assets: content identity + per-user IOC dedup

Reconciles the three conflicting DigitalAsset contracts (02-Domain-Model
content-addressed model, E3.T5 IOC model, and the previous IOC-only
implementation) into one schema:

- Content identity (file / file_hash assets): new sha256_hash column
  (64 lowercase hex, CHECK-enforced format) with a GLOBAL partial unique
  index — identical content uploaded by any user resolves to the SAME
  asset. mime_type and size_bytes become first-class columns
  (CHECK-required for 'file'). storage_key is nullable: object-storage
  assignment happens later in the upload lifecycle (E5.T4).
- Classification (url / domain / ip_address assets): unchanged columns;
  deduplication becomes per-user — the old GLOBAL unique
  (normalized_value, asset_type) is replaced by
  (user_id, normalized_value, asset_type) per 04-Database-Design §6.3
  ("dedup key is per-user"), fixing the contradiction where the old
  constraint blocked different users from owning the same indicator.

Ownership semantics (explicit decision): digital_assets is globally
content-addressed; user_id records the originating/first-upload context
only, NOT exclusive ownership. Per-user file visibility arrives with the
E5.T3 Upload rebuild (uploads.digital_asset_id); a user↔asset
association table remains the documented alternative.

Best-effort backfill promotes existing file/file_hash metadata
(checksum_sha256 / hash_value keys) into the new columns before the
CHECK constraints are added.

Runs as schema_owner via DATABASE_MIGRATION_URL.

Revision ID: reconcile_digital_assets
Revises: 66ffcf8ae2f3
Create Date: 2026-08-23 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "reconcile_digital_assets"
down_revision: str | Sequence[str] | None = "66ffcf8ae2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "digital_assets"


def upgrade() -> None:
    """Add content-identity columns; swap dedup constraint to per-user."""
    op.add_column(
        _TABLE,
        sa.Column(
            "sha256_hash",
            sa.String(64),
            nullable=True,
            comment=(
                "SHA-256 content hash (64 lowercase hex); business identity "
                "for file/file_hash assets, NULL for IOC assets"
            ),
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "mime_type",
            sa.String(100),
            nullable=True,
            comment="Detected MIME type (required for file assets)",
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "size_bytes",
            sa.BigInteger(),
            nullable=True,
            comment="Content size in bytes (required for file assets)",
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "storage_key",
            sa.String(1024),
            nullable=True,
            comment="Object storage key; assigned during upload lifecycle",
        ),
    )

    # Best-effort backfill from the pre-reconciliation JSONB metadata
    # (04-Database-Design §5.4.1 key names) before CHECKs land.
    op.execute(
        """
        UPDATE digital_assets
        SET sha256_hash = metadata->>'checksum_sha256'
        WHERE asset_type = 'file'
          AND metadata->>'checksum_sha256' ~ '^[a-f0-9]{64}$'
        """
    )
    op.execute(
        """
        UPDATE digital_assets
        SET mime_type = metadata->>'detected_mime_type'
        WHERE asset_type = 'file'
          AND metadata ? 'detected_mime_type'
        """
    )
    op.execute(
        """
        UPDATE digital_assets
        SET size_bytes = (metadata->>'file_size_bytes')::bigint
        WHERE asset_type = 'file'
          AND metadata ? 'file_size_bytes'
        """
    )
    op.execute(
        """
        UPDATE digital_assets
        SET sha256_hash = metadata->>'hash_value'
        WHERE asset_type = 'file_hash'
          AND metadata->>'algorithm' = 'sha256'
          AND metadata->>'hash_value' ~ '^[a-f0-9]{64}$'
        """
    )

    # Dedup swap: global (normalized_value, asset_type) → per-user.
    op.drop_constraint(
        "uq_digital_assets_normalized_value_type",
        _TABLE,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_digital_assets_user_value_type",
        _TABLE,
        ["user_id", "normalized_value", "asset_type"],
        comment=(
            "Per-user deduplication: one (normalized_value, asset_type) "
            "per user; identical content across users dedups by sha256_hash"
        ),
    )

    # Global content identity: one asset per content hash.
    op.create_index(
        "uq_digital_assets_sha256_hash",
        _TABLE,
        ["sha256_hash"],
        unique=True,
        postgresql_where=sa.text("sha256_hash IS NOT NULL"),
    )

    # Structural invariants. NOTE: bare names — op.create_check_constraint
    # prefixes them with the table name, producing the
    # ck_digital_assets_* names declared in the ORM __table_args__.
    op.create_check_constraint(
        "file_hash_required",
        _TABLE,
        "asset_type NOT IN ('file', 'file_hash') OR sha256_hash IS NOT NULL",
    )
    op.create_check_constraint(
        "file_mime_required",
        _TABLE,
        "asset_type <> 'file' OR mime_type IS NOT NULL",
    )
    op.create_check_constraint(
        "file_size_required",
        _TABLE,
        "asset_type <> 'file' OR size_bytes IS NOT NULL",
    )
    op.create_check_constraint(
        "sha256_format",
        _TABLE,
        "sha256_hash IS NULL OR sha256_hash ~ '^[a-f0-9]{64}$'",
    )


def downgrade() -> None:
    """Restore the pre-reconciliation IOC-only schema."""
    # Bare names: the naming convention prefixes them with the table
    # name, matching the names created in upgrade().
    op.drop_constraint("sha256_format", _TABLE, type_="check")
    op.drop_constraint("file_size_required", _TABLE, type_="check")
    op.drop_constraint("file_mime_required", _TABLE, type_="check")
    op.drop_constraint("file_hash_required", _TABLE, type_="check")
    op.drop_index("uq_digital_assets_sha256_hash", table_name=_TABLE)
    op.drop_constraint(
        "uq_digital_assets_user_value_type", _TABLE, type_="unique"
    )
    op.create_unique_constraint(
        "uq_digital_assets_normalized_value_type",
        _TABLE,
        ["normalized_value", "asset_type"],
    )
    op.drop_column(_TABLE, "storage_key")
    op.drop_column(_TABLE, "size_bytes")
    op.drop_column(_TABLE, "mime_type")
    op.drop_column(_TABLE, "sha256_hash")
