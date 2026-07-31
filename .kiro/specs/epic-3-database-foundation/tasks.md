# Task List

## E3.T1 — Database Foundation: Connection & Session Management

**Objective:** Complete database connectivity layer by wiring DI, implementing graceful shutdown, creating test infrastructure, and verifying Alembic.

**Task Execution Order:** Sequential (tasks 1–4 are independent prerequisites; tasks 5–6 depend on 1–4)

---

## Task 1: Export Database Dependency

**Metadata:**
| Field | Value |
|-------|-------|
| **Requirement** | R1: Export Database Dependency |
| **Design Decision** | D1: Re-export from dependencies.py |
| **Complexity** | Low |
| **Risk** | Low |
| **Files** | `app/core/dependencies.py` |

**Description:**

Export `get_db_session()` from `app.core.dependencies` so route handlers can use it via FastAPI's `Depends()` mechanism. Currently, `get_db_session()` exists in `app.infrastructure.database.session`, but is not exposed through the DI interface.

**Deliverables:**

1. **Export Statement**: Add import to `app/core/dependencies.py`:
   ```python
   from app.infrastructure.database.session import get_db_session
   ```

2. **Type Hints Preserved**: Verify `AsyncSession` type hint is available when imported:
   ```python
   from app.core.dependencies import get_db_session
   # Should be recognized by mypy as returning AsyncGenerator[AsyncSession, None]
   ```

3. **Verify Existing Imports**: Ensure no circular imports or side effects:
   - `get_settings()` still works
   - `get_logger()` still works
   - `get_request_context()` still works

**Acceptance Criteria:**

- ✅ Import statement added to `app/core/dependencies.py`
- ✅ `from app.core.dependencies import get_db_session` succeeds
- ✅ MyPy recognizes type: `AsyncGenerator[AsyncSession, None]`
- ✅ Route handler can declare: `db: AsyncSession = Depends(get_db_session)`
- ✅ No existing dependencies broken (ruff + mypy + pytest pass)

**Test:**
```python
# Pseudo-test to verify import works
from app.core.dependencies import get_db_session

assert get_db_session is not None
assert callable(get_db_session)
```

---

## Task 2: Engine Lifecycle — Dispose on Shutdown

**Metadata:**
| Field | Value |
|-------|-------|
| **Requirement** | R2: Application Shutdown Lifecycle |
| **Design Decision** | D2: Engine disposal in lifespan shutdown |
| **Complexity** | Low |
| **Risk** | Medium |
| **Files** | `app/main.py`, `app/infrastructure/database/session.py` |

**Description:**

Add database engine disposal to the application lifespan shutdown hook. This ensures the connection pool is properly closed when the application terminates, preventing resource leaks.

**Deliverables:**

1. **Import Engine Reference**: In `app/main.py`, import the engine module:
   ```python
   from app.infrastructure.database.session import _engine
   ```

2. **Add Disposal to Shutdown**: In the lifespan context manager's shutdown block (after `yield`):
   ```python
   @asynccontextmanager
   async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
       # ... startup ...
       yield
       # --- Shutdown ---
       if _engine is not None:
           try:
               await _engine.dispose()
               logger.info("Database connection pool disposed")
           except Exception as e:
               logger.error(f"Failed to dispose database pool: {e}")
               # Error logged but does not prevent termination
   ```

3. **Independent Execution**: Ensure disposal runs regardless of other shutdown failures:
   - Wrap in try/except (already shown above)
   - Place in finally block if other shutdown steps are added later
   - Do not raise exception on failure

4. **Logging**: Log both success and failure cases

**Acceptance Criteria:**

- ✅ Shutdown block modified with disposal code
- ✅ Engine disposal completes without crashing the shutdown process
- ✅ Application terminates cleanly even if disposal encounters errors
- ✅ Failure is logged (searchable in logs)
- ✅ No regression: existing lifespan behavior (logging initialization) unaffected

**Test:**
```python
# Pseudo-test to verify disposal happens
# Start app, make request, signal graceful shutdown
# Verify: engine is disposed (check logs for "Database connection pool disposed")
```

---

## Task 3: Database Test Infrastructure

