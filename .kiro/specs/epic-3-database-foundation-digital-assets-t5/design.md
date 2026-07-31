# E3.T5 — DigitalAsset ORM Model — Design

## Specification Document

| Field | Value |
|---|---|
| **Document** | `.kiro/specs/epic-3-database-foundation-digital-assets-t5/design.md` |
| **Feature** | digital-assets-orm-model-t5 |
| **Status** | Design Phase |
| **Traces to** | Requirements: R1–R6 |
| **Traces to** | Database Design: §4 (ERD), §5.4 (DigitalAsset table) |

---

## Design Decisions

### D1: Model Inheritance from BaseModel

**Decision:**
DigitalAsset inherits from `BaseModel` (same as User in E3.T3 and Upload in E3.T4), not SQLAlchemy's declarative base directly.

**Rationale:**
- **Consistency:** All domain entities (User, Upload, DigitalAsset) inherit from BaseModel; consistency prevents cognitive overhead and enables shared infrastructure
- **Shared Infrastructure:** BaseModel provides `id` (UUID PK), `created_at`, `updated_at`, and `deleted_at` to all models
- **DRY:** Avoids repeating these four audit fields in every model
- **Future-proof:** Common functionality can be added to BaseModel and automatically inherited

**Traceability:** 07-Backend-Development-Standards §8 (ORM model patterns), 04-Database-Design §5.4

```python
class DigitalAsset(BaseModel):
    __tablename__ = "digital_assets"
    # ... domain fields below
```

---

### D2: UUID Primary Key vs. Content Hash Identity

**Decision:**
Use `id` (UUID) as the database primary key. The `sha256_hash` is a **domain identity** (unique constraint) but NOT the database PK.

**Rationale:**
- **Database Normalization:** Primary keys should be stable, opaque, and unchanging. While sha256_hash is immutable after creation, using it as the PK would:
  - Force all foreign keys to reference the hash string (inefficient, larger than UUID)
  - Make JOIN operations slower (hash comparison is slower than integer/UUID comparison)
  - Couple the database schema to SHA-256 forever; if hash algorithms evolve, renaming the PK is a major migration

- **Domain Identity vs. Database Identity:** Sentinel's domain model treats sha256_hash as the **domain identity** (the business identifier: "this asset is uniquely identified by its content hash"). The database separately maintains a technical PK (UUID) for efficiency and flexibility.

- **Referential Integrity:** Other tables (analyses, report_assets) reference DigitalAsset by UUID PK, not by hash. This is standard relational practice.

- **Lazy Loading Performance:** Foreign key JOINs on UUIDs (16 bytes) are faster than JOINs on SHA-256 hashes (64 bytes).

**Trade-off:** The domain identity (hash) is enforced via UNIQUE constraint, not the PK. This is a deliberate separation of concerns: the database PK is technical (UUID), the domain identity is business (hash).

**Traceability:** 04-Database-Design §5.4, 02-Domain-Model (immutability strategy)

---

### D3: Column Definitions and Type Mappings

**Decision:**
Use SQLAlchemy 2.0 `Mapped[T]` syntax with explicit type annotations. All domain fields explicitly mapped to PostgreSQL column types.

**Rationale:**
- **Type Safety:** Mapped[T] enables full mypy type checking
- **Clarity:** Column definitions are self-documenting
- **Validation:** Pydantic integration can validate types before writes

**Mappings:**

