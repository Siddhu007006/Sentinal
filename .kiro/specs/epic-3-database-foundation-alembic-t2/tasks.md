# E3.T2 — Task List

## Specification Document

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-alembic-t2/tasks.md |
| **Feature** | alembic-configuration-t2 |
| **Status** | Ready for Implementation |
| **Traces to** | Requirements: R1–R5 |
| **Traces to** | Design: D1–D6 |

---

## Task Dependency Graph

```
┌─ Task 1: Alembic Autogenerate Validation
│  └─ Enables: Task 2
│
├─ Task 2: Upgrade & Downgrade Testing
│  └─ Enables: Task 3
│
├─ Task 3: CI Integration
│  └─ Enables: Task 4
│
└─ Task 4: Documentation & Validation

Execution Strategy: Sequential (strict dependencies)
Total Effort: ~7–8 hours
Complexity: Low–Medium
```

---

## Task 1: Alembic Autogenerate Validation

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Requirement** | R1 (Migration Generation Workflow) |
| **Design Decision** | D1 (Migration Naming), D2 (Autogenerate Workflow) |
| **Complexity** | Low |
| **Risk** | Low |
| **Estimated Effort** | 1.5h |
| **Files Affected** | `backend/migrations/versions/` (validation only, no new migrations yet) |
| **Definition of Done** | Migration generation workflow validated; no schema changes needed |

### Description

Validate that the Alembic autogenerate workflow operates correctly with the async engine configuration and ORM metadata from E3.T1.

**What This Task Does:**
1. Test that `env.py` can import Base metadata without errors
2. Verify `alembic revision --autogenerate` command execution succeeds (with or without pending changes)
3. Test migration file naming convention (timestamps, slugs)
4. Verify generated migration files are syntactically valid Python
5. Document findings

**What This Task Does NOT Do:**
- ❌ Create actual ORM models (E3.T3 does this)
- ❌ Apply migrations to database (Task 2 does this)
- ❌ Create permanent migrations in repository (first real migration in E3.T3)

### Acceptance Criteria

1. ✅ **Base Import**: `env.py` successfully imports `Base` from `app.infrastructure.database.base` without errors
2. ✅ **Autogenerate Command**: `alembic revision --autogenerate` completes without error (even with no pending changes)
3. ✅ **File Naming**: Generated migration files (if any) follow pattern `YYYYMMDD_HHMM_<rev>_<slug>.py`
4. ✅ **File Validation**: Generated migration files are syntactically valid Python (can be imported)
5. ✅ **Migration Chain**: Generated migration includes proper `up_revision` and `down_revision` metadata
6. ✅ **Documentation**: Findings recorded; verify no schema changes needed to Alembic configuration
7. ✅ **No Regressions**: All E3.T1 tests still pass

### Implementation Checklist

- [x] Read current state of `env.py`, `alembic.ini`, `script.py.mako`
- [x] Verify `env.py` imports Base successfully
- [x] Run: `cd backend && alembic revision --autogenerate -m "test"`
- [x] Inspect generated migration file (if created)
- [x] Verify migration file syntax: `python -m py_compile migrations/versions/<file>.py`
- [x] Delete temporary test migration
- [ ] Run: `pytest backend/tests/ -v` (verify no regressions)
- [x] Document findings in task completion note

### Scope Boundaries

- ✅ In scope: Validate autogenerate workflow, naming conventions, file validity
- ❌ Out of scope: Create real migrations, modify Alembic configuration, apply/downgrade migrations

---

## Task 2: Upgrade & Downgrade Testing

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Requirement** | R2 (Upgrade Workflow), R3 (Downgrade Workflow) |
| **Design Decision** | D3 (Upgrade/Downgrade Semantics) |
| **Complexity** | Medium |
| **Risk** | Medium |
| **Estimated Effort** | 2h |
| **Dependencies** | Task 1 complete |
| **Files Affected** | `backend/tests/integration/test_migrations.py` (NEW) |
| **Definition of Done** | Integration tests verify upgrade/downgrade behavior on clean database |

### Description

Create integration tests that validate the migration lifecycle: upgrade from clean state, verify schema state, downgrade to clean state.