**Metadata:**
| Field | Value |
|-------|-------|
| **Requirement** | R3: Database Test Fixtures |
| **Design Decision** | D3: Reusable fixtures with transaction rollback |
| **Complexity** | Medium |
| **Risk** | Medium |
| **Files** | `tests/conftest.py` (new), `backend/.env` (test config) |

**Description:**

Create `tests/conftest.py` with reusable fixtures for database integration testing. Fixtures provide a clean, isolated database session for each test using transaction rollback pattern.

**Deliverables:**

1. **Create conftest.py** at `backend/tests/conftest.py`:

   ```python
   import pytest
   from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
   from app.core.settings import Settings
   from app.infrastructure.database.base import Base


   @pytest.fixture(scope="session")
   async def async_engine():
       """Create async engine once per test session."""
       settings = Settings()
       engine = create_async_engine(
           settings.database.url,
           echo=False,
       )
       yield engine
       await engine.dispose()


   @pytest.fixture(scope="function")
   async def db_session(async_engine):
       """Provide session with transaction rollback on cleanup."""
       async with AsyncSession(async_engine, expire_on_commit=False) as session:
           try:
               yield session
               # Explicit rollback: undo all mutations from test
               await session.rollback()
           except Exception:
               await session.rollback()
               raise
           finally:
               await session.close()


   @pytest.fixture(scope="function")
   async def clean_db(db_session):
       """Verify clean state before test (rollback from prior test ensures this)."""
       # No-op: just verify session is ready
       yield
       # Cleanup handled by db_session fixture
   ```

2. **Session-Scoped Engine Fixture**:
   - Created once per test session
   - Reused across all tests (faster than per-test creation)
   - Disposed after all tests complete

3. **Function-Scoped Session Fixture**:
   - New session per test
   - Explicit transaction rollback on cleanup
   - Returns connection to pool

4. **Optional Application Fixture** (only create if actually needed):
   - Skip for now; can be added if E3.T2+ tests need full app instance

**Acceptance Criteria:**

- ✅ `tests/conftest.py` created and valid Python
- ✅ Fixtures auto-discovered by pytest (no manual registration needed)
- ✅ Session isolation verified: data from test_a absent in test_b
- ✅ Rollback pattern works: insert-commit in fixture setup, rollback on cleanup
- ✅ MyPy + Ruff pass (type hints correct, no linting issues)
- ✅ Pytest discovers fixtures: `pytest --fixtures | grep db_session`

**Test:**
```python
# Example test using fixture (verifies isolation)
@pytest.mark.asyncio
async def test_fixture_isolation_a(db_session):
    # Insert test data
    await db_session.execute(insert(User).values(email="test@example.com"))
    # Test logic...


@pytest.mark.asyncio
async def test_fixture_isolation_b(db_session):
    # Should NOT see data from test_a
    result = await db_session.execute(
        select(User).where(User.email == "test@example.com")
    )
    assert result.scalar_one_or_none() is None  # Rollback cleared it
```

---

## Task 4: Alembic Configuration Verification

**Metadata:**
| Field | Value |
|-------|-------|
| **Requirement** | R4: Alembic Configuration Verification |
| **Design Decision** | D4: Verify async compatibility (inspection only) |
| **Complexity** | Low |
| **Risk** | Low |
| **Files** | `backend/alembic.ini`, `backend/migrations/env.py` (inspect only) |

**Description:**

Verify that Alembic is configured correctly for async SQLAlchemy operations. This is an inspection task; no modifications required unless the audit discovers incompatibility.

**Deliverables:**

1. **Inspect alembic.ini**:
   - Verify `DATABASE_URL` is read from environment variable (not hardcoded)
   - Check that `sqlalchemy.url` is not set to a literal value
   - Expected: `sqlalchemy.url` line is commented or empty (read from env at runtime)

2. **Inspect migrations/env.py**:
   - Verify async pattern compatibility:
     - Look for `create_async_engine` usage OR async runner (asyncio.run pattern)
     - Check that import statement works: `from app.infrastructure.database.base import Base`
     - Ensure no circular imports
   - Expected: Can be used with async engine without modification

