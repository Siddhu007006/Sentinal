# E3.T2 Design Document

## Specification Document

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-alembic-t2/design.md |
| **Feature** | alembic-configuration-t2 |
| **Status** | In Review |
| **Traces to** | 22-Engineering-Backlog E3.T2 |

---

## Design Decisions

### Design Decision 1: Migration Naming & Organization

**Requirement:** R1 (Migration Generation Workflow)

**Decision:**
Use Alembic's default naming convention: timestamp-based revision IDs with semantic slugs.
- Format: `YYYYMMDD_HHMM_<alembic-revision-id>_<slug>.py`
- Example: `20250117_1430_001_create_users_table.py`
- Organization: All migrations in single `backend/migrations/versions/` directory (flat structure)
- Alembic tracks order via `down_revision` and `up_revision` metadata in each file

**Rationale:**
- Timestamp-based names prevent merge conflicts (each developer gets unique timestamp)
- Sequential numbering (`001`, `002`, …) provides human-readable ordering
- Single flat directory simplifies discovery and maintenance
- Alembic handles dependency chain automatically via revision metadata
- Consistent with industry standard (Django, SQLAlchemy best practices)

**Trade-offs:**
- ❌ Single directory becomes large after many migrations (mitigated by timestamping and Alembic state)
- ✅ No need for complex directory structure or manual version numbering
- ✅ Easy to understand evolution of schema

**Implementation:**
- `backend/migrations/script.py.mako` already configured with this format (verified in E3.T1)
- No changes required; use as-is

---

### Design Decision 2: Alembic Autogenerate Workflow

**Requirement:** R1 (Migration Generation Workflow)

**Decision:**
Workflow for developers adding a new ORM model:
1. Create ORM model class in `backend/app/models/<model_name>.py`
2. Register model with Base metadata (via import in `app/models/__init__.py`)
3. Run: `alembic revision --autogenerate -m "Add <table> table"`
4. Review generated migration (inspect `backend/migrations/versions/<timestamp>_….py`)
5. Test locally: `alembic upgrade head` (verify schema matches ORM)
6. Commit both model and migration together

**Rationale:**
- Autogenerate only works when ORM models define the schema
- Pairing model + migration in same commit ensures consistency
- Code review process catches schema mistakes before merge
- Testing locally ensures migration runs cleanly

**Alembic Configuration (already in place from E3.T1):**
- `backend/migrations/env.py` imports `app.infrastructure.database.base.Base`
- `target_metadata = Base.metadata` provides schema for autogenerate
- Async pattern handling (asyncpg → psycopg2 conversion) already present

