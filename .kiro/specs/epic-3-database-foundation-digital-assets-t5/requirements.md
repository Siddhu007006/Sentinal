# E3.T5 — DigitalAsset ORM Model — Requirements

## Specification Document

| Field | Value |
|---|---|
| **Document** | `.kiro/specs/epic-3-database-foundation-digital-assets-t5/requirements.md` |
| **Feature** | digital-assets-orm-model-t5 |
| **Status** | Requirements Phase |
| **Traces to** | Engineering Backlog: E3.T5 |
| **Traces to** | Database Design: §4 (ERD), §5.3 (DigitalAsset table) |
| **Traces to** | Domain Model: §3 (DigitalAsset entity) |

---

## Glossary

| Term | Definition |
|---|---|
| **DigitalAsset** | ORM entity representing a unique, immutable piece of content ingested into Sentinel. Identified by its SHA-256 content hash. Links many uploads (deduplicated) and may be associated with multiple analyses. |
| **Content Hash (SHA-256)** | Cryptographic fingerprint of file content computed server-side from actual bytes received. Uniqueness enforced at database level. Never trusted from client. |
| **Asset Type** | Classification of the asset (e.g., url, file, domain, ip) per the Domain Model. Determines which analyzers can process it. |
| **Storage Key** | Reference to the binary file location in object storage (S3/MinIO). Immutable after creation. |
| **Metadata** | Asset-type-specific schema-flexible data stored as JSONB (e.g., HTTP headers for URLs, EXIF for files). |
| **Immutability** | DigitalAsset rows never change after creation. New content = new row with new hash. History is preserved, never rewritten. |
| **Deduplication** | Multiple uploads producing identical content hash reference the same DigitalAsset row. Eliminates redundant storage and analysis. |

---

## Scope Definition

### In Scope — What R1–R6 Require

1. **DigitalAsset ORM Model Definition** (R1)
   - Create `app/models/digital_asset.py`
   - 9 fields per Database Design §5.3
   - Inherit from BaseModel
   - Comprehensive docstrings and field comments
   - Export from `app/models/__init__.py`

2. **Asset Type Definition** (R2)
   - Enum or constants defining valid asset types
   - Supported types: url, file, domain, ip (per Domain Model)
   - Validation enforced at model level

3. **Immutability Enforcement** (R3)
   - All fields except audit timestamps are NOT NULL and immutable
   - No UPDATE operations permitted on core fields
   - New analysis or asset = new row, never edit existing

4. **Constraints and Defaults** (R4)
   - UNIQUE constraint on sha256_hash (deduplication key, domain identity)
   - NOT NULL on required fields: sha256_hash, asset_type, size_bytes, created_at
   - Nullable fields: metadata (JSONB for asset-type-specific data)
   - Defaults: is_active = true, created_at = now()

5. **Initial Alembic Migration** (R5)
   - Generate migration from ORM model
   - File created in backend/migrations/versions/ with YYYYMMDD_HHMM_<rev>_<slug>.py naming
   - Syntax valid (py_compile succeeds)
   - upgrade() creates digital_assets table with all columns, constraints, indexes
   - downgrade() drops table
   - Reversible and idempotent

6. **ORM Model Test Coverage** (R6)
   - Unit tests: instantiation, defaults, field types, asset types, immutability
   - Integration tests: UNIQUE hash constraint, FK relationships, asset lifecycle
   - No regressions in E3.T3 (User), E3.T4 (Upload) tests

---

### Out of Scope — What E3.T5 Does NOT Do

| Item | Why Out of Scope | Future Task |
|---|---|---|
| Analysis service layer | Business logic orchestration belongs to application layer | E5.T4 |
| Upload deduplication logic | Lookup and linking happens at service layer | E5.T2 |
| Asset type validation rules | Type-specific validation belongs to domain/service layer | E5.T5 |
| Metadata schema definition | Asset-type-specific schemas defined by analyzers | E5+ |
| API route handlers | Routes belong to API layer | E4+ |
| Query optimization | Full-text search, analytics queries added later | Phase 2+ |
| Storage key generation | Object storage integration done later | E5.T1 |

