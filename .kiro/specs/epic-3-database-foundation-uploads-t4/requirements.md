# E3.T4 — Upload ORM Model — Requirements

## Specification Document

| Field | Value |
|---|---|
| **Document** | `.kiro/specs/epic-3-database-foundation-uploads-t4/requirements.md` |
| **Feature** | uploads-orm-model-t4 |
| **Status** | Requirements Phase |
| **Traces to** | Engineering Backlog: E3.T4 |
| **Traces to** | Database Design: §4 (ERD), §5.2 (Upload table) |
| **Traces to** | Domain Model: §4 (Upload entity) |

---

## Glossary

| Term | Definition |
|---|---|
| **Upload** | ORM entity representing a document (file) ingested by a user. Links a user, an original file, and optionally a digital asset. Includes lifecycle state and metadata. |
| **Storage Key** | Unique identifier for the file in object storage (S3/MinIO). Immutable after creation. |
| **Upload Status** | Lifecycle state of an upload: pending (received, awaiting processing) → processing (being validated/hashed) → completed (asset created) or failed (validation error). Terminal states: completed, failed. |
| **Checksum** | SHA-256 hash of file content. Used for deduplication: if an upload produces a checksum matching an existing DigitalAsset, the assets are linked (not duplicated). |
| **Idempotency Key** | Optional unique identifier for upload requests. Prevents duplicate uploads if the same file is submitted multiple times (e.g., due to network retry). |
| **Completed Timestamp** | When the upload transitioned to completed or failed state. Null while pending or processing. |
| **FK (Foreign Key)** | Database constraint enforcing referential integrity. An upload must reference an existing user; deleting a user cascades to uploads (per business rules). |

---

## Scope Definition

### In Scope — What R1–R5 Require

1. **Upload ORM Model Definition** (R1)
   - Create `app/models/upload.py`
   - 10 fields per Database Design §5.2
   - Inherit from BaseModel
   - Comprehensive docstrings and field comments
   - Export from `app/models/__init__.py`

2. **UploadStatus Enum** (R2)
   - Four values: pending, processing, completed, failed
   - StrEnum (string-based for CHECK constraint)
   - Docstrings for each state

3. **Foreign Key to Users** (R3)
   - `user_id` column references users.id
   - NOT NULL constraint (every upload belongs to a user)
   - Cascade delete NOT used (soft delete preferred; see R5)
   - FK enforced at database level

4. **Constraints and Defaults** (R4)
   - UNIQUE constraint on storage_key (immutable object storage key)
   - UNIQUE constraint on idempotency_key (allows null; deduplicates retries)
   - NOT NULL on required fields: user_id, original_filename, storage_key, content_type, file_size_bytes, upload_status, created_at
   - Nullable fields: checksum_sha256, completed_at, error_message, idempotency_key
   - Defaults: upload_status = 'pending', created_at = now()

5. **Initial Alembic Migration** (R5)
   - Generate migration from ORM model
   - File created in backend/migrations/versions/ with YYYYMMDD_HHMM_<rev>_<slug>.py naming
   - Syntax valid (py_compile succeeds)
   - upgrade() creates uploads table with all columns, constraints, indexes
   - downgrade() drops table
   - Reversible and idempotent

6. **ORM Model Test Coverage** (R6)
   - Unit tests: instantiation, defaults, field types, enums, relationships
   - Integration tests: FK enforcement, UNIQUE constraints, state transitions
   - No regressions in E3.T1, E2 tests

---

### Out of Scope — What E3.T4 Does NOT Do

| Item | Why Out of Scope | Future Task |
|---|---|---|
| Upload service layer | Business logic orchestration belongs to application layer | E5.T4 |
| File streaming | Infrastructure concern (S3/MinIO integration) | E5.T1 |
| File validation | Validation logic belongs to domain/application layer | E5.T5 |
| API route handlers | Routes belong to API layer | E5.T6 |
| Soft delete implementation | ORM model only; soft delete applied during maintenance | Future work |
| Digital asset linking | Upload → DigitalAsset relationship created by service layer | E5.T4 |

---

