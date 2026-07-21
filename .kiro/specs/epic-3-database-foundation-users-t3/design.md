# E3.T3 Design Document

## Specification Document

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-users-t3/design.md |
| **Feature** | users-orm-model-t3 |
| **Status** | In Review |
| **Traces to** | 22-Engineering-Backlog E3.T3 |

---

## Design Decisions

### Design Decision 1: Model Inheritance from BaseModel

**Requirement:** R1 (User ORM Model Definition)

**Decision:**
The User model inherits from BaseModel (not Base directly). BaseModel provides:
- `id: Mapped[uuid.UUID]` — UUID primary key with dual defaults (client + server)
- `created_at: Mapped[datetime]` — Immutable creation timestamp (UTC)
- `updated_at: Mapped[datetime]` — Auto-updated modification timestamp (UTC)
- `__repr__()` — Debugging string representation

**Rationale:**
BaseModel ensures consistency across all entity models. All primary keys are UUIDs (preventing enumeration attacks), all timestamps are UTC (preventing timezone confusion), and all models follow the same pattern (reducing cognitive load).

**Trade-offs:**
- ✅ Consistent patterns across entities
- ✅ Security properties (UUIDs) inherited automatically
- ✅ Timestamp handling standardized
- ✅ No custom __repr__() needed for each model

**Implementation:**
```python
class User(BaseModel):  # Inherits from BaseModel, not Base
    __tablename__ = "users"
    # Define domain-specific fields only
    email: Mapped[str] = mapped_column(...)
    # id, created_at, updated_at inherited automatically
```

---

### Design Decision 2: Column Definitions and Type Mappings

**Requirement:** R1 (User ORM Model Definition), R2 (Constraints and Indexes)

**Decision:**

| Column | Type | Nullable | Default | Constraint |
|--------|------|----------|---------|-----------|
| `id` | uuid.UUID | NO | gen_random_uuid() (both client + server) | PK |
| `email` | str (320 chars) | NO | — | UNIQUE, indexed |
| `password_hash` | str (60 chars) | NO | — | NOT NULL |
| `full_name` | str (255 chars) | NO | — | NOT NULL |
| `role` | str (20 chars) | NO | 'viewer' | CHECK constraint |
| `is_active` | bool | NO | true | NOT NULL |
| `is_verified` | bool | NO | false | NOT NULL |
| `created_at` | datetime (TZ) | NO | now() (both client + server) | NOT NULL |
| `updated_at` | datetime (TZ) | NO | now() (both client + server) | NOT NULL |
| `deleted_at` | datetime (TZ) | YES | NULL | — |

**Field Rationale:**

- **email (text, 320 chars)**: RFC 5321 max length. Unique constraint ensures one account per email. Indexed for login lookups. Application layer normalizes to lowercase before queries.

- **password_hash (text, 60 chars)**: bcrypt output is exactly 60 characters. Never exposed in API responses or logs (repository layer filters). Validation happens in E4 (authentication).

- **full_name (text, 255 chars)**: Display name for UI. Not used in authentication. User can update via profile endpoint (E4+).

- **role (text, 20 chars)**: RBAC role stored as VARCHAR with CHECK constraint (not PostgreSQL ENUM) for zero-downtime additions. Values: 'admin', 'analyst', 'viewer'. Defaults to 'viewer' (least privileged).

- **is_active (boolean)**: Administrative deactivation flag. `false` = login rejected, but data preserved. Separate from `is_verified` (email verification status) and `deleted_at` (soft delete).

- **is_verified (boolean)**: Email verification status. `false` = unverified, `true` = verified. Separate from `is_active`. Used by E4 to determine feature access.

- **deleted_at (nullable timestamp)**: Soft delete timestamp. NULL = active, non-null = soft-deleted. Excluded from queries by default (repository layer). Preserves audit trail and referential integrity.

- **created_at, updated_at**: Inherited from BaseModel. Always UTC. Managed by SQLAlchemy with server-side triggers.

**Type Mapping Choices:**

- `Mapped[str]` instead of `Mapped[str | None]` — Email, password_hash, full_name, role are required (no null allowed)
- `Mapped[bool]` instead of `Mapped[bool | None]` — Flags have definite true/false, not unknown state
- `Mapped[datetime | None]` for `deleted_at` — Explicitly optional (nullable) for soft delete pattern
- `String(320)` for email — Explicit length limit prevents database bloat
- `String(60)` for password_hash — Matches bcrypt output exactly
- `TIMESTAMP(timezone=True)` for timestamps — Always timezone-aware (forces UTC on application side)

**Trade-offs:**
- ✅ Type-safe with Mapped[] syntax
- ✅ Explicit nullable/not-null in Python (matches database constraints)
- ✅ Field lengths documented and enforced
- ✅ No silent NULL surprises at runtime

