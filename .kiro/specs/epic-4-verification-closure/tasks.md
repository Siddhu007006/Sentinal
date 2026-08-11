# Tasks: Epic 4 Verification Closure

## Overview

Epic 4 Verification Closure consists of 5 tasks corresponding to the 6 requirements plus integration:

1. **E4V.T1** — PostgreSQL Infrastructure Setup & Database Initialization
2. **E4V.T2** — Integration Test Execution (19 test cases)
3. **E4V.T3** — MyPy --strict Type Checking
4. **E4V.T4** — Compileall Verification
5. **E4V.T5** — Token Rotation Concurrency Review & Security Certification

**Completion Criteria:** All 5 tasks must pass; Epic 4 status updated to 🟢 **COMPLETE & VERIFIED**

---

## Task Dependencies

```
E4V.T1 (PostgreSQL Setup)
    ↓
E4V.T2 (Integration Tests) ← depends on E4V.T1
    ↓
E4V.T3 (MyPy --strict) [can run in parallel with E4V.T2]
    ↓
E4V.T4 (Compileall) [can run in parallel with E4V.T3]
    ↓
E4V.T5 (Concurrency Review & Certification) [depends on E4V.T2, E4V.T3, E4V.T4]
```

---

## Task Definitions

### E4V.T1: PostgreSQL Infrastructure Setup & Database Initialization

**Objective:** Provision PostgreSQL database and initialize test database schema so integration tests can execute.

**Requirements Traceability:** Requirement 1 (PostgreSQL Infrastructure Setup)

**Design Reference:** design.md § Verification Gate 1

**Acceptance Criteria:**

1. PostgreSQL server running and accessible at `localhost:5432` (or configured in `.env`)
2. Test database `sentinel_test` created and accessible
3. Test database user `sentinel` with appropriate permissions
4. `.env` file configured with `DATABASE_URL=postgresql://sentinel:password@localhost/sentinel_test`
5. Alembic migrations successfully applied: `alembic upgrade head` exits with 0
6. Test database schema verified: `psql -d sentinel_test -c "\dt"` shows users, refresh_tokens, audit_logs tables
7. Database connection tested: Simple SELECT query executed successfully
8. Database is clean/empty before first test run (or test fixtures reset state)

**Implementation Steps:**

1. Provision PostgreSQL (Docker or local installation)
2. Create test database: `createdb sentinel_test`
3. Create test user: `createuser sentinel`
4. Grant permissions: `GRANT ALL PRIVILEGES ON DATABASE sentinel_test TO sentinel`
5. Configure `.env`: Set `DATABASE_URL` to point to test database
6. Run migrations: `uv run alembic upgrade head`
7. Verify schema: Check tables exist in test database
8. Test connection: Execute test query to confirm connectivity

**Subtasks:**

- [x] PostgreSQL server running (Docker or local)
- [x] Test database created and configured
- [x] Alembic migrations applied successfully
- [x] Database schema verified (tables present)
- [x] `.env` configuration complete
- [x] Database connection tested

**Exit Criteria:**

- Exit code: 0
- All subtasks completed
- Database is ready for integration tests

---

### E4V.T2: Integration Test Execution (19 test cases)

**Objective:** Execute all 19 integration tests and verify all pass without modification.

**Requirements Traceability:** Requirement 2 (Integration Test Execution)

**Design Reference:** design.md § Verification Gate 2

**Acceptance Criteria:**

1. `pytest backend/tests/integration/test_auth_routes.py -v` executes without errors
2. All 19 test cases **PASS** (not skip, not xfail):
   - 6 registration tests: success, duplicate, weak password, invalid email, missing email, optional fullname
   - 4 login tests: success, wrong password, user not found, missing credentials
   - 3 refresh tests: success with rotation, invalid token, missing token
   - 3 logout tests: device-specific, missing header, invalid token
   - 3 profile tests: get authenticated profile, missing token, invalid token
3. Exit code: 0 (all tests pass)
4. No test failures, no timeouts, no skip conditions
5. Each test verifies HTTP status code, response structure, and (where applicable) database state

**Implementation Steps:**

