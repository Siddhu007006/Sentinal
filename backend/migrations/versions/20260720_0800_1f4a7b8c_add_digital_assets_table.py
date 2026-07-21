"""Add digital_assets table

Revision ID: 1f4a7b8c
Revises: 85764e04d85a
Create Date: 2026-07-20 08:00:00.000000

This migration creates the digital_assets table, establishing the central entity
of Sentinel. Every analysis, report, and verdict revolves around a DigitalAsset.
The table represents a unique piece of content (URL, domain, IP, file hash, or
uploaded file) submitted for security evaluation.

Each digital asset has:
- UUID primary key (auto-generated, prevents enumeration)
- Foreign key to users (every asset belongs to exactly one user, immutable)
- Optional foreign key to uploads (only for 'file' type assets)
- Asset type classification (url, domain, ip_address, file_hash, file)
- Raw value (original submitted form, up to 2048 chars)
- Normalized value (canonicalized form for deduplication, up to 2048 chars)
- Optional display label (user-provided annotation, up to 512 chars)
- Metadata (JSONB, asset-type-specific attributes, nullable)
- Active flag (true = queryable, false = archived by user)
- Timestamps (created_at immutable, updated_at auto-managed, deleted_at soft delete)

Constraints:
- Foreign key: user_id -> users.id (RESTRICT on delete)
- Foreign key: upload_id -> uploads.id (SET NULL on delete, only for file type)
- UNIQUE on (normalized_value, asset_type) composite key for deduplication
- NOT NULL on: user_id, asset_type, raw_value, normalized_value, is_active, created_at
- CHECK on asset_type (must be one of five values: url, domain, ip_address, file_hash, file)
- CHECK on (asset_type = 'file') = (upload_id IS NOT NULL) - structural invariant
- Nullable: upload_id, display_label, metadata, deleted_at

Immutability:
- All core fields (asset_type, raw_value, normalized_value, upload_id, metadata)
  are immutable after creation. New content = new row, never edit existing.
- Only user_mutable field: display_label (optional annotation)
- Soft delete field: deleted_at (archive timestamp)

Indexes:
- Primary key index (id)
- Foreign key index (user_id, automatic)
- UNIQUE index on (normalized_value, asset_type) (automatic)
- Composite index on (user_id, created_at DESC) for user asset history
- Composite index on (user_id, asset_type, created_at DESC) for type filtering
- Index on (normalized_value, asset_type) for deduplication checks
- GIN index on metadata for JSONB containment queries

Deduplication:
The UNIQUE constraint on (normalized_value, asset_type) ensures a user cannot
have two assets with the same normalized value and type. This is the deduplication
key: submitting the same asset twice returns the existing asset (idempotent).
Different users can have the same asset; it is not deduplicated globally.

Lifecycle:
1. Created: User submits asset. created_at set, is_active=true, deleted_at=NULL
2. Active: Asset queryable, analyzable, included in reports
3. Archived: User sets is_active=false. Asset hidden but preserved.
4. Soft-deleted: User deletes asset. deleted_at set, excluded from queries.

Traces to:
- 04-Database-Design §4 (ERD), §5.4 (digital_assets table specification)
- 02-Domain-Model §3 (DigitalAsset entity, immutability, deduplication)
- 22-Engineering-Backlog E3.T5 (DigitalAsset ORM model task)
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '1f4a7b8c'
down_revision: str | Sequence[str] | None = '85764e04d85a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the digital_assets table with all columns, constraints, and indexes."""
    # Create digital_assets table
    op.create_table(
        'digital_assets',
        sa.Column('user_id', sa.UUID(as_uuid=True), nullable=False, comment='Asset owner; foreign key to users.id with RESTRICT on delete'),
        sa.Column('upload_id', sa.UUID(as_uuid=True), nullable=True, comment='FK to uploads.id; only non-NULL for file asset type'),
        sa.Column('asset_type', sa.String(20), nullable=False, comment='Asset classification: url, domain, ip_address, file_hash, file'),
        sa.Column('raw_value', sa.String(2048), nullable=False, comment='Original submitted value (up to 2048 chars)'),
        sa.Column('normalized_value', sa.String(2048), nullable=False, comment='Canonicalized form for deduplication (lowercased domain, defanged URL, etc.)'),
        sa.Column('display_label', sa.String(512), nullable=True, comment='Optional user-provided label for UI and reports'),
        sa.Column('metadata', JSONB(), nullable=True, server_default='null', comment='Asset-type-specific metadata (JSONB, see Database Design §5.4.1)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='false = user archived this asset (soft visibility control)'),
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='Soft delete timestamp; NULL for active records'),
        sa.CheckConstraint("asset_type IN ('url', 'domain', 'ip_address', 'file_hash', 'file')", name='ck_digital_assets_asset_type_valid'),
        sa.CheckConstraint("(asset_type = 'file') = (upload_id IS NOT NULL)", name='ck_digital_assets_file_upload_invariant'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_digital_assets_user_id_users', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['upload_id'], ['uploads.id'], name='fk_digital_assets_upload_id_uploads', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_digital_assets'),
        sa.UniqueConstraint('normalized_value', 'asset_type', name='uq_digital_assets_normalized_value_type', comment='Deduplication constraint: user cannot have duplicate (normalized_value, asset_type)'),
    )

    # Create indexes
    op.create_index(
        'ix_digital_assets_user_created',
        'digital_assets',
        ['user_id', 'created_at'],
        postgresql_ops={'created_at': 'DESC'},
    )

    op.create_index(
        'ix_digital_assets_user_type_created',
        'digital_assets',
        ['user_id', 'asset_type', 'created_at'],
        postgresql_ops={'created_at': 'DESC'},
    )

    op.create_index(
        'ix_digital_assets_normalized_value_type',
        'digital_assets',
        ['normalized_value', 'asset_type'],
    )

    op.create_index(
        'ix_digital_assets_metadata_gin',
        'digital_assets',
        ['metadata'],
        postgresql_using='gin',
    )


def downgrade() -> None:
    """Drop the digital_assets table and all associated indexes."""
    op.drop_index('ix_digital_assets_metadata_gin', table_name='digital_assets')
    op.drop_index('ix_digital_assets_normalized_value_type', table_name='digital_assets')
    op.drop_index('ix_digital_assets_user_type_created', table_name='digital_assets')
    op.drop_index('ix_digital_assets_user_created', table_name='digital_assets')
    op.drop_table('digital_assets')
