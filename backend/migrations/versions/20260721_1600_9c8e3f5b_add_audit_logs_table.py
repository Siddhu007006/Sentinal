"""Add audit_logs table for E3.T8

Revision ID: 9c8e3f5b
Revises: baf6d10dde4e
Create Date: 2026-07-21 16:00:00.000000

This migration creates the audit_logs table, establishing the immutable audit
trail for all state-changing operations in Sentinel. Every create, update, delete,
or other significant action is recorded with full context: who did it, what changed
(before/after state), when, how (IP/user-agent), and whether it succeeded.

The audit_logs table records:
- UUID primary key (auto-generated)
- Foreign key to users (nullable for system actions)
- Actor role at time of action (snapshot for audit trail)
- Action type (e.g., "CREATE_ASSET", "DELETE_REPORT")
- Resource type and ID (what was changed)
- Before/after state snapshots (JSONB, nullable)
- IP address and request context (security/traceability)
- Success flag and failure reason
- Occurred timestamp (operation time, not audit record creation time)
- Standard timestamps (created_at, updated_at, deleted_at from BaseModel)

Constraints:
- UNIQUE on (actor_id, resource_id, occurred_at) to prevent duplicates
- Foreign key: actor_id -> users.id (nullable for system actions)
- Indexes for efficient querying by actor, resource, or time

Immutability:
- Application database role has GRANT SELECT, INSERT only
- No UPDATE or DELETE privileges for application role
- Attempt to modify raises PostgreSQL permission denied error
- Admin role retains full privileges for forensics

Indexes:
- Primary key index (id)
- Foreign key index (actor_id, automatic)
- UNIQUE index on (actor_id, resource_id, occurred_at)
- Composite index on (resource_type, resource_id) for resource change queries
- Index on occurred_at DESC for chronological queries

Lifecycle:
1. Operation occurs (user creates asset, modifies report, etc.)
2. AuditLog record created with before_state, after_state, actor, timestamp
3. Record inserted to database (INSERT allowed by role)
4. Record immutable forever (UPDATE/DELETE denied by role)
5. Queryable for compliance, audit, forensics

Traces to:
- 04-Database-Design §4 (ERD), §11 (Audit Strategy, immutability)
- 08-Security-Architecture §6 (audit trail integrity)
- 22-Engineering-Backlog E3.T8 (AuditLog ORM model task)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import INET, JSON


# revision identifiers, used by Alembic.
revision: str = "9c8e3f5b"
down_revision: str | Sequence[str] | None = "baf6d10dde4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the audit_logs table with all columns, constraints, and indexes."""
    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column(
            "actor_id",
            sa.UUID(as_uuid=True),
            nullable=True,
            comment="Who performed the action (FK to users.id, nullable for system actions)",
        ),
        sa.Column(
            "actor_role",
            sa.String(20),
            nullable=False,
            comment="Role of actor at time of action (captured snapshot)",
        ),
        sa.Column(
            "action",
            sa.String(100),
            nullable=False,
            comment='Operation type (e.g., "CREATE_ASSET", "DELETE_REPORT")',
        ),
        sa.Column(
            "resource_type",
            sa.String(100),
            nullable=False,
            comment="Entity type affected (e.g., DigitalAsset, Report)",
        ),
        sa.Column(
            "resource_id",
            sa.UUID(as_uuid=True),
            nullable=False,
            comment="ID of the entity that was affected",
        ),
        sa.Column(
            "before_state",
            JSON(),  # type: ignore[no-untyped-call]
            nullable=True,
            server_default="null",
            comment="Entity state before operation (JSONB, null for creates)",
        ),
        sa.Column(
            "after_state",
            JSON(),  # type: ignore[no-untyped-call]
            nullable=True,
            server_default="null",
            comment="Entity state after operation (JSONB, null for deletes)",
        ),
        sa.Column(
            "ip_address",
            INET(),  # type: ignore[no-untyped-call]
            nullable=True,
            comment="Client IP address (INET type, from X-Forwarded-For or request.client.host)",
        ),
        sa.Column(
            "request_id",
            sa.String(255),
            nullable=True,
            comment="Request correlation ID for distributed tracing",
        ),
        sa.Column(
            "user_agent",
            sa.String(500),
            nullable=True,
            comment="Client HTTP User-Agent header for context",
        ),
        sa.Column(
            "success",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Operation success flag (false means see failure_reason for error)",
        ),
        sa.Column(
            "failure_reason",
            sa.String(1000),
            nullable=True,
            server_default="null",
            comment="Error message if success=false",
        ),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Server timestamp of operation (UTC)",
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
            ["actor_id"],
            ["users.id"],
            name="fk_audit_logs_actor_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        sa.UniqueConstraint(
            "actor_id",
            "resource_id",
            "occurred_at",
            name="uq_audit_logs_actor_resource_time",
        ),
    )

    # Create indexes
    op.create_index(
        "ix_audit_logs_resource",
        "audit_logs",
        ["resource_type", "resource_id"],
    )

    op.create_index(
        "ix_audit_logs_occurred_at",
        "audit_logs",
        ["occurred_at"],
        postgresql_ops={"occurred_at": "DESC"},
    )

    # Note: actor_id index is automatically created by the foreign key constraint


def downgrade() -> None:
    """Drop the audit_logs table and all associated indexes."""
    op.drop_index("ix_audit_logs_occurred_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.drop_table("audit_logs")
