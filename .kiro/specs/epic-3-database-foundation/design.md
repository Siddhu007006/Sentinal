# Design Document

## E3.T1 — Database Foundation: Connection & Session Management

**Phase:** Design  
**Status:** Ready for Implementation  
**Based On:** requirements.md (4 requirements, 15 acceptance criteria)

---

## Architecture Overview

The database foundation consists of three interconnected components:

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  Lifespan Manager                     │  │
│  │  startup: configure_logging()                        │  │
│  │  shutdown: await engine.dispose() [NEW]              │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │
         ├─→ app.core.dependencies.get_db_session [NEW EXPORT]
         │
         └─→ Route Handler (via Depends)
              │
              ├─→ Request Start: Session acquired from pool
              ├─→ Request Body: Route handler executes queries
              ├─→ Success: await session.commit() (automatic in get_db_session)
              ├─→ Exception: await session.rollback() (automatic in get_db_session)
              └─→ Request End: await session.close() (automatic in get_db_session)
```

**Key Insight**: The session lifecycle is managed entirely by FastAPI's dependency injection context manager. Route handlers execute queries normally; the `get_db_session()` dependency guarantees commit on success, rollback on exception, and close regardless (via try/except/finally).

---

## Design Decisions

### 1. Dependency Injection Export Strategy

**Requirement:** Route handlers must declare `AsyncSession` as a dependency.

**Decision:** Export `get_db_session()` from `app.core.dependencies` (re-export, not move).

**Rationale:**
- `get_db_session()` already exists in `app.infrastructure.database.session`
- Re-exporting keeps infrastructure details private (session.py is internal)
- Centralizes DI interface in `app.core.dependencies` (single import point for developers)
- Matches current pattern: `get_settings()`, `get_logger()`, `get_request_context()` all exported from dependencies.py

**Implementation:**
```python
# app/core/dependencies.py
from app.infrastructure.database.session import get_db_session

# This makes it available as:
# from app.core.dependencies import get_db_session
```

**Complexity:** Minimal (1 import line)  
**Risk:** Low (re-export, no logic changes)

---

### 2. Engine Disposal in Application Lifespan

**Requirement:** Clean connection pool shutdown without leaks.

**Decision:** Add `await engine.dispose()` to the lifespan shutdown hook (already exists in app/main.py from Epic 2).

**Rationale:**
- Lifespan manager guarantees execution order: startup → yield → shutdown
- FastAPI's lifespan context ensures all in-flight requests complete before shutdown
- Single point of control (no scattered cleanup code)
- Matches pattern: logging already configured in startup, will be extended with DB setup

**Current Lifespan Structure** (app/main.py):
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # --- Startup ---
    settings = get_settings()
    configure_logging(settings)
    
    yield
    
    # --- Shutdown ---
    # [ADD HERE: await engine.dispose()]
```

**Implementation Pattern:**
```python
# app/main.py - in lifespan shutdown block
from app.infrastructure.database.session import _engine

# During shutdown:
if _engine is not None:
    await _engine.dispose()
    logger.info("Database connection pool disposed")
```

**Ordering:**
1. All in-flight requests finish (guaranteed by FastAPI lifespan context)
2. Database pool is disposed
3. Logging is still active (can log disposal)
4. Application terminates

**Complexity:** Low (2-3 lines)  
**Risk:** Medium (see Risk Mitigation below)

**Risk Mitigation:**
- Test 1: Graceful shutdown signal during active request
- Test 2: Disposal completes within timeout
- Test 3: Subsequent requests after shutdown fail appropriately

---

### 3. Test Database Fixtures

**Requirement:** Reusable fixtures for integration testing with real PostgreSQL.

**Decision:** Create `backend/tests/conftest.py` with 3-4 fixtures using transaction rollback pattern.

**Fixture Architecture:**

