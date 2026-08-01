# E3.T3 — Task List

## Specification Document

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-users-t3/tasks.md |
| **Feature** | users-orm-model-t3 |
| **Status** | Ready for Implementation |
| **Traces to** | Requirements: R1–R5 |
| **Traces to** | Design: D1–D8 |

---

## Task Dependency Graph

```
┌─ Task 1: Validate Frozen User Model
│  └─ Enables: Task 2
│
├─ Task 2: Generate Initial Alembic Migration
│  └─ Enables: Task 3
│
├─ Task 3: Manual Review of Generated Migration
│  └─ Enables: Task 4
│
├─ Task 4: ORM and Migration Tests
│  └─ Enables: Task 5
│
└─ Task 5: Validation and Final Audit

Execution Strategy: Sequential (strict dependencies)
Total Effort: ~3–4 hours
Complexity: Medium
Criticality: P0 (foundational entity)
```

---

## Task 1: Validate Frozen User Model

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Requirement** | R1 (User ORM Model Definition) |
| **Design Decision** | D1 (Inheritance), D2 (Column Definitions) |
| **Complexity** | Low |
| **Risk** | Low |
| **Estimated Effort** | 20 min |
| **Files Affected** | `backend/app/models/user.py`, `backend/app/models/__init__.py` |
| **Definition of Done** | Model passes all validation checks; no syntax errors; proper export |

### Description

Verify the frozen User model (from Phase 1 audit) is correctly structured, properly exported, and ready for migration generation.

**What This Task Does:**
1. Verify User model file syntax
2. Verify all required fields present with correct types
3. Verify UserRole enum defined with all values
4. Verify User exported from models package
5. Verify no circular imports
6. Verify BaseModel inheritance
7. Verify __tablename__ and __repr__() defined

**What This Task Does NOT Do:**
- ❌ Generate migration (Task 2 does this)
- ❌ Create database schema (migration does this)
- ❌ Test constraint enforcement (Task 4 does this)

### Acceptance Criteria

1. ✅ User model file exists: `backend/app/models/user.py`
2. ✅ Model syntax valid: `python -m py_compile app/models/user.py` succeeds
3. ✅ All required fields present:
   - email (Mapped[str], unique)
   - password_hash (Mapped[str])
   - full_name (Mapped[str])
   - role (Mapped[str], default 'viewer')
   - is_active (Mapped[bool], default true)
   - is_verified (Mapped[bool], default false)
   - deleted_at (Mapped[datetime | None], nullable)
4. ✅ BaseModel inheritance: `class User(BaseModel):`
5. ✅ __tablename__ defined: `__tablename__ = "users"`
6. ✅ UserRole enum defined with ADMIN, ANALYST, VIEWER
7. ✅ __repr__() method present and doesn't expose password_hash
8. ✅ User exported: `python -c "from app.models import User; print(User)"`
9. ✅ No circular imports: imports succeed without errors
10. ✅ Docstrings comprehensive (model docstring, field docstrings, UserRole docstring)
11. ✅ No last_login_at field (removed for traceability, per audit)
12. ✅ All E3.T1 tests still passing (no regressions)

### Implementation Checklist

- [x] Read `backend/app/models/user.py`
- [x] Verify syntax: `python -m py_compile app/models/user.py`
- [~] Test import: `python -c "from app.models import User; print(User)"`
- [~] Count fields (should match requirements: email, password_hash, full_name, role, is_active, is_verified, deleted_at, + inherited id, created_at, updated_at)
- [~] Verify __tablename__ = "users"
- [~] Verify UserRole enum values: ADMIN, ANALYST, VIEWER
- [~] Verify __repr__() doesn't expose password_hash
- [~] Run: `pytest backend/tests/ -v` (verify no regressions)
- [~] Record findings in task completion note

### Scope Boundaries

- ✅ In scope: Validate model structure, syntax, exports, documentation
- ❌ Out of scope: Generate migration, test constraints, create schema

---

## Task 2: Generate Initial Alembic Migration

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Requirement** | R3 (Initial Alembic Migration) |
| **Design Decision** | D7 (Migration Generation Workflow) |
| **Complexity** | Low |
| **Risk** | Low |
| **Estimated Effort** | 10 min |
| **Dependencies** | Task 1 complete |
| **Files Affected** | `backend/migrations/versions/<YYYYMMDD_HHMM>_*.py` (NEW) |
| **Definition of Done** | Migration file generated with correct naming; no syntax errors |

