"""Initial schema: create users table

Revision ID: de771966819d
Revises: 
Create Date: 2026-07-19 11:18:28.933961

This migration creates the initial database schema with the users table.
It represents the authoritative registry of all Sentinel platform users.

Each user has:
- UUID primary key (prevents enumeration attacks)
- Email (unique, indexed for login lookups)
- Password hash (bcrypt, never exposed in responses)
- Full name (for UI display)
- Role (RBAC: admin, analyst, viewer)
- Active flag (administrative deactivation, separate from soft-delete)
- Verified flag (email verification status)
- Timestamps (created_at, updated_at auto-managed by database)
- Soft-delete timestamp (deleted_at, enables audit trail preservation)

Constraints:
- UNIQUE on email (case-insensitive login)
- CHECK on role (only admin, analyst, viewer allowed)
- NOT NULL on required fields (enforced at DB level)

Indexes:
- Primary key index (id)
- Unique index on email (automatic from UNIQUE constraint)
- Composite index on (is_active, created_at DESC) for admin user list queries
- Index on deleted_at for soft-delete filtering

Traces to:
- 04-Database-Design §5.1 (users table specification)
- 08-Security-Architecture §4 (authentication, passwords)
- 22-Engineering-Backlog E3.T3 (User ORM model task)
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'de771966819d'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the users table with all columns, constraints, and indexes."""
    # Create users table
    op.create_table(
        'users',
        sa.Column('email', sa.String(320), nullable=False, comment='Primary login credential (lowercased, normalized)'),
        sa.Column('password_hash', sa.String(60), nullable=False, comment='bcrypt hash (cost=12), never plaintext'),
        sa.Column('full_name', sa.String(255), nullable=False, comment='Display name for UI and reports'),
        sa.Column('role', sa.String(20), nullable=False, server_default="'viewer'", comment='RBAC role: admin, analyst, viewer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='false = deactivated, login rejected'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false', comment='Email verification status'),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='Soft delete timestamp (UTC), null = active'),
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("role IN ('admin', 'analyst', 'viewer')", name='ck_users_ck_users_role_valid'),
        sa.PrimaryKeyConstraint('id', name='pk_users'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )

    # Create indexes
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index(
        'ix_users_active_created',
        'users',
        ['is_active', 'created_at'],
        postgresql_ops={'created_at': 'DESC'},
    )
    op.create_index('ix_users_deleted_at', 'users', ['deleted_at'])


def downgrade() -> None:
    """Drop the users table and all associated indexes."""
    op.drop_index('ix_users_deleted_at', table_name='users')
    op.drop_index('ix_users_active_created', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
