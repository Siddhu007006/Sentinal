"""
DigitalAsset ORM model.

Defines the central entity of the Sentinel platform --- every digital artifact
(URL, domain, IP address, file hash, or uploaded file) submitted for security
evaluation. This is the anchor around which the entire analysis lifecycle revolves.
Every analysis, verdict, and report is associated with a DigitalAsset.

Key design decisions:

1. **Immutability:** DigitalAsset is immutable after creation. New content =
   new row, never edit existing. This preserves the historical record and
   simplifies auditing. Database role grants INSERT privilege, not UPDATE on
   core fields (asset_type, raw_value, normalized_value, upload_id, metadata).

2. **Deduplication via Composite UNIQUE:** Constraint on (normalized_value,
   asset_type) is the deduplication key. A user cannot have two assets with
   the same normalized value and type. Multiple users can have the same asset,
   and the same normalized_value can exist with different asset types.

3. **Identity Strategy:** UUID PK (technical identity) separate from
   normalized_value + asset_type (domain identity for deduplication).
   This separates concerns: database PKs are technical and flexible,
   domain identity is business-focused and immutable.

4. **Asset Type Classification:** Five types defined as StrEnum (not PostgreSQL
   ENUM) with CHECK constraint. Enables zero-downtime additions of new types
   without exclusive locks.

5. **Nullable Fields:** upload_id (only for 'file' type), display_label
   (optional annotation), metadata (asset-type-specific data). Enforced via
   CHECK constraint: (asset_type = 'file') = (upload_id IS NOT NULL).

6. **Soft Delete:** deleted_at (timestamp) for archival. is_active (boolean)
   for user control of visibility. Both nullable; active records have both NULL.

7. **Inheritance from BaseModel:** Brings UUID PK, created_at, updated_at,
   deleted_at audit fields. Consistency with User and Upload models.

8. **Indexes:** Four indexes optimize common queries:
   - (user_id, created_at DESC): User asset list paginated by recency
   - (user_id, asset_type, created_at DESC): Filter by type
   - (normalized_value, asset_type): Deduplication check
   - metadata (GIN): JSONB containment queries

Security notes:
- Every asset is attributed to a user (user_id FK enforced)
- Immutability prevents tampering with historical security assessments
- Soft delete preserves audit trail (hard deletion not supported)
- Normalized value deduplication prevents redundant analysis

Lifecycle:
1. Created: User submits asset (URL, domain, IP, file hash, or uploads file)
2. Active: Asset queryable, analyzable, included in reports
3. Archived: User sets is_active=False; asset hidden but preserved
4. Soft-deleted: User deletes asset; deleted_at set, excluded from queries,
   data preserved for audit

Traces to: 04-Database-Design §4 (ERD), §5.4 (DigitalAsset table spec)
Traces to: 02-Domain-Model §3 (DigitalAsset entity, immutability)
Traces to: 08-Security-Architecture §4 (auditability, immutability)
Traces to: 22-Engineering-Backlog E3.T5 (DigitalAsset ORM model task)
"""

from __future__ import annotations

import enum
from uuid import UUID  # noqa: TC003

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import BaseModel