### Description

Generate the initial migration from the User ORM model using `alembic revision --autogenerate`.

**What This Task Does:**
1. Run `alembic revision --autogenerate -m "Add users table"`
2. Verify migration file created in `backend/migrations/versions/`
3. Verify naming: YYYYMMDD_HHMM_<rev>_<slug>.py
4. Verify migration syntax is valid Python
5. Verify migration includes upgrade() and downgrade() functions

**What This Task Does NOT Do:**
- ❌ Review migration content (Task 3 does this)
- ❌ Apply migration to database (Task 4 tests do this)
- ❌ Commit migration (only after review in Task 3)

### Acceptance Criteria

1. ✅ Migration file created in `backend/migrations/versions/`
2. ✅ Filename follows pattern: YYYYMMDD_HHMM_<revision>_add_users_table.py
3. ✅ File is syntactically valid Python: `python -m py_compile migrations/versions/<file>.py`
4. ✅ File can be imported: `python -c "from migrations.versions.<file> import ..."`
5. ✅ Migration includes docstring with description
6. ✅ Migration includes revision, down_revision, branch_labels, depends_on metadata
7. ✅ upgrade() function present and non-empty
8. ✅ downgrade() function present and non-empty
9. ✅ upgrade() includes CREATE TABLE or ALTER TABLE statement
10. ✅ downgrade() reverses upgrade() changes
11. ✅ No uncommitted migration file (still in working directory, not committed)

### Implementation Checklist

- [~] Navigate to backend directory: `cd backend`
- [~] Run autogenerate: `python -m alembic revision --autogenerate -m "Add users table"`
- [~] Verify file created: `ls -la migrations/versions/`
- [~] Check naming format: YYYYMMDD_HHMM_*.py
- [~] Syntax check: `python -m py_compile migrations/versions/<file>.py`
- [~] Import test: `python -c "import migrations.versions.<file>; print('OK')"`
- [~] View file: `cat migrations/versions/<file>.py` (preview for next task)
- [~] Record filename in task completion note

### Scope Boundaries

- ✅ In scope: Run autogenerate, verify file created and syntactically valid
- ❌ Out of scope: Review content (Task 3), apply to DB (Task 4), commit (after Task 3)

---

## Task 3: Manual Review of Generated Migration

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Requirement** | R4 (Migration Validation) |
| **Design Decision** | D7 (Migration Generation Workflow) |
| **Complexity** | Medium |
| **Risk** | Medium (review quality affects all future migrations) |
| **Estimated Effort** | 45 min |
| **Dependencies** | Task 2 complete (migration file generated) |
| **Files Affected** | `backend/migrations/versions/<file>.py` (may edit if needed) |
| **Definition of Done** | Migration reviewed, verified correct, signed off |

### Description

Manually review the generated migration to ensure it correctly represents the User schema before it's committed. This task establishes the quality standard for all future migrations.

**What This Task Does:**
1. Read and understand the generated migration code
2. Verify table definition matches ORM model
3. Verify all columns present with correct types and defaults
4. Verify all constraints present (UNIQUE, CHECK, NOT NULL)
5. Verify all indexes present and correctly defined
6. Verify downgrade() function correctly reverses upgrade()
7. Verify naming conventions followed (ck_, uq_, pk_, ix_)
8. Document review findings

**What This Task Does NOT Do:**
- ❌ Apply migration to database (Task 4 tests do this)
- ❌ Test constraint enforcement (Task 4 tests do this)
- ❌ Commit migration (happens after full validation in Task 5)

### Acceptance Criteria

**Critical Review Points:**

1. ✅ **Table Name**: `CREATE TABLE users` (matches __tablename__)
2. ✅ **Column Definitions**: All columns present with correct types
   - `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`
   - `email text NOT NULL`
   - `password_hash text NOT NULL`
   - `full_name text NOT NULL`
   - `role text NOT NULL DEFAULT 'viewer'`
   - `is_active boolean NOT NULL DEFAULT true`
   - `is_verified boolean NOT NULL DEFAULT false`
   - `created_at timestamptz NOT NULL DEFAULT now()`
   - `updated_at timestamptz NOT NULL DEFAULT now()`
   - `deleted_at timestamptz` (nullable)

