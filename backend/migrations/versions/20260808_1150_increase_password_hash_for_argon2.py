"""Increase password_hash column size for Argon2 hashes

Revision ID: increase_password_hash_argon2
Revises: create_reports
Create Date: 2026-08-08 11:50:00.000000

This migration increases the password_hash column from String(60) to String(255)
to accommodate Argon2id hashes, which are significantly longer than bcrypt hashes.

Argon2id output format: $argon2id$v=19$m=65536,t=2,p=4$<salt>$<hash>
This can be 92+ characters, whereas bcrypt is fixed at 60 characters.

The password hashing algorithm was updated to use Argon2id by default,
but the column size was not updated to accommodate the longer hashes.
This migration fixes that discrepancy.

Traces to:
- Epic 4: Verification Closure
- Password hashing configuration changes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "increase_password_hash_argon2"
down_revision: str | Sequence[str] | None = "create_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Increase password_hash column size to accommodate Argon2 hashes."""
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(60),
        type_=sa.String(255),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert password_hash column size back to bcrypt size."""
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(255),
        type_=sa.String(60),
        existing_nullable=False,
    )
