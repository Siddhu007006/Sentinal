# Requirements Document

## E3.T1 — Database Foundation: Connection & Session Management

**Objective:** Complete the database connectivity layer by wiring dependency injection, implementing graceful shutdown lifecycle management, and establishing test infrastructure for database integration.

**Status:** Requirements Phase  
**Backlog Reference:** docs/22-Engineering-Backlog.md § E3.T1  
**Priority:** P0 (foundation for all subsequent database tasks)

---

## Introduction

Epic 3 introduces stateful persistence to the Sentinel backend. The infrastructure foundation (SQLAlchemy, async engine, session factory) is already scaffolded and production-ready. This task completes the integration by:

1. **Exporting the database dependency** so route handlers can request sessions via FastAPI's `Depends()`
2. **Adding lifecycle management** to properly dispose of the database connection pool on application shutdown
3. **Creating test fixtures** to enable safe integration testing with real database connections
4. **Verifying Alembic configuration** ensures migration tooling works with the async engine

No new models or migrations are required for this task. The scope is strictly completing the existing foundation to support downstream tasks (E3.T2–E3.T11).

---

## Glossary

| Term | Definition |
|------|-----------|
| **AsyncSession** | SQLAlchemy's async-compatible session for executing queries |
| **Session Factory** | `async_sessionmaker` instance that creates new sessions on demand |
| **Request-Scoped** | Lifecycle tied to HTTP request (created on entry, disposed on exit) |
| **DI (Dependency Injection)** | FastAPI's `Depends()` mechanism for declarative dependency provision |
| **Connection Pool** | Maintains reusable database connections (pool_size + max_overflow total) |
| **Fixture** | Reusable test helper (pytest terminology) |
| **Conftest** | `conftest.py` file defining pytest fixtures available to all tests |
| **Alembic** | Database migration tool paired with SQLAlchemy |
| **Autogenerate** | Alembic's ability to create migration scripts from model changes |

---

## Requirements

### Requirement 1: Export Database Dependency

**User Story:**  
As a route handler developer, I want to declare a database session as a dependency so I can query the database without managing session lifecycle manually.

#### Acceptance Criteria

1. `get_db_session()` is exported from `app.core.dependencies` (not just `session.py`)
2. Route handlers can use: `async def my_route(..., db: AsyncSession = Depends(get_db_session))`
3. The session is valid and connected for the duration of the request
4. The session is closed before the response is sent
5. Type hints are preserved (`AsyncSession` from `sqlalchemy.ext.asyncio`)

#### Architectural Notes

- Traces to: 07-Backend-Development-Standards §3 (DI), §7 (async sessions)
- Traces to: 10-Observability-Architecture §2 (request context propagation)
- This is a **localization** task, not new functionality (the dependency already exists in session.py)

---

### Requirement 2: Application Shutdown Lifecycle

**User Story:**  
As an operations engineer, I want the application to cleanly dispose of database connections when shutting down so that connection pooling resources are released and no connections leak.

#### Acceptance Criteria

1. Database engine is disposed during application shutdown (in the lifespan manager)
2. Shutdown happens **after** all in-flight requests complete (FastAPI lifespan context ensures this)
3. **Engine disposal is attempted regardless of other shutdown failures**: If other shutdown steps fail, engine disposal still happens
4. **WHEN** engine disposal completes, **THEN** it executes without errors
5. **WHEN** all shutdown hooks complete, **THEN** graceful shutdown is achieved only if cleanup finishes within configured timeout (default 30 seconds)
6. Connection pool is empty after shutdown (all connections closed)
7. **IF** engine disposal fails, **THEN** the failure is logged but does not prevent application from terminating

#### Architectural Notes

- Traces to: 09-Deployment-Architecture §3 (graceful shutdown)
- Traces to: 07-Backend-Development-Standards §8 (lifecycle management)
- **Shutdown Guarantee**: Engine disposal happens in finally block, ensuring cleanup regardless of request-handling failures
- **Timeout Semantics**: Graceful shutdown is only achieved if cleanup completes within timeout. Exceeding timeout means shutdown is not graceful (may require forced termination).
- **Risk**: Incorrect shutdown ordering can cause connection leaks or deadlocks (see Risk Assessment)

