"""
Upload ORM model.

Defines the authoritative registry of all documents (files) ingested into the
Sentinel platform. Every upload represents a single file submission by a user,
tracking its lifecycle from receipt (pending) through processing (validation,
hashing) to terminal state (completed/failed). Uploads may be linked to
DigitalAssets (via checksum matching) or stand alone if validation failed.

Key design decisions:
1. Storage key immutable and unique (S3/MinIO object key; deduplicates at storage level)
2. UploadStatus state machine enforced at domain layer (not database triggers)
3. Checksum SHA-256 populated during processing (null until validation completes)
4. Bidirectional relationship to User (many-to-one; Upload.user joins User efficiently,
   User.uploads lists without Cartesian product)
5. Nullable completed_at and error_message (set only when reaching terminal state)
6. First cross-table FK relationship establishes pattern for subsequent entities

Lifecycle states:
- pending: Upload received, awaiting processing
- processing: Validation, hashing, storage operations in progress
- completed: Terminal state, processing succeeded, DigitalAsset created
- failed: Terminal state, processing failed, error_message populated

Security notes:
- Storage key is sensitive (not exposed in public APIs but needed
  for server-to-server calls)
- File size must be ≥ 0 (CHECK constraint prevents negative sizes)
- User FK ensures every upload is attributed to exactly one user
- Soft delete: If user is soft-deleted (deleted_at set), uploads
  remain for audit trail

State transitions (enforced at domain layer, not database):
- pending → processing (when validation starts)
- pending → failed (if immediate validation fails, e.g., unsupported type)
- processing → completed (if hashing/storage succeeds)
- processing → failed (if hashing/storage fails)
- completed/failed are terminal (no further transitions)

Traces to: 04-Database-Design §4 (ERD), §5.2 (uploads table specification)
Traces to: 02-Domain-Model §4 (Upload entity, state machine)
Traces to: 08-Security-Architecture §4 (auditability, user attribution)
Traces to: 22-Engineering-Backlog E3.T4 (Upload ORM model task)
"""

from __future__ import annotations

import enum
from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import BaseModel


class UploadStatus(enum.StrEnum):
    """
    Upload lifecycle states.

    Implements a state machine for upload processing with clear entry/exit points
    and terminal states. Transitions are enforced at the domain layer (application
    service), not the database (enables complex business logic).

    States:
        PENDING: Upload received, awaiting processing. Transition to PROCESSING
                 when validation begins, or directly to FAILED if immediate
                 validation fails (e.g., unsupported MIME type).

        PROCESSING: Validation, hashing, and storage operations in progress.
                    Checksum is being computed, file integrity verified. Transition
                    to COMPLETED if all checks pass, or FAILED if any check fails.

        COMPLETED: Terminal state. Processing succeeded: checksum computed,
                   file stored, DigitalAsset created. No further transitions.
                   completed_at timestamp set. error_message null.

        FAILED: Terminal state. Processing failed: validation error, storage
                failure, or integrity issue detected. completed_at and error_message
                set. No further transitions. Upload may be deleted by user or
                retained for debugging.

    Valid transition paths:
        - pending → processing: Standard path, validation beginning
        - pending → failed: Immediate validation failure (invalid MIME type, etc.)
        - processing → completed: Validation passed, storage succeeded
        - processing → failed: Validation failed or storage error
        - Terminal states (completed, failed) do not transition further

    Invalid transitions (rejected at domain layer):
        - Backward transitions (completed/failed cannot revert to pending/processing)
        - Sideways transitions (completed → failed, etc.)
        - Skipping states (pending cannot jump to completed without processing)
        - From terminal states (completed/failed are absorbing states)

    Traces to: 02-Domain-Model §4 (state machine), §11 (Upload entity)
    Traces to: 22-Engineering-Backlog E3.T4 (UploadStatus enum)
    """

    PENDING = "pending"
    """
    Upload received, awaiting processing.
    Initial state when upload is accepted by the system.
    """

    PROCESSING = "processing"
    """
    Validation, hashing, and storage operations in progress.
    Intermediate state while file is being processed.
    """

    COMPLETED = "completed"
    """
    Terminal state: processing succeeded, asset created.
    File successfully validated, hashed, stored, and linked to DigitalAsset.
    """

    FAILED = "failed"
    """
    Terminal state: processing failed, error recorded.
    File validation failed, storage error, or integrity issue. See error_message.
    """