---

## Requirements

### R1: DigitalAsset ORM Model Definition

**User Story:**
As an architect, I want a type-safe DigitalAsset ORM model so that the application can track every piece of unique content ingested into the system, deduplicate uploads by content hash, and support diverse asset types (URLs, files, domains, IPs).

#### Acceptance Criteria

1. ✅ **Model File Exists**
   - File: `backend/app/models/digital_asset.py`
   - Syntax valid: `python -m py_compile` succeeds
   - Imports BaseModel from `app.infrastructure.database.base`
   - No circular imports

2. ✅ **All 9 Fields Present with Correct Types**
   - `id` (Mapped[UUID], PK, auto-generated via gen_random_uuid())
   - `sha256_hash` (Mapped[str], NOT NULL, UNIQUE, 64 chars)
   - `asset_type` (Mapped[str], NOT NULL, CHECK constraint: url/file/domain/ip)
   - `raw_value` (Mapped[str], NOT NULL, ≤2048 chars, original raw form)
   - `normalized_value` (Mapped[str], NOT NULL, ≤2048 chars, canonicalized for deduplication)
   - `storage_key` (Mapped[str | None], nullable, S3/MinIO reference, ≤1024 chars)
   - `metadata` (Mapped[dict | None], JSONB nullable, asset-type-specific data)
   - `is_active` (Mapped[bool], NOT NULL, default True)
   - `created_at` (Mapped[datetime], NOT NULL, inherited from BaseModel, DEFAULT now())

3. ✅ **AssetType Enum or Constants**
   - Define valid types: URL, FILE, DOMAIN, IP
   - Each with docstring explaining use case
   - Enum (Str or Int) or module-level constants

4. ✅ **BaseModel Inheritance**
   - `class DigitalAsset(BaseModel):`
   - Inherits `id`, `created_at`, `updated_at` from BaseModel
   - All inherited fields are Mapped with correct types

5. ✅ **Table Name and Metadata**
   - `__tablename__ = "digital_assets"`
   - `__repr__()` method returns useful debugging string (includes id, asset_type, short hash)
   - Does NOT expose metadata in repr

6. ✅ **Comprehensive Documentation**
   - Module docstring (50+ lines): purpose, immutability, deduplication, constraints, traceability
   - Class docstring: DigitalAsset entity purpose, identity strategy (content hash), invariants
   - AssetType docstring: enum purpose, supported types, examples
   - Field docstrings for each column: purpose, constraints, examples

7. ✅ **Export from Models Package**
   - Import in `backend/app/models/__init__.py`: `from app.models.digital_asset import DigitalAsset, AssetType`
   - Test import succeeds: `python -c "from app.models import DigitalAsset, AssetType; print(DigitalAsset)"`

8. ✅ **No Regressions**
   - All E3.T3 (User) tests still pass (≥250 tests)
   - All E3.T4 (Upload) tests still pass
   - E2 tests unaffected

---

### R2: Asset Type Definition with Validation

**User Story:**
As a domain architect, I want AssetType to define and validate the supported content types (URL, file, domain, IP) so that analyzers can route to appropriate handlers and metadata schemas are consistent per asset type.

#### Acceptance Criteria

1. ✅ **Four Asset Types Defined**
   - URL: Uniform Resource Locator (http/https/ftp)
   - FILE: Binary or text file content
   - DOMAIN: DNS domain name
   - IP: IPv4 or IPv6 address

2. ✅ **Type Characteristics Documented**
   - Each type has comments explaining: intended use, example value, analyzers that process it
   - Example raw values: "https://example.com", "malware.bin", "evil.com", "192.0.2.1"

3. ✅ **Validation Enforceable**
   - AssetType can be used in CHECK constraint at database level
   - Values are strings (StrEnum) or constants
   - Comparison works in Python: `if asset.asset_type == AssetType.URL`

4. ✅ **Docstrings Complete**
   - AssetType docstring: explains classification, valid values, purpose
   - Each value has comment: type name, use case, examples

