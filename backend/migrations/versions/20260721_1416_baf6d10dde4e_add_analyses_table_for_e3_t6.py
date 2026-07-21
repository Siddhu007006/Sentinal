"""Add analyses table for E3.T6

Revision ID: baf6d10dde4e
Revises: 1f4a7b8c
Create Date: 2026-07-21 14:16:53.735645

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'baf6d10dde4e'
down_revision: str | Sequence[str] | None = '1f4a7b8c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the analyses table with all columns, constraints, and foreign keys
    op.create_table(
        'analyses',
        sa.Column('digital_asset_id', sa.UUID(), nullable=False),
        sa.Column('requested_by', sa.UUID(), nullable=False),
        sa.Column('analyzer_key', sa.String(length=255), nullable=False),
        sa.Column('analyzer_version', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('analyzer_slugs', postgresql.ARRAY(sa.String(), dimensions=1), nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.String(length=1024), nullable=True),
        sa.Column('error_code', sa.String(length=100), nullable=True),
        sa.Column('threat_score', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('reasoning_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('enrichment_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') OR severity IS NULL", name='ck_analyses_severity'),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled')", name='ck_analyses_status'),
        sa.CheckConstraint('confidence BETWEEN 0.0 AND 1.0 OR confidence IS NULL', name='ck_analyses_confidence'),
        sa.CheckConstraint('retry_count >= 0', name='ck_analyses_retry_count'),
        sa.CheckConstraint('threat_score BETWEEN 0.0 AND 1.0 OR threat_score IS NULL', name='ck_analyses_threat_score'),
        sa.ForeignKeyConstraint(['digital_asset_id'], ['digital_assets.id'], name='fk_analyses_digital_asset_id_digital_assets', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'], name='fk_analyses_requested_by_users', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='pk_analyses'),
    )
    
    # Create indexes
    op.create_index('ix_analyses_asset_analyzer_completed', 'analyses', ['digital_asset_id', 'analyzer_key', 'analyzer_version'], unique=True, postgresql_where="status = 'completed'")
    op.create_index('ix_analyses_asset_latest', 'analyses', ['digital_asset_id', 'created_at'], unique=False, postgresql_ops={'created_at': 'DESC'})
    op.create_index('ix_analyses_asset_status', 'analyses', ['digital_asset_id', 'status'], unique=False)
    op.create_index('ix_analyses_celery_task', 'analyses', ['celery_task_id'], unique=False, postgresql_where='celery_task_id IS NOT NULL')
    op.create_index('ix_analyses_pending', 'analyses', ['created_at'], unique=False, postgresql_where="status = 'pending'")
    op.create_index('ix_analyses_severity_completed', 'analyses', ['severity', 'created_at'], unique=False, postgresql_ops={'created_at': 'DESC'}, postgresql_where="status = 'completed'")
    op.create_index('ix_analyses_user_history', 'analyses', ['requested_by', 'created_at'], unique=False, postgresql_ops={'created_at': 'DESC'})


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes (in reverse order of creation)
    op.drop_index('ix_analyses_user_history', table_name='analyses')
    op.drop_index('ix_analyses_severity_completed', table_name='analyses')
    op.drop_index('ix_analyses_pending', table_name='analyses')
    op.drop_index('ix_analyses_celery_task', table_name='analyses')
    op.drop_index('ix_analyses_asset_status', table_name='analyses')
    op.drop_index('ix_analyses_asset_latest', table_name='analyses')
    op.drop_index('ix_analyses_asset_analyzer_completed', table_name='analyses')
    
    # Drop the analyses table
    op.drop_table('analyses')