class Upload(BaseModel):
    """
    Upload entity representing a document ingested by a user.

    Inherits from BaseModel:
        - id: UUID primary key (automatically generated)
        - created_at: Timestamp of upload receipt (immutable)
        - updated_at: Timestamp of last modification (auto-updated)

    This is a core entity in the asset ingestion pipeline. Every DigitalAsset
    originates from an Upload. Uploads track the full lifecycle from receipt
    through processing to terminal state (success/failure).

    Lifecycle:
        1. Created: Upload instantiated with original_filename, content_type,
                   file_size_bytes. Status = 'pending'. created_at set by database.
        2. Processing: Status transitions to 'processing' when validation begins.
                       checksum_sha256 null (not yet hashed).
        3. Terminal: Status transitions to 'completed' or 'failed'.
                     completed_at and error_message (if failed) populated.
                     No further state changes.

    Deduplication:
        - storage_key: Immutable S3/MinIO key. If two uploads produce the same
                      storage_key, the second is rejected (UNIQUE constraint).
                      Prevents duplicate objects in storage.
        - checksum_sha256: If two uploads produce the same checksum, the second
                          upload is linked to the existing DigitalAsset (no
                          duplicate processing). Deduplication logic in service layer.

    Invariants:
        - Every upload belongs to exactly one user (user_id NOT NULL, FK enforced)
        - storage_key is unique and immutable after creation
        - file_size_bytes >= 0 (CHECK constraint)
        - upload_status is one of (pending, processing, completed, failed)
        - If completed: completed_at is set, error_message is null
        - If failed: completed_at is set, error_message is populated
        - If pending/processing: completed_at is null

    Example:
        >>> from app.models.upload import Upload, UploadStatus
        >>> from datetime import datetime
        >>> from uuid import uuid4
        >>> user_id = uuid4()
        >>> upload = Upload(
        ...     user_id=user_id,
        ...     original_filename="report.pdf",
        ...     storage_key="uploads/2025/07/19/uuid4/report.pdf",
        ...     content_type="application/pdf",
        ...     file_size_bytes=1024576,
        ...     upload_status=UploadStatus.PENDING.value,
        ... )
        >>> session.add(upload)
        >>> await session.commit()
        >>> print(upload.id, upload.created_at, upload.user)

    Security:
        - storage_key is NOT exposed in public APIs (server-to-server only)
        - User attribution enforced via FK (audit trail links uploads to users)
        - File size prevents unbounded storage claims (CHECK >= 0)
        - Soft-deleted users retain their uploads (audit trail preservation)

    Performance:
        - Composite index (user_id, created_at DESC) optimizes "user's recent uploads"
        - UNIQUE storage_key index supports fast deduplication checks
        - Lazy loading on User.uploads (selectin) avoids Cartesian product
        - Eager loading on Upload.user (joined) optimizes typical access pattern

    Traces to: 04-Database-Design §4 (ERD), §5.2 (uploads table)
    Traces to: 02-Domain-Model §4 (Upload entity), §11 (state machine)
    Traces to: backend/openapi.yaml Upload schema
    """

    __tablename__ = "uploads"

    # User relationship - Many-to-one: each upload belongs to exactly one user
    # Lazy loading strategy: "joined" (eager join when fetching uploads)
    # Rationale: When querying uploads, we nearly always need user info (display,
    #           authorization). Joined load avoids N+1 queries. Each upload has
    #           exactly one user, so no Cartesian product concern.
    user: Mapped[User] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="uploads",
        lazy="joined",
    )

    # User ID - Foreign key to users table
    # Every upload belongs to exactly one user. NOT NULL enforced at database.
    # Constraint name auto-generated: fk_uploads_user_id_users
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        comment="Foreign key to users table; every upload belongs to exactly one user",
    )

    # Original filename - As provided by the user during upload
    # Normalized by application layer (may contain path separators, special chars).
    # Stored as-is for display and audit purposes.
    # Max 255 chars: common limit for filesystem filenames across OSes.
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment=(
            "Original filename as provided by user "
            "(normalized, may contain special chars)"
        ),
    )

    # Storage key - Immutable identifier in S3/MinIO
    # Format: uploads/{year}/{month}/{day}/{upload_id}/{filename}
    # Example: uploads/2025/07/19/a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6/report.pdf
    # UNIQUE constraint prevents duplicate keys (immutable once created).
    # Used by DigitalAsset service to retrieve file from storage.
    storage_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True,
        index=True,
        comment="S3/MinIO object key (immutable, unique, max 1024 chars)",
    )

    # Content type - MIME type of the file
    # Standard MIME type: application/pdf, image/png, text/plain, etc.
    # Application layer may normalize (e.g., application/vnd.ms-excel → xlsx).
    # Used to route to appropriate validation/processing handler.
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="MIME type (e.g., application/pdf, image/png)",
    )

    # File size - Number of bytes in the file
    # Captured at upload time (before processing).
    # Used for quota checks, storage estimation, and validation.
    # Must be >= 0 (CHECK constraint prevents negative sizes).
    # Python int → PostgreSQL bigint (supports up to 2^63-1 ≈ 9 exabytes).
    file_size_bytes: Mapped[int] = mapped_column(
        nullable=False,
        comment="File size in bytes (>= 0)",
    )

    # Checksum SHA-256 - Hex-encoded SHA-256 hash of file content
    # Null until validation completes (computed during processing state).
    # 64 characters: SHA-256 hash in hexadecimal (32 bytes x 2 hex chars/byte).
    # Used for deduplication: if checksum matches existing DigitalAsset,
    # link instead of creating duplicate asset.
    # Immutable after population.
    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of file (64-char hex); null until validation completes",
    )

    # Upload status - Lifecycle state of this upload
    # Values: pending (received), processing (in progress),
    #         completed (success), failed (error)
    # Stored as text (not PostgreSQL ENUM) with CHECK constraint
    # for zero-downtime additions.
    # Default: 'pending' (set at database level).
    # Transitions enforced at domain layer (application service).
    upload_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UploadStatus.PENDING.value,
        server_default=f"'{UploadStatus.PENDING.value}'",
        comment="Upload lifecycle state: pending, processing, completed, failed",
    )

    # Completion timestamp - When upload reached terminal state
    # Null while pending or processing.
    # Set when status transitions to completed or failed.
    # Allows answering: "How long did processing take?"
    # (completed_at - created_at).
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment=(
            "When upload reached terminal state (completed/failed); "
            "null if pending/processing"
        ),
    )

    # Table-level constraints and indexes
    __table_args__ = (
        # CHECK constraint: upload_status must be one of the valid values
        # Prevents invalid states at database level (defense in depth).
        CheckConstraint(
            (
                f"upload_status IN ('{UploadStatus.PENDING.value}', "
                f"'{UploadStatus.PROCESSING.value}', "
                f"'{UploadStatus.COMPLETED.value}', '{UploadStatus.FAILED.value}')"
            ),
            name="ck_uploads_upload_status_valid",
        ),
        # CHECK constraint: file_size_bytes >= 0
        # Prevents negative file sizes (nonsensical).
        CheckConstraint(
            "file_size_bytes >= 0",
            name="ck_uploads_file_size_bytes_nonnegative",
        ),
        # Composite index: (user_id, created_at DESC)
        # Optimizes query: SELECT * FROM uploads
        # WHERE user_id = ? ORDER BY created_at DESC LIMIT 10
        # Common use case: "Show user their recent uploads, most recent first"
        # Named ix_uploads_user_created per naming convention.
        Index(
            "ix_uploads_user_created",
            "user_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
    )

    def __repr__(self) -> str:
        """
        String representation for debugging.

        Returns model name, id, user_id, status, and original filename.
        Does NOT expose storage_key or checksum for security.

        Returns:
            String like
            '<Upload id=uuid user_id=uuid status=pending filename=report.pdf>'

        Example:
            >>> upload = Upload(...)
            >>> repr(upload)
            '<Upload id=a1b2c3d4-... user_id=e5f6g7h8-... \
status=pending filename=report.pdf>'
        """
        return (
            f"<Upload id={self.id} user_id={self.user_id} "
            f"status={self.upload_status} filename={self.original_filename}>"
        )