3. ✅ **Unique Constraint**: `UNIQUE (email)` or `CONSTRAINT uq_users_email UNIQUE (email)`
4. ✅ **Check Constraint**: `CHECK (role IN ('admin', 'analyst', 'viewer'))` named `ck_users_role_valid`
5. ✅ **Not Null Constraints**: All required fields have NOT NULL
6. ✅ **Primary Key**: `PRIMARY KEY (id)` named `pk_users`
7. ✅ **Indexes**:
   - Primary key index (automatic)
   - Unique email index (from UNIQUE constraint)
   - Composite index on (is_active, created_at DESC) — `CREATE INDEX ix_users_active_created ...`
   - Optional: Soft-delete index on deleted_at — `CREATE INDEX ix_users_deleted_at ...`

8. ✅ **Default Values**:
   - `id`: `DEFAULT gen_random_uuid()`
   - `role`: `DEFAULT 'viewer'`
   - `is_active`: `DEFAULT true`
   - `is_verified`: `DEFAULT false`
   - `created_at`, `updated_at`: `DEFAULT now()`
   - `deleted_at`: No default (NULL)

9. ✅ **Downgrade Function**: `DROP TABLE users` (reverses upgrade completely)
10. ✅ **Constraint Naming**: Follow convention (ck_, uq_, pk_, ix_)
11. ✅ **Migration Metadata**:
    - `revision = <id>`
    - `down_revision = None` (first migration)
    - `branch_labels = None`
    - `depends_on = None`

12. ✅ **Code Quality**:
    - Docstring explains what migration does
    - upgrade() and downgrade() are inverse operations
    - No syntax errors
    - Idempotency (can re-run upgrade safely)

13. ✅ **Sign-Off**: Add comment to migration or git commit message confirming manual review
    ```
    # Reviewed 2025-01-17: Table structure, constraints, indexes, defaults all verified correct.
    ```

### Implementation Checklist

- [~] Read migration file: `cat migrations/versions/<file>.py`
- [~] Verify table name: "users"
- [~] Count columns: 10 total (9 fields + id inherited)
- [~] Check each column type and default
- [~] Verify UNIQUE constraint on email
- [~] Verify CHECK constraint on role with all 3 values
- [~] Verify NOT NULL on required fields
- [~] Verify indexes (composite on is_active/created_at, unique on email)
- [~] Verify downgrade drops table
- [~] Add review comment to migration file
- [~] Record review findings in task completion note
- [~] Do NOT commit yet (Task 5 does this after all tests pass)

### Scope Boundaries

- ✅ In scope: Review content, verify correctness, document findings, request changes if needed
- ❌ Out of scope: Apply to DB (Task 4), commit (Task 5), modify schema (only if autogenerate had errors)

---

## Task 4: ORM and Migration Tests

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Requirement** | R4 (Migration Validation), R5 (ORM Test Coverage) |
| **Design Decision** | D8 (Testing Strategy) |
| **Complexity** | Medium |
| **Risk** | Low |
| **Estimated Effort** | 1.5h |
| **Dependencies** | Task 3 complete (migration reviewed) |
| **Files Affected** | `backend/tests/unit/test_user_model.py` (NEW), `backend/tests/integration/test_user_migration.py` (NEW) |
| **Definition of Done** | All tests pass (unit + integration); migration upgrade/downgrade works |

### Description

Create comprehensive tests for the User model and migration, then validate the migration lifecycle (generate → upgrade → downgrade).

**What This Task Does:**
1. Create unit tests: Model instantiation, defaults, types, __repr__()
2. Create integration tests: Constraint enforcement (unique, check, not-null)
3. Test migration upgrade: `alembic upgrade head` creates table
4. Test migration downgrade: `alembic downgrade base` drops table
5. Verify idempotency: Re-running upgrade/downgrade is safe
6. Run all tests: Ensure no regressions in E3.T1, E2 tests

**What This Task Does NOT Do:**
- ❌ Commit migration (Task 5 does this)
- ❌ Create schema permanently (only temporary during tests)
- ❌ Implement repository pattern (E3.T10 does this)

### Acceptance Criteria

**Unit Tests** (no database):
1. ✅ Test: Instantiate User with all fields succeeds
2. ✅ Test: Instantiate User with minimal fields succeeds
3. ✅ Test: Default values are correct (role='viewer', is_active=true, is_verified=false)
4. ✅ Test: Field types are correct (email is str, password_hash is str, role is str, etc.)
5. ✅ Test: __repr__() returns useful string and doesn't expose password_hash
6. ✅ Test: created_at and updated_at are set on creation
7. ✅ Test: deleted_at is None for active user

