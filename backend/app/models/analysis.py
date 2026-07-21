"""
Analysis ORM model.

Defines the Analysis entity representing a complete security analysis job
lifecycle.

An Analysis represents one invocation of one or more analyzers against one
digital asset. It captures:
- Identity: which asset is being analyzed, who requested it
- Analyzer metadata: which analyzers were applied, at what version
- Execution state: current status (pending, running, completed, failed,
  cancelled)
- Results: threat score, confidence, severity (written once on completion)
- Reasoning: full AI output and extracted threat intelligence (JSON payloads)
- Lifecycle: timestamps for request, start, completion

Key design decisions:

1. **Immutability after completion:** Once an Analysis reaches completed,
   failed, or cancelled (terminal states), verdict fields (threat_score,
   confidence, severity) and reasoning payloads are never modified.
   Re-analysis creates a new Analysis row.

2. **Lazy loading strategy:** Analysis->DigitalAsset and Analysis->User use
   lazy="selectin" (not joined) to accommodate 10M+ row scale. Separate
   SELECT IN queries are more efficient than JOINs for queries that only
   need Analysis fields.

3. **Partial unique index for idempotency:** (digital_asset_id, analyzer_key,
   analyzer_version) is UNIQUE WHERE status='completed'. This enforces
   Domain Model invariant 6: re-running the same analyzer version returns the
   existing Analysis, not a duplicate. Allows multiple pending/failed/
   cancelled for the same triple (permits retries).

4. **Status as TEXT + CHECK:** Not PostgreSQL ENUM, for schema evolution
   flexibility.

5. **JSONB for flexible payloads:** reasoning_payload and enrichment_data
   have flexible schemas (vary by AI model, by enrichment source) and are
   immutable after completion.

6. **Inheritance from BaseModel:** Brings UUID PK, created_at, updated_at
   inherited fields.

Traces to: 04-Database-Design §5.6 (Analysis table spec)
Traces to: 02-Domain-Model §Analysis (entity definition, invariants)
Traces to: 22-Engineering-Backlog E3.T6 (Analysis ORM model task)
"""

from __future__ import annotations

import enum
import uuid  # noqa: TC003 (needed for type hints at runtime)
from datetime import datetime  # noqa: TC003 (needed for type hints at runtime)
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.digital_asset import DigitalAsset
    from app.models.user import User


class AnalysisStatus(str, enum.Enum):  # noqa: UP042
    """
    Lifecycle states for an analysis job.

    Represents the complete lifecycle of an analysis job from initial request
    through terminal completion. Analysis progresses through states: pending
    (queued), running (executing), and then one of three terminal states:
    completed (success), failed (error), or cancelled (user/system cancellation).

    **State Machine Transitions:**

    - pending → running: Worker claims job
    - pending → cancelled: User cancels before pickup
    - running → completed: Analysis succeeded with verdict
    - running → failed: Analysis failed (error details in error_message/code)
    - running → cancelled: User/system cancels during execution
    - completed, failed, cancelled: Terminal (no further transitions)

    **Immutability After Terminal State:**

    Once an Analysis reaches a terminal state, its verdict fields (threat_score,
    confidence, severity) and reasoning payloads (reasoning_payload,
    enrichment_data) are permanently immutable. Re-analysis of the same asset
    with the same analyzer version creates a new Analysis record (enforced by
    partial unique index).

    Stored as TEXT in PostgreSQL with CHECK constraint (not ENUM type) for
    schema evolution flexibility.

    Traces to: 02-Domain-Model §Analysis, 04-Database-Design §5.6
    """

    PENDING = "pending"
    """Queued, awaiting worker pickup."""

    RUNNING = "running"
    """Worker actively processing this analysis."""

    COMPLETED = "completed"
    """Finished successfully with a verdict."""

    FAILED = "failed"
    """Failed with error details in error_message and error_code."""

    CANCELLED = "cancelled"
    """Cancelled before completion."""


