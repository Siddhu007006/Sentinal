"""
DigitalAsset domain entity.

Represents a digital asset in the Sentinel system. This is a domain model
(business logic), not an ORM model. It contains no SQLAlchemy imports or
database-specific code.

Reconciled contract (02-Domain-Model § DigitalAsset + 04-Database-Design
§5.4, reconciled 2026-08-23):

The entity unifies two concerns:

1. Content identity (file / file_hash assets):
   - sha256_hash is the business identity — unique, immutable, and
     ALWAYS computed server-side from the actual received bytes
     (never trusted from the client).
   - mime_type and size_bytes describe the content.
   - storage_key points into object storage; it is assigned later in
     the lifecycle and may be None transiently.

2. Classification / representation (url / domain / ip_address assets):
   - asset_type + raw_value + normalized_value carry the observable
     indicator; identity is per-user (user_id, asset_type,
     normalized_value).

Ownership semantics (explicit decision): DigitalAsset is globally
content-addressed. `user_id` records the originating/first-upload
context only — it is NOT exclusive ownership. When a second user
uploads bytes identical to an existing asset, the upload resolves to
the SAME asset (deduplication). Per-user file visibility arrives with
the E5.T3 Upload rebuild (uploads.digital_asset_id); per-user IOC
ownership is enforced by the (user_id, normalized_value, asset_type)
unique constraint. A separate user↔asset association table remains
the documented alternative if per-user file scoping is needed sooner.

Immutability: the entity is frozen after creation; no field is
modifiable (02-Domain-Model invariant: "the row never changes").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from uuid import UUID


_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

FILE_LIKE_TYPES = ("file", "file_hash")
VALID_ASSET_TYPES = ("url", "domain", "ip_address", "file_hash", "file")


@dataclass(frozen=True, eq=False)
class DigitalAsset:
    """DigitalAsset domain entity (immutable, content-addressed).

    Identity:
    - file / file_hash assets: the SHA-256 content hash (two assets
      with the same hash are the same entity).
    - url / domain / ip_address assets: the per-user tuple
      (user_id, asset_type, normalized_value).

    Invariants (validated at construction):
    - sha256_hash, when present, is 64 lowercase hex characters
    - asset_type is one of: url, domain, ip_address, file_hash, file
    - file/file_hash assets REQUIRE a sha256_hash
    - file assets REQUIRE mime_type and size_bytes
    - size_bytes, when present, is non-negative
    """

    id: UUID
    user_id: UUID
    asset_type: str
    normalized_value: str
    raw_value: str
    display_label: str | None = None
    metadata_json: str | None = None
    is_active: bool = True
    # Content identity (file / file_hash assets)
    sha256_hash: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    storage_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
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
        if self.asset_type not in VALID_ASSET_TYPES:
            valid = ", ".join(VALID_ASSET_TYPES)
            raise ValueError(
                f"Invalid asset_type {self.asset_type!r}. "
                f"Must be one of: {valid}"
            )

        if self.sha256_hash is not None and (
            not isinstance(self.sha256_hash, str)
            or not _SHA256_PATTERN.fullmatch(self.sha256_hash)
        ):
            raise ValueError(
                "sha256_hash must be exactly 64 lowercase hex characters"
            )

        if self.asset_type in FILE_LIKE_TYPES and self.sha256_hash is None:
            raise ValueError(
                f"asset_type {self.asset_type!r} requires a sha256_hash "
                "(content-addressed identity)"
            )

        if self.asset_type == "file":
            if self.mime_type is None:
                raise ValueError("file assets require mime_type")
            if self.size_bytes is None:
                raise ValueError("file assets require size_bytes")

        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")

    @classmethod
    def create_file(
        cls,
        *,
        user_id: UUID,
        sha256_hash: str,
        mime_type: str,
        size_bytes: int,
        raw_value: str,
        id: UUID,  # noqa: A002
        storage_key: str | None = None,
        display_label: str | None = None,
        metadata_json: str | None = None,
        created_at: datetime | None = None,
    ) -> DigitalAsset:
        """Create a content-addressed file asset.

        E5.T2 factory: sha256_hash, mime_type, and size_bytes are
        required inputs; the hash is always the server-computed digest
        of the received bytes, never client-supplied.

        Asset↔upload linkage lives on the Upload side
        (uploads.digital_asset_id, per 02-Domain-Model ERD: one asset
        matched by many uploads).

        Args:
            user_id: Originating (first-upload) user context
            sha256_hash: Server-computed SHA-256 hex digest (64 chars)
            mime_type: Detected MIME type of the content
            size_bytes: Content size in bytes
            raw_value: Original filename
            id: Entity UUID (surrogate key)
            storage_key: Object-storage key (assigned later; optional)
            display_label: Human-readable label (optional)
            metadata_json: Additional metadata as JSON string (optional)
            created_at: Creation timestamp (defaults to now)

        Returns:
            New immutable DigitalAsset

        Raises:
            ValueError: If any invariant is violated
        """
        return cls(
            id=id,
            user_id=user_id,
            asset_type="file",
            normalized_value=sha256_hash,
            raw_value=raw_value,
            display_label=display_label,
            metadata_json=metadata_json,
            sha256_hash=sha256_hash,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            created_at=created_at or datetime.now(tz=UTC),
        )

    @classmethod
    def create_ioc(
        cls,
        *,
        user_id: UUID,
        asset_type: str,
        raw_value: str,
        normalized_value: str,
        id: UUID,  # noqa: A002
        display_label: str | None = None,
        metadata_json: str | None = None,
        created_at: datetime | None = None,
    ) -> DigitalAsset:
        """Create an observable indicator asset (url/domain/ip_address).

        Identity is per-user: (user_id, asset_type, normalized_value).

        Args:
            user_id: Owning user context
            asset_type: One of url, domain, ip_address
            raw_value: Value as submitted
            normalized_value: Normalized form used for deduplication
            id: Entity UUID (surrogate key)
            display_label: Human-readable label (optional)
            metadata_json: Additional metadata as JSON string (optional)
            created_at: Creation timestamp (defaults to now)

        Returns:
            New immutable DigitalAsset

        Raises:
            ValueError: If any invariant is violated
        """
        return cls(
            id=id,
            user_id=user_id,
            asset_type=asset_type,
            normalized_value=normalized_value,
            raw_value=raw_value,
            display_label=display_label,
            metadata_json=metadata_json,
            created_at=created_at or datetime.now(tz=UTC),
        )

    def __eq__(self, other: object) -> bool:
        """Hash-based identity for file assets; tuple identity for IOCs.

        Two file-like assets with the same SHA-256 hash are the same
        entity regardless of surrogate id. IOC assets are the same
        entity when user, type, and normalized value all match.
        """
        if not isinstance(other, DigitalAsset):
            return NotImplemented
        if self.sha256_hash is not None and other.sha256_hash is not None:
            return self.sha256_hash == other.sha256_hash
        return (
            self.user_id == other.user_id
            and self.asset_type == other.asset_type
            and self.normalized_value == other.normalized_value
        )

    def __hash__(self) -> int:
        if self.sha256_hash is not None:
            return hash(self.sha256_hash)
        return hash((self.user_id, self.asset_type, self.normalized_value))
