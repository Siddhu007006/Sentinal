# E3.T8 — Audit Logs ORM Model and Migration — Task Breakdown

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-audit-logs-t8/tasks.md |
| **Feature** | audit-logs-orm-model-t8 |
| **Status** | Ready for Implementation |
| **Total Tasks** | 6 (+ quality gates) |

---

## Task Overview

| # | Task | Owner | Status | Effort |
|---|---|---|---|---|
| 1 | Implement AuditLog ORM Model | Dev | 🔲 Pending | 1h |
| 2 | Export AuditLog from models/__init__.py | Dev | 🔲 Pending | 10m |
| 3 | Generate Alembic Migration | Dev | 🔲 Pending | 10m |
| 4 | Review and Validate Migration | Dev | 🔲 Pending | 20m |
| 5 | Create Unit and Integration Tests | Dev | 🔲 Pending | 1.5h |
| 6 | Run Quality Gates (ruff, mypy, pytest) | Dev | 🔲 Pending | 20m |

---

## Task 1: Implement AuditLog ORM Model

**File:** `backend/app/models/audit_log.py`

**Acceptance Criteria:**

- [ ] File created: `backend/app/models/audit_log.py`
- [ ] AuditLog class defined (inherits from BaseModel)
- [ ] All required fields present with correct types:
  - [ ] id (Mapped[UUID], PK, auto-generated from BaseModel)
  - [ ] actor_id (Mapped[UUID | None], FK to users.id, nullable, indexed)
  - [ ] actor_role (Mapped[str], VARCHAR(20), captures role at time)
  - [ ] action (Mapped[str], VARCHAR(100), e.g., "CREATE_ASSET")
  - [ ] resource_type (Mapped[str], VARCHAR(100), e.g., "DigitalAsset")
  - [ ] resource_id (Mapped[UUID], identifies affected entity)
  - [ ] before_state (Mapped[dict | None], JSONB, nullable)
  - [ ] after_state (Mapped[dict | None], JSONB, nullable)
  - [ ] ip_address (Mapped[str | None], INET, nullable)
  - [ ] request_id (Mapped[str | None], VARCHAR(255), nullable)
  - [ ] user_agent (Mapped[str | None], VARCHAR(500), nullable)
  - [ ] success (Mapped[bool], default=True)
  - [ ] failure_reason (Mapped[str | None], VARCHAR(1000), nullable)
  - [ ] occurred_at (Mapped[datetime], TIMESTAMPTZ, server_default=now())
- [ ] __tablename__ = "audit_logs" defined
- [ ] Unique constraint on (actor_id, resource_id, occurred_at)
- [ ] Indexes created:
  - [ ] Index on actor_id
  - [ ] Composite index on (resource_type, resource_id)
  - [ ] Index on occurred_at DESC
- [ ] __repr__() method defined (excludes state blobs, ip_address, user_agent)
- [ ] Comprehensive docstrings on class and all fields
- [ ] Comments document immutability constraint
- [ ] Follows User model patterns exactly
- [ ] No syntax errors: `python -m py_compile backend/app/models/audit_log.py`
- [ ] No import errors: Can import from app.models.audit_log

**Implementation Notes:**

- Pattern: Follow `backend/app/models/user.py` exactly
- Use Mapped[] syntax for all fields (SQLAlchemy 2.0 style)
- Foreign key: `ForeignKey("users.id")`
- JSONB type: `from sqlalchemy.dialects.postgresql import JSON` (use JSON for JSONB type)
- DateTime type: `TIMESTAMP(timezone=True)` with UTC
- Comments explain immutability at ORM level
- Docstring references requirement traceability

---

## Task 2: Export AuditLog from models/__init__.py

**File:** `backend/app/models/__init__.py`

**Acceptance Criteria:**

- [ ] Import added: `from app.models.audit_log import AuditLog`
- [ ] AuditLog added to __all__ list
- [ ] Import succeeds: `python -c "from app.models import AuditLog; print(AuditLog)"`
- [ ] Module exports are complete and correct

**Implementation Notes:**

- Add import in alphabetical order with existing imports
- Add to __all__ in alphabetical order
- No circular imports

---

## Task 3: Generate Alembic Migration

**Command:**
```bash
cd backend
alembic revision --autogenerate -m "Add audit_logs table"
```

**Acceptance Criteria:**

- [ ] Migration file created in `backend/migrations/versions/`
- [ ] File named with pattern: `YYYYMMDD_HHMM_<rev>_add_audit_logs_table.py`
- [ ] Migration is valid Python (no syntax errors)
- [ ] Can import: `python -c "import sys; sys.path.insert(0, 'backend'); from migrations.versions.<name> import upgrade, downgrade"`
- [ ] Migration file located in workspace and confirmed