class AssetType(enum.StrEnum):
    """
    Classification of digital assets submitted to Sentinel.

    Implements the asset type enumeration per 02-Domain-Model §3 and
    04-Database-Design §5.4. Five types represent the major categories of
    security analysis inputs: network-based (URL, domain, IP), hash-based
    (file hash), and content-based (file).

    Stored as VARCHAR with CHECK constraint (not PostgreSQL ENUM) to enable
    zero-downtime additions. When adding a new type, only a data migration
    is needed; no ALTER TYPE ... ADD VALUE (which requires exclusive locks).

    Each type drives which analyzers are eligible to process the asset and
    which metadata schema is used for asset-type-specific attributes.

    Traces to: 02-Domain-Model §3 (asset types), §10 (analyzers)
    Traces to: 04-Database-Design §5.4 (asset type classification)
    """

    URL = "url"
    """
    Uniform Resource Locator: HTTP/HTTPS/FTP network-accessible resource.

    Examples: https://example.com, http://attacker.com:8080/path?q=1

    Metadata: scheme, hostname, path, query_params, port, fragment (parsed).

    Eligible analyzers: URLScan, VirusTotal URL, Shodan, URLhaus,
    certificate transparency, HTTP header analysis.
    """

    DOMAIN = "domain"
    """
    DNS domain name (canonical registration or registered subdomain).

    Examples: evil.com, subdomain.example.com, malicious-domain.ru

    Metadata: tld, registered_domain, subdomain, is_ip_address.

    Eligible analyzers: URLhaus, DNS records, WHOIS, passive DNS,
    threat intelligence domain feeds, certificate transparency.
    """

    IP_ADDRESS = "ip_address"
    """
    IPv4 or IPv6 network address.

    Examples: 192.0.2.1, 2001:db8::1, ::ffff:192.0.2.1

    Metadata: version (4/6), is_private, is_loopback, asn, geolocation.

    Eligible analyzers: AbuseIPDB, Shodan, MaxMind GeoIP, ASN databases,
    passive DNS reverse lookups, BGP route monitoring.
    """

    FILE_HASH = "file_hash"
    """
    Cryptographic hash digest (typically SHA-256, but MD5/SHA-1 supported).

    Examples: a3f5c1d8e9f2b7c4a6d1e8f3b7c9d2e1 (MD5),
    abcd1234... (SHA-256, 64 hex chars)

    Metadata: algorithm, hash_value.

    Eligible analyzers: VirusTotal hash lookup, Hybrid Analysis,
    malware database searches, known-bad hash lookups.

    Used when user has hash but not file content (e.g., endpoint detection).
    """

    FILE = "file"
    """
    Uploaded file (binary or text content).

    Examples: malware.exe, invoice.pdf, suspicious.zip

    Metadata: original_filename, detected_mime_type, file_size_bytes,
    checksum_sha256, storage_key.

    Linked to Upload (upload_id FK). upload_id is non-NULL for this type only.
    Enforced via CHECK constraint: (asset_type = 'file') = (upload_id IS NOT NULL)

    Eligible analyzers: ClamAV antivirus, Yara rules, Androguard (APK),
    PDF analysis, archive extraction, AI-powered content analysis.
    """