1. Ensure E4V.T1 (PostgreSQL) has completed successfully
2. Verify test file exists: `backend/tests/integration/test_auth_routes.py`
3. Run tests: `uv run pytest backend/tests/integration/test_auth_routes.py -v`
4. Review output: All 19 tests should show `PASSED`
5. If any test fails: Diagnose root cause and fix implementation (or test configuration)
6. Re-run until all 19 pass

**Subtasks:**

- [x] Test file verified (19 test cases present)
- [x] Database setup complete (E4V.T1 passed)
- [x] All 6 registration tests pass
- [x] All 4 login tests pass
- [~] All 3 refresh tests pass
- [~] All 3 logout tests pass
- [~] All 3 profile tests pass
- [~] Exit code: 0

**Exit Criteria:**

- Exit code: 0
- All 19 tests pass (0 failures, 0 skips)
- Output: `19 passed in X.XXs`

---

### E4V.T3: MyPy --strict Type Checking

**Objective:** Formally verify all code is correctly typed with no implicit `Any` types.

**Requirements Traceability:** Requirement 3 (MyPy --strict Type Checking)

**Design Reference:** design.md § Verification Gate 3

**Acceptance Criteria:**

1. Python venv initialized and activated (if using local venv)
2. Dependencies installed: `pip install -e ".[dev]"` or equivalent
3. `uv run mypy backend/app --strict` executed
4. Exit code: **0** (no errors)
5. Output includes: `Success: no issues found in N source files`
6. Critical modules (must have 0 errors):
   - `backend/app/infrastructure/security/password.py`
   - `backend/app/infrastructure/security/jwt.py`
   - `backend/app/api/v1/dependencies/auth.py`
   - `backend/app/application/services/auth_service.py`
   - `backend/app/domain/entities/user.py`

**Implementation Steps:**