3. **Test Alembic Commands** (verify, don't execute upgrade/downgrade):
   - Run: `alembic revision --autogenerate` (should complete without error, even if no models exist)
   - Do NOT run: `alembic upgrade head` (no migrations exist yet; belongs in E3.T2)
   - Do NOT run: `alembic downgrade base` (deferred to E3.T2)

4. **Document Findings**:
   - If verification passes: Record "✅ Verified, no changes needed"
   - If incompatible: Record specific incompatibility and plan fix for E3.T2

**Acceptance Criteria:**

- ✅ `alembic.ini` verified to read DATABASE_URL from environment
- ✅ `migrations/env.py` compatible with async engine
- ✅ `alembic revision --autogenerate` completes successfully
- ✅ No changes required to Alembic configuration (outcome: verified, ready for E3.T2)
- ✅ Verification results documented (for final audit)

**Verification Checklist** (record in final audit):
- [ ] `alembic.ini` reads DATABASE_URL from env
- [ ] `env.py` uses async pattern (create_async_engine or asyncio.run)
- [ ] `env.py` can import Base from app.infrastructure.database.base
- [ ] `alembic revision --autogenerate` succeeds
- [ ] Result: ✅ Verified / ❌ Incompatible

---

## Task 5: Integration Tests

**Metadata:**
| Field | Value |
|-------|-------|
| **Requirement** | R1–R4 (all requirements) |
| **Design Decision** | D1–D4 (all design decisions) |
| **Complexity** | Medium |
| **Risk** | Medium |
| **Files** | `tests/integration/test_database.py` (new) |

**Description:**

Create focused integration tests verifying:
1. Dependency injection (get_db_session export works)
2. Session lifecycle (acquire → query → commit/rollback → close)
3. Engine disposal (shutdown closes pool)
4. Fixture isolation (test data doesn't leak between tests)

**Deliverables:**

1. **Create tests/integration/test_database.py**:

   ```python
   import pytest
   from sqlalchemy import select, insert
   from sqlalchemy.ext.asyncio import AsyncSession
   from fastapi import Depends
   from app.core.dependencies import get_db_session
   # (Import User model once it exists in E3.T3+)


   @pytest.mark.asyncio
   async def test_get_db_session_export():
       """Verify get_db_session is exported from dependencies module."""
       from app.core.dependencies import get_db_session

       assert callable(get_db_session)


   @pytest.mark.asyncio
   async def test_session_lifecycle(db_session):
       """Verify session lifecycle: acquire, query, cleanup."""
       assert db_session is not None
       assert isinstance(db_session, AsyncSession)
       # Can execute queries
       result = await db_session.execute(select(1))
       assert result.scalar() == 1


   @pytest.mark.asyncio
   async def test_fixture_isolation_data_cleared(db_session):
       """Verify rollback clears test data between tests."""
       # Insert test marker
       await db_session.execute(insert(SomeTable).values(marker="test"))
       # (Rollback happens in fixture cleanup, verified in next test)


   @pytest.mark.asyncio
   async def test_fixture_isolation_no_leakage(db_session):
       """Verify data from previous test is not present."""
       # This test runs after test_fixture_isolation_data_cleared
       # If rollback didn't work, this test would see the marker from the previous test
       result = await db_session.execute(
           select(SomeTable).where(SomeTable.marker == "test")
       )
       assert result.scalar_one_or_none() is None  # Should not exist
   ```

2. **Test Dependency Injection**:
   - Verify import succeeds: `from app.core.dependencies import get_db_session`
   - Verify it can be used in route handler context (mock with Depends)

3. **Test Session Lifecycle**:
   - Session acquired and available
   - Queries can be executed
   - Session is closed after use (connection returned to pool)

4. **Test Engine Disposal** (via shutdown):
   - Start app, verify engine exists
   - Signal graceful shutdown
   - Verify engine is disposed (check logs)

5. **Test Fixture Isolation**:
   - Insert data in test_a
   - Verify data is absent in test_b
   - Confirms rollback pattern works

**Acceptance Criteria:**

- ✅ All 5 test cases pass
- ✅ Dependency injection test passes
- ✅ Session lifecycle test passes
- ✅ Engine disposal verified in logs
- ✅ Fixture isolation verified (data cleared between tests)
- ✅ No ORM model dependencies (tests work with raw queries or mocks)
- ✅ 100% pass rate: `pytest tests/integration/test_database.py -v`

---

## Task 6: Final Validation & Audit

**Metadata:**
| Field | Value |
|-------|-------|
| **Requirement** | All (R1–R4) |
| **Design Decision** | All (D1–D4) |
| **Complexity** | Low |
| **Risk** | Low |
| **Files** | `.github/E3-T1-FINAL-AUDIT.md` (new) |

**Description:**

Run all quality gates and produce the final audit document for E3.T1.

**Deliverables:**

1. **Run Quality Gates**:

   ```bash
   # Lint check
   cd backend
   ruff check app

   # Format check
   ruff format --check app

   # Type check
   mypy app --strict

   # Test suite (including new database tests)
   pytest tests/ -v

   # Compilation check
   python -m compileall -b app/

   # Import verification
   python -m py_compile app/main.py app/core/dependencies.py app/core/settings.py
   ```

2. **Verify All Gates Pass**:
   - ✅ Ruff: 0 violations (app code)
   - ✅ MyPy --strict: 0 errors
   - ✅ Pytest: All tests pass (including new integration tests)
   - ✅ Compileall: Success
   - ✅ Imports: All resolved

3. **Create Final Audit Document** (`.github/E3-T1-FINAL-AUDIT.md`):

   Following the same template as E2.T1–E2.T9:
   - Executive Summary (3-4 sentences)
   - Acceptance Criteria Verification (checklist)
   - Definition of Done Verification (checklist)
   - Files Modified Summary
   - Test Coverage Summary
   - Quality Gates Summary
   - Architecture Compliance Verification
   - Blast Radius & Risk Assessment
   - **Stateful Component Review** (per Epic 3 guidance):
     - Transaction boundaries verified
     - Connection lifecycle verified
     - Concurrency (async safety) verified
     - Failure modes reviewed
   - Final Verdict

**Acceptance Criteria:**

- ✅ All 6 quality gates pass
- ✅ Final audit document created (`.github/E3-T1-FINAL-AUDIT.md`)
- ✅ Audit includes all sections (requirements, design decisions, tests, gates, risk)
- ✅ All acceptance criteria from requirements.md verified
- ✅ All stateful component checks completed (transaction, connection, concurrency, failure modes)
- ✅ Verdict: Ready for E3.T2

---

## Task Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│ Task 1: Export DB Dependency                                │
│ (Independent — modify app/core/dependencies.py only)        │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│ Task 2: Engine Lifecycle                                    │
│ (Depends on: Settings, Logging from Epic 2)                 │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│ Task 3: Test Infrastructure                                 │
│ (Depends on: Task 1 export for import availability)         │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│ Task 4: Alembic Verification                                │
│ (Independent — inspection only)                             │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼────────┐  ┌───▼────────────┐
│ Task 5:       │  │ (Parallel OK)   │
│ Integration   │  │ Run in parallel │
│ Tests         │  │ if desired      │
└──────┬────────┘  └───────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│ Task 6: Final Validation & Audit                            │
│ (Depends on: Tasks 1–5 complete)                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Execution Notes

- **Sequential Execution**: Tasks 1 → 2 → 3 → 4 are in order (dependencies exist)
- **Parallel Possible**: Tasks 5 and 4 can run in parallel if desired (independent)
- **Task 6 Blocking**: Final validation must run after all other tasks complete
- **Estimated Duration**: Total 3–4 hours (matches backlog E3.T1 estimate of 3h)

---

## Quality Gates (Before Merging)

| Gate | Tool | Target | Status |
|------|------|--------|--------|
| **Lint** | Ruff | 0 violations (app code) | ⏳ Pending |
| **Format** | Ruff | Compliant | ⏳ Pending |
| **Types** | MyPy --strict | 0 errors | ⏳ Pending |
| **Tests** | Pytest | 100% pass rate | ⏳ Pending |
| **Coverage** | Pytest-cov | No regression | ⏳ Pending |
| **Compile** | Python -m compileall | Success | ⏳ Pending |

---

## Definition of Done Checklist

- [ ] Task 1: get_db_session exported from dependencies.py
- [ ] Task 2: Engine disposal added to lifespan shutdown
- [ ] Task 3: conftest.py created with fixtures
- [ ] Task 4: Alembic configuration verified
- [ ] Task 5: Integration tests pass
- [ ] Task 6: Final audit document created
- [ ] All quality gates pass (ruff, mypy, pytest, compileall)
- [ ] No regression in existing Epic 2 tests
- [ ] Commit message references all 6 tasks
- [ ] Ready for E3.T2: Alembic Configuration