**What This Task Does:**
1. Create reusable test fixtures for migration testing (fresh PostgreSQL per test)
2. Test `alembic upgrade head` on clean database (should be no-op, 0 migrations applied)
3. Test `alembic downgrade base` on clean database (idempotent no-op)
4. Test state transitions with mock migration (create temporary test migration, apply, revert)
5. Verify `alembic_version` table state before/after transitions

**What This Task Does NOT Do:**
- ❌ Create permanent migrations (E3.T3 does this)
- ❌ Test with real ORM models (E3.T3+ do this)
- ❌ Deploy to production (CI/CD handles this)

### Acceptance Criteria

1. ✅ **Upgrade on Clean DB**: `alembic upgrade head` completes successfully on fresh database (no migrations to apply)
2. ✅ **Idempotent Upgrade**: Re-running `alembic upgrade head` on same database is no-op (no error, no changes)
3. ✅ **Downgrade on Clean DB**: `alembic downgrade base` completes successfully (already at baseline)
4. ✅ **Idempotent Downgrade**: Re-running `alembic downgrade base` is no-op (no error, no changes)
5. ✅ **Version Tracking**: `alembic_version` table state is consistent before/after operations
6. ✅ **Test Isolation**: Each test gets fresh database (via Docker container or fixture scope)
7. ✅ **Error Handling**: Failures are captured and logged; tests verify expected behavior
8. ✅ **No Regressions**: All existing E3.T1 tests still pass

### Implementation Checklist

- [x] Create `backend/tests/integration/test_migrations.py`
- [x] Add migration test fixtures:
  - `fresh_migration_db` (creates clean database for each test)
  - Helper: `run_alembic_upgrade()`
  - Helper: `run_alembic_downgrade()`
- [x] Test 1: Upgrade on clean database (should succeed, no changes)
- [x] Test 2: Idempotent upgrade (re-run, verify no-op)
- [x] Test 3: Downgrade on clean database (should succeed, already at base)
- [x] Test 4: Idempotent downgrade (re-run, verify no-op)
- [x] Test 5: alembic_version table state verification
- [x] Run: `pytest backend/tests/integration/test_migrations.py -v`
- [ ] Run: `pytest backend/tests/ -v` (verify no regressions)

### Test Fixtures

```python
@pytest.fixture
def fresh_migration_db():
    """Provide clean database for migration testing."""
    # Use testcontainers or docker-compose to provide fresh PostgreSQL
    # Yield database URL
    # Teardown: drop database
    yield db_url


def run_alembic_upgrade(db_url, target="head"):
    """Helper: Execute alembic upgrade command."""
    # Set environment variable: DATABASE_MIGRATION_URL
    # Run: alembic upgrade <target>
    # Return exit code and output
    pass


def run_alembic_downgrade(db_url, target="base"):
    """Helper: Execute alembic downgrade command."""
    # Set environment variable: DATABASE_MIGRATION_URL
    # Run: alembic downgrade <target>
    # Return exit code and output
    pass
```

### Scope Boundaries

- ✅ In scope: Test upgrade/downgrade on clean database, idempotency, version tracking
- ❌ Out of scope: Test with real migrations (E3.T3+), test with production data, stress testing

---

## Task 3: CI Integration

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Requirement** | R4 (CI Integration) |
| **Design Decision** | D4 (CI Strategy) |
| **Complexity** | Medium |
| **Risk** | Low |
| **Estimated Effort** | 1.5h |
| **Dependencies** | Task 2 complete |
| **Files Affected** | `.github/workflows/ci.yml` (modify existing), `backend/Dockerfile` (if needed) |
| **Definition of Done** | CI pipeline includes migration validation stage; migration tests pass on main |

### Description

Integrate migration validation into the GitHub Actions CI pipeline. Sequence: lint → type-check → **upgrade database** → run tests → **downgrade database** → success.

**What This Task Does:**
1. Add `alembic upgrade head` stage to `.github/workflows/ci.yml` (after linting, before tests)
2. Configure PostgreSQL service container for CI
3. Set `DATABASE_MIGRATION_URL` environment variable
4. Add `alembic downgrade base` stage after tests
5. Verify CI workflow file syntax
6. Test CI workflow locally (optional: `act` tool or manual GitHub runner)