---

### Design Decision 3: UserRole Enum Strategy

**Requirement:** R1 (User ORM Model Definition)

**Decision:**
Define `UserRole` as Python `enum.StrEnum` with values ADMIN, ANALYST, VIEWER. Store in database as `text` with CHECK constraint (not PostgreSQL ENUM type).

```python
class UserRole(enum.StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

# In User model:
role: Mapped[str] = mapped_column(
    String(20),
    nullable=False,
    default=UserRole.VIEWER.value,
    server_default="'viewer'",
)

# Table constraint:
CheckConstraint(
    "role IN ('admin', 'analyst', 'viewer')",
    name="ck_users_role_valid"
)
```

**Rationale:**

Using `text` + `CHECK` instead of PostgreSQL ENUM enables zero-downtime role additions:
- Adding a new role to PostgreSQL ENUM requires `ALTER TYPE ... ADD VALUE`, which acquires an exclusive lock (blocking all writes)
- Adding a role as text requires only inserting into a lookup table or updating application code (no lock needed)
- CHECK constraint enforces only valid values are stored

**Trade-offs:**
- ✅ Zero-downtime role additions (no ALTER TYPE exclusive lock)
- ✅ Application-level validation in Python (StrEnum provides IDE autocompletion)
- ✅ Flexible for future workspace-scoped roles
- ❌ Slightly less database-native than ENUM type (but CHECK constraint provides same safety)

---

### Design Decision 4: Constraint Strategy

**Requirement:** R2 (Database Constraints and Indexes)

**Decision:**

| Constraint | Type | Enforcement | Rationale |
|-----------|------|------------|-----------|
| `id` | PRIMARY KEY | Database | Unique identifier, enforced at DB level |
| `email` | UNIQUE | Database | Prevents duplicate accounts, enforced at DB level |
| `email` | INDEX (btree) | Database | Enables fast login lookups by email |
| `role` | CHECK | Database | Ensures only valid RBAC values stored |
| `email, password_hash, full_name, role, is_active, is_verified` | NOT NULL | Database | Enforced by SQLAlchemy `nullable=False` + database constraint |
| `(is_active, created_at DESC)` | COMPOSITE INDEX | Database | Enables fast admin user list queries (filter by is_active, sort by creation date) |
| `deleted_at` | INDEX (btree) | Database | Enables efficient soft-delete filtering queries |

**Constraint Naming Convention:**
- Primary key: `pk_users`
- Unique: `uq_users_email`
- Check: `ck_users_role_valid`
- Foreign key: `fk_users_<col>_<ref_table>` (for E3.T4+)
- Index: `ix_users_<column>` or `ix_users_<columns>` for composite

**Rationale:**

Database constraints enforce data integrity at the source. Application code can fail or be bypassed; databases cannot. Predictable naming (via `naming_convention` in BaseModel metadata) makes migrations readable and maintainable.

**Trade-offs:**
- ✅ Data integrity guaranteed even if app code has bugs
- ✅ Consistent constraint naming across all migrations
- ✅ Constraints visible in `\d users` (PostgreSQL describe)
- ✅ Migration scripts reference constraints by name

---

### Design Decision 5: Index Strategy

**Requirement:** R2 (Database Constraints and Indexes)

**Decision:**

Create three indexes on the `users` table:

1. **Primary Key (automatic)**: `pk_users` on `id`
   - Enabled by `primary_key=True` in SQLAlchemy
   - Used by all FK references and direct lookups
   - Type: btree, unique

2. **Unique Email Index**: `uq_users_email` on `email`
   - Enabled by `unique=True` in SQLAlchemy
   - Used by login lookups (WHERE email = '...')
   - Type: btree, unique, case-insensitive (application normalizes to lowercase)

3. **Composite Index**: `ix_users_active_created` on `(is_active, created_at DESC)`
   - Used by admin user list queries: WHERE is_active = true ORDER BY created_at DESC
   - Enables single-pass scan with sort already applied
   - Type: btree
   - PostgreSQL `DESC` nulls handling: NULLS LAST (standard)

4. **Soft-Delete Index**: `ix_users_deleted_at` on `deleted_at`
   - Used by soft-delete filtering: WHERE deleted_at IS NULL
   - Optional but recommended for large tables
   - Type: btree

**Rationale:**

