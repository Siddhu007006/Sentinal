"""
Upload domain entity.

Represents a file upload in the Sentinel system. This is a domain model
(business logic), not an ORM model. It contains no SQLAlchemy imports or
database-specific code.

State machine (02-Domain-Model §11 / 22-Engineering-Backlog E5.T3):

    pending ──→ processing ──→ completed
       │             │
       └─────────────┴──→ failed

- pending → processing: processing starts (upload service pipeline)
- pending → failed: abandoned-upload cleanup (E5.T8) rejects stale
  uploads that never started processing
- processing → completed: content stored and hashed; the upload
  resolves to a DigitalAsset (digital_asset_id + checksum set)
- processing → failed: pipeline error
- completed and failed are TERMINAL and immutable: every transition
  method raises on a terminal state

Invariants (validated at construction, mirrored at the database):
- upload_status is one of: pending, processing, completed, failed
- digital_asset_id is NULL until status is completed (asset linkage
  is assigned only by the completing transition)
- checksum_sha256, when present, is 64 lowercase hex characters
- completed_at is set exactly when the upload is in a terminal state
- file_size_bytes is non-negative
- every upload belongs to exactly one user (user_id required)

Relationship direction (E5.T3 decision, per 02-Domain-Model ERD):
the foreign key lives on Uploads (uploads.digital_asset_id →
digital_assets.id). One DigitalAsset is matched by many uploads
(content deduplication); an upload matches at most one asset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from uuid import UUID

_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

PENDING = "pending"
PROCESSING = "processing"
COMPLETED = "completed"
FAILED = "failed"

VALID_UPLOAD_STATUSES = (PENDING, PROCESSING, COMPLETED, FAILED)
TERMINAL_STATUSES = (COMPLETED, FAILED)


class UploadTransitionError(Exception):
    """An invalid upload state transition was attempted.

    Includes any transition out of a terminal state (completed/failed
    are immutable) and transitions that skip required states (e.g.
    pending → completed without processing).
    """


@dataclass
class Upload:
    """Upload domain entity with a lifecycle state machine.

    Transitions return a NEW Upload instance (the entity itself is
    never mutated in place), mirroring the User domain entity style.
    Terminal states reject all further transitions.
    """

    id: UUID
    user_id: UUID
    original_filename: str
    storage_key: str
    content_type: str
    file_size_bytes: int
    upload_status: str
    created_at: datetime
    checksum_sha256: str | None = None
    digital_asset_id: UUID | None = None
    idempotency_key: str | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate all invariants at construction."""
        self.validate()

    def validate(self) -> None:
        """Validate entity invariants.

        Raises:
            ValueError: If any invariant is violated
        """
        if self.upload_status not in VALID_UPLOAD_STATUSES:
            valid = ", ".join(VALID_UPLOAD_STATUSES)
            raise ValueError(
                f"Invalid upload_status {self.upload_status!r}. "
                f"Must be one of: {valid}"
            )

        if not self.user_id:
            raise ValueError("user_id is required (upload ownership)")

        if not self.original_filename or not isinstance(
            self.original_filename, str
        ):
            raise ValueError("original_filename is required")
        if not self.storage_key or not isinstance(self.storage_key, str):
            raise ValueError("storage_key is required")
        if not self.content_type or not isinstance(self.content_type, str):
            raise ValueError("content_type is required")

        if self.file_size_bytes < 0:
            raise ValueError("file_size_bytes must be non-negative")

        if self.checksum_sha256 is not None and (
            not _SHA256_PATTERN.fullmatch(self.checksum_sha256)
        ):
            raise ValueError(
                "checksum_sha256 must be exactly 64 lowercase hex characters"
            )

        # digital_asset_id is NULL until completed (02-Domain-Model
        # invariant; mirrored by DB CHECK
        # ck_uploads_digital_asset_completed).
        if self.digital_asset_id is not None and self.upload_status != COMPLETED:
            raise ValueError(
                "digital_asset_id must be NULL until status is "
                f"'completed' (got status {self.upload_status!r})"
            )

        # completed_at is set exactly on terminal states.
        is_terminal = self.upload_status in TERMINAL_STATUSES
        if is_terminal and self.completed_at is None:
            raise ValueError(
                f"terminal status {self.upload_status!r} requires "
                "completed_at to be set"
            )
        if not is_terminal and self.completed_at is not None:
            raise ValueError(
                f"non-terminal status {self.upload_status!r} must have "
                "completed_at NULL"
            )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        id: UUID,  # noqa: A002
        user_id: UUID,
        original_filename: str,
        storage_key: str,
        content_type: str,
        file_size_bytes: int,
        idempotency_key: str | None = None,
        created_at: datetime | None = None,
    ) -> Upload:
        """Create a new upload in the pending state.

        The pending upload has no checksum and no asset linkage — both
        are assigned by the processing pipeline (E5.T4).

        Args:
            id: Entity UUID
            user_id: Owning user (exactly one per upload)
            original_filename: Filename as submitted
            storage_key: Object-storage key assigned at intake
            content_type: Declared MIME type (verified later by
                magic-byte validation, E5.T5)
            file_size_bytes: Content size in bytes
            idempotency_key: Optional client key; one upload per
                (user, key)
            created_at: Creation timestamp (defaults to now)

        Returns:
            New Upload in state 'pending'

        Raises:
            ValueError: If any invariant is violated
        """
        return cls(
            id=id,
            user_id=user_id,
            original_filename=original_filename,
            storage_key=storage_key,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
            upload_status=PENDING,
            created_at=created_at or datetime.now(tz=UTC),
            idempotency_key=idempotency_key,
        )

    # ------------------------------------------------------------------
    # State machine transitions (each returns a new Upload)
    # ------------------------------------------------------------------

    def _transitioned(
        self,
        *,
        upload_status: str,
        checksum_sha256: str | None = None,
        digital_asset_id: UUID | None = None,
        set_completed_at: bool = False,
    ) -> Upload:
        """Build the next state, preserving identity fields.

        checksum_sha256 and digital_asset_id are only ever assigned by
        complete(); other transitions leave them NULL.
        """
        return Upload(
            id=self.id,
            user_id=self.user_id,
            original_filename=self.original_filename,
            storage_key=self.storage_key,
            content_type=self.content_type,
            file_size_bytes=self.file_size_bytes,
            upload_status=upload_status,
            created_at=self.created_at,
            checksum_sha256=checksum_sha256,
            digital_asset_id=digital_asset_id,
            completed_at=(
                datetime.now(tz=UTC) if set_completed_at else None
            ),
            updated_at=datetime.now(tz=UTC),
            deleted_at=self.deleted_at,
        )

    def _assert_not_terminal(self, operation: str) -> None:
        if self.upload_status in TERMINAL_STATUSES:
            raise UploadTransitionError(
                f"Cannot {operation}: upload is in terminal state "
                f"{self.upload_status!r} (terminal states are immutable)"
            )

    def start_processing(self) -> Upload:
        """Transition pending → processing.

        Returns:
            New Upload in state 'processing'

        Raises:
            UploadTransitionError: If not currently pending
        """
        self._assert_not_terminal("start processing")
        if self.upload_status != PENDING:
            raise UploadTransitionError(
                f"Cannot start processing from state {self.upload_status!r} "
                "(only 'pending' can transition to 'processing')"
            )
        return self._transitioned(upload_status=PROCESSING)

    def complete(
        self,
        *,
        digital_asset_id: UUID,
        checksum_sha256: str,
    ) -> Upload:
        """Transition processing → completed.

        Completion resolves the upload to its DigitalAsset: the
        server-computed content hash and the asset linkage become
        immutable facts of the completed upload.

        Args:
            digital_asset_id: The asset this upload's content resolved
                to (new or existing, per deduplication)
            checksum_sha256: Server-computed SHA-256 hex digest

        Returns:
            New Upload in state 'completed'

        Raises:
            UploadTransitionError: If not currently processing
        """
        self._assert_not_terminal("complete")
        if self.upload_status != PROCESSING:
            raise UploadTransitionError(
                f"Cannot complete from state {self.upload_status!r} "
                "(only 'processing' can transition to 'completed')"
            )
        return self._transitioned(
            upload_status=COMPLETED,
            checksum_sha256=checksum_sha256,
            digital_asset_id=digital_asset_id,
            set_completed_at=True,
        )

    def fail(self) -> Upload:
        """Transition pending|processing → failed.

        Used both for pipeline errors (from processing) and the
        abandoned-upload cleanup job (from pending, E5.T8).

        Returns:
            New Upload in state 'failed'

        Raises:
            UploadTransitionError: If already in a terminal state
        """
        self._assert_not_terminal("fail")
        return self._transitioned(upload_status=FAILED, set_completed_at=True)