## Requirements

### R1: Upload ORM Model Definition

**User Story:**
As an architect, I want a type-safe Upload ORM model so that the application can track every document ingested by users, manage its lifecycle, and link it to the resulting DigitalAsset.

#### Acceptance Criteria

1. ✅ **Model File Exists**
   - File: `backend/app/models/upload.py`
   - Syntax valid: `python -m py_compile` succeeds
   - Imports BaseModel from `app.infrastructure.database.base`
   - No circular imports

2. ✅ **All 10 Fields Present with Correct Types**
   - `id` (Mapped[UUID], PK, auto-generated via gen_random_uuid())
   - `user_id` (Mapped[UUID], NOT NULL, FK → users.id)
   - `original_filename` (Mapped[str], NOT NULL, ≤255 chars)
   - `storage_key` (Mapped[str], NOT NULL, UNIQUE, ≤1024 chars)
   - `content_type` (Mapped[str], NOT NULL, e.g., "application/pdf", ≤100 chars)
   - `file_size_bytes` (Mapped[int], NOT NULL, ≥0)
   - `checksum_sha256` (Mapped[str | None], nullable, 64 chars when present)
   - `upload_status` (Mapped[str], NOT NULL, CHECK constraint: pending/processing/completed/failed, default 'pending')
   - `created_at` (Mapped[datetime], NOT NULL, inherited from BaseModel, DEFAULT now())
   - `completed_at` (Mapped[datetime | None], nullable, set when status becomes terminal)

3. ✅ **UploadStatus Enum Defined**
   - Class: `UploadStatus(enum.StrEnum)`
   - Values: PENDING = "pending", PROCESSING = "processing", COMPLETED = "completed", FAILED = "failed"
   - Each value has a docstring explaining the state
   - Docstring for enum explaining the state machine

4. ✅ **BaseModel Inheritance**
   - `class Upload(BaseModel):`
   - Inherits `id`, `created_at`, `updated_at` from BaseModel
   - All inherited fields are Mapped with correct types

5. ✅ **Table Name and Metadata**
   - `__tablename__ = "uploads"`
   - `__repr__()` method returns useful debugging string (includes id, user_id, status, filename)
   - Does NOT expose sensitive data in repr

6. ✅ **User Relationship**
   - Relationship property (not a bare FK column) linking to User entity
   - Type: `Mapped["User"]` with back_populates for bidirectional access
   - Lazy loading: "joined" or "selectin" (per ORM optimization)

7. ✅ **Comprehensive Documentation**
   - Module docstring (45+ lines): purpose, lifecycle, constraints, traceability
   - Class docstring: Upload entity purpose, state machine, invariants
   - UploadStatus docstring: enum purpose, state transitions, valid paths
   - Field docstrings for each column: purpose, constraints, examples

8. ✅ **Export from Models Package**
   - Import in `backend/app/models/__init__.py`: `from app.models.upload import Upload, UploadStatus`
   - Test import succeeds: `python -c "from app.models import Upload, UploadStatus; print(Upload)"`

9. ✅ **No Regressions**
   - All E3.T1 tests still pass (≥250 tests)
   - All E2 tests still pass
   - User model and relationships unaffected

---

### R2: Upload Status Enum with State Validation

**User Story:**
As a domain architect, I want an UploadStatus enum that enforces valid state transitions so that uploads cannot transition to invalid states (e.g., from completed to failed).

#### Acceptance Criteria

1. ✅ **Four States Defined**
   - PENDING: Upload received, awaiting processing
   - PROCESSING: Validation, hashing, storage in progress
   - COMPLETED: Processing succeeded, DigitalAsset created
   - FAILED: Processing failed, error_message populated

2. ✅ **State Transitions Documented**
   - Valid paths:
     - pending → processing
     - pending → failed (invalid file)
     - processing → completed
     - processing → failed
   - Invalid paths (enforced in domain layer, not ORM):
     - Cannot move backward (completed/failed are terminal)
     - Cannot skip states (pending must go through processing)

