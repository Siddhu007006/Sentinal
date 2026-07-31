# E3.T4 — Upload ORM Model — Design

## Specification Document

| Field | Value |
|---|---|
| **Document** | `.kiro/specs/epic-3-database-foundation-uploads-t4/design.md` |
| **Feature** | uploads-orm-model-t4 |
| **Status** | Design Phase |
| **Traces to** | Requirements: R1–R6 |
| **Traces to** | Database Design: §4 (ERD), §5.2 (Upload table) |

---

## Design Decisions

### D1: Model Inheritance from BaseModel

**Decision:**
Upload inherits from `BaseModel` (same as User in E3.T3), not SQLAlchemy's declarative base directly.

**Rationale:**
- **Consistency:** User and all subsequent domain entities inherit from BaseModel; consistency across the ORM layer prevents cognitive overhead
- **Shared Infrastructure:** BaseModel provides `id` (UUID PK), `created_at` (immutable creation timestamp), and `updated_at` (auto-managed modification timestamp) to all models
- **DRY:** Avoids repeating these three fields in every model
- **Future-proof:** If BaseModel needs to add common functionality (e.g., soft delete helpers), all models benefit automatically

**Traceability:** 07-Backend-Development-Standards §8 (ORM model patterns)

```python
class Upload(BaseModel):
    __tablename__ = "uploads"
    # ... domain fields below
```

---

### D2: Column Definitions and Type Mappings

**Decision:**
Use SQLAlchemy 2.0 `Mapped[T]` syntax with explicit type annotations. All domain fields explicitly mapped to PostgreSQL column types.

**Rationale:**
- **Type Safety:** Mapped[T] enables full mypy type checking at development time
- **Clarity:** Column definitions are self-documenting: types are visible in the code, not inferred from defaults
- **Validation:** Pydantic integration can validate types before database writes
- **Future: Query Hints:** Type information enables better IDE autocomplete and query hints

**Mappings:**

| Field | Python Type | SQLAlchemy Type | PostgreSQL Type | Rationale |
|---|---|---|---|---|
| `id` | UUID | UUID(as_uuid=True) | uuid | Inherited from BaseModel; auto-generated PK |
| `user_id` | UUID | UUID(as_uuid=True) | uuid | FK to users; required |
| `original_filename` | str | String(255) | text | Max 255 chars; common filename limit |
| `storage_key` | str | String(1024) | text | S3/MinIO key path; up to 1024 chars allowed |
| `content_type` | str | String(100) | text | MIME type; e.g., "application/pdf", "image/png" |
| `file_size_bytes` | int | BigInteger | bigint | Files up to ~9 EB; Python int → PostgreSQL bigint |
| `checksum_sha256` | str \| None | String(64) | text | SHA-256 hex (64 chars); nullable |
| `upload_status` | str | String(20) | text | Enum as string; stored values: pending/processing/completed/failed |
| `created_at` | datetime | TIMESTAMP(timezone=True) | timestamptz | Inherited; auto-set by database |
| `completed_at` | datetime \| None | TIMESTAMP(timezone=True) | timestamptz | When status reached terminal state; nullable |

**Example Column Definition:**
```python
user_id: Mapped[UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("users.id"),
    nullable=False,
    comment="Foreign key to users table; every upload belongs to exactly one user",
)

checksum_sha256: Mapped[str | None] = mapped_column(
    String(64),
    nullable=True,
    comment="SHA-256 hash of file content (hex); null until validation completes",
)
```

**Traceability:** 07-Backend-Development-Standards §8, 04-Database-Design §5.2

---

### D3: UploadStatus Enum as StrEnum

**Decision:**
Define `UploadStatus` as `enum.StrEnum` (not PostgreSQL ENUM type). Store as `VARCHAR` with `CHECK` constraint.

**Rationale:**
- **Zero-Downtime Role Additions:** Adding a new status to a PostgreSQL ENUM requires `ALTER TYPE ... ADD VALUE`, which acquires an exclusive lock, blocking all queries
- **PostgreSQL Migration Limitation:** `ALTER TYPE` cannot be executed inside a transaction; complex migration workflows required
- **CHECK Constraint Alternative:** Storing as text + CHECK constraint is simpler: `CHECK (status IN ('pending', 'processing', 'completed', 'failed'))`; adding a new status is just a data migration (add new row to a config table, update CHECK constraint)
- **StrEnum Benefit:** String enum in Python means values are strings (not enum objects), so direct SQL comparisons work: `WHERE status = 'pending'` (not `WHERE status = UploadStatus.PENDING`)
- **Consistency:** Matches User.role (StrEnum, VARCHAR + CHECK constraint)

**Implementation:**
```python
class UploadStatus(enum.StrEnum):
    """Upload lifecycle states."""

    PENDING = "pending"  # Received, awaiting processing
    PROCESSING = "processing"  # Validation/hashing in progress
    COMPLETED = "completed"  # Terminal: processing succeeded, asset created
    FAILED = "failed"  # Terminal: processing failed, see error_message
```