---

### Requirement 3: Database Test Fixtures

**User Story:**  
As a test developer, I want reusable database fixtures so I can write integration tests without duplicating setup/teardown logic.

#### Acceptance Criteria

1. `conftest.py` exists at `backend/tests/conftest.py` and is auto-discovered by pytest
2. Fixtures provided with correct scoping:
   - **db_session fixture (function-scoped)**: Provides an `AsyncSession` connected to the test database, rolls back after each test
   - **clean_db fixture (function-scoped)**: Clears mutations from previous tests via transaction rollback
   - **app_with_db fixture (module-scoped)**: Application instance configured with test database (optional, if needed for cross-app tests)
   - **async_engine fixture (session-scoped)**: Creates engine once per test session; disposed after all tests
3. **WHEN** fixtures are used in multiple tests, **THEN** data mutations do not leak between tests (rollback pattern isolation)
4. **WHEN** a fixture is session-scoped (engine), **THEN** it cannot be overridden to function-scoped without explicit redesign**
5. Test database is distinct from development/production (TEST_DATABASE_URL configured separately, defaults to test_db)
6. Fixtures support both sync and async test functions (pytest-asyncio compatibility)

#### Architectural Notes

- Traces to: 11-Testing-Strategy §6 (fixture patterns, factory-boy foundation)
- Traces to: 07-Backend-Development-Standards §13 (test isolation)
- **Pattern**: Transaction rollback pattern for isolation (vs. delete/truncate, which is slower)
- **Prohibition**: Do not reverse scoping (e.g., session-level cleanup with function-level engine)

---

### Requirement 4: Alembic Configuration Verification

**User Story:**  
As a database engineer, I want to verify the Alembic configuration works with the async engine so migrations can be created and applied reliably.

#### Acceptance Criteria

1. `alembic.ini` reads `DATABASE_URL` from environment (not hardcoded)
2. `env.py` is configured for async operations (uses async pattern compatible with async engine)
3. `env.py` can import ORM models for autogenerate support (import succeeds, no circular dependencies)
4. **Alembic commands work**: `alembic revision --autogenerate` executes without error (even if no migrations needed)
5. **Verification only**: This task verifies Alembic setup is correct. First real migration will be created in E3.T2 when models are defined.
6. **Deferred to E3.T2**: `alembic upgrade head` and `alembic downgrade base` will be tested once migrations exist.

#### Architectural Notes

- Traces to: 04-Database-Design §2 (migrations), §3 (naming conventions)
- Traces to: 06-Repository-Structure §3 (migrations/ directory)
- **Scope**: Verification only — do not rewrite `env.py` unless it fails async compatibility checks
- First migration will be created in E3.T2 (when models exist)

---

## Definition of Done

The task is complete when ALL of the following are verified:

1. ✅ `get_db_session()` exported from `app.core.dependencies`
2. ✅ Engine disposal implemented in `app.main.lifespan()`
3. ✅ `conftest.py` created with all fixtures
4. ✅ Alembic configuration verified as async-compatible
5. ✅ Integration test proves session injection works
6. ✅ Integration test proves shutdown disposal occurs
7. ✅ Fixture isolation test proves transaction rollback works
8. ✅ All quality gates pass:
   - Ruff: 0 violations (app code)
   - MyPy --strict: 0 errors
   - Pytest: All tests pass, including new database tests
   - Compileall: Success
9. ✅ Final audit document created

---

## Acceptance Criteria Summary

| Criterion | Status | Evidence |
|-----------|--------|----------|
| DI export | Pending | Export in dependencies.py, test proving route can inject |
| Shutdown lifecycle | Pending | Code in lifespan, test proving disposal happens |
| Test fixtures | Pending | conftest.py with 3+ fixtures, tests using them |
| Alembic verification | Pending | env.py reviewed, autogenerate tested |
| Quality gates | Pending | ruff/mypy/pytest all pass |

