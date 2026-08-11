"""Make full_name column optional in users table

Revision ID: make_full_name_optional
Revises: add_jti_to_refresh_tokens
Create Date: 2026-08-08 14:30:00.000000

This migration makes the full_name column nullable to support optional user input
during registration. Users can now register without providing a full name.

Traces to:
- Epic 4: Verification Closure (E4V.T2 fixes)
- UserResponse schema: fullName should be optional
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "make_full_name_optional"
down_revision: str | Sequence[str] | None = "add_jti_to_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make full_name column nullable."""
    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.String(255),
        nullable=True,
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert full_name column back to NOT NULL."""
    # Set existing NULL values to empty string before making NOT NULL
    op.execute("UPDATE users SET full_name = '' WHERE full_name IS NULL")
    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.String(255),
        nullable=False,
        existing_nullable=True,
    )