**Traceability:** 07-Backend-Development-Standards §8, 04-Database-Design §2.1 (StrEnum strategy)

---

### D4: Foreign Key Relationship to Users

**Decision:**
Use SQLAlchemy `Relationship` with `back_populates` to establish bidirectional Upload ↔ User relationship.

**Rationale:**
- **Object-Oriented Access:** Upload.user and User.uploads available in application code without explicit queries
- **Lazy Loading Strategy (Asymmetric):**
  - **Upload.user (many-to-one):** `lazy="joined"` — When loading an Upload, eagerly join User. Efficient because each Upload has exactly one User; avoids N+1 query problem. Query returns one row per Upload.
  - **User.uploads (one-to-many):** `lazy="selectin"` — When loading a User, use separate SELECT IN query for uploads. Avoids Cartesian product (row multiplication) that would occur with joined. Better for collections that may be large or accessed infrequently.
- **Referential Integrity:** FK constraint at database level enforces that every upload has a valid user
- **Bidirectional:** User.uploads relationship enables reverse lookup (list all uploads for a user) efficiently with pagination in application layer

**Design:**
```python
# In Upload model:
user: Mapped["User"] = relationship(
    "User",
    back_populates="uploads",
    lazy="joined",
    comment="User who created this upload",
)

# In User model (updated from E3.T3):
uploads: Mapped[list["Upload"]] = relationship(
    "Upload",
    back_populates="user",
    lazy="selectin",
    cascade="all, delete-orphan",  # or restrict (soft delete preferred)
)
```

**Cascade Strategy:** TBD by domain layer (soft delete preferred; hard delete raises error).

**Lazy Loading Justification:**
- **Upload.user (joined):** Nearly always accessed when querying uploads (need to display user info). Joined load optimizes this common case and avoids N+1 queries. One row per upload, so no Cartesian product concern.
- **User.uploads (selectin):** Collection may be large; joined would cause row multiplication. Selectin performs separate query, returns full result set efficiently. Application layer handles pagination if needed.

**Traceability:** 04-Database-Design §4 (ERD), 02-Domain-Model §4 (Upload-User relationship)

---

### D5: Index Strategy

**Decision:**
Create 4 indexes optimized for common query patterns:
1. **PK index (automatic):** On `id` (insert/lookup by ID)
2. **FK index (automatic):** On `user_id` (join, filter by user)
3. **Composite index:** `(user_id, created_at DESC)` (user upload history, most recent first)
4. **Unique constraint index:** On `storage_key` (deduplication, foreign key from digital_assets)