1. Initialize Python venv (if not already done):
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```
2. Install dependencies:
   ```bash
   uv pip install -e ".[dev]"  # or: pip install -e ".[dev]"
   ```
3. Run MyPy:
   ```bash
   uv run mypy backend/app --strict
   ```
4. If errors found:
   - Read error message and line number
   - Add type hint or fix incompatible type
   - Re-run MyPy
   - Repeat until exit code 0

**Subtasks:**

- [~] Python venv initialized (if needed)
- [~] Dependencies installed
- [~] MyPy command executed
- [~] All errors resolved
- [ ] Exit code: 0
- [~] Critical modules verified (0 errors each)

**Exit Criteria:**

- Exit code: 0
- Output: `Success: no issues found in N source files`

---

### E4V.T4: Compileall Verification

**Objective:** Verify all Python modules compile to bytecode without syntax errors.

**Requirements Traceability:** Requirement 4 (Compileall Verification)

**Design Reference:** design.md § Verification Gate 4

**Acceptance Criteria:**

1. `python -m compileall backend/app` executed
2. Exit code: **0** (success, no errors)
3. No syntax errors reported
4. All `.py` files in `backend/app/` compile successfully
5. `.pyc` bytecode files generated in `__pycache__/` directories

**Implementation Steps:**

1. Ensure Python is in PATH and venv activated (if using venv)
2. Run compileall:
   ```bash
   python -m compileall backend/app
   ```
3. Review output: Should list all files being compiled
4. Verify exit code is 0
5. If syntax errors found: Fix code and re-run

**Subtasks:**

- [~] Python available in PATH
- [~] Compileall command executed
- [~] No syntax errors
- [ ] Exit code: 0
- [~] `.pyc` files generated

**Exit Criteria:**

- Exit code: 0
- All modules compiled successfully

---

### E4V.T5: Token Rotation Concurrency Review & Security Certification

**Objective:** Verify token rotation is immune to race conditions and complete the security certification checklist.

**Requirements Traceability:** Requirement 5 (Token Rotation Concurrency Review), Requirement 6 (Security Certification Checklist)

**Design Reference:** design.md § Security Review: Token Rotation Concurrency

**Acceptance Criteria:**

1. Code review of `refresh()` method confirms use of database row locking (SELECT ... FOR UPDATE or equivalent)
2. Concurrency test written and **PASSES**:
   - Two concurrent refresh requests with same token
   - Only one succeeds (HTTP 200)
   - One fails with 401 Unauthorized (TokenRevokedError)
3. Security & Quality Certification Checklist completed:
   - [~] Ruff: 0 violations
   - [~] MyPy --strict: 0 errors
   - [~] Compileall: Exit 0
   - [~] Integration Tests: 19/19 pass
   - [~] Password Hashing: Constant-time verification
   - [~] JWT Claims: All required claims present
   - [~] Token Lifetimes: Access 15min, Refresh 30days
   - [~] Token Revocation: Checked on every refresh
   - [~] RBAC: Role from JWT only
   - [~] Enumeration Prevention: 404 on forbidden
   - [~] Audit Logging: All events logged
   - [~] Soft-Delete: Inactive users filtered
   - [~] Token Rotation Concurrency: Atomic, race-condition-free
4. All checklist items marked ✓ (complete)
5. Verification report created with final status

**Implementation Steps:**

1. Verify E4V.T2, E4V.T3, E4V.T4 all passed
2. Code review:
   - Open `backend/app/infrastructure/database/repositories/refresh_token.py`
   - Find `get_by_jti()` or equivalent method
   - Verify it uses `SELECT ... FOR UPDATE` or database row locking
   - Document findings
3. Write concurrency test:
   - File: `backend/tests/integration/test_auth_routes.py` (or new file)
   - Test concurrent refresh with same token
   - Verify one succeeds, one fails
4. Run concurrency test: `pytest backend/tests/integration/test_concurrency.py -v`
5. Complete security checklist:
   - Review each item in Requirement 6
   - Verify implementation matches requirement
   - Mark ✓ for each completed item
6. Create verification report:
   - Document test results (gate 1–4 pass/fail)
   - Document security review (checklist)
   - Final status classification
7. Update Epic 4 status to 🟢 **COMPLETE & VERIFIED**

**Subtasks:**

- [~] Code review: Database row locking verified
- [~] Concurrency test written
- [~] Concurrency test passes (one success, one failure)
- [~] Security checklist reviewed and completed
- [~] All checklist items marked ✓
- [~] Verification report created
- [~] Epic 4 status updated to COMPLETE & VERIFIED

**Exit Criteria:**

- Concurrency test passes
- Security checklist 100% complete (all items ✓)
- Verification report generated
- Epic 4 status: 🟢 **COMPLETE & VERIFIED**
- Next milestone ready: Epic 5 can begin

---

## Completion Criteria

Epic 4 Verification Closure is **COMPLETE** when:

1. ✅ **E4V.T1 PASSED:** PostgreSQL infrastructure ready, database initialized, migrations applied
2. ✅ **E4V.T2 PASSED:** All 19 integration tests pass, exit code 0
3. ✅ **E4V.T3 PASSED:** MyPy --strict exits with 0 errors
4. ✅ **E4V.T4 PASSED:** Compileall exits with 0 errors
5. ✅ **E4V.T5 PASSED:** Concurrency review complete, security checklist 100%, verification report created
6. ✅ **Epic 4 Status Updated:** 🟢 **COMPLETE & VERIFIED**
7. ✅ **No Blocking Issues:** All three verification gates closed, security review passed
8. ✅ **Next Milestone Clear:** Epic 5 entry point ready, no dependencies blocking

---

## Notes

- **Wave-Based Scheduling:** Tasks E4V.T3 and E4V.T4 can run in parallel (both depend only on E4V.T1)
- **Failure Recovery:** If any task fails, refer to design.md § Failure Scenarios & Recovery for diagnosis
- **Concurrency Test:** Must use async/concurrent execution (not sequential); sequential test would pass even if code is vulnerable
- **Database State:** Test database should be fresh for each test run (or fixtures reset state); no cross-test dependencies
- **Documentation:** All results documented in verification report for project record

---

## Success Criteria

All 5 tasks passed with these outcomes:

1. ✅ PostgreSQL database running and test schema initialized
2. ✅ All 19 integration tests execute and pass (no failures, no skips)
3. ✅ MyPy --strict: Success: no issues found
4. ✅ Compileall: All modules compile (exit 0)
5. ✅ Concurrency test passes; security checklist 100% complete
6. ✅ Epic 4 status: 🟢 **IMPLEMENTATION COMPLETE & VERIFIED**
7. ✅ Ready to begin Epic 5

</content>