**Non-Idempotent Note:**
- `alembic revision --autogenerate` is **not idempotent** (creates new migration each time)
- Always review generated migration before commit
- Manual edits should be done with care (don't remove important changes)

---

### Design Decision 3: Upgrade & Downgrade Semantics

**Requirement:** R2 (Upgrade Workflow), R3 (Downgrade Workflow)

**Decision:**
Alembic upgrade/downgrade operate on the migration chain tracked in `alembic_version` table:
- **Upgrade:** Apply all pending migrations in order (`alembic upgrade head`)
- **Downgrade:** Reverse all migrations to baseline (`alembic downgrade base`)
- Both are idempotent (already-applied/already-downgraded migrations are no-ops)

**Transaction Model:**
- Each migration runs in an implicit PostgreSQL transaction
- If any statement fails, entire migration is rolled back by database
- Migration history (`alembic_version`) is updated atomically with schema changes
- On failure, `alembic_version` is NOT updated, so retry attempts the same migration again

**Idempotency:**
- `alembic upgrade head` on already-upgraded db: no-op (checks `alembic_version`, sees head already applied)
- `alembic downgrade base` on already-downgraded db: no-op (checks `alembic_version`, sees base already reached)
- Safe to re-run without side effects

**DDL & Transactions:**
- PostgreSQL wraps DDL (CREATE TABLE, ALTER COLUMN) in implicit transactions
- Alembic respects this wrapping; no special handling required
- Non-transactional DDL (PostgreSQL 9.0+): not applicable; all DDL is transactional

---

### Design Decision 4: CI Integration Strategy

**Requirement:** R4 (CI Integration of Migration Workflow)

**Decision:**
Add migration validation stage to `.github/workflows/ci.yml`:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install -e ".[dev]"
      
      - name: Lint (ruff)
        run: ruff check .
      
      - name: Type check (mypy)
        run: mypy .
      
      # NEW: Migration validation stage
      - name: Migrate database (upgrade)
        env:
          DATABASE_MIGRATION_URL: postgresql://test:test@localhost/test
        run: |
          cd backend
          alembic upgrade head
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost/test
        run: pytest backend/tests/ -v
      
      - name: Downgrade database
        env:
          DATABASE_MIGRATION_URL: postgresql://test:test@localhost/test
        run: |
          cd backend
          alembic downgrade base
```

**Sequence:**
1. ✅ Lint & type check (existing)
2. ✅ **Upgrade database** (NEW: apply all pending migrations)
3. ✅ Run application tests (against migrated schema)
4. ✅ **Downgrade database** (NEW: verify reversibility)

**Rationale:**
- Validates migrations work on every PR/push
- Catches broken migrations before they reach main
- Downgrade tests ensure rollback procedures work
- Isolated PostgreSQL container ensures clean state each run
- Matches recommended practices (Django, Alembic docs)

**Trade-offs:**
- ⏱️ Adds ~30-60 seconds to CI (migration apply/test/revert)
- ✅ Catches critical issues early
- ✅ Prevents "migrations work on my machine but not in prod" scenarios

---

### Design Decision 5: Failure Handling & Error Messages

**Requirement:** R4 (CI Integration)

**Decision:**
On migration failures:
1. Alembic exits with non-zero status code
2. Error message is captured in CI logs (GitHub Actions automatically archives)
3. CI stage marked as failed (prevents merge)
4. Developer must fix migration locally before re-pushing

**Handling Common Scenarios:**
- **Database connection fails** → explicit error message from Alembic; check DATABASE_MIGRATION_URL env var
- **Migration syntax error** → Python import error; check migration script for typos
- **Constraint violation during upgrade** → schema constraint issue; may need manual migration editing
- **Already-applied migration** → idempotent behavior; no error, treated as no-op

**No Automatic Rollback:**
- If migration fails, database is automatically rolled back by PostgreSQL (transactional DDL)
- Developer must investigate, fix, and re-run
- Manual recovery only needed for catastrophic failures (e.g., database connection lost mid-migration)

---

### Design Decision 6: Documentation Location & Format

**Requirement:** R5 (Migration Development Documentation)

**Decision:**
Create `backend/ALEMBIC_SETUP.md` with:
1. **Quick Start** section (5 min to first migration)
2. **Workflow** section (step-by-step for adding ORM model)
3. **Examples** section (reference User model from E3.T3)
4. **Troubleshooting** section (common errors and fixes)
5. **Reference** section (Alembic configuration, environment variables)

**Location:**
- File: `backend/ALEMBIC_SETUP.md`
- Linked from: `backend/README.md` and `docs/00-Project-Context.md`
- Keep it concise (< 500 lines) for developer accessibility

**Audience:**
- New engineers onboarding to the project
- Developers adding new ORM models
- DevOps/SRE reviewing migration procedures

---

## Architecture Diagram

```
Developer Workflow
==================

1. Create ORM Model
   └─ File: app/models/user.py
      ```python
      class User(BaseModel):
          email: Mapped[str] = mapped_column(unique=True)
          # ... fields ...
      ```

2. Register Model Metadata
   └─ File: app/models/__init__.py
      ```python
      from app.models.user import User  # Import triggers registration with Base
      ```

3. Generate Migration
   └─ Command: alembic revision --autogenerate -m "Add users table"
   └─ Output: migrations/versions/20250117_1430_001_add_users_table.py
   └─ Content:
      ```python
      def upgrade() -> None:
          op.create_table('users', ...)  # Generated by Alembic
      
      def downgrade() -> None:
          op.drop_table('users')
      ```

4. Review & Test Locally
   └─ Command: alembic upgrade head
   └─ Command: pytest  # Run tests against migrated schema
   └─ Command: alembic downgrade base

5. Commit & Push
   └─ Commit: User model + migration together
   └─ Push: to feature branch

6. CI Validation (Automatic)
   └─ Step 1: ruff check . (lint)
   └─ Step 2: mypy . (type check)
   └─ Step 3: alembic upgrade head (apply migrations)
   └─ Step 4: pytest (run tests)
   └─ Step 5: alembic downgrade base (verify rollback)

7. Merge
   └─ If all CI checks pass, safe to merge


Alembic State Machine
=====================

Database State Transitions:

[Clean] --upgrade-head--> [Schema v1] --upgrade-head--> [Schema v2]
          (apply m001)              (apply m002)

[Schema v2] --downgrade-base--> [Clean]
              (reverse m002, m001)

Migration Ordering (tracked in alembic_version table):
- m001: down_revision=None,  up_revision=m002 (initial)
- m002: down_revision=m001,  up_revision=m003
- m003: down_revision=m002,  up_revision=None (current head)


Integration Points
==================

With E3.T1 (Database Foundation):
├─ Uses AsyncSession fixture (for app tests)
├─ Uses database connection pool (for migrations)
└─ Uses Base.metadata (for autogenerate) ✅

With E3.T3+ (ORM Models):
├─ Models import from Base (inherited by E3.T2)
├─ Models trigger `alembic revision --autogenerate`
└─ Migrations generated via E3.T2 workflow ✅

With CI/CD (E1.T6, E12.T3):
├─ `.github/workflows/ci.yml` includes migration stage
├─ Migrations tested on every PR/push
└─ Deployment requires successful migration pipeline ✅
```

---

## Design Clarifications

### Q1: What if `alembic revision --autogenerate` detects no changes?
**A:** Alembic creates an empty migration with up/downgrade as pass statements. This is harmless but unnecessary. Best practice: review before committing. Document in contributor guide.

### Q2: Should we create an initial empty migration now?
**A:** No. Wait for E3.T3 (User model) to create the first real migration. Empty migrations have no value and add confusion.

### Q3: How do we handle database schema conflicts during parallel development?
**A:** Alembic uses timestamp-based naming to avoid conflicts. Each developer's `alembic revision --autogenerate` creates a unique migration. If conflicts arise (rare), merge conflicts happen in git, not in Alembic. Standard conflict resolution applies.

### Q4: What about test database isolation?
**A:** CI uses separate PostgreSQL container per run. Each test run: fresh database → upgrade head → run tests → downgrade base. No test pollution between CI runs. Between unit tests, use the conftest.py fixtures from E3.T1 (transaction rollback).

### Q5: Do we need separate migration credentials?
**A:** Out of scope for E3.T2. Security considerations (separate migration user, least privilege) are deferred to E8 (Security: Advanced).

---

## Stateful Component Review

### Transaction Boundaries ✅
- **Decision D3** explicitly covers upgrade/downgrade transaction semantics
- PostgreSQL implicit wrapping; Alembic respects it
- Failure handling: entire migration rolled back, no partial state

### Connection Lifecycle ✅
- **Decision D4** (CI Integration) uses fresh PostgreSQL container per run
- Isolated from application runtime
- Connection pooling not applicable to migrations (simple sync connection)

### Concurrency ✅
- Migrations are sequential (Alembic enforces ordering via revision chain)
- No concurrent migrations (would corrupt schema)
- Database provides row-level locking if needed (deferred to application layer)

### Failure Modes ✅
- **Database unavailable** → Alembic connection fails, CI stage fails (expected)
- **Migration syntax error** → Python import error, caught during migration test
- **Constraint violation** → Database constraint violation during upgrade, entire transaction rolled back
- **Partial migration** → Not possible (transactional DDL); either full success or full rollback

---

## Risks Addressed

| Risk | Mitigation | D-Ref |
|---|---|---|
| Migration ordering bug | Alembic enforces ordering via revision chain; CI tests all transitions | D1, D4 |
| Naming conflicts (parallel dev) | Timestamp-based naming prevents collisions | D1 |
| Unfixable migrations in main | CI tests every migration; broken migrations prevent merge | D4 |
| Database rollback failures | Transactional DDL (PostgreSQL); auto-rollback on error | D3 |
| Developer confusion | Clear documentation (D6); reference example (E3.T3 User model) | D6 |

---

## References

- 22-Engineering-Backlog: E3.T2 specification
- 06-Repository-Structure §3: `migrations/` directory
- 07-Backend-Development-Standards §8: Migration standards
- 12-CI-CD-Architecture §3: CI stages and validation
- E3.T1 Audit: Alembic async configuration verified
- Alembic Documentation: https://alembic.sqlalchemy.org/