3. ✅ **StrEnum Implementation**
   - Values are strings (e.g., "pending") for SQL CHECK constraint
   - Can be used directly in comparisons: `if upload.status == UploadStatus.COMPLETED`

4. ✅ **Docstrings Complete**
   - Enum docstring: explains state machine and valid transitions
   - Each value has comment: meaning, when transition occurs, next states

---

### R3: Foreign Key Relationship to Users

**User Story:**
As a data architect, I want a FK constraint linking Upload to User so that the database enforces referential integrity and prevents orphaned uploads.

#### Acceptance Criteria

1. ✅ **Foreign Key Column**
   - Column: `user_id` (Mapped[UUID], NOT NULL)
   - References: `users.id`
   - Constraint name: `fk_uploads_user_id` (naming convention)

2. ✅ **Constraint Enforcement**
   - Insert upload with non-existent user_id → IntegrityError
   - Attempting to delete a user with uploads → handled per business rules (soft delete, cascade, or error)

3. ✅ **Relationship Mapped**
   - SQLAlchemy Relationship: `user: Mapped["User"]`
   - back_populates: User has reverse relationship to uploads
   - Lazy loading: "joined" (optimize common case of fetching upload + user)

4. ✅ **No Orphaned Uploads**
   - Every upload in production has a valid user_id
   - Tests verify FK constraint blocks invalid references

---

### R4: Constraints, Defaults, Nullable Columns

**User Story:**
As a database architect, I want constraints and defaults that enforce data integrity so that invalid states cannot be inserted (UNIQUE storage_key, nullable idempotency_key for deduplication retries).

#### Acceptance Criteria

1. ✅ **UNIQUE Constraints**
   - `storage_key`: UNIQUE (immutable object storage key; no duplicate keys allowed)
   - `idempotency_key`: UNIQUE but NULLABLE (allows multiple uploads with null idempotency_key; deduplicates non-null keys)

2. ✅ **NOT NULL Constraints**
   - NOT NULL: user_id, original_filename, storage_key, content_type, file_size_bytes, upload_status, created_at
   - Required at database level (prevents silent nulls)

3. ✅ **Nullable Columns**
   - NULLABLE: checksum_sha256 (null until validation complete)
   - NULLABLE: completed_at (null until terminal state reached)
   - NULLABLE: error_message (null unless status = failed)
   - NULLABLE: idempotency_key (null for non-retried uploads)

4. ✅ **Default Values**
   - `upload_status`: DEFAULT 'pending' (server-side)
   - `created_at`: DEFAULT now() (server-side timestamp)
   - All other fields: no default (must be explicitly provided)

5. ✅ **CHECK Constraints**
   - `CHECK (upload_status IN ('pending', 'processing', 'completed', 'failed'))`
   - `CHECK (file_size_bytes >= 0)` (no negative file sizes)

---

### R5: Initial Alembic Migration (Manually Reviewed)

**User Story:**
As a DevOps engineer, I want a generated migration that creates the uploads table so that the schema can be versioned, reviewed, and applied to production.

#### Acceptance Criteria

1. ✅ **Migration File Generated**
   - File: `backend/migrations/versions/<YYYYMMDD_HHMM>_<rev>_<slug>.py`
   - Filename example: `20260719_1130_a1b2c3d4_add_uploads_table.py`
   - Naming pattern matches specification

2. ✅ **Syntax Valid**
   - `python -m py_compile migrations/versions/<file>.py` → Exit 0
   - Migration can be imported: `from migrations.versions.<file> import upgrade, downgrade`

3. ✅ **upgrade() Function**
   - Creates uploads table with all 10 columns
   - Column order: id, user_id, original_filename, storage_key, content_type, file_size_bytes, checksum_sha256, upload_status, created_at, completed_at
   - Types: UUID, UUID, text, text, text, bigint, text, text, timestamptz, timestamptz
   - Constraints: PK, FK, UNIQUE (2x), NOT NULL (per spec), CHECK (status), CHECK (file_size >= 0)
   - Indexes: PK (automatic), FK (for joins), UNIQUE storage_key, composite on (user_id, created_at DESC) for listing uploads

