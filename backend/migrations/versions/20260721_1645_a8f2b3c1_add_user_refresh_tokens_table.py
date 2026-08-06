"""Add user_refresh_tokens table for E3.T9

Revision ID: a8f2b3c1
Revises: 9c8e3f5b
Create Date: 2026-07-21 16:45:00.000000

This migration creates the user_refresh_tokens table, establishing the server-side
refresh token store for session management and per-device revocation.

The user_refresh_tokens table records:
- UUID primary key (auto-generated)
- Foreign key to users (NOT NULL, ON DELETE CASCADE)
- Token hash (SHA-256 hex digest, 64 chars, unique, never raw token)
- Expiry timestamp (absolute UTC, not relative TTL)
- Revocation flag (true = token unusable, false = active)
- User agent (HTTP User-Agent header, for audit context)
- IP address (Client IP, INET type, for audit context)
- Revocation timestamp (when token was revoked, null if active)
- Standard timestamps (created_at, updated_at, deleted_at from BaseModel)

Token Lifecycle:

1. **Issuance:** User logs in. Application generates random token, hashes with
   SHA-256, creates RefreshToken record with expiry and session context. Raw
   token returned to client (HTTPS only).

2. **Storage:** Client stores token securely (HttpOnly cookie or secure storage).

3. **Refresh:** Client sends token. Application hashes it, looks up by hash,
   validates expiry and revocation status. If valid, issues new access token
   and new refresh token (rotation pattern).

4. **Revocation:** User logs out or admin revokes. Application sets is_revoked=true
   and revoked_at=now(). Token cannot be used again.

5. **Cleanup:** Background job queries (expires_at < now() AND is_revoked=false)
   and hard-deletes expired tokens. Partial index makes this efficient.

6. **Deletion:** User deleted. ON DELETE CASCADE removes all refresh tokens for
   that user.

Security Design:

- **Token Hash Storage:** Only SHA-256 hash of opaque token is stored (never raw).
  If database breached, attacker sees hashes only (cryptographically infeasible
  to reverse-engineer SHA-256). Active sessions remain secure.

- **Server-Side Revocation:** Unlike stateless JWT access tokens, refresh tokens
  can be revoked at any time. Revocation is immediate (checked on next API request).

- **Per-Device Sessions:** Each device has its own token record. User can logout
  from one device without affecting other logins. User agent + IP provide audit
  context.

- **Cascade Deletion:** ON DELETE CASCADE ensures tokens are hard-deleted when user
  is deleted (not orphaned). Simplifies data retention and prevents querying tokens
  for deleted users.

Constraints:

- **Primary Key:** id (UUID)
- **Foreign Key:** user_id -> users.id (ON DELETE CASCADE)
- **Unique Constraint:** token_hash (prevents duplicate hashes)
- **Not Null:** user_id, token_hash, expires_at, is_revoked, created_at
- **Nullable:** user_agent, ip_address, revoked_at, updated_at (immutability
  intent: no updates to refresh tokens)

Indexes:

- **user_id:** Efficient session listing (get all tokens for a user)
- **token_hash (unique):** O(1) token validation lookup
- **Partial on expires_at:** WHERE is_revoked=false for cleanup queries
  (efficient cleanup of expired, non-revoked tokens)

Query Patterns:

```sql
-- Token validation (most frequent)
SELECT * FROM user_refresh_tokens
WHERE token_hash = %s
AND is_revoked = false
AND expires_at > now()
LIMIT 1

-- Session listing (user views active sessions)
SELECT * FROM user_refresh_tokens
WHERE user_id = %s
AND is_revoked = false
AND expires_at > now()
ORDER BY created_at DESC

-- Revoke all user sessions (password change, admin action)
UPDATE user_refresh_tokens
SET is_revoked = true, revoked_at = now(), updated_at = now()
WHERE user_id = %s
AND is_revoked = false

-- Cleanup expired tokens (background job, nightly)
DELETE FROM user_refresh_tokens
WHERE is_revoked = false
AND expires_at < now()
```

Immutability Note:

This model is designed to be immutable after creation. Tokens should never be
modified in place (no UPDATE on token_hash, expires_at). Revocation is the only
allowed modification (setting is_revoked, revoked_at). Future versions may enforce
immutability at the database level (GRANT SELECT, INSERT only to app role).

Traces to:
- 04-Database-Design §4 (ERD, user_refresh_tokens table)
- 04-Database-Design §3.2 (Refresh tokens as server-side session control)
- 04-Database-Design §5.2 (RefreshToken schema specification)
- 08-Security-Architecture §5 (JWT and refresh token lifecycle)
- 22-Engineering-Backlog E3.T9 (Refresh Tokens ORM Model and Migration task)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import INET


# revision identifiers, used by Alembic.
revision: str = "a8f2b3c1"
down_revision: str | Sequence[str] | None = "9c8e3f5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create user_refresh_tokens table with columns, constraints, indexes."""
    # Create user_refresh_tokens table
    op.create_table(
        "user_refresh_tokens",
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            nullable=False,
            comment="FK to users.id; ON DELETE CASCADE (every token belongs to a user)",
        ),
        sa.Column(
            "token_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 hash of token (64 hex); UNIQUE; never raw token",
        ),
        sa.Column(
            "expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            comment="Absolute UTC expiry timestamp (not relative TTL)",
        ),
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Explicit revocation flag (false=active, true=revoked)",
        ),
        sa.Column(
            "user_agent",
            sa.String(512),
            nullable=True,
            comment="HTTP User-Agent; context for audit trail (not security)",
        ),
        sa.Column(
            "ip_address",
            INET(),  # type: ignore[no-untyped-call]
            nullable=True,
            comment="Client IP; from X-Forwarded-For or request.client.host",
        ),
        sa.Column(
            "revoked_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="UTC timestamp when token was revoked (null for active tokens)",
        ),
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "deleted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_refresh_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_refresh_tokens"),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_user_refresh_tokens_token_hash",
        ),
    )

    # Create indexes
    # Index on user_id for efficient session listing queries
    op.create_index(
        "ix_user_refresh_tokens_user_id",
        "user_refresh_tokens",
        ["user_id"],
    )

    # Partial index on expires_at for efficient cleanup of expired tokens
    # Condition: is_revoked = false (don't include revoked tokens)
    # Query: SELECT * FROM user_refresh_tokens WHERE
    #        is_revoked=false AND expires_at < now()
    op.create_index(
        "ix_user_refresh_tokens_expires_at_active",
        "user_refresh_tokens",
        ["expires_at"],
        postgresql_where="is_revoked = false",
    )

    # Note: token_hash index is automatically created by UNIQUE constraint
    # Note: user_id index for foreign key is explicitly created above


def downgrade() -> None:
    """Drop the user_refresh_tokens table and all associated indexes."""
    op.drop_index(
        "ix_user_refresh_tokens_expires_at_active",
        table_name="user_refresh_tokens",
    )
    op.drop_index(
        "ix_user_refresh_tokens_user_id",
        table_name="user_refresh_tokens",
    )
    op.drop_table("user_refresh_tokens")