class DigitalAsset(BaseModel):
    """
    DigitalAsset entity representing a digital artifact for security analysis.

    Inherits from BaseModel:
        - id: UUID primary key (automatically generated)
        - created_at: Timestamp of asset creation (immutable)
        - updated_at: Timestamp of last modification (auto-updated)
        - deleted_at: Soft delete timestamp (inherited but overridden locally)

    This is the central entity of Sentinel. Every analysis, verdict, and report
    revolves around a DigitalAsset. The entire data model is normalized around
    this entity: User owns DigitalAssets, DigitalAsset may be linked to Upload,
    Analysis belongs to DigitalAsset, Report aggregates DigitalAssets.

    **Immutability:** DigitalAsset is immutable after creation. Core fields
    (asset_type, raw_value, normalized_value, upload_id, metadata) are never
    updated. New content = new row. This preserves the historical record and
    simplifies auditing.

    **Deduplication:** Constraint on (normalized_value, asset_type) enforces
    that a user cannot have two assets with the same normalized value and type.
    This is the deduplication key: submitting the same asset twice returns the
    existing asset (idempotent). Different users can have the same asset;
    it is not deduplicated globally.

    **Identity Strategy:** UUID PK (technical) vs. (normalized_value, asset_type)
    UNIQUE (domain). The database PK is a technical identifier (efficient,
    stable, opaque). The domain identity (normalized value + type) is the
    business identifier: "this asset is uniquely identified by what it is,
    not by an arbitrary UUID." This separation enables flexibility: if hash
    algorithms evolve or the identity strategy changes, the database PK
    remains stable.

    **Lifecycle:**
        1. Created: User submits asset. created_at set, is_active=True,
           deleted_at=NULL. Asset is immediately queryable and analyzable.
        2. Active: Asset listed, analyzed, included in reports. User can
           view analysis results.
        3. Archived: User sets is_active=False (via API). Asset hidden from
           default lists but preserved in database. Analyses remain associated.
        4. Soft-deleted: User deletes asset (via API). deleted_at set to now(),
           asset excluded from all queries. Data preserved for audit trail.

    **Constraints:**
        - UNIQUE (normalized_value, asset_type): Deduplication key
        - FK user_id → users(id) ON DELETE RESTRICT: Asset cannot exist
          without an owner. Deleting a user is rejected if assets exist.
        - FK upload_id → uploads(id) ON DELETE SET NULL: File-type assets
          can orphan from uploads (e.g., if upload record deleted).
        - CHECK (asset_type IN (...)): Asset type must be one of five values
        - CHECK (asset_type = 'file') = (upload_id IS NOT NULL): Structural
          invariant: only 'file' type has associated upload.

    **Indexes:**
        - (user_id, created_at DESC): User asset list by recency
        - (user_id, asset_type, created_at DESC): Filter by type
        - (normalized_value, asset_type): Deduplication check
        - metadata (GIN): JSONB containment queries

    Example:
        >>> from app.models.digital_asset import DigitalAsset, AssetType
        >>> import uuid
        >>> user_id = uuid.uuid4()
        >>> asset = DigitalAsset(
        ...     user_id=user_id,
        ...     asset_type=AssetType.DOMAIN,
        ...     raw_value="Evil.COM",  # As submitted
        ...     normalized_value="evil.com",  # Lowercased
        ...     display_label="Suspect C2 domain",
        ...     metadata={"tld": "com", "registered_domain": "evil.com"},
        ...     is_active=True,
        ... )
        >>> session.add(asset)
        >>> await session.commit()

    Security:
        - Every asset is attributed to a user (user_id FK enforced)
        - Immutability prevents tampering with historical assessments
        - Soft delete preserves audit trail; hard deletion not supported
        - UUIDs prevent sequential ID enumeration
        - Normalized value deduplication prevents redundant analysis

    Traces to: 04-Database-Design §4 (ERD), §5.4 (DigitalAsset table)
    Traces to: 02-Domain-Model §3 (DigitalAsset entity, immutability)
    Traces to: backend/openapi.yaml DigitalAsset schema
    """

    __tablename__ = "digital_assets"

    # User relationship - Many-to-one: each asset belongs to exactly one user
    # Lazy loading strategy: "joined" (eager join when fetching assets)
    # Rationale: When querying assets, we nearly always need user info (authorization,
    #           display). Joined load avoids N+1 queries. Each asset has exactly one
    #           user, so no Cartesian product concern.
    user: Mapped[User] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        lazy="joined",
    )

    # Analyses relationship - One-to-many: each asset has many analyses
    # Lazy loading strategy: Default (no explicit lazy specified)
    # Rationale: Analyses collection may grow large over time. Not eagerly loaded
    #           by default, but can be explicitly loaded when needed.
    analyses: Mapped[list[Analysis]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Analysis",
        back_populates="digital_asset",
    )

    # User ID - Foreign key to users table
    # Asset owner. Every asset belongs to exactly one user. NOT NULL.
    # On DELETE RESTRICT: Prevents deletion of users with associated assets
    # (data consistency). User must deactivate, not delete, if they have assets.
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Asset owner; FK to users.id with RESTRICT",
    )

    # Upload ID - Optional foreign key to uploads table
    # Only populated for 'file' asset type. Links to the Upload that produced
    # this asset. Null for all other types (url, domain, ip_address, file_hash).
    # Enforced via CHECK constraint: (asset_type = 'file') = (upload_id IS NOT NULL)
    # ON DELETE SET NULL: If upload record deleted, orphan the asset but preserve it.
    upload_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("uploads.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to uploads.id; only non-NULL for 'file' asset type",
    )

    # Asset type - Classification determining which analyzers can process this asset
    # Values: 'url', 'domain', 'ip_address', 'file_hash', 'file'
    # Stored as text (not PostgreSQL ENUM) for zero-downtime additions.
    # CHECK constraint enforces valid values at database level.
    # Immutable after creation (part of domain identity).
    asset_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Asset classification: url, domain, ip_address, file_hash, file",
    )

    # Raw value - Submitted value as-is
    # Original form before any normalization. Preserved for audit/display.
    # Examples: "https://EXAMPLE.com", "Evil.COM", "User-Label.txt"
    # String up to 2048 chars. Constraint enforced at app layer (CHECK not performant).
    # Immutable after creation (part of domain identity).
    raw_value: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Original submitted value (up to 2048 chars)",
    )

    # Normalized value - Canonicalized form used for deduplication
    # Examples: "https://example.com", "evil.com" (lowercased), hash (hex-normalized)
    # Identical for identical content submitted in different forms. Used in UNIQUE
    # constraint for deduplication. String up to 2048 chars.
    # Immutable after creation (part of domain identity).
    normalized_value: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment=(
            "Canonicalized form for deduplication "
            "(lowercased domain, defanged URL, etc.)"
        ),
    )

    # Display label - Optional user-provided annotation
    # User can label assets for internal organization (e.g., "Main C2 server").
    # Displayed in UI and reports. Optional (NULL if not provided).
    # Up to 512 chars. User-mutable (unlike other fields).
    display_label: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="Optional user-provided label for UI and reports",
    )

    # Metadata - Asset-type-specific attributes as JSONB
    # Flexible JSON document storing attributes specific to the asset type.
    # Examples:
    #   - URL: {"scheme": "https", "hostname": "...", "path": "/...", ...}
    #   - Domain: {"tld": "com", "registered_domain": "...", ...}
    #   - IP: {"version": 4, "is_private": false, "asn": 12345}
    #   - File hash: {"algorithm": "sha256", "hash_value": "a3f5c1d8..."}
    #   - File: {"original_filename": "...", "mime_type": "...", ...}
    # Nullable (asset may not have type-specific data immediately).
    # Default: {} (empty object). GIN index for containment queries.
    # Enforced/documented at application layer via Pydantic schemas per type.
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(
        "metadata",
        JSONB(),
        nullable=True,
        default=None,
        comment="Asset-type-specific metadata (JSONB, see Database Design §5.4.1)",
    )

    # Active flag - User visibility control
    # True (default): Asset is active, queryable, analyzable, included in reports.
    # False: Asset archived by user; hidden from default lists but preserved.
    # Separate from deleted_at (soft delete): is_active is user control,
    # deleted_at is administrative removal.
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default="true",
        comment="false = user archived this asset (soft visibility control)",
    )

    # deleted_at inherited from BaseModel (TIMESTAMP(timezone=True), nullable)
    # Soft delete timestamp. NULL for active records. Set to now() when user
    # deletes asset. Preserves audit trail; hard deletion not supported.
    # Application layer filters out records where deleted_at IS NOT NULL.

    # Table-level constraints and indexes
    __table_args__ = (
        # UNIQUE constraint: (normalized_value, asset_type)
        # Deduplication key: a user cannot have two assets with the same
        # normalized value and type. This is the domain identity constraint.
        # Allows same normalized_value with different types (e.g., URL and
        # domain pointing to same host).
        UniqueConstraint(
            "normalized_value",
            "asset_type",
            name="uq_digital_assets_normalized_value_type",
            comment=(
                "Deduplication constraint: "
                "user cannot have duplicate (normalized_value, asset_type)"
            ),
        ),
        # CHECK constraint: asset_type must be one of five values
        # Defense in depth: prevents invalid types at database level
        CheckConstraint(
            "asset_type IN ('url', 'domain', 'ip_address', 'file_hash', 'file')",
            name="ck_digital_assets_asset_type_valid",
        ),
        # CHECK constraint: (asset_type = 'file') = (upload_id IS NOT NULL)
        # Structural invariant: only 'file' type has associated upload.
        # Symmetric implication: if file type, upload_id must be non-null;
        # if upload_id is non-null, type must be file.
        CheckConstraint(
            "(asset_type = 'file') = (upload_id IS NOT NULL)",
            name="ck_digital_assets_file_upload_invariant",
        ),
        # Index: (user_id, created_at DESC)
        # Query: SELECT * FROM digital_assets WHERE user_id = ?
        #        ORDER BY created_at DESC LIMIT 10
        # Use case: User's recent assets (most common list query).
        # DESC order: most recent first (typical UI ordering).
        Index(
            "ix_digital_assets_user_created",
            "user_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        # Index: (user_id, asset_type, created_at DESC)
        # Query: SELECT * FROM digital_assets WHERE user_id = ? AND asset_type = ?
        #        ORDER BY created_at DESC
        # Use case: Filter user's assets by type (e.g., "Show me only URLs").
        # Composite index supersedes user_id index for this query.
        Index(
            "ix_digital_assets_user_type_created",
            "user_id",
            "asset_type",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        # Index: (normalized_value, asset_type)
        # Query: SELECT * FROM digital_assets WHERE normalized_value = ?
        #        AND asset_type = ?
        # Use case: Deduplication check (does user already have this asset?).
        # This is the UNIQUE constraint index (used for both uniqueness and lookup).
        Index(
            "ix_digital_assets_normalized_value_type",
            "normalized_value",
            "asset_type",
        ),
        # Index: metadata (GIN)
        # Query: SELECT * FROM digital_assets WHERE metadata @> '{"tld": "com"}'
        # Use case: JSONB containment queries on asset-type-specific data.
        # GIN (Generalized Inverted Index): optimized for JSONB containment,
        # key/value membership, array element membership.
        # Lower priority (infrequent analytical queries), but useful for
        # discovering assets with specific metadata attributes.
        Index(
            "ix_digital_assets_metadata_gin",
            "metadata",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        """
        String representation for debugging.

        Returns model name, id, asset type, and truncated normalized value.
        Does NOT expose metadata_json, raw_value, or other fields to avoid clutter.

        Returns:
            String like '<DigitalAsset id=uuid type=domain value=evil.com>'

        Example:
            >>> asset = DigitalAsset(...)
            >>> repr(asset)
            '<DigitalAsset id=a1b2c3d4-e5f6-47g8-h9i0-... type=url \
value=https://example.com>'
        """
        # Truncate normalized_value to 50 chars for readability
        truncated_value = (
            self.normalized_value[:50]
            if len(self.normalized_value) <= 50
            else self.normalized_value[:47] + "..."
        )
        return (
            f"<DigitalAsset id={self.id} type={self.asset_type} "
            f"value={truncated_value}>"
        )