Indexes are chosen based on expected query patterns:
- **Login**: Fast lookup by email (index #2)
- **User list**: Filter active, sort by recency (index #3)
- **Soft-delete**: Exclude deleted rows from all queries (index #4)

Composite indexes are preferred when columns are always queried together. Avoid over-indexing (each index has write cost).

**Trade-offs:**
- ✅ Fast lookups for common queries
- ✅ Single-pass execution for admin user list
- ✅ Soft-delete filtering efficient
- ❌ Slightly slower INSERT/UPDATE (maintains indexes)
- ❌ Storage overhead (~10-20% depending on workload)

---

### Design Decision 6: Soft-Delete Approach

**Requirement:** R1 (Model Definition), R2 (Constraints)

**Decision:**

Implement soft delete via `deleted_at` nullable timestamp column:
- `NULL` = active user (included in all queries by default)
- Non-null = soft-deleted user (excluded by repository default WHERE clause)
- No cascade deletes (user rows preserved for audit)

```python
deleted_at: Mapped[datetime | None] = mapped_column(
    TIMESTAMP(timezone=True),
    nullable=True,
    comment="Soft delete timestamp (UTC), null = active"
)
```

**Query Pattern** (implemented in E3.T10 Repository layer):
```sql
-- Default query (exclude deleted users)
SELECT * FROM users WHERE deleted_at IS NULL;

-- Admin query (show all)
SELECT * FROM users;

-- Archive query (show only deleted)
SELECT * FROM users WHERE deleted_at IS NOT NULL;
```

**Rationale:**

Soft delete preserves audit trail and referential integrity. Foreign key references (Upload.user_id → User.id) remain valid even after user deactivation. Hard deletion is irreversible and destroys audit history.

**Trade-offs:**
- ✅ Audit trail preserved (when was user deleted?)
- ✅ FKs never become invalid
- ✅ User assets not orphaned
- ✅ Reversible (set deleted_at back to NULL)
- ❌ Queries must remember WHERE deleted_at IS NULL (repository layer handles this)
- ❌ Disk space not reclaimed immediately

---

### Design Decision 7: Migration Generation Workflow

**Requirement:** R3 (Initial Alembic Migration)

**Decision:**

Migration is generated via Alembic autogenerate, then **manually reviewed** before commit:

1. **Generation Phase** (automated):
   ```bash
   cd backend
   python -m alembic revision --autogenerate -m "Add users table"
   ```
   
   Alembic compares ORM model (User) to current database (empty) and generates migration script.

2. **Review Phase** (manual, MANDATORY):
   - Read the generated migration file
   - Verify table structure (columns, types, defaults)
   - Verify constraints (UNIQUE, CHECK, NOT NULL)
   - Verify indexes (names, columns, order)
   - Verify downgrade correctness (drops table, reverts all changes)
   - Sign off: Add comment in migration or git commit message

3. **Testing Phase** (automated by CI):
   - `alembic upgrade head` — applies migration to test database
   - `pytest` — runs tests against migrated schema
   - `alembic downgrade base` — reverts migration, verifies downgrade works

**Rationale:**

Alembic autogenerate is fast but not infallible. Manual review of the first migration establishes a quality standard for all future migrations. This prevents schema mistakes from reaching production.

**Trade-offs:**
- ✅ Catches autogenerate mistakes before commit
- ✅ Establishes review discipline
- ✅ Documents intent (comments in migration)
- ✅ Enables custom SQL if needed
- ❌ Adds manual step (but only for first migration as pattern)
- ❌ Requires developer to understand generated SQL

---

### Design Decision 8: Testing Strategy

**Requirement:** R5 (ORM Model Test Coverage)

**Decision:**

Create two test suites:

**Unit Tests** (`backend/tests/unit/test_user_model.py`):
- Test model instantiation
- Test default values
- Test field types
- Test __repr__()
- Run fast, no database needed
- In-memory ORM validation

**Integration Tests** (`backend/tests/integration/test_user_model.py`):
- Test constraint enforcement (unique email)
- Test check constraint (valid roles only)
- Test not-null constraint
- Test insert/update behavior
- Run against real PostgreSQL (via test fixtures from E3.T1)
- Verify actual database behavior

**Rationale:**

Unit tests validate ORM behavior quickly. Integration tests validate database constraints actually work. Both are needed for comprehensive coverage.

**Example Test:**
```python
def test_duplicate_email_raises_unique_violation():
    """Integration test: UNIQUE constraint on email enforced."""
    user1 = User(email="jane@example.com", password_hash="...", full_name="Jane", role="viewer")
    session.add(user1)
    await session.commit()  # First insert succeeds
    
    user2 = User(email="jane@example.com", password_hash="...", full_name="Other", role="viewer")
    session.add(user2)
    
    with pytest.raises(IntegrityError):  # Unique violation
        await session.commit()
```

**Trade-offs:**
- ✅ Comprehensive coverage (unit + integration)
- ✅ Fast feedback (unit tests run without DB)
- ✅ Production confidence (integration tests verify actual DB)
- ❌ Two test suites to maintain

---

## Architecture Diagram

```
Domain Layer (clean)
│
├─ User (ORM Model)
│  ├─ id (UUID PK, inherited)
│  ├─ email (unique, indexed)
│  ├─ password_hash (never exposed)
│  ├─ full_name
│  ├─ role (CHECK constraint)
│  ├─ is_active
│  ├─ is_verified
│  ├─ created_at, updated_at (inherited)
│  └─ deleted_at (soft delete)
│
└─ UserRole (Enum)
   ├─ ADMIN
   ├─ ANALYST
   └─ VIEWER


Database Layer
│
└─ users table
   ├─ COLUMNS: id, email, password_hash, full_name, role, is_active, is_verified, created_at, updated_at, deleted_at
   ├─ CONSTRAINTS:
   │  ├─ PK: pk_users (id)
   │  ├─ UNIQUE: uq_users_email (email)
   │  ├─ CHECK: ck_users_role_valid (role IN ('admin', 'analyst', 'viewer'))
   │  └─ NOT NULL: email, password_hash, full_name, role, is_active, is_verified, created_at, updated_at
   │
   └─ INDEXES:
      ├─ pk_users (automatic)
      ├─ uq_users_email (automatic)
      ├─ ix_users_active_created (is_active, created_at DESC)
      └─ ix_users_deleted_at (deleted_at)


Migration Layer
│
├─ Initial Migration (E3.T3)
│  ├─ upgrade(): CREATE TABLE users (...)
│  └─ downgrade(): DROP TABLE users
│
└─ Future Migrations (E3.T4+)
   ├─ Upload model (FK → users)
   ├─ DigitalAsset model
   ├─ Analysis model
   └─ ... (other models reference User via FK)
```

---

## Design Clarifications

### Q1: Why no password validation in the User model?
**A:** Password validation (strength checks, pattern matching) belongs in E4 (Authentication) where password reset/change flows are implemented. The ORM model just stores the hash; validation happens at service layer.

### Q2: Why is `is_verified` separate from `is_active`?
**A:** Two independent flags for two independent concerns:
- `is_active`: Admin deactivation (no login allowed)
- `is_verified`: Email verification (may restrict feature access but login allowed)

A user can be inactive but still verified, or active but unverified.

### Q3: Why store role as text instead of PostgreSQL ENUM?
**A:** PostgreSQL ENUM additions require exclusive locks (`ALTER TYPE ... ADD VALUE`), blocking all writes. TEXT + CHECK constraint allows zero-downtime role additions. Future workspace-scoped roles will use a join table anyway.

### Q4: Why composite index on (is_active, created_at DESC)?
**A:** Admin dashboard queries: "Show me active users sorted by newest first." Composite index enables single-pass scan with sort already applied (no sort operation needed).

### Q5: Why manual review of generated migration?
**A:** Autogenerate is fast but not infallible. Manual review catches mistakes (wrong defaults, missing constraints, incorrect indexes) before they reach production. Establishes quality discipline.

### Q6: Why is deleted_at nullable, not a boolean is_deleted?
**A:** Timestamps answer "when was this deleted?" (useful for audit/compliance). Booleans only answer "is deleted?". Soft-delete best practice is timestamp + WHERE deleted_at IS NULL filter.

---

## Stateful Component Review

### Transaction Boundaries ✅
- User model has no transaction semantics (stateless ORM class)
- Transactions handled by repository layer (E3.T10) and application services (E4)
- INSERT, UPDATE, DELETE are atomic per PostgreSQL semantics

### Connection Lifecycle ✅
- AsyncSession acquired from dependency injection (E3.T1)
- ORM model is just data; connection managed by session
- Soft delete doesn't require special transaction handling

### Concurrency ✅
- UNIQUE constraint on email handled by database (isolation level)
- ROLE CHECK constraint atomic at INSERT time
- No application-level locking needed (database handles it)

### Failure Modes ✅
- Duplicate email → IntegrityError (caught by application)
- Invalid role → CheckConstraintError (caught by application)
- Null on required field → NOT NULL violation (caught at DB)
- All failures are idempotent (can retry after fixing)

---

## Risks Addressed

| Risk | Mitigation | D-Ref |
|---|---|---|
| **Autogenerate errors** | Manual review before commit (R4) | D7 |
| **Email not unique** | UNIQUE constraint + index | D4, D5 |
| **Invalid roles stored** | CHECK constraint + Python enum | D3 |
| **Defaults not captured** | Manual review verifies defaults | D7 |
| **Indexes missing** | Manual review + Design spec reference | D7 |
| **Data loss on delete** | Soft delete preserves rows | D6 |

---

## References

- 22-Engineering-Backlog: E3.T3 specification
- 04-Database-Design §5.1: users table specification
- 02-Domain-Model: User as identity anchor
- 07-Backend-Development-Standards §8: ORM model conventions
- E3.T1: Database Foundation (BaseModel infrastructure)
- E3.T2: Alembic Configuration (migration workflow)