**Rationale:**
- **User Upload History:** `SELECT * FROM uploads WHERE user_id = ? ORDER BY created_at DESC LIMIT 10` is a common query (user's recent uploads). Composite index on (user_id, created_at DESC) satisfies the filter and sort in a single index scan.
- **Storage Key Lookup:** Digital Asset creation looks up existing Upload by storage_key; UNIQUE index accelerates this.
- **No Index on completed_at:** Not indexed (nullable, queried rarely); if needed later, add selectively.

**Implementation:**
```python
__table_args__ = (
    Index(
        "ix_uploads_user_created",
        "user_id",
        "created_at",
        postgresql_ops={"created_at": "DESC"},
    ),
    Index("ix_uploads_storage_key", "storage_key", unique=True),
)
```

**Traceability:** 04-Database-Design §8 (indexing strategy), 07-Backend-Development-Standards §9 (query optimization)

---

### D6: Nullable Columns Strategy

**Decision:**
Three columns are nullable; all others required:
- `checksum_sha256`: null until validation completes
- `completed_at`: null until terminal state reached
- `error_message`: null unless status = failed
- `idempotency_key`: null for non-retried uploads (UNIQUE allows multiple nulls)

**Rationale:**
- **State Machine:** Nullable fields reflect upload state:
  - pending/processing: checksum null (not yet hashed), completed_at null (not done), error_message null (no error yet)
  - completed: checksum set, completed_at set, error_message null
  - failed: checksum may be partial, completed_at set, error_message populated
- **Idempotency Key:** Null allows any number of uploads without explicit idempotency key; non-null keys are deduplicated
- **Data Integrity:** Nullability at database level prevents invalid combinations (e.g., completed_at set but status = pending)

**Rationale for NOT NULL on file_size_bytes:**
File size must be known at upload creation time (can be 0 for empty files, but must be recorded). Not nullable.

**Traceability:** 04-Database-Design §5.2, 02-Domain-Model §4 (state machine)

---

### D7: Migration Generation Workflow

**Decision:**
Generate migration from ORM model using `alembic revision --autogenerate -m "Add uploads table"`. Manual review required before commit (same as E3.T3).

**Rationale:**
- **Consistency:** Same workflow as E3.T3 (User model)
- **Audit Trail:** Autogenerate produces DDL traceable back to the ORM model
- **Manual Review Gate:** Critical first migration (establishes schema; errors propagate to all deployments); manual review catches missed constraints or incorrect types

**Process:**
1. Define ORM model (all fields, types, constraints, relationships)
2. Run `alembic revision --autogenerate -m "Add uploads table"`
3. Review generated migration for:
   - Table name: "uploads"
   - All 10 columns with correct types
   - UNIQUE constraints (2x)
   - FK constraint to users
   - CHECK constraint on status
   - Indexes (3x named)
   - downgrade() drops table
4. Sign off on review (add comment to migration)
5. Merge to git

**Traceability:** 04-Database-Design §16 (migration strategy), 07-Backend-Development-Standards §8 (ORM patterns)

---

### D8: Testing Strategy

**Decision:**
Two test suites:
- **Unit Tests:** Instantiation, defaults, types, enums (no database)
- **Integration Tests:** FK enforcement, UNIQUE constraints, CHECK constraints, state transitions (with database)

**Unit Test Scope:**
```python
# backend/tests/unit/test_upload_model.py
- Test: Create Upload with all fields
- Test: Create Upload with minimal fields
- Test: Verify UploadStatus enum (4 values)
- Test: Field types correct
- Test: Relationship type is Mapped["User"]
- Test: __repr__() doesn't expose sensitive data
```

**Integration Test Scope:**
```python
# backend/tests/integration/test_upload_migration.py
- Test: FK constraint (valid/invalid user_id)
- Test: UNIQUE storage_key constraint
- Test: UNIQUE idempotency_key with null handling
- Test: NOT NULL constraints (each required field)
- Test: CHECK constraint on status
- Test: Migration upgrade/downgrade idempotent
- Test: All E3.T1, E2 tests still pass (regression)
```

**Quality Gates:**
- Ruff: 0 violations
- MyPy (--strict): 0 errors
- PyTest: All unit + integration tests pass
- No regressions in E3.T1, E2 tests

**Traceability:** 07-Backend-Development-Standards §7 (ORM testing), 11-Testing-Strategy §6 (unit/integration patterns)

---

## Design Decision Matrix

| Decision | Rationale | Trade-offs | Alternatives |
|---|---|---|---|
| **D1: Inherit from BaseModel** | Consistency, code reuse | Ties to project pattern | Direct declarative_base |
| **D2: Mapped[T] syntax** | Type safety, clarity | Verbose | untyped columns |
| **D3: StrEnum + CHECK** | Zero-downtime additions | Needs manual constraint updates | PostgreSQL ENUM |
| **D4: Bidirectional Relationship** | OOP convenience | Potential circular imports | Lazy load on demand |
| **D5: 4 Indexes** | Query optimization | Storage overhead (~1.2x table size) | Single composite index |
| **D6: Nullable Fields** | State machine accuracy | Query null-checks needed | All columns NOT NULL + defaults |
| **D7: Autogenerate + Review** | Audit trail + quality | Manual review overhead | Pure manual DDL |
| **D8: Unit + Integration** | Comprehensive coverage | Longer test suite | Unit tests only |

---

## Implementation Checklist

- [ ] Define UploadStatus enum
- [ ] Define Upload model class with all 10 fields
- [ ] Add field docstrings and comments
- [ ] Define User.uploads relationship (update E3.T3 model)
- [ ] Create indexes via __table_args__
- [ ] Export Upload and UploadStatus from models/__init__.py
- [ ] Generate migration with `alembic revision --autogenerate`
- [ ] Review migration (critical review gate)
- [ ] Create unit tests (32 minimum)
- [ ] Create integration tests (15 minimum)
- [ ] Verify all quality gates (Ruff, MyPy, PyTest)
- [ ] Verify no regressions (E3.T1, E2 tests still pass)

---

## Readiness Checklist

Before implementation begins:
- [x] E3.T3 complete (User model frozen, migration approved)
- [x] Database design reviewed (04-Database-Design §4, §5.2)
- [x] Domain model reviewed (02-Domain-Model §4)
- [x] Engineering backlog reviewed (22-Engineering-Backlog E3.T4)
- [x] E3.T1 test patterns understood
- [x] Alembic workflow proven (E3.T3)

---

## Next Steps

Proceed to Tasks phase to specify:
- Task 1: Validate ORM model structure
- Task 2: Generate migration
- Task 3: Manual migration review (critical gate)
- Task 4: Unit and integration tests
- Task 5: Final validation and audit

---

## References

- Engineering Backlog: `docs/22-Engineering-Backlog.md` E3.T4
- Database Design: `docs/04-Database-Design.md` §4 (ERD), §5.2 (Upload table)
- Domain Model: `docs/02-Domain-Model.md` §4 (Upload entity), §11 (state machine)
- Backend Standards: `docs/07-Backend-Development-Standards.md` §8 (ORM patterns), §9 (indexing)
- E3.T3 Design: `.kiro/specs/epic-3-database-foundation-users-t3/design.md` (pattern reference)

