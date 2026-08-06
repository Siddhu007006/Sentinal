# E3.T9 — Tasks — Refresh Tokens ORM Model and Migration

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-refresh-tokens-t9/tasks.md |
| **Feature** | refresh-tokens-orm-model-t9 |
| **Status** | Task Breakdown |
| **Owner** | Engineering Team |
| **Traces to** | design.md, requirements.md |

---

## Task Breakdown

### Task 1: Implement RefreshToken ORM Model

**File:** `backend/app/models/refresh_token.py`

**Objective:** Create the RefreshToken ORM model with all required fields, constraints, and docstrings.

**Acceptance Criteria:**

1. [ ] File `backend/app/models/refresh_token.py` exists
2. [ ] RefreshToken class inherits from BaseModel (not Base)
3. [ ] All required fields defined with correct types:
   - `id` (inherited from BaseModel)
   - `user_id` (UUID FK, NOT NULL, indexed)
   - `token_hash` (VARCHAR(64), NOT NULL, UNIQUE, indexed)
   - `expires_at` (TIMESTAMPTZ, NOT NULL)
   - `is_revoked` (BOOLEAN, NOT NULL, default=false)
   - `user_agent` (VARCHAR(512), nullable)
   - `ip_address` (INET, nullable)
   - `revoked_at` (TIMESTAMPTZ, nullable)
   - `created_at` (inherited from BaseModel)
   - `updated_at` (inherited from BaseModel)
4. [ ] Table name is "user_refresh_tokens"
5. [ ] Foreign key on user_id with ON DELETE CASCADE
6. [ ] Unique constraint on token_hash
7. [ ] Indexes defined (user_id, partial expires_at)
8. [ ] __repr__() method implemented (NO token_hash exposure)
9. [ ] Comprehensive docstrings on class and fields
10. [ ] No syntax errors: `python -m py_compile app/models/refresh_token.py`
11. [ ] No import errors: `python -c "from app.models import RefreshToken"`

**Details:**

Follow the User model pattern exactly:
- Field definitions using `Mapped[type]` syntax
- mapped_column() with constraints and comments
- __table_args__ for indexes and constraints
- comprehensive docstrings (security notes, lifecycle, examples)
- ForeignKey with ondelete="CASCADE"

**Traces to:** design.md §RefreshToken ORM Model Design

---

### Task 2: Update models/__init__.py Export

**File:** `backend/app/models/__init__.py`

**Objective:** Export RefreshToken from models package for Alembic discovery.

**Acceptance Criteria:**

1. [ ] RefreshToken imported from app.models.refresh_token
2. [ ] RefreshToken added to __all__ list
3. [ ] Exports are in alphabetical order
4. [ ] No syntax errors: `python -c "from app.models import RefreshToken"`
5. [ ] Alembic can discover RefreshToken: `python -c "from app.models import *; print(RefreshToken)"`

**Details:**

Add import:
```python
from app.models.refresh_token import RefreshToken
```

Update __all__ (alphabetical):
```python
__all__ = [
    "Analysis",
    "AnalysisStatus",
    "AuditLog",
    "AssetType",
    "DigitalAsset",
    "RefreshToken",  # <- Add here
    "Upload",
    "UploadStatus",
    "User",
    "UserRole",
]
```

**Traces to:** design.md §RefreshToken ORM Model Design

---

### Task 3: Generate Alembic Migration

**Command:**
```bash
cd backend
alembic revision --autogenerate -m "Add user_refresh_tokens table"
```

**Objective:** Generate Alembic migration file with table creation and constraints.

**Acceptance Criteria:**

1. [ ] Migration file created in `backend/migrations/versions/`
2. [ ] File named with pattern: `YYYYMMDD_HHMM_<rev>_add_user_refresh_tokens_table.py`
3. [ ] Migration is valid Python (no syntax errors)
4. [ ] Migration can be imported: `python -c "from alembic import ..."`
5. [ ] upgrade() function exists with:
   - op.create_table("user_refresh_tokens", ...)
   - All columns defined (id, created_at, updated_at, deleted_at, user_id, token_hash, expires_at, is_revoked, user_agent, ip_address, revoked_at)
   - All column types correct (UUID, TIMESTAMPTZ, String, Boolean, INET)
   - All defaults correct (gen_random_uuid(), now(), false)
   - Primary key constraint (pk_user_refresh_tokens)
   - Unique constraint (uq_user_refresh_tokens_token_hash)
   - Foreign key constraint (fk_user_refresh_tokens_user_id_users) with ON DELETE CASCADE
   - Indexes created (ix_user_refresh_tokens_user_id, ix_user_refresh_tokens_expires_at_active)