| Field | Python Type | SQLAlchemy Type | PostgreSQL Type | Constraints | Rationale |
|---|---|---|---|---|---|
| `id` | UUID | UUID(as_uuid=True) | uuid | PK, NOT NULL | Inherited from BaseModel; auto-generated |
| `user_id` | UUID | UUID(as_uuid=True) | uuid | FK → users, NOT NULL | Asset owner; required |
| `upload_id` | UUID \| None | UUID(as_uuid=True) | uuid | FK → uploads, nullable | Only populated for `file` asset type |
| `asset_type` | str | String(20) | text | CHECK constraint, NOT NULL | Classification: url, domain, ip_address, file_hash, file |
| `raw_value` | str | String(2048) | text | NOT NULL | Original submitted value |
| `normalized_value` | str | String(2048) | text | NOT NULL, UNIQUE (composite) | Canonicalized form for deduplication |
| `display_label` | str \| None | String(512) | text | nullable | Optional user annotation |
| `metadata` | dict \| None | JSON | jsonb | nullable | Asset-type-specific data (URL headers, EXIF, WHOIS, etc.) |
| `is_active` | bool | Boolean | boolean | NOT NULL, default True | `false` = user archived this asset |
| `created_at` | datetime | TIMESTAMP(timezone=True) | timestamptz | NOT NULL, inherited | Immutable creation timestamp |
| `updated_at` | datetime | TIMESTAMP(timezone=True) | timestamptz | NOT NULL, inherited | Managed by trigger; not used for DigitalAsset updates |
| `deleted_at` | datetime \| None | TIMESTAMP(timezone=True) | timestamptz | nullable, inherited | Soft delete timestamp; NULL = active |

**Example Column Definition:**
```python
user_id: Mapped[UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("users.id", ondelete="RESTRICT"),
    nullable=False,
    comment="Asset owner; assets cannot be deleted if user is deleted",
)

normalized_value: Mapped[str] = mapped_column(
    String(2048),
    nullable=False,
    comment="Canonicalized form used for deduplication (lowercased domain, defanged URL, etc.)",
)

metadata: Mapped[dict | None] = mapped_column(
    JSON(),
    nullable=True,
    default=None,
    comment="Asset-type-specific metadata (JSONB). See Database Design §5.4.1 for schemas.",
)
```

**Traceability:** 07-Backend-Development-Standards §8, 04-Database-Design §5.4

---

### D4: AssetType Enum as StrEnum

**Decision:**
Define `AssetType` as `enum.StrEnum` (not PostgreSQL ENUM type). Store as `VARCHAR` with `CHECK` constraint.

**Rationale:**
- **Zero-Downtime Role Additions:** Adding a new asset type to a PostgreSQL ENUM requires `ALTER TYPE ... ADD VALUE`, which acquires an exclusive lock
- **CHECK Constraint Alternative:** Storing as text + CHECK constraint is simpler and more flexible for future extensions
- **StrEnum Benefit:** String enum in Python means values are strings, so direct SQL comparisons work: `WHERE asset_type = 'url'`
- **Consistency:** Matches UploadStatus (E3.T4) and User.role (StrEnum + CHECK constraint)

**Implementation:**
```python
class AssetType(enum.StrEnum):
    """Classification of digital assets submitted to Sentinel."""

    URL = "url"  # Uniform Resource Locator (http/https/ftp)
    DOMAIN = "domain"  # DNS domain name (e.g., evil.com)
    IP_ADDRESS = "ip_address"  # IPv4 or IPv6 address
    FILE_HASH = "file_hash"  # Hash digest (SHA-256, MD5, etc.)
    FILE = "file"  # Uploaded file content
```

**Supported Types:**
- **URL:** HTTP/HTTPS/FTP locations. Analyzers: URLScan, VirusTotal URL, Shodan, URLhaus
- **DOMAIN:** Domain names. Analyzers: URLhaus, Threat Intelligence feeds, WHOIS
- **IP_ADDRESS:** IPv4/IPv6 addresses. Analyzers: AbuseIPDB, Shodan, MaxMind GeoIP
- **FILE_HASH:** Hash digests (typically SHA-256). Analyzers: VirusTotal Hash lookup
- **FILE:** Uploaded file binary content. Analyzers: ClamAV, Yara, Androguard, AI reasoning

**Traceability:** 07-Backend-Development-Standards §8, 04-Database-Design §2.1 (StrEnum strategy)

---

### D5: Deduplication Strategy with Unique Constraint