4. ✅ **downgrade() Function**
   - Drops uploads table
   - Reverses all changes from upgrade()
   - Is idempotent (can run multiple times safely)

5. ✅ **Metadata Correct**
   - `revision`: Unique revision ID (e.g., `a1b2c3d4`)
   - `down_revision`: Revision ID of previous migration (`de771966819d` from E3.T3)
   - `branch_labels`: None (linear history)
   - `depends_on`: None (no extra dependencies)

6. ✅ **Reversible**
   - Downgrade completely reverses upgrade
   - Can upgrade then downgrade then upgrade again without errors (idempotent)

---

### R6: ORM Model and Migration Test Coverage

**User Story:**
As a QA lead, I want comprehensive unit and integration tests so that the Upload model behavior and database constraints are validated before deployment.

#### Acceptance Criteria

**Unit Tests** (no database required):

1. ✅ **Instantiation Tests**
   - Test: Create Upload with all fields provided
   - Test: Create Upload with minimal fields (nullable fields omitted)
   - Test: Verify field types after instantiation

2. ✅ **Enum Tests**
   - Test: All four UploadStatus values present (PENDING, PROCESSING, COMPLETED, FAILED)
   - Test: Values are strings (not objects)
   - Test: Enum values compare correctly

3. ✅ **Relationship Tests**
   - Test: Upload.user relationship type is Mapped["User"]
   - Test: Relationship back_populates configured

4. ✅ **Default Value Tests**
   - Test: Default upload_status is 'pending' (or null, to be set by domain layer)
   - Test: created_at field exists and is mapped correctly

**Integration Tests** (with database):

5. ✅ **Foreign Key Constraint**
   - Test: Insert upload with valid user_id → succeeds
   - Test: Insert upload with non-existent user_id → IntegrityError

6. ✅ **UNIQUE Constraints**
   - Test: Insert upload with unique storage_key → succeeds
   - Test: Insert second upload with duplicate storage_key → IntegrityError
   - Test: Insert two uploads with null idempotency_key → both succeed (null not constrained)
   - Test: Insert upload with idempotency_key=X, then again with same key → IntegrityError

7. ✅ **NOT NULL Constraints**
   - Test: Omit each required field, insert → IntegrityError
   - Test: Fields tested: user_id, original_filename, storage_key, content_type, file_size_bytes, upload_status

8. ✅ **CHECK Constraints**
   - Test: Insert with valid status → succeeds
   - Test: Insert with invalid status (e.g., "archived") → IntegrityError
   - Test: Insert with file_size_bytes = -1 → IntegrityError

9. ✅ **No Regressions**
   - Test: All E3.T1 tests still pass
   - Test: All E2 tests still pass
   - Test: User model unchanged
   - Test: Total test count ≥ 250 (E3.T1 + E2) + new Upload tests

---

## Acceptance Criteria Summary

| Requirement | Acceptance Criteria Count | Status |
|---|---|---|
| **R1** | 9 | ⏳ Ready for Implementation |
| **R2** | 4 | ⏳ Ready for Implementation |
| **R3** | 4 | ⏳ Ready for Implementation |
| **R4** | 5 | ⏳ Ready for Implementation |
| **R5** | 6 | ⏳ Ready for Implementation |
| **R6** | 9 | ⏳ Ready for Implementation |
| **Total** | **37** | ⏳ Ready for Implementation |

---

## References

- Engineering Backlog: `docs/22-Engineering-Backlog.md` E3.T4
- Database Design: `docs/04-Database-Design.md` §4 (ERD), §5.2 (Upload table)
- Domain Model: `docs/02-Domain-Model.md` §4 (Upload entity)
- Backend Standards: `docs/07-Backend-Development-Standards.md` §8 (ORM conventions)
- E3.T3 Spec: `.kiro/specs/epic-3-database-foundation-users-t3/requirements.md` (pattern reference)

---

## Next Steps

Proceed to Design phase to specify:
- Upload model inheritance and field mappings
- UploadStatus enum implementation strategy
- Relationship configuration (User ↔ Upload)
- Index strategy for common queries
- Testing patterns (unit + integration)