6. [ ] downgrade() function exists and drops table
7. [ ] Migration passes linting: `ruff check migrations/versions/<file>.py`

**Details:**

Review generated migration for accuracy. Manual review checklist:
- [ ] Table name is "user_refresh_tokens" (matches __tablename__)
- [ ] All columns present with correct types
- [ ] Column defaults correct
- [ ] Nullable/not-null flags correct
- [ ] Unique constraint on token_hash present
- [ ] Foreign key with ON DELETE CASCADE present
- [ ] All indexes present (user_id, partial expires_at)
- [ ] downgrade() reverses all changes

**Traces to:** design.md §Alembic Migration Strategy

---

### Task 4: Review and Validate Migration

**Objective:** Manually review migration for accuracy before commit.

**Acceptance Criteria:**

1. [ ] Migration code reviewed line-by-line
2. [ ] Table name matches __tablename__
3. [ ] All columns present and types correct
4. [ ] All column defaults correct
5. [ ] Nullable/not-null flags correct
6. [ ] Unique constraint on token_hash present
7. [ ] Foreign key with ON DELETE CASCADE present
8. [ ] All indexes present and named correctly
9. [ ] downgrade() reverses all changes
10. [ ] Migration passes syntactic validation
11. [ ] Migration is safe to deploy (no data loss, backward compatible)

**Details:**

Verify in migration file:

```python
# Verify table creation
op.create_table(
    "user_refresh_tokens",
    sa.Column("id", sa.UUID(as_uuid=True), ..., nullable=False),
    sa.Column("user_id", sa.UUID(as_uuid=True), ..., nullable=False),
    sa.Column("token_hash", sa.String(64), ..., nullable=False),
    sa.Column("expires_at", TIMESTAMP(timezone=True), ..., nullable=False),
    sa.Column("is_revoked", sa.Boolean(), ..., nullable=False),
    sa.Column("user_agent", sa.String(512), nullable=True),
    sa.Column("ip_address", INET(), nullable=True),
    sa.Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
    # ... timestamps inherited from BaseModel
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", ...),
    sa.PrimaryKeyConstraint("id", ...),
    sa.UniqueConstraint("token_hash", ...),
)

# Verify indexes
op.create_index("ix_user_refresh_tokens_user_id", ...)
op.create_index("ix_user_refresh_tokens_expires_at_active", ..., postgresql_where="is_revoked = false")
```

**Traces to:** design.md §Alembic Migration Strategy

---

### Task 5: Create Unit and Integration Tests

**File:** `backend/tests/unit/test_refresh_token_model.py`

**Objective:** Comprehensive test coverage for RefreshToken model and database constraints.

**Acceptance Criteria:**

1. [ ] Test file created: `backend/tests/unit/test_refresh_token_model.py`
2. [ ] Unit tests:
   - [ ] test_refresh_token_instantiation() — valid data succeeds
   - [ ] test_refresh_token_defaults() — default values correct
   - [ ] test_refresh_token_repr_no_hash() — __repr__() doesn't expose hash
   - [ ] test_refresh_token_import() — can import from app.models
   - [ ] test_refresh_token_field_types() — all fields have correct types
3. [ ] Integration tests:
   - [ ] test_insert_refresh_token() — insert succeeds
   - [ ] test_duplicate_token_hash_fails() — unique constraint enforced
   - [ ] test_user_deletion_cascades_to_tokens() — ON DELETE CASCADE works
   - [ ] test_query_tokens_by_user_id() — session listing works
   - [ ] test_revoke_token() — revocation succeeds
   - [ ] test_query_active_tokens() — can filter by is_revoked
   - [ ] test_validation_query() — standard validation query works
4. [ ] All tests pass: `pytest tests/unit/test_refresh_token_model.py -v`
5. [ ] Tests follow project conventions (async tests, fixtures, etc.)
6. [ ] Tests are in Git and tracked

**Details:**

See design.md §ORM Model Tests for complete test implementations.

Test structure:
- Use pytest fixtures (Session, User)
- Use async/await for database operations
- Test both happy path and error cases
- Verify database constraints (unique, FK, not null)
- Document what each test validates

**Traces to:** design.md §ORM Model Tests

---

### Task 6: Run Quality Gates

**Objective:** Verify code quality, type safety, and test coverage.

**Commands:**