**Expected Output:**

Migration file should contain:
- `upgrade()` function that creates audit_logs table
- `downgrade()` function that drops audit_logs table
- All columns with correct types
- All constraints (UNIQUE, FK)
- All indexes

---

## Task 4: Review and Validate Migration

**Manual Review Checklist:**

- [ ] Table name is "audit_logs" (matches __tablename__)
- [ ] All columns present with correct PostgreSQL types:
  - [ ] id: UUID, PRIMARY KEY
  - [ ] actor_id: UUID, REFERENCES users(id), NULL allowed
  - [ ] actor_role: VARCHAR(20), NOT NULL
  - [ ] action: VARCHAR(100), NOT NULL
  - [ ] resource_type: VARCHAR(100), NOT NULL
  - [ ] resource_id: UUID, NOT NULL
  - [ ] before_state: JSONB, NULL allowed
  - [ ] after_state: JSONB, NULL allowed
  - [ ] ip_address: INET, NULL allowed
  - [ ] request_id: VARCHAR(255), NULL allowed
  - [ ] user_agent: VARCHAR(500), NULL allowed
  - [ ] success: BOOLEAN, NOT NULL, DEFAULT true
  - [ ] failure_reason: VARCHAR(1000), NULL allowed
  - [ ] occurred_at: TIMESTAMP WITH TIMEZONE, NOT NULL, DEFAULT now()
  - [ ] created_at: TIMESTAMP WITH TIMEZONE, NOT NULL, DEFAULT now()
  - [ ] updated_at: TIMESTAMP WITH TIMEZONE, NOT NULL, DEFAULT now()
  - [ ] deleted_at: TIMESTAMP WITH TIMEZONE, NULL allowed
- [ ] Unique index on (actor_id, resource_id, occurred_at)
- [ ] Index on actor_id
- [ ] Composite index on (resource_type, resource_id)
- [ ] Index on occurred_at (DESC order preferred)
- [ ] Foreign key: actor_id → users.id
- [ ] No circular dependencies
- [ ] downgrade() function reverses all changes

**Validation Commands:**

```bash
# Test upgrade/downgrade cycle
cd backend
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# Verify table structure
psql $DATABASE_URL -c "\d audit_logs"
psql $DATABASE_URL -c "\di audit_logs*"
```

---

## Task 5: Create Unit and Integration Tests

**File:** `backend/tests/unit/test_audit_log_model.py`

**Unit Tests (No Database Required):**

- [ ] test_instantiate_audit_log_with_all_fields()
  - Create AuditLog with all fields populated
  - Verify all fields set correctly
  - Validates: R5 AC #2

- [ ] test_instantiate_audit_log_with_required_fields()
  - Create AuditLog with only required fields
  - Verify defaults applied (success=true, state=None)
  - Validates: R5 AC #3

- [ ] test_actor_id_can_be_none()
  - Create AuditLog with actor_id=None
  - Verify nullable field works (system actions)
  - Validates: R1 AC #3

- [ ] test_default_success_is_true()
  - Create AuditLog with success not specified
  - Verify defaults to True
  - Validates: R5 AC #3

- [ ] test_before_state_can_be_none()
  - Create AuditLog with before_state=None
  - Verify nullable field works (creates have no before state)
  - Validates: R1 AC #3

- [ ] test_after_state_can_be_none()
  - Create AuditLog with after_state=None
  - Verify nullable field works (deletes have no after state)
  - Validates: R1 AC #3

- [ ] test_field_types_are_correct()
  - Verify all fields have correct Python types
  - Validates: R5 AC #4

- [ ] test_repr_returns_string()
  - Call repr(audit_log)
  - Verify returns string
  - Validates: R5 AC #6

- [ ] test_repr_excludes_state_blobs()
  - Create audit_log with before_state/after_state populated
  - Call repr()
  - Verify state content NOT in repr string (for security)
  - Validates: R5 AC #6

- [ ] test_repr_includes_action_and_actor()
  - Verify repr includes action type and actor info
  - Validates: R5 AC #6

- [ ] test_audit_log_exports_from_models()
  - `from app.models import AuditLog`
  - Verify import succeeds
  - Validates: R1 AC #8

- [ ] test_model_has_tablename()
  - Verify __tablename__ == "audit_logs"
  - Validates: R1 AC #5

- [ ] test_model_inherits_from_basemodel()
  - Verify issubclass(AuditLog, BaseModel)
  - Validates: R1 AC #2

**Integration Tests (With Database):**

- [ ] test_insert_audit_log_succeeds(db_session)
  - Create and insert valid audit record
  - Commit to database
  - Verify insert succeeded (id set, created_at set)
  - Validates: R2 AC #6