```
conftest.py (pytest auto-discovery)
│
├── async_engine fixture (session-scoped)
│   └── Creates engine once per test session
│       Connected to TEST_DATABASE_URL (distinct DB)
│
├── db_session fixture (function-scoped)
│   └── Provides AsyncSession from async_engine
│       Yields session to test
│       After test: rollback (no commit)
│
├── clean_db fixture (function-scoped)
│   └── Dependency on db_session
│       Runs before test to verify clean state
│       (Rollback from previous test ensures this)
│
└── app_with_db fixture (module-scoped, optional)
    └── FastAPI app instance configured with test engine
        For cross-app integration tests
```

**Fixture Scoping Rationale:**

| Fixture | Scope | Why |
|---------|-------|-----|
| `async_engine` | Session | Create once, reuse for all tests (faster) |
| `db_session` | Function | New session per test (isolation via rollback) |
| `clean_db` | Function | Verify clean state before each test |
| `app_with_db` | Module | App startup overhead → reuse across tests |

**Transaction Rollback Pattern:**

The session uses explicit transaction management via `try/except/finally`:

```python
@pytest.fixture
async def db_session(async_engine):
    """Provide session with explicit transaction rollback on cleanup."""
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        try:
            yield session
            # After test completes successfully: rollback (intentional)
            # This undoes all mutations from the test
            await session.rollback()
        except Exception:
            # If test raises exception: also rollback
            await session.rollback()
            raise
        finally:
            # Always close session, returning connection to pool
            await session.close()
```

**Guarantee:** No data from test A persists to test B (via explicit rollback). Tests are isolated.

**Note:** This differs from `async with session.begin()` which auto-commits. We explicitly rollback to guarantee isolation.

**Test Database Configuration:**

Environment variable in CI/local:
```bash
TEST_DATABASE_URL=postgresql+asyncpg://test_user:test_password@localhost:5432/test_db
```

Settings validation:
```python
# app/core/settings.py - already has DATABASE_URL
# CI sets TEST_DATABASE_URL separately
# Tests read TEST_DATABASE_URL env var (fallback to DATABASE_URL if not set)
```

**Complexity:** Medium (50-100 lines of conftest.py, test utilities)  
**Risk:** Medium (fixture isolation bugs can cause test pollution)

**Risk Mitigation:**
- Test: Insert data in test_a, verify absent in test_b (rollback verification)
- Test: Run full test suite twice, verify same results (no state leakage)
- Code review: Fixture scoping explicitly reviewed

---

### 4. Alembic Configuration Verification