**Integration Tests** (with database):
1. ✅ Test: Migration upgrade: `alembic upgrade head` succeeds (creates users table)
2. ✅ Test: Users table exists after upgrade (query information_schema)
3. ✅ Test: All columns present in schema (id, email, password_hash, full_name, role, is_active, is_verified, created_at, updated_at, deleted_at)
4. ✅ Test: Unique constraint on email (insert duplicate → error)
5. ✅ Test: Check constraint on role (insert invalid role → error)
6. ✅ Test: Not-null constraint (insert null on required field → error)
7. ✅ Test: Insert valid user succeeds
8. ✅ Test: Migration downgrade: `alembic downgrade base` succeeds (drops users table)
9. ✅ Test: Users table gone after downgrade (query information_schema)
10. ✅ Test: Upgrade/downgrade idempotent (can run multiple times safely)
11. ✅ Test: All E3.T1 tests still pass (no regressions)
12. ✅ Test: All E2 tests still pass (no regressions)

**Command Validation:**
```bash
# Unit tests
pytest backend/tests/unit/test_user_model.py -v

# Integration tests
pytest backend/tests/integration/test_user_migration.py -v

# Full suite
pytest backend/tests/ -v

# Migration lifecycle
cd backend
python -m alembic upgrade head      # Creates schema
pytest backend/tests/ -v              # Tests run
python -m alembic downgrade base    # Reverts schema
```

### Implementation Checklist

- [~] Create `backend/tests/unit/test_user_model.py` (5–7 unit tests)
- [~] Create `backend/tests/integration/test_user_migration.py` (10+ integration tests)
- [~] Run unit tests: `pytest backend/tests/unit/test_user_model.py -v`
- [~] Run integration tests: `pytest backend/tests/integration/test_user_migration.py -v`
- [~] Test migration upgrade: `python -m alembic upgrade head`
- [~] Test migration downgrade: `python -m alembic downgrade base`
- [~] Run full test suite: `pytest backend/tests/ -v`
- [~] Verify no regressions (all E3.T1, E2 tests passing)
- [~] Record test results in task completion note

### Scope Boundaries

- ✅ In scope: Unit tests (model), integration tests (constraints, migration), migration lifecycle
- ❌ Out of scope: API endpoint tests (E4+), repository tests (E3.T10)

---

## Task 5: Validation and Final Audit

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Requirement** | All R1–R5 |
| **Design Decision** | All D1–D8 |
| **Complexity** | Medium |
| **Risk** | Low |
| **Estimated Effort** | 30 min |
| **Dependencies** | Task 4 complete (all tests pass) |
| **Files Affected** | `.github/E3-T3-FINAL-AUDIT.md` (NEW) |
| **Definition of Done** | All quality gates passing; audit document created; ready to commit |

### Description

Run all quality gates, verify no regressions, and create the final audit document.

**What This Task Does:**
1. Run Ruff linter
2. Run MyPy type checker (--strict)
3. Run full pytest suite
4. Run Python compileall
5. Verify migration files
6. Create final audit document
7. Prepare commit summary

**What This Task Does NOT Do:**
- ❌ Commit changes (user does this after review)
- ❌ Push to repository (user does this)
- ❌ Deploy to production (future step)

### Acceptance Criteria

**Quality Gates:**

1. ✅ **Ruff (Linting)**: 
   ```bash
   ruff check app --fix  # Auto-fix what can be fixed
   ruff check app        # Should return 0 violations
   ```
   Expected: 0 violations

2. ✅ **MyPy (Type Checking)**:
   ```bash
   mypy app --strict
   ```
   Expected: 0 errors (or only acceptable suppressions documented)

3. ✅ **PyTest (Unit + Integration)**:
   ```bash
   pytest backend/tests/ -v --tb=short
   ```
   Expected: All tests pass, including:
   - 7+ unit tests for User model
   - 10+ integration tests for migration
   - 250+ existing tests (E3.T1, E2) still passing

4. ✅ **Compileall (Syntax)**:
   ```bash
   python -m compileall backend/app/ -q
   ```
   Expected: 0 errors