- [ ] test_select_audit_logs_succeeds(db_session)
  - Insert audit record
  - Query via session.query(AuditLog)
  - Verify SELECT allowed
  - Validates: R2 AC #7

- [ ] test_update_audit_logs_fails_with_permission_error(db_session)
  - Insert audit record
  - Attempt: `session.execute(update(AuditLog).where(...).values(...))`
  - Catch psycopg2.errors.InsufficientPrivilege
  - Verify UPDATE denied by database
  - Validates: R2 AC #4

- [ ] test_delete_audit_logs_fails_with_permission_error(db_session)
  - Insert audit record
  - Attempt: `session.execute(delete(AuditLog).where(...))`
  - Catch psycopg2.errors.InsufficientPrivilege
  - Verify DELETE denied by database
  - Validates: R2 AC #5

- [ ] test_unique_constraint_violation(db_session)
  - Insert audit record with (actor_id=A, resource_id=B, occurred_at=T)
  - Attempt to insert duplicate with exact same values
  - Catch IntegrityError (unique constraint violation)
  - Verify constraint enforced
  - Validates: R2 AC #2

**Test File Structure:**

```python
# Unit Tests Section (no database)
def test_instantiate_audit_log_with_all_fields() -> None:
    """..."""

# Integration Tests Section (with database)
@pytest.mark.asyncio
async def test_insert_audit_log_succeeds(db_session: AsyncSession) -> None:
    """..."""
```

**Running Tests:**

```bash
cd backend

# Unit tests only
pytest tests/unit/test_audit_log_model.py -v

# All tests (unit + integration)
pytest tests/unit/test_audit_log_model.py -v
pytest tests/ -v  # Verify no regressions
```

---

## Task 6: Run Quality Gates

**Command Set:**

```bash
cd backend

# 1. Ruff (linter) - Check for style violations
ruff check app/models/audit_log.py
# Expected: 0 violations

# 2. MyPy (type checker) - Strict type checking
mypy app/models/audit_log.py --strict
# Expected: 0 errors

# 3. Pytest (unit tests) - AuditLog tests
pytest tests/unit/test_audit_log_model.py -v
# Expected: All tests pass

# 4. Pytest (all tests) - Regression check
pytest tests/ -v
# Expected: All tests pass (no regressions in E3.T1-E3.T7)
```

**Acceptance Criteria:**

- [ ] Ruff check: 0 violations
- [ ] MyPy check: 0 errors (strict mode)
- [ ] Pytest (audit log tests): All tests pass ✅
- [ ] Pytest (all tests): No regressions ✅
- [ ] No new warnings or errors introduced

**If Issues Found:**

1. **Ruff violations:** Run `ruff check --fix app/models/audit_log.py` (auto-fix many issues)
2. **MyPy errors:** Add type annotations or `# type: ignore` comments (with justification)
3. **Pytest failures:** Review test output, debug in test_audit_log_model.py
4. **Regressions:** Check if changes affected other models or migrations

---

## Implementation Order

1. ✅ Create design.md (planning complete)
2. ✅ Create tasks.md (this document)
3. **→ Task 1:** Implement audit_log.py (core model)
4. **→ Task 2:** Export from models/__init__.py (discovery)
5. **→ Task 3:** Generate migration (schema versioning)
6. **→ Task 4:** Review migration (quality control)
7. **→ Task 5:** Create tests (coverage & validation)
8. **→ Task 6:** Quality gates (final check)

---

## Definition of Done

- [ ] All 6 tasks completed
- [ ] All acceptance criteria met
- [ ] All tests passing (0 regressions)
- [ ] Ruff: 0 violations
- [ ] MyPy: 0 errors
- [ ] Design document reviewed
- [ ] Code review completed
- [ ] Commit ready for merge

---

## Key Files

| File | Purpose | Status |
|---|---|---|
| `backend/app/models/audit_log.py` | AuditLog ORM model | 🔲 To Create |
| `backend/app/models/__init__.py` | Model exports | 🔲 To Update |
| `backend/migrations/versions/*.py` | Alembic migration | 🔲 To Generate |
| `backend/tests/unit/test_audit_log_model.py` | Unit + integration tests | 🔲 To Create |

---

## References

- Requirements: `.kiro/specs/epic-3-database-foundation-audit-logs-t8/requirements.md`
- Design: `.kiro/specs/epic-3-database-foundation-audit-logs-t8/design.md`
- User Model Example: `backend/app/models/user.py`
- BaseModel: `backend/app/infrastructure/database/base.py`
- Test Patterns: `backend/tests/unit/test_user_model.py`
- Test Fixtures: `backend/tests/conftest.py`
- Alembic Docs: https://alembic.sqlalchemy.org/