class Analysis(BaseModel):
    """
    Analysis entity representing a security analysis job.

    Inherits from BaseModel:
        - id: UUID primary key (automatically generated)
        - created_at: Timestamp of analysis request (immutable)
        - updated_at: Timestamp of last update (auto-updated on status
          changes)

    Structure (7 logical domains):

    **1. IDENTITY** (3 columns + inherited id)
        Identifies the asset and requester
        - id (inherited): UUID primary key
        - digital_asset_id: FK to DigitalAsset (what is being analyzed)
        - requested_by: FK to User (who requested the analysis)
        - created_at (inherited): When analysis was requested

    **2. ANALYZER METADATA** (2 columns)
        Tracks which analyzer and version produced this analysis
        - analyzer_key: Name of analyzer module (e.g.,
          "virustotal_analyzer")
        - analyzer_version: Specific version (e.g., "v2.1.0")

    **3. EXECUTION STATE** (6 columns)
        Tracks job status and execution details
        - status: Current lifecycle state (pending, running, completed,
          failed, cancelled)
        - analyzer_slugs: Array of analyzer identifiers applied
        - retry_count: Number of retry attempts consumed
        - celery_task_id: Celery job correlation ID (for worker
          callbacks)
        - error_message: Human-readable error (populated on failed
          status)
        - error_code: Machine-readable error code (e.g.,
          "ENRICHMENT_TIMEOUT")

    **4. RESULTS** (3 columns)
        Verdict written once on completion, then immutable
        - threat_score: Threat probability [0.0-1.0] or NULL
        - confidence: Confidence in assessment [0.0-1.0] or NULL
        - severity: Derived severity (LOW, MEDIUM, HIGH, CRITICAL) or
          NULL

    **5. JSON PAYLOADS** (2 columns)
        Flexible schemas for reasoning and enrichment data
        - reasoning_payload: Full AI model output (immutable after
          completion)
        - enrichment_data: Extracted threat intelligence from APIs
          (immutable after completion)

    **6. LIFECYCLE TIMESTAMPS** (2 columns)
        Track analysis job progression
        - started_at: When worker picked up the job
        - completed_at: When job reached terminal state

    **Total: 18 explicit columns + 2 inherited (id, created_at) = 20
    ORM fields**

    **Immutability:**
    Verdict fields and reasoning payloads are immutable after status
    reaches completed, failed, or cancelled (terminal states).
    Re-analysis creates a new Analysis row (idempotency via partial
    unique index).

    **Indexes (8 total):**
    - ix_analyses_asset_status: (digital_asset_id, status) - dashboard
    - ix_analyses_asset_latest: (digital_asset_id, created_at DESC) -
      recent analysis
    - ix_analyses_pending: (created_at) WHERE status='pending' - worker
      queue
    - ix_analyses_user_history: (requested_by, created_at DESC) - audit
      trail
    - ix_analyses_celery_task: (celery_task_id) WHERE celery_task_id IS
      NOT NULL - callback
    - ix_analyses_severity_completed: (severity, created_at DESC) WHERE
      status='completed' - dashboard
    - uq_analyses_asset_analyzer_completed: UNIQUE (asset_id,
      analyzer_key, analyzer_version) WHERE status='completed' -
      idempotency

    **Constraints (5 CHECK):**
    - status must be in ('pending', 'running', 'completed', 'failed',
      'cancelled')
    - threat_score must be in [0.0, 1.0] or NULL
    - confidence must be in [0.0, 1.0] or NULL
    - severity must be in ('LOW','MEDIUM','HIGH','CRITICAL') or NULL
    - retry_count must be >= 0
    """

    __tablename__ = "analyses"

    # ========================================================================
    # STEP 1: Class skeleton (done)
    # STEP 2: IDENTITY (3 explicit columns + inherited id, created_at)
    # ========================================================================

    digital_asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("digital_assets.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        doc="FK to DigitalAsset. Asset being analyzed. Immutable after creation.",
    )

    requested_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        doc="FK to User. Who requested this analysis. Immutable. Audit trail.",
    )

    # ========================================================================
    # STEP 3: ANALYZER METADATA (2 columns)
    # ========================================================================

    analyzer_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Analyzer module name (e.g., 'virustotal_analyzer'). "
        "Immutable. Part of idempotency key.",
    )

    analyzer_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Analyzer version (e.g., 'v2.1.0'). Immutable. Paired with "
        "analyzer_key for idempotency.",
    )

    # ========================================================================
    # STEP 4: EXECUTION STATE (6 columns)
    # ========================================================================

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="pending",
        doc="Current lifecycle state: pending, running, completed, "
        "failed, cancelled. Mutable during job.",
    )

    analyzer_slugs: Mapped[list[str]] = mapped_column(
        ARRAY(String, dimensions=1),
        nullable=False,
        doc="Ordered list of analyzer slugs applied. Immutable.",
    )

    retry_count: Mapped[int] = mapped_column(
        nullable=False,
        server_default="0",
        doc="Number of retry attempts consumed. Incremented by worker.",
    )

    celery_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Celery task ID for job correlation. Immutable. Used by worker callbacks.",
    )

    error_message: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        doc="Human-readable error message. Populated on failed status only.",
    )

    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Machine-readable error code (e.g., "
        "ENRICHMENT_TIMEOUT). Populated on failed status.",
    )

    # ========================================================================
    # STEP 5: RESULTS (3 columns, written once on completion, then immutable)
    # ========================================================================

    threat_score: Mapped[float | None] = mapped_column(
        nullable=True,
        doc="Threat probability [0.0-1.0] or NULL before completion. "
        "Immutable once set.",
    )

    confidence: Mapped[float | None] = mapped_column(
        nullable=True,
        doc="Confidence in assessment [0.0-1.0] or NULL before "
        "completion. Immutable once set.",
    )

    severity: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Threat severity (LOW, MEDIUM, HIGH, CRITICAL) or NULL. "
        "Derived from threat_score. Immutable once set.",
    )

    # ========================================================================
    # STEP 6: JSON PAYLOADS (2 columns, immutable after completion)
    # ========================================================================

    reasoning_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Full AI model output including reasoning steps, IOCs, "
        "data gaps, model metadata. Immutable after completion.",
    )

    enrichment_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Extracted threat intelligence from external sources "
        "(VirusTotal, Shodan, etc.). Immutable after completion.",
    )

    # ========================================================================
    # STEP 7: LIFECYCLE TIMESTAMPS (2 columns)
    # ========================================================================

    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        doc="When worker picked up the job. Immutable once set.",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        doc="When job reached terminal state (completed, failed, "
        "cancelled). Immutable once set.",
    )

    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================

    digital_asset: Mapped[DigitalAsset] = relationship(
        "DigitalAsset",
        back_populates="analyses",
        lazy="selectin",
        doc="Related DigitalAsset. Loaded via selectin (separate query) for scale.",
    )

    user: Mapped[User] = relationship(
        "User",
        foreign_keys=[requested_by],
        back_populates="analyses_requested",
        lazy="selectin",
        doc="User who requested this analysis. Loaded via selectin (separate query).",
    )

    # ========================================================================
    # CONSTRAINTS (via __table_args__)
    # ========================================================================

    __table_args__ = (
        # CHECK constraints for domain validation
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_analyses_status",
        ),
        CheckConstraint(
            "threat_score BETWEEN 0.0 AND 1.0 OR threat_score IS NULL",
            name="ck_analyses_threat_score",
        ),
        CheckConstraint(
            "confidence BETWEEN 0.0 AND 1.0 OR confidence IS NULL",
            name="ck_analyses_confidence",
        ),
        CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') OR severity IS NULL",
            name="ck_analyses_severity",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_analyses_retry_count",
        ),
        # Application indexes (8 total, 3 partial, 1 unique partial)
        Index(
            "ix_analyses_asset_status",
            "digital_asset_id",
            "status",
        ),
        Index(
            "ix_analyses_asset_latest",
            "digital_asset_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index(
            "ix_analyses_pending",
            "created_at",
            postgresql_where="status = 'pending'",
        ),
        Index(
            "ix_analyses_user_history",
            "requested_by",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index(
            "ix_analyses_celery_task",
            "celery_task_id",
            postgresql_where="celery_task_id IS NOT NULL",
        ),
        Index(
            "ix_analyses_severity_completed",
            "severity",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
            postgresql_where="status = 'completed'",
        ),
        Index(
            "ix_analyses_asset_analyzer_completed",
            "digital_asset_id",
            "analyzer_key",
            "analyzer_version",
            postgresql_where="status = 'completed'",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        """Return a useful debugging representation."""
        return (
            f"<Analysis id={self.id!r} asset_id={self.digital_asset_id!r} "
            f"status={self.status!r} analyzer={self.analyzer_key!r} "
            f"v{self.analyzer_version!r}>"
        )