5. ✅ **Migration Validation**:
   - Verify migration file exists and is valid Python
   - Verify naming follows pattern
   - Verify syntax: `python -m py_compile migrations/versions/<file>.py`

6. ✅ **No Regressions**:
   - All E3.T1 tests passing
   - All E2 tests passing
   - No new failures introduced

7. ✅ **Audit Document**:
   - Create `.github/E3-T3-FINAL-AUDIT.md`
   - Document completion status
   - Document test results
   - Document readiness for E3.T4

### Implementation Checklist

- [~] Ruff: `ruff check app --fix; ruff check app`
- [~] MyPy: `mypy app --strict`
- [~] PyTest: `pytest backend/tests/ -v`
- [~] Compileall: `python -m compileall backend/app/ -q`
- [~] Verify migration file syntax
- [~] Check for regressions (compare E3.T1, E2 test counts)
- [~] Create final audit document: `.github/E3-T3-FINAL-AUDIT.md`
- [~] Record all results
- [~] Prepare commit message referencing all tasks

### Audit Document Contents

The final audit should include:

```markdown
# E3.T3 — Final Audit & Completion Report

## Executive Summary
- Status: ✅ COMPLETE
- Date: [date]
- Requirements Met: R1–R5 (100%)
- Quality Gates: All passing

## Tasks Completed
- Task 1: Validate Frozen User Model ✅
- Task 2: Generate Initial Alembic Migration ✅
- Task 3: Manual Review of Generated Migration ✅
- Task 4: ORM and Migration Tests ✅
- Task 5: Validation and Final Audit ✅

## Quality Gate Results
- Ruff: 0 violations
- MyPy: 0 errors
- PyTest: NNN tests passing (MM new User tests)
- Compileall: Success
- No regressions

## Files Created/Modified
- backend/app/models/user.py (existing, validated)
- backend/migrations/versions/<timestamp>_add_users_table.py (NEW)
- backend/tests/unit/test_user_model.py (NEW)
- backend/tests/integration/test_user_migration.py (NEW)

## Readiness for E3.T4
✅ Ready — User model complete, first migration in place, all tests passing

## Next Steps
- E3.T4: Implement Upload model (FK → users)
- E3.T5: Implement DigitalAsset model
- E3.T6: Implement Analysis model
```

### Scope Boundaries

- ✅ In scope: Run quality gates, document results, create audit
- ❌ Out of scope: Modify model (Task 1–3 if issues found), commit (user does after review)

---

## Summary

| Task | Requirement | Effort | Status |
|---|---|---|---|
| Task 1: Validate User Model | R1 | 20 min | ⏳ Pending |
| Task 2: Generate Migration | R3 | 10 min | ⏳ Pending |
| Task 3: Review Migration | R4 | 45 min | ⏳ Pending |
| Task 4: ORM & Migration Tests | R4, R5 | 1.5h | ⏳ Pending |
| Task 5: Validation & Audit | R1–R5 | 30 min | ⏳ Pending |
| **Total** | **R1–R5** | **~3–3.5h** | ⏳ Ready to Start |

---

## Quality Gates (Final Validation)

After all tasks complete:
- [~] Ruff: `ruff check app` → 0 violations
- [~] MyPy: `mypy app --strict` → 0 errors
- [~] Pytest: `pytest backend/tests/ -v` → All passing
- [~] Compileall: `python -m compileall backend/app/` → Success
- [~] No regressions in E3.T1 tests
- [~] No regressions in E2 tests
- [~] Migration file exists and is valid
- [~] All acceptance criteria met
- [~] Audit document created
- [~] Ready for commit and E3.T4

---

## Readiness Checklist

Before starting Task 1:
- ✅ E3.T1 complete (database foundation, fixtures, engine disposal)
- ✅ E3.T2 complete (Alembic configuration, migration workflow)
- ✅ User model frozen (audit complete, validated)
- ✅ PostgreSQL 16 container operational
- ✅ Alembic ready to generate migrations
- ✅ CI pipeline ready to validate migrations

---

## References

- 22-Engineering-Backlog: E3.T3
- 04-Database-Design §5.1: users table specification
- 02-Domain-Model: User as identity anchor
- 07-Backend-Development-Standards §8: ORM model conventions
- E3.T1 Complete: Database Foundation
- E3.T2 Complete: Alembic Configuration
- E3.T3 Audit: Phase 1 audit findings