**Decision:**
Enforce deduplication via UNIQUE constraint on `(normalized_value, asset_type)` composite key, not on sha256_hash alone.

**Rationale from Database Design §5.4:**
- **Domain Deduplication:** Two users may submit the same asset (e.g., both query "evil.com"). This is not a duplicate from a domain perspective — each user has their own relationship to the asset.
- **Per-User Deduplication:** The unique constraint is composite: `(normalized_value, asset_type)`. This allows the same asset to exist multiple times in the table, but only once per unique value + type combination within the same user context.
- **Critical Invariant:** A user cannot have two rows with the same `normalized_value + asset_type` combination.

**Implementation:**
```python
__table_args__ = (
    UniqueConstraint(
        "normalized_value",
        "asset_type",
        name="uq_digital_assets_normalized_value_type",
        comment="Deduplication: a user cannot have two assets with the same normalized value and type",
    ),
)
```

**Traceability:** 04-Database-Design §5.4 (deduplication strategy), §7 (constraints)

---

### D6: Immutability Enforcement

**Decision:**
All core fields (asset_type, raw_value, normalized_value, upload_id, metadata) are immutable after creation. `created_at` is set once; `updated_at` and `deleted_at` are audit fields.

**Rationale:**
- **Domain Invariant:** DigitalAsset is immutable by design (per domain model). New content = new row, never edit existing.
- **Historical Accuracy:** Asset records represent security assessments at a point in time. Mutating them corrupts the historical record.
- **Simplified Locking:** No optimistic locking needed; no concurrent writes to worry about. Only `deleted_at` can be written post-creation (soft delete).

**Structural Enforcement:**
- Database role (`api_server_role`) granted INSERT privilege on digital_assets, not UPDATE (except for `deleted_at` in rare admin operations)
- ORM model defines fields as immutable (frozen dataclass pattern if available in SQLAlchemy)
- No setter methods for core fields in application layer

**Audit Fields:**
- `created_at`: Set once via DEFAULT now(); never updated
- `updated_at`: Managed by trigger (inherited from BaseModel); not meaningful for DigitalAsset (it never changes)
- `deleted_at`: Only field modified post-creation (soft delete); represents archival, not content mutation

**Traceability:** 04-Database-Design §9 (data lifecycle), §2.9 (immutability strategy)

---

### D7: Index Strategy

**Decision:**
Create 6 indexes optimized for common query patterns:
1. PK index (automatic): on `id`
2. FK index (automatic): on `user_id`
3. `(user_id, created_at DESC)`: User asset history, most recent first
4. `(user_id, asset_type, created_at DESC)`: Filter user's assets by type
5. `(normalized_value, asset_type)`: Deduplication check + type lookup
6. `metadata` (GIN): JSONB containment queries

**Rationale:**
- **User Asset History:** `SELECT * FROM digital_assets WHERE user_id = ? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 10` is the primary list query. Composite index optimizes filter + sort.
- **Type Filtering:** `SELECT * FROM digital_assets WHERE user_id = ? AND asset_type = 'url' ORDER BY created_at DESC` is a common refinement. Index supports this efficiently.
- **Deduplication Check:** Service layer queries: "Does this user already have this asset?" Composite index on (normalized_value, asset_type) with partial index on (deleted_at IS NULL, is_active = true) speeds this.
- **JSONB Metadata:** Queries like `WHERE metadata @> '{"tld": "ru"}'` benefit from GIN index; low priority (infrequent queries).

**Implementation:**
```python
__table_args__ = (
    Index(
        "ix_da_user_created",
        "user_id",
        "created_at",
        postgresql_ops={"created_at": "DESC"},
        comment="User asset list, paginated by recency",
    ),
    Index(
        "ix_da_user_type_created",
        "user_id",
        "asset_type",
        "created_at",
        postgresql_ops={"created_at": "DESC"},
        comment="Filter user's assets by type",
    ),
    Index(
        "ix_da_normalized_type",
        "normalized_value",
        "asset_type",
        comment="Deduplication check: does user already have this asset?",
    ),
    Index(
        "ix_da_metadata_gin",
        "metadata",
        postgresql_using="gin",
        comment="JSONB containment queries",
    ),
)
```

