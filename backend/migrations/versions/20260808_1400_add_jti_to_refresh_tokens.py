"""Add jti field to RefreshToken for JWT ID tracking

Revision ID: add_jti_to_refresh_tokens
Revises: increase_password_hash_argon2
Create Date: 2026-08-08 14:00:00.000000

This migration adds the 'jti' (JWT ID) field to the user_refresh_tokens table.

The jti field stores the unique JWT ID claim from the refresh token payload,
enabling efficient revocation tracking and token validation. Each token has
a unique jti that identifies it in the database.

Changes:
- Add jti column (String(256), NOT NULL, UNIQUE)
- Add index on jti for efficient lookup
- Set default value for existing rows (empty string for backward compatibility)

Traces to:
- RefreshToken domain entity (jti required field)
- Token revocation tracking in auth service
- E4V.T2 test suite requirements
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_jti_to_refresh_tokens"
down_revision: str | Sequence[str] | None = "increase_password_hash_argon2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add jti column to user_refresh_tokens table."""
    # Add jti column as nullable first (to allow existing rows)
    op.add_column(
        "user_refresh_tokens",
        sa.Column(
            "jti",
            sa.String(256),
            nullable=True,
            comment="JWT ID from token payload; unique constraint for revocation",
        ),
    )
    
    # Set existing rows to have a default jti value (empty string)
    # This is necessary for backward compatibility
    op.execute("UPDATE user_refresh_tokens SET jti = '' WHERE jti IS NULL")
    
    # Make jti not nullable
    op.alter_column(
        "user_refresh_tokens",
        "jti",
        existing_type=sa.String(256),
        nullable=False,
    )
    
    # Add unique constraint on jti
    op.create_unique_constraint(
        "uq_user_refresh_tokens_jti",
        "user_refresh_tokens",
        ["jti"],
    )
    
    # Add index on jti for efficient lookup
    op.create_index(
        "ix_user_refresh_tokens_jti",
        "user_refresh_tokens",
        ["jti"],
    )


def downgrade() -> None:
    """Remove jti column from user_refresh_tokens table."""
    # Drop index first
    op.drop_index("ix_user_refresh_tokens_jti", table_name="user_refresh_tokens")
    
    # Drop unique constraint
    op.drop_constraint(
        "uq_user_refresh_tokens_jti",
        "user_refresh_tokens",
        type_="unique",
    )
    
    # Drop column
    op.drop_column("user_refresh_tokens", "jti")