```bash
cd backend

# 1. Ruff linting
ruff check app/models/refresh_token.py
ruff check tests/unit/test_refresh_token_model.py

# 2. MyPy type checking (strict mode)
mypy app/models/refresh_token.py --strict

# 3. Unit tests
pytest tests/unit/test_refresh_token_model.py -v

# 4. All tests (ensure no regressions)
pytest tests/ -v
```

**Acceptance Criteria:**

1. [ ] Ruff: 0 violations in refresh_token.py
2. [ ] Ruff: 0 violations in test_refresh_token_model.py
3. [ ] MyPy: 0 errors in refresh_token.py (strict mode)
4. [ ] Pytest: All tests in test_refresh_token_model.py pass (12 tests)
5. [ ] Pytest: All tests in test suite pass (no regressions in E3.T1-E3.T8)
6. [ ] Coverage: Refresh token model fully covered

**Details:**

**Ruff Checks:**
- Unused imports
- Code style (PEP 8)
- Security warnings
- Complexity checks

**MyPy Checks (Strict Mode):**
- All variables have explicit types (no Any)
- All function parameters have type hints
- All return types specified
- No implicit Optional
- No missing function docstrings

**Pytest:**
- All tests pass
- No skipped tests
- Coverage >= 95% for refresh_token.py
- No warnings or errors in output

**Traces to:** design.md §Migration Validation Checklist

---

### Task 7: Verify Completion

**Objective:** Final verification that E3.T9 is complete and ready for integration.

**Verification Checklist:**

- [ ] refresh_token.py exists and is syntactically valid
- [ ] No import errors: `python -c "from app.models import RefreshToken; print(RefreshToken)"`
- [ ] Alembic migration generated and reviewed
- [ ] Migration file is syntactically valid
- [ ] All unit tests pass (12 tests)
- [ ] All integration tests pass
- [ ] Ruff: 0 violations
- [ ] MyPy: 0 errors (strict)
- [ ] No regressions in E3.T1-E3.T8 tests
- [ ] design.md complete and accurate
- [ ] tasks.md complete and accurate
- [ ] requirements.md acceptance criteria all met

**Details:**

Run final verification:

```bash
cd backend

# Syntax check
python -m py_compile app/models/refresh_token.py

# Import check
python -c "from app.models import RefreshToken; print(RefreshToken)"

# Linting
ruff check app/models/refresh_token.py tests/unit/test_refresh_token_model.py

# Type checking
mypy app/models/refresh_token.py --strict

# Tests
pytest tests/unit/test_refresh_token_model.py -v
pytest tests/ -v

# Migration check
python -c "from alembic import config; cfg = config.Config('alembic.ini'); cfg.get_section('sqlalchemy')"
```

**Traces to:** design.md §Migration Validation Checklist

---

## Implementation Sequence

Execute tasks in this order:

1. **Task 1** — Implement RefreshToken ORM Model
2. **Task 2** — Update models/__init__.py
3. **Task 3** — Generate Alembic Migration
4. **Task 4** — Review and Validate Migration
5. **Task 5** — Create Unit and Integration Tests
6. **Task 6** — Run Quality Gates
7. **Task 7** — Verify Completion

---

## Success Criteria (Completion)

All acceptance criteria for all tasks must be met:

- ✅ RefreshToken ORM model defined and exported
- ✅ Alembic migration generated and validated
- ✅ All unit tests pass (12 tests)
- ✅ All integration tests pass
- ✅ Ruff: 0 violations
- ✅ MyPy: 0 errors (strict)
- ✅ No regressions in prior test suites (E3.T1-E3.T8)
- ✅ design.md complete and accurate
- ✅ tasks.md complete and accurate
- ✅ requirements.md acceptance criteria all met (R1-R5)

---

## Dependencies

**Depends On:**
- E3.T1 (Database Foundation)
- E3.T2 (Alembic Configuration)
- E3.T3 (User ORM Model)
- E3.T8 (AuditLog ORM Model) — for testing patterns

**Enables:**
- E3.T10 (RefreshToken Repository Interface)
- E3.T11+ (Token Service, Authentication Service)
- E4.T2+ (Token generation, validation, endpoints)

---

## References

- design.md — Full design specification
- requirements.md — Feature requirements and acceptance criteria
- backend/app/models/user.py — User model example
- backend/app/models/audit_log.py — AuditLog model example
- backend/app/infrastructure/database/base.py — BaseModel definition
- backend/migrations/versions/ — Existing migrations for reference
- 04-Database-Design §4 — ERD and table specifications
- 08-Security-Architecture §5 — JWT and token lifecycle