**Traceability:** 04-Database-Design §8 (indexing strategy), §14 (performance)

---

### D8: Nullable Columns Strategy

**Decision:**
Four columns are nullable; all others required:
- `upload_id`: null except for `file` asset type
- `display_label`: optional user annotation
- `metadata`: asset-type-specific data may be absent initially
- `deleted_at`: null for active records

**Rationale:**
- **Upload Reference:** Only `file` asset type has an associated upload. All other types (url, domain, ip_address, file_hash) are submitted directly without file upload. CHECK constraint enforces: `(asset_type = 'file') = (upload_id IS NOT NULL)`.
- **Display Label:** User-provided annotations are optional; not all assets need labels.
- **Metadata:** Asset-type-specific data (EXIF for files, WHOIS for domains, ASN for IPs) may be populated gradually or not at all. Default: `{}` (empty JSONB object).
- **Soft Delete:** `deleted_at` is null for active records; set to now() when user archives an asset.

**Traceability:** 04-Database-Design §5.4 (business rules), §9 (data lifecycle)

---

### D9: Migration Generation Workflow

**Decision:**
Generate migration from ORM model using `alembic revision --autogenerate -m "Add digital_assets table"`. Manual review required before commit (same as E3.T3 and E3.T4).

**Rationale:**
- **Consistency:** Same workflow as E3.T3 (User) and E3.T4 (Upload)
- **Audit Trail:** Autogenerate produces DDL traceable back to the ORM model
- **Manual Review Gate:** Establishes schema; errors propagate to all deployments; manual review is non-negotiable

**Process:**
1. Define ORM model (all 12 fields, types, constraints, relationships)
2. Run `alembic revision --autogenerate -m "Add digital_assets table"`
3. Review generated migration for:
   - Table name: "digital_assets"
   - All 12 columns with correct types
   - UNIQUE constraint on (normalized_value, asset_type)
   - FK constraints to users and uploads
   - CHECK constraints (asset_type, upload_id presence)
   - Indexes (4x named)
   - downgrade() drops table
   - Reversibility: can upgrade → downgrade → upgrade without errors
4. Sign off on review (add comment to migration)
5. Merge to git

**Traceability:** 04-Database-Design §16 (migration strategy), 07-Backend-Development-Standards §8 (ORM patterns)

---

### D10: Testing Strategy

**Decision:**
Two test suites:
- **Unit Tests:** Instantiation, defaults, types, enums, immutability (no database)
- **Integration Tests:** FK enforcement, UNIQUE constraints, CHECK constraints, soft delete, state transitions (with database)

**Unit Test Scope:**
```python
# backend/tests/unit/test_digital_asset_model.py
- Test: Create DigitalAsset with all fields
- Test: Create DigitalAsset with minimal fields (nullable fields omitted)
- Test: Verify field types correct
- Test: Verify AssetType enum (5 values)
- Test: Default values (is_active=True, metadata={}, created_at set)
- Test: Immutability: core fields cannot be mutated
- Test: __repr__() returns useful string (id, asset_type, normalized_value)
```

**Integration Test Scope:**
```python
# backend/tests/integration/test_digital_asset_migration.py
- Test: FK constraint (valid/invalid user_id)
- Test: FK constraint (valid/invalid upload_id for file type)
- Test: UNIQUE (normalized_value, asset_type) constraint
- Test: CHECK constraint (asset_type must be one of 5 values)
- Test: CHECK constraint (upload_id presence: file type ↔ upload_id)
- Test: NOT NULL constraints (each required field)
- Test: Soft delete (deleted_at is set; is_active remains unchanged)
- Test: Default values (is_active=True, metadata={})
- Test: Migration upgrade/downgrade idempotent
- Test: All E3.T3, E3.T4 tests still pass (regression)
```