---

## Risk Assessment

### Regression Risks (Primary Concerns for E3.T1)

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| **Shutdown ordering bug** | Medium | Connection leaks, hung connections | Test: graceful shutdown with in-flight request |
| **Fixture isolation failure** | Medium | Test pollution (test A affects test B) | Test: verify rollback clears all mutations |
| **Alembic env.py incompatibility** | Low | Migration failures in E3.T2 | Verify async pattern matches runtime engine |
| **Import circular dependency** | Low | Module initialization failure | Verify no circular imports in dependencies |

### Mitigation Strategy

1. **Shutdown test**: Create request, start long-running query, issue shutdown signal, verify connection closed
2. **Fixture test**: Insert data in test A, verify it's gone in test B (via rollback)
3. **Alembic test**: Run `alembic upgrade head` → `alembic downgrade base` on clean DB
4. **Import test**: Verify `from app.core.dependencies import get_db_session` succeeds

---

## Out of Scope (For Later Tasks)

- ❌ Creating ORM models (E3.T3–E3.T9)
- ❌ Initial Alembic migration (E3.T2, which happens after models exist)
- ❌ Repository pattern implementation (E3.T10–E3.T11)
- ❌ Soft delete filtering (E3.T11)
- ❌ Pagination query helpers (E3.T11)

---

## Key Decisions

### 1. Transaction Rollback Pattern for Test Isolation

**Decision:** Use transaction rollback (commit after test, rollback fixture) rather than truncate/delete.

**Rationale:**
- Faster (no DELETE/TRUNCATE overhead per test)
- Simpler (single rollback vs. figuring out all tables to truncate)
- Respects foreign keys (no ordering issues)
- Matches pytest-asyncio best practices

### 2. Engine Disposal in Lifespan (vs. Manual Cleanup)

**Decision:** Add `await engine.dispose()` to the lifespan shutdown hook (already defined in E2.T2).

**Rationale:**
- Guaranteed execution (lifespan manager ensures cleanup)
- Ordered properly (waits for in-flight requests via FastAPI's context)
- Single point of control (no scattered cleanup code)

### 3. No Initial Empty Migration

**Decision:** Do not create an empty Alembic revision for E3.T1.

**Rationale:**
- First migration should capture actual schema (models in E3.T3+)
- Empty migration has no value
- E3.T2 handles Alembic setup; E3.T3 creates first real migration

---

## Specification Artifacts

**Input Documents:**
- docs/04-Database-Design (database schema, naming conventions)
- docs/07-Backend-Development-Standards §7 (async session patterns)
- docs/07-Backend-Development-Standards §8 (ORM models)
- docs/07-Backend-Development-Standards §13 (testing patterns)
- docs/11-Testing-Strategy (fixture patterns)
- backend/app/infrastructure/database/ (existing scaffolding)

**Implementation will produce:**
- Modified: `app/core/dependencies.py` (export get_db_session)
- Modified: `app/main.py` (lifespan shutdown)
- Created: `tests/conftest.py` (fixtures)
- Created: `tests/integration/test_database.py` (integration tests)
- Verified: `backend/alembic.ini`, `backend/migrations/env.py`
- Created: `.github/E3-T1-FINAL-AUDIT.md` (audit report)

---

## Dependency Graph

```
E3.T1 (Database Foundation - THIS TASK)
├── Enables: E3.T2 (Alembic configuration)
├── Enables: E3.T3+ (ORM models)
└── Dependency: E2.T1 (Settings already done)
```

This is a **blocking task** for the entire persistence layer. All subsequent database work depends on E3.T1 completion.

---

## Next Steps (After Requirements Approval)

Once these requirements are approved:

1. **Design Phase**: Architecture decisions (fixture patterns, shutdown sequence, etc.)
2. **Task Phase**: Specific implementation tasks (modify dependencies.py, add fixtures, etc.)
3. **Execution Phase**: Code implementation and testing
4. **Validation Phase**: Quality gates and final audit