**Requirement:** Verify (don't rewrite) Alembic works with async engine.

**Decision:** Audit `alembic.ini` and `env.py`. Only modify if incompatible with async pattern. Do NOT run migration commands that depend on models (those belong in E3.T2+).

**Audit Checklist:**

| Item | Check | Required Action |
|------|-------|---------|
| `alembic.ini` reads DATABASE_URL from env | ✅ Yes | None |
| `env.py` uses async pattern | ⚠️ Verify | Only if incompatible |
| `env.py` can import models | ⚠️ Verify | Only if imports fail |
| `sqlalchemy.url` not hardcoded | ✅ Yes | None |

**What to Verify:**
1. `alembic revision --autogenerate` runs without error (even though no models exist yet)
2. No import failures in env.py
3. DATABASE_URL sourced from environment

**What NOT to do:**
- ❌ Run `alembic upgrade head` (no migrations exist yet)
- ❌ Run `alembic downgrade base` (no migrations exist yet)
- ❌ Create an empty initial migration (E3.T2 will do this with actual models)

**Complexity:** Low (inspection only, max 5 lines changes if needed)  
**Risk:** Low (verification only, migrations deferred to E3.T2)

---

## Implementation Flow

```
Phase: Design (THIS DOCUMENT)
│
├─→ Decision 1: Re-export get_db_session from dependencies.py
├─→ Decision 2: Add engine.dispose() to lifespan shutdown
├─→ Decision 3: Create conftest.py with fixtures + transaction rollback
├─→ Decision 4: Verify (not rewrite) Alembic async compatibility
│
└─→ Next Phase: Tasks (task.md will break into specific actions)
```

---

## Integration Points

### With Epic 2 (Settings & Logging)
- Settings.database_url already configured ✅
- Logging configured in lifespan startup ✅
- Extending lifespan shutdown (not conflicting) ✅

### With E3.T2 (Alembic)
- Alembic already initialized ✅
- First migration will be created in E3.T2 (not E3.T1) ✅

### With E3.T3+ (ORM Models)
- DI export ready for route handlers ✅
- Fixtures ready for model tests ✅
- No model definitions required in E3.T1 ✅

---

## Testing Strategy

### Unit Tests
- ✅ `test_dependencies.py` extended: Verify `get_db_session` export succeeds
- ✅ Engine creation succeeds with settings

### Integration Tests
- ✅ `test_database.py` (NEW): Session lifecycle (acquire → commit/rollback → close)
- ✅ Session injection works in route handler mock
- ✅ Shutdown disposal completes without error
- ✅ Fixture isolation (test A data absent in test B)

### CI Verification
- ✅ Alembic commands (`revision --autogenerate`, `upgrade head`, `downgrade base`)
- ✅ Full test suite runs with real PostgreSQL
- ✅ Pytest discovers and runs conftest.py fixtures

---

## Files Modified / Created

| File | Action | Summary |
|------|--------|---------|
| `app/core/dependencies.py` | Modify | Add: `from app.infrastructure.database.session import get_db_session` |
| `app/main.py` | Modify | Lifespan shutdown: Add engine disposal |
| `tests/conftest.py` | Create | Fixtures: async_engine, db_session, clean_db, app_with_db |
| `tests/integration/test_database.py` | Create | Integration tests: lifecycle, injection, shutdown, isolation |
| `alembic.ini` | Verify | No changes (already correct) |
| `migrations/env.py` | Verify | No changes (verify async compatibility) |

---

## Quality Gates

All code must pass before merging:

| Gate | Tool | Target |
|------|------|--------|
| **Lint** | Ruff | 0 violations (app code) |
| **Format** | Ruff | Compliant with standards |
| **Types** | MyPy --strict | 0 errors |
| **Tests** | Pytest | 100% pass rate |
| **Coverage** | Pytest-cov | No regression in new code |
| **Compile** | Python -m compileall | Success |

---

## Risk Assessment & Mitigations

### Primary Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| **Shutdown ordering bug** | Medium | Connection leaks | Test with in-flight request during shutdown |
| **Fixture isolation failure** | Medium | Test pollution | Test: verify data cleared between tests |
| **Alembic incompatibility** | Low | E3.T2 blocked | Verify async pattern during audit |
| **Circular import** | Low | Module load failure | Review imports, test app startup |

### Regression Prevention

1. **Existing Epic 2 tests**: Verify settings, logging, middleware still work
2. **New database tests**: Specifically test session lifecycle
3. **Shutdown test**: Signal graceful shutdown with active request
4. **Fixture test**: Insert-in-A, verify-absent-in-B pattern

---

## Decisions Deferred to Tasks Phase

Once design is approved, task phase will specify:

- Exact line numbers to modify
- Code snippets for each fixture
- Test case outline (pseudocode → implementation)
- CI pipeline modifications (if any)
- Audit template for final verification

---

## Architecture Compliance

**Traces to Documents:**
- ✅ 04-Database-Design (UUID PKs, async engine)
- ✅ 06-Repository-Structure §3 (migrations/ location, session.py)
- ✅ 07-Backend-Development-Standards §7 (async sessions)
- ✅ 07-Backend-Development-Standards §8 (ORM models, lifecycle)
- ✅ 07-Backend-Development-Standards §13 (testing patterns)
- ✅ 09-Deployment-Architecture §3 (graceful shutdown)
- ✅ 10-Observability-Architecture §2 (request context)
- ✅ 11-Testing-Strategy §6 (fixtures)
- ✅ 22-Engineering-Backlog § E3.T1

**No Contradictions:** Design aligns with all approved architecture documents.

---

## Sign-Off

**Design Approval Checklist:**

- [ ] Re-export strategy approved
- [ ] Lifespan shutdown approach approved
- [ ] Fixture architecture approved
- [ ] Alembic verification strategy approved
- [ ] Risk mitigations accepted
- [ ] Ready to proceed to tasks phase

**Next Step:** Once design is approved, generate `tasks.md` with specific implementation actions.