**Quality Gates:**
- Ruff: 0 violations
- MyPy (--strict): 0 errors
- PyTest: All unit + integration tests pass
- No regressions in E3.T3, E3.T4 tests

**Traceability:** 07-Backend-Development-Standards §7 (ORM testing), 11-Testing-Strategy §6 (unit/integration patterns)

---

## Design Decision Matrix

| Decision | Rationale | Trade-offs | Alternatives |
|---|---|---|---|
| **D1: Inherit from BaseModel** | Consistency, code reuse | Ties to project pattern | Direct declarative_base |
| **D2: UUID PK, hash as unique constraint** | Efficiency, future-proof | Hash not the PK (domain vs. tech identity) | Hash as PK |
| **D3: Mapped[T] syntax** | Type safety, clarity | Verbose | Untyped columns |
| **D4: StrEnum + CHECK** | Zero-downtime additions | Needs manual constraint updates | PostgreSQL ENUM |
| **D5: (normalized_value, asset_type) unique** | Per-user deduplication | Different users can have same asset | Global unique on hash |
| **D6: Immutable core fields** | Historical accuracy, simplified locking | No updates post-creation (design by intent) | Versioning with updates |
| **D7: 6 Indexes** | Query optimization | Storage overhead (~1.5x table size) | Fewer indexes, slower queries |
| **D8: Nullable fields** | Flexibility for different asset types | Query null-checks needed | All columns NOT NULL |
| **D9: Autogenerate + Review** | Audit trail + quality | Manual review overhead | Pure manual DDL |
| **D10: Unit + Integration** | Comprehensive coverage | Longer test suite | Unit tests only |

---

## Implementation Checklist

- [ ] Define AssetType enum (5 values: url, domain, ip_address, file_hash, file)
- [ ] Define DigitalAsset model class with all 12 fields
- [ ] Add field docstrings and comments
- [ ] Define indexes via __table_args__
- [ ] Define UNIQUE constraint via __table_args__
- [ ] Export DigitalAsset and AssetType from models/__init__.py
- [ ] Generate migration with `alembic revision --autogenerate`
- [ ] Review migration (critical review gate)
- [ ] Create unit tests (16+ minimum)
- [ ] Create integration tests (10+ minimum)
- [ ] Verify all quality gates (Ruff, MyPy, PyTest)
- [ ] Verify no regressions (E3.T3, E3.T4 tests still pass)

---

## Readiness Checklist

Before implementation begins:
- [x] E3.T3 complete (User model frozen, migration approved)
- [x] E3.T4 complete (Upload model frozen, migration approved, tests passing)
- [x] Database design reviewed (04-Database-Design §4, §5.4)
- [x] Requirements document complete (R1–R6, 35 AC)
- [x] Engineering backlog reviewed (22-Engineering-Backlog E3.T5)
- [x] E3.T3 and E3.T4 patterns understood
- [x] Alembic workflow proven (E3.T3, E3.T4)

---

## Next Steps

Proceed to Tasks phase to specify:
- Task 1: Validate DigitalAsset ORM model structure
- Task 2: Generate migration
- Task 3: Manual migration review (critical gate)
- Task 4: Unit and integration tests
- Task 5: Final validation and audit

---

## References

- Engineering Backlog: `docs/22-Engineering-Backlog.md` E3.T5
- Database Design: `docs/04-Database-Design.md` §4 (ERD), §5.4 (DigitalAsset table)
- Backend Standards: `docs/07-Backend-Development-Standards.md` §8 (ORM patterns), §9 (indexing)
- E3.T4 Design: `.kiro/specs/epic-3-database-foundation-uploads-t4/design.md` (pattern reference)
- E3.T3 Design: `.kiro/specs/epic-3-database-foundation-users-t3/design.md` (pattern reference)