**What This Task Does NOT Do:**
- ❌ Modify application code
- ❌ Create migrations
- ❌ Deploy to production

### Acceptance Criteria

1. ✅ **CI Workflow Updated**: `.github/workflows/ci.yml` includes migration stages
2. ✅ **PostgreSQL Service**: CI uses containerized PostgreSQL 16 (same as docker-compose)
3. ✅ **Upgrade Stage**: `alembic upgrade head` executes before application tests
4. ✅ **Downgrade Stage**: `alembic downgrade base` executes after application tests
5. ✅ **Environment Setup**: `DATABASE_MIGRATION_URL` properly set for CI environment
6. ✅ **Workflow Syntax**: CI configuration is valid YAML (no syntax errors)
7. ✅ **Fail-Fast**: If `alembic upgrade head` fails, subsequent stages do not run
8. ✅ **Logs**: Alembic output is captured in CI logs (for debugging)
9. ✅ **Regression Test**: Push to main branch, verify CI passes (no broken migrations)

### Implementation Checklist

- [x] Read current `.github/workflows/ci.yml`
- [x] Add PostgreSQL service container:
  ```yaml
  services:
    postgres:
      image: postgres:16-alpine
      env:
        POSTGRES_USER: test
        POSTGRES_PASSWORD: test
        POSTGRES_DB: test
  ```
- [x] Add migration upgrade stage (after linting):
  ```yaml
  - name: Migrate database (upgrade)
    env:
      DATABASE_MIGRATION_URL: postgresql://test:test@localhost/test
    run: |
      cd backend
      alembic upgrade head
  ```
- [x] Add migration downgrade stage (after tests):
  ```yaml
  - name: Downgrade database
    env:
      DATABASE_MIGRATION_URL: postgresql://test:test@localhost/test
    run: |
      cd backend
      alembic downgrade base
  ```
- [x] Verify workflow syntax: `yamllint .github/workflows/ci.yml`
- [x] Commit and push to test branch
- [x] Verify CI runs successfully on GitHub

### Scope Boundaries

- ✅ In scope: Add migration stages to CI, verify workflow syntax, test locally
- ❌ Out of scope: Modify application logic, create actual migrations, production deployment

---

## Task 4: Documentation & Final Validation

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Requirement** | R5 (Migration Development Documentation) |
| **Design Decision** | D6 (Documentation Format) |
| **Complexity** | Low |
| **Risk** | Low |
| **Estimated Effort** | 1.5–2h |
| **Dependencies** | Task 1, Task 2, Task 3 complete |
| **Files Affected** | `backend/ALEMBIC_SETUP.md` (NEW), `backend/README.md`, `docs/00-Project-Context.md` (update links) |
| **Definition of Done** | Documentation complete; all quality gates pass; task ready for merge |

### Description

Create developer-facing documentation on Alembic workflow. Document migration development practices with clear examples. Link from main README and project context.

**What This Task Does:**
1. Create `backend/ALEMBIC_SETUP.md` with:
   - Quick start (5 min to first migration)
   - Workflow (step-by-step for adding ORM model)
   - Example (reference User model from E3.T3)
   - Troubleshooting (common errors)
   - Reference (configuration, env vars)
2. Update `backend/README.md` to link to migration guide
3. Update `docs/00-Project-Context.md` to link to migration guide
4. Run full quality gates (ruff, mypy, pytest)
5. Create comprehensive final audit document

**What This Task Does NOT Do:**
- ❌ Create ORM models or migrations
- ❌ Modify application code

### Acceptance Criteria

1. ✅ **Documentation File**: `backend/ALEMBIC_SETUP.md` created with all sections (Quick Start, Workflow, Example, Troubleshooting, Reference)
2. ✅ **Content Quality**: Documentation is clear, concise, and practical (<500 lines)
3. ✅ **Link Coverage**: README.md and docs/00-Project-Context.md link to migration guide
4. ✅ **Example Clarity**: References E3.T3 (User model) as concrete example
5. ✅ **Troubleshooting**: Covers common errors (connection failures, syntax errors, constraint violations)
6. ✅ **Quality Gates**: Ruff 0 violations, mypy --strict 0 errors, pytest 100% pass rate
7. ✅ **No Regressions**: All E3.T1 tests still pass; no new test failures
8. ✅ **Audit Document**: Create `.github/E3-T2-FINAL-AUDIT.md` documenting completion status, test results, and readiness for E3.T3