---

### R3: Immutability Enforcement

**User Story:**
As a domain architect, I want DigitalAsset to be immutable after creation so that the historical record is never rewritten and deduplication by content hash remains reliable.

#### Acceptance Criteria

1. ✅ **No UPDATE After Creation**
   - All core fields (hash, type, values, storage_key, metadata) are never modified
   - Database role grants INSERT privilege, not UPDATE on content columns
   - ORM model structure prevents in-place mutation

2. ✅ **Immutability Documented**
   - Class docstring explicitly states: "immutable, no UPDATE"
   - Each field comment notes immutability
   - Example code shows: new content = new row, not edit

3. ✅ **Timestamps Are Audit-Only**
   - `created_at` set once at creation via DEFAULT now()
   - `updated_at` inherited from BaseModel but not used for DigitalAsset
   - No mutation timestamp tracking (not needed for immutable entity)

---

### R4: Constraints, Defaults, Nullable Columns

**User Story:**
As a database architect, I want constraints that enforce immutability and deduplication so that the database itself prevents invalid states (duplicate hash, missing required fields) independent of application logic.

#### Acceptance Criteria

1. ✅ **UNIQUE Constraint**
   - `sha256_hash`: UNIQUE (enforces deduplication; no two assets with identical hash)
   - Constraint named: `uq_digital_assets_sha256_hash`

2. ✅ **NOT NULL Constraints**
   - NOT NULL: sha256_hash, asset_type, raw_value, normalized_value, created_at, is_active
   - Required at database level (prevents silent nulls)

3. ✅ **Nullable Columns**
   - NULLABLE: storage_key (null until object storage integration, future work)
   - NULLABLE: metadata (null unless asset-type-specific data is available)

4. ✅ **Default Values**
   - `is_active`: DEFAULT True (asset is queryable by default)
   - `created_at`: DEFAULT now() (server-side timestamp)
   - All other fields: no default (must be explicitly provided)

5. ✅ **CHECK Constraints**
   - `CHECK (asset_type IN ('url', 'file', 'domain', 'ip'))`
   - `CHECK (sha256_hash ~ '^[a-f0-9]{64}$')` (SHA-256 is 64 hex chars)
   - `CHECK (length(raw_value) > 0 AND length(raw_value) <= 2048)`
   - `CHECK (length(normalized_value) > 0 AND length(normalized_value) <= 2048)`

---

### R5: Initial Alembic Migration

**User Story:**
As a DevOps engineer, I want a generated migration that creates the digital_assets table so that the schema can be versioned, reviewed, and applied to production.

#### Acceptance Criteria

1. ✅ **Migration File Generated**
   - File: `backend/migrations/versions/<YYYYMMDD_HHMM>_<rev>_<slug>.py`
   - Filename example: `20260719_1130_a1b2c3d4_add_digital_assets_table.py`
   - Naming pattern matches specification

2. ✅ **Syntax Valid**
   - `python -m py_compile migrations/versions/<file>.py` → Exit 0
   - Migration can be imported: `from migrations.versions.<file> import upgrade, downgrade`

3. ✅ **upgrade() Function**
   - Creates digital_assets table with all 9 columns
   - Column order: id, sha256_hash, asset_type, raw_value, normalized_value, storage_key, metadata, is_active, created_at, updated_at
   - Types: UUID, text, text, text, text, text, JSONB, boolean, timestamptz, timestamptz
   - Constraints: PK, UNIQUE sha256_hash, NOT NULL (per spec), CHECK (asset_type), CHECK (hash format), indexes

4. ✅ **downgrade() Function**
   - Drops digital_assets table
   - Reverses all changes from upgrade()
   - Is idempotent (can run multiple times safely)

5. ✅ **Metadata Correct**
   - `revision`: Unique revision ID (e.g., `a1b2c3d4`)
   - `down_revision`: Revision ID of previous migration (`85764e04d85a` from E3.T4)
   - `branch_labels`: None (linear history)
   - `depends_on`: None (no extra dependencies)

