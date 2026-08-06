"""
AuditLog ORM model.

Defines the immutable audit trail for all state-changing operations in Sentinel.
Every create, update, delete, or other significant action is recorded with full
context: who did it, what changed (before/after state), when, how (IP/user-agent),
and whether it succeeded.

Key design decisions:

1. **Immutability by Design:** AuditLog is append-only, never modified. Enforced at
   both ORM layer (no update/delete methods) and database layer (GRANT SELECT, INSERT
   only). This is essential for compliance (SOC2, PCI-DSS, HIPAA) and security
   (audit trail integrity).

2. **Nullable actor_id:** System-initiated operations (cleanup jobs, retries) may
   have no actor. Rationale: Audit trail must cover all operations, not just
   user-initiated ones. Security monitoring needs complete picture.

3. **JSONB for State Snapshots:** before_state and after_state are full entity
   snapshots, not individual field changes. Enables forensic analysis ("what was
   the old value?") without schema coupling. Schema can evolve independently of
   audit log structure.

4. **Unique Constraint on (actor_id, resource_id, occurred_at):** Prevents
   accidental duplicate audits. Same actor + same resource + same microsecond =
   same operation. Database-level enforcement prevents race conditions.

5. **Timestamp Fields Separation:** occurred_at (operation time) separate from
   created_at (audit record creation time). Most queries use occurred_at;
   created_at is for audit log rotation/archival.

6. **Role-Based Access Control:** Application database role has GRANT SELECT,
   INSERT on audit_logs. No UPDATE or DELETE privileges. Admin role retains
   full privileges for forensics. Attempt to UPDATE/DELETE raises permission
   denied error.

7. **No update() or delete() Methods:** ORM layer forbids modification operations.
   Application code must never call session.update(audit_log) or
   session.delete(audit_log). Only session.add() (for inserts).

Security notes:
- AuditLog is the compliance anchor: immutability is non-negotiable
- State blobs must be sanitized (no passwords, tokens, PII) by application layer
- IP address enables geographic tracking and abuse detection
- Request ID links audit log to application logs for distributed tracing
- Immutability enforced at database level (defense in depth)

Lifecycle:
1. Operation occurs (user creates asset, modifies report, etc.)
2. AuditLog record created with before_state, after_state, actor, timestamp
3. Record inserted to database (INSERT allowed by role)
4. Record immutable forever (UPDATE/DELETE denied by role)
5. Admin can query for forensics, compliance officers can access for audits
6. Archived/retained per compliance policy (future retention management)

Traces to: 04-Database-Design §4 (ERD), §11 (Audit Strategy, immutability)
Traces to: 08-Security-Architecture §6 (audit trail integrity)
Traces to: 02-Domain-Model §2 (observability as cross-cutting concern)
Traces to: 22-Engineering-Backlog E3.T8 (AuditLog ORM model task)
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import INET, JSON, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.database.base import BaseModel


class AuditLog(BaseModel):
    """
    Immutable audit trail record for state-changing operations.

    Inherits from BaseModel:
        - id: UUID primary key (automatically generated)
        - created_at: Timestamp of audit record creation (immutable)
        - updated_at: Timestamp of last modification (should rarely change)
        - deleted_at: Soft-delete timestamp (nullable)

    This model captures the complete context of every operation for compliance,
    forensics, and security analysis. Once created, audit logs cannot be modified
    or deleted—this is enforced at both the ORM layer (semantic) and database layer
    (role-based access control).

    Operation Lifecycle:
        1. User or system initiates action (create/update/delete entity)
        2. Before state captured (full entity snapshot or null for creates)
        3. Operation executed
        4. After state captured (full entity snapshot or null for deletes)
        5. AuditLog record created with both states
        6. Record inserted to database (immutable from this point)
        7. Queryable forever for compliance, audit, and forensics

    Immutability Enforcement:
        - **ORM Layer:** No update() or delete() methods exposed. Application code
          must never modify audit logs. Session.add() for inserts only.
        - **Database Layer:** GRANT SELECT, INSERT on audit_logs to app role.
          REVOKE UPDATE, DELETE. Attempt to modify raises "permission denied" error.
        - **Semantic:** Class docstring and comments reinforce immutability as a
          non-negotiable design constraint.

    State Snapshots (JSONB):
        - before_state: Full entity state before operation (null for creates)
        - after_state: Full entity state after operation (null for deletes)
        - Application layer must sanitize before inserting (no passwords, tokens, PII)
        - Enables forensic analysis: "What was the old value?"
        - JSONB is queryable and indexable (GIN indexes possible)

    Actor Semantics:
        - actor_id + actor_role captures WHO performed the operation
        - actor_id nullable for system-initiated operations (cleanup, retries)
        - actor_role captures role AT TIME OF ACTION (snapshot for audit trail)
        - Later role changes don't affect the audit record

    Resource Tracking:
        - resource_type + resource_id identifies WHAT changed
        - Enables filtering: "What happened to this asset?"
        - Examples: resource_type="DigitalAsset", resource_type="Report"

    Request Context:
        - ip_address: Client IP (from X-Forwarded-For or request.client.host)
        - request_id: Correlation ID linking audit log to application logs
        - user_agent: Client HTTP User-Agent for context
        - Enables: "Who accessed this from where?" and "Trace the request"

    Example:
        ```python
        # Application captures state before modification
        asset = session.get(DigitalAsset, asset_id)
        before_state = asset.to_dict()

        # Application executes modification
        asset.status = "archived"
        session.commit()

        # Application creates audit log
        audit = AuditLog(
            actor_id=current_user.id,
            actor_role=current_user.role,
            action="UPDATE_ASSET",
            resource_type="DigitalAsset",
            resource_id=asset_id,
            before_state=before_state,
            after_state=asset.to_dict(),
            ip_address=request.client.host,
            request_id=request.headers.get("X-Request-ID"),
            user_agent=request.headers.get("User-Agent"),
            success=True,
            occurred_at=datetime.now(UTC),
        )
        session.add(audit)
        await session.commit()
        # From this point, audit log is immutable forever
        ```

    Security Considerations:
        - State blobs MUST be sanitized (app layer strips passwords, tokens)
        - IP address enables geographic tracking and abuse detection
        - Request ID links audit log to other distributed system logs
        - Immutability at database level (defense in depth)
        - Even if application is compromised, audit trail cannot be tampered with

    Performance:
        - Indexes optimize common queries:
            - actor_id: "What did user X do?"
            - (resource_type, resource_id): "What happened to this asset?"
            - occurred_at DESC: "What's the latest activity?"
        - JSONB is queryable and indexable (GIN indexes possible)
        - Unique constraint prevents accidental duplicates

    Future Considerations (E4+):
        - Repository layer: AuditLogRepository with create() and query() methods only
        - Service layer: AuditLogService to publish audit events from app logic
        - API layer: AuditLogRoute to expose query endpoints (admin-only)
        - Retention: Compliance automation for archival/deletion policies
        - Streaming: Real-time audit log streaming to SIEM systems

    Traces to: 04-Database-Design §11 (Audit Strategy, immutability)
    Traces to: 08-Security-Architecture §6 (audit trail integrity)
    Traces to: 22-Engineering-Backlog E3.T8 (AuditLog ORM model task)
    """

    __tablename__ = "audit_logs"

    # Actor: WHO performed the action
    # Nullable for system-initiated operations (cleanup jobs, retries)
    actor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment=(
            "Who performed the action (FK to users.id, nullable for "
            "system actions)"
        ),
    )

    # Actor's role at time of action (snapshot for audit trail)
    # Captured at insert time; later role changes don't affect this record
    # Non-nullable: always record the role context
    actor_role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Role of actor at time of action (captured snapshot)",
    )

    # Action type: WHAT operation was performed
    # Examples: "CREATE_ASSET", "UPDATE_REPORT", "DELETE_ANALYSIS"
    # Standardized by application layer (use constants for action types)
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Operation type (e.g., CREATE_ASSET, DELETE_REPORT)",
    )

    # Resource type: WHAT entity was affected
    # Examples: "DigitalAsset", "Report", "Analysis", "User"
    # Standardized by application layer
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Entity type affected (e.g., DigitalAsset, Report)",
    )

    # Resource ID: Identifies the affected entity
    # UUID of the entity (asset ID, report ID, user ID, etc.)
    # Combined with resource_type to answer: "What happened to this entity?"
    resource_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="ID of the entity that was affected",
    )

    # Before state: Full entity snapshot BEFORE operation
    # JSONB type: queryable, indexable, flexible schema
    # Null for create operations (no "before" state)
    # Null for system-level operations without full entity context
    # Application layer: MUST sanitize (strip passwords, tokens, PII)
    before_state: Mapped[dict[str, object] | None] = mapped_column(
        JSON,  # JSON type in SQLAlchemy dialects.postgresql maps to JSONB
        nullable=True,
        comment="Entity state before operation (JSONB, null for creates)",
    )

    # After state: Full entity snapshot AFTER operation
    # JSONB type: queryable, indexable, flexible schema
    # Null for delete operations (entity deleted, no "after" state)
    # Null for system-level operations without full entity context
    # Application layer: MUST sanitize (strip passwords, tokens, PII)
    after_state: Mapped[dict[str, object] | None] = mapped_column(
        JSON,  # JSON type in SQLAlchemy dialects.postgresql maps to JSONB
        nullable=True,
        comment="Entity state after operation (JSONB, null for deletes)",
    )

    # Client IP address: WHERE did the request come from?
    # INET type: PostgreSQL network address type, supports CIDR notation
    # Extracted from X-Forwarded-For header (if behind proxy) or request.client.host
    # Nullable: system operations may have no IP
    # Used for: geographic tracking, abuse detection, forensics
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        comment=(
            "Client IP address (INET type, from X-Forwarded-For or "
            "request.client.host)"
        ),
    )

    # Request ID: Correlation ID for distributed tracing
    # Links this audit log to application logs, spans, and other telemetry
    # Generated by middleware or application (e.g., via uuid.uuid4())
    # Enables: "Trace the full request across all systems"
    request_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Request correlation ID for distributed tracing",
    )

    # Client context: HTTP User-Agent header
    # Browser/client information for context
    # Used for: detecting suspicious clients, understanding access patterns
    # Nullable: system operations may have no User-Agent
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Client HTTP User-Agent header for context",
    )

    # Operation success: Did the operation succeed or fail?
    # true = operation completed successfully
    # false = operation failed (see failure_reason for error message)
    # Used for: compliance (failed operations may indicate attack attempts)
    success: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default="true",
        comment="Operation success flag (false means see failure_reason for error)",
    )

    # Failure reason: Error message if success=false
    # Null if success=true
    # Examples: "Permission denied", "Resource not found", "Invalid input"
    # Used for: debugging and compliance analysis
    failure_reason: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Error message if success=false",
    )

    # Operation timestamp: WHEN did the operation occur?
    # UTC timestamp (TIMESTAMPTZ in PostgreSQL)
    # Server-side default: now() (database generates, not application)
    # This is the authoritative operation time (separate from created_at)
    # Most queries use occurred_at, not created_at
    # Rationale: Prevents timezone confusion and clock skew in audit trails
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Server timestamp of operation (UTC)",
    )

    # Table-level constraints and indexes
    __table_args__ = (
        # Unique constraint: prevent duplicate audits
        # (actor_id, resource_id, occurred_at) uniqueness enforced
        # Same actor + same resource + same microsecond = same operation
        # Handles race conditions at database level
        # Traces to: 04-Database-Design §11 (immutability constraints)
        UniqueConstraint(
            "actor_id",
            "resource_id",
            "occurred_at",
            name="uq_audit_logs_actor_resource_time",
        ),
        # Composite index: Query by resource
        # Enable efficient filtering: "What happened to this asset?"
        # resource_type often filtered by (asset, report, analysis, user)
        # resource_id identifies the specific entity
        Index(
            "ix_audit_logs_resource",
            "resource_type",
            "resource_id",
        ),
        # Index for chronological queries
        # DESC order: efficient for "latest first" queries
        # Enable efficient filtering: "What's the most recent activity?"
        Index(
            "ix_audit_logs_occurred_at",
            "occurred_at",
            postgresql_ops={"occurred_at": "DESC"},
        ),
        # actor_id index created by foreign key constraint, but explicit for clarity
        # Enable efficient filtering: "What did user X do?"
        # Already indexed by ForeignKey, but explicit index optimizes queries
    )

    def __repr__(self) -> str:
        """
        String representation for debugging.

        Returns useful audit context WITHOUT exposing sensitive fields:
        - Includes: action, actor_id, resource, occurred_at
        - Excludes: before_state, after_state (could contain sensitive data)
        - Excludes: ip_address, user_agent, request_id (could enable tracking)
        - Excludes: failure_reason (could leak security details)

        Example:
            '<AuditLog action=CREATE_ASSET actor=550e8400 '
            'resource=DigitalAsset:660e8400>'

        Returns:
            String representation for debugging (safe to log)
        """
        # Truncate actor and resource IDs to first 8 chars for readability
        actor_short = str(self.actor_id)[:8] if self.actor_id else "system"
        resource_short = str(self.resource_id)[:8] if self.resource_id else "?"

        return (
            f"<AuditLog "
            f"action={self.action} "
            f"actor={actor_short} "
            f"resource={self.resource_type}:{resource_short} "
            f"success={self.success}>"
        )