### Implementation Checklist

- [x] Create `backend/ALEMBIC_SETUP.md`:
  - [x] Quick Start section (5 min overview)
  - [x] Workflow section (step-by-step with User model example)
  - [x] Example section (walkthrough of User model migration)
  - [x] Troubleshooting section (connection, syntax, constraint errors)
  - [x] Reference section (env vars, Alembic commands, file locations)
- [x] Update `backend/README.md`:
  - [x] Add link to `backend/ALEMBIC_SETUP.md`
  - [x] Add short blurb about Alembic workflow
- [x] Update `docs/00-Project-Context.md`:
  - [x] Add reference to migration guide
  - [x] Update reading order if applicable
- [x] Run quality gates:
  - [x] `ruff check backend/` (0 violations)
  - [x] `mypy backend/ --strict` (0 errors)
  - [x] `pytest backend/tests/ -v` (100% pass)
  - [x] `python -m compileall backend/` (success)
- [x] Create final audit document: `.github/E3-T2-FINAL-AUDIT.md`
- [x] Commit with message: "E3.T2: Alembic Configuration & Migration Workflow Complete"

### Documentation Outline

**backend/ALEMBIC_SETUP.md:**
```
1. Quick Start (what to do first)
   - Prerequisites (Python, Docker, Alembic)
   - Common commands (upgrade, downgrade, revision)
   
2. Workflow (how to add a migration)
   - Create ORM model
   - Run `alembic revision --autogenerate`
   - Review migration
   - Test locally
   - Commit
   
3. Example (User model walkthrough)
   - Define User model
   - Generate migration
   - Inspect generated SQL
   - Run upgrade/downgrade
   
4. Troubleshooting (common issues)
   - "Connection refused" → check DATABASE_MIGRATION_URL
   - "ImportError" → check Base import
   - "Column already exists" → migration already applied
   
5. Reference
   - Environment variables
   - Alembic commands
   - File structure
   - Links to docs
```

### Scope Boundaries

- ✅ In scope: Create documentation, link from README, update context docs, final audit
- ❌ Out of scope: Modify ORM code, create migrations, deploy changes

---

## Summary

| Task | Requirement | Effort | Status |
|---|---|---|---|
| Task 1: Autogenerate Validation | R1 | 1.5h | ⏳ Pending |
| Task 2: Upgrade/Downgrade Testing | R2, R3 | 2h | ⏳ Pending |
| Task 3: CI Integration | R4 | 1.5h | ⏳ Pending |
| Task 4: Documentation & Validation | R5 | 1.5–2h | ⏳ Pending |
| **Total** | R1–R5 | **7–8h** | ⏳ Ready to Start |

---

## Quality Gates (Final Validation)

After all tasks complete:
- [x] Ruff: `ruff check .` → 0 violations
- [x] MyPy: `mypy . --strict` → 0 errors
- [x] Pytest: `pytest backend/tests/ -v` → 100% pass rate
- [x] Compileall: `python -m compileall backend/` → success
- [x] No regressions in E3.T1 tests
- [x] No regressions in E2 tests
- [x] Git: All changes committed; branch clean

---

## Readiness Checklist

Before starting Task 1:
- ✅ E3.T1 complete (database foundation, fixtures, engine disposal)
- ✅ Alembic verified as async-compatible (E3.T1 audit)
- ✅ PostgreSQL 16 container operational (`docker compose up`)
- ✅ Requirements and design reviewed and approved
- ✅ All dependencies available (alembic, sqlalchemy, pytest, testcontainers)

---

## References

- 22-Engineering-Backlog: E3.T2
- 06-Repository-Structure §3: migrations/ directory
- 07-Backend-Development-Standards §8: migration standards
- 12-CI-CD-Architecture §3: CI stages
- E3.T1 Complete: database foundation, fixtures, engine disposal
- Design decisions: D1–D6 (documented in design.md)