6. ✅ **Reversible**
   - Downgrade completely reverses upgrade
   - Can upgrade then downgrade then upgrade again without errors (idempotent)

---

### R6: ORM Model and Migration Test Coverage

**User Story:**
As a QA lead, I want comprehensive unit and integration tests so that the DigitalAsset model behavior and database constraints are validated before deployment.

#### Acceptance Criteria

**Unit Tests** (no database required):

1. ✅ **Instantiation Tests**
   - Test: Create DigitalAsset with all fields provided
   - Test: Create DigitalAsset with minimal fields (nullable fields omitted)
   - Test: Verify field types after instantiation

2. ✅ **AssetType Tests**
   - Test: All four AssetType values present (URL, FILE, DOMAIN, IP)
   - Test: Values are strings (not objects)
   - Test: AssetType values compare correctly

3. ✅ **Immutability Tests**
   - Test: DigitalAsset object cannot be mutated after creation
   - Test: hash field is marked as immutable

4. ✅ **Default Value Tests**
   - Test: Default is_active = True
   - Test: created_at field exists and is mapped correctly

**Integration Tests** (with database):

5. ✅ **Unique Hash Constraint** (MOST CRITICAL)
   - Test: Insert asset with unique hash → succeeds
   - Test: Insert second asset with SAME hash → IntegrityError (uniqueness enforced)
   - This is the core deduplication mechanism; must work perfectly

6. ✅ **NOT NULL Constraints**
   - Test: Omit each required field, insert → IntegrityError
   - Test: Fields tested: sha256_hash, asset_type, raw_value, normalized_value, created_at, is_active

7. ✅ **CHECK Constraints**
   - Test: Insert with valid asset_type → succeeds
   - Test: Insert with invalid asset_type → IntegrityError
   - Test: Insert with valid SHA-256 hash (64 hex chars) → succeeds
   - Test: Insert with invalid hash format → IntegrityError
   - Test: Insert with value lengths 1–2048 chars → succeeds
   - Test: Insert with value length > 2048 → IntegrityError

8. ✅ **Nullable Fields**
   - Test: Insert with null storage_key → succeeds
   - Test: Insert with null metadata → succeeds
   - Test: Insert with populated metadata → succeeds

9. ✅ **No Regressions**
   - Test: All E3.T3 (User) tests still pass
   - Test: All E3.T4 (Upload) tests still pass
   - Test: E2 tests unaffected
   - Test: Total test count ≥ 300+ (250+ existing + new DigitalAsset tests)

---

## Acceptance Criteria Summary

| Requirement | Acceptance Criteria Count | Status |
|---|---|---|
| **R1** | 8 | ⏳ Ready for Implementation |
| **R2** | 4 | ⏳ Ready for Implementation |
| **R3** | 3 | ⏳ Ready for Implementation |
| **R4** | 5 | ⏳ Ready for Implementation |
| **R5** | 6 | ⏳ Ready for Implementation |
| **R6** | 9 | ⏳ Ready for Implementation |
| **Total** | **35** | ⏳ Ready for Implementation |

---

## References

- Engineering Backlog: `docs/22-Engineering-Backlog.md` E3.T5
- Database Design: `docs/04-Database-Design.md` §4 (ERD), §5.3 (DigitalAsset table)
- Domain Model: `docs/02-Domain-Model.md` §3 (DigitalAsset entity)
- Backend Standards: `docs/07-Backend-Development-Standards.md` §8 (ORM conventions)
- E3.T4 Spec: `.kiro/specs/epic-3-database-foundation-uploads-t4/requirements.md` (pattern reference)
- E3.T3 Spec: `.kiro/specs/epic-3-database-foundation-users-t3/requirements.md` (pattern reference)

---

## Next Steps

Proceed to Design phase to specify:
- DigitalAsset model inheritance and field mappings
- AssetType implementation strategy
- Immutability enforcement mechanisms
- Index strategy for common queries (hash lookup, type filtering)
- Testing patterns (unit + integration)
