# Design Document

## Epic 4 Verification Closure

**Date:** August 2026
**Status:** Design Phase (Entry Point)
**Trace to:** requirements.md (6 requirements), tasks.md (TBD)

---

## Architecture Overview

Epic 4 Verification Closure consists of **4 verification gates** and **1 security review**, executed sequentially to formally validate that Epic 4 is production-ready:

```
┌─ Verification Gate 1: PostgreSQL Setup ─────────────────┐
│  - Provision/run PostgreSQL                            │
│  - Initialize test database (sentinel_test)            │
│  - Run Alembic migrations                              │
│  - Configure .env DATABASE_URL                         │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─ Verification Gate 2: Integration Test Execution ──────┐
│  - Execute pytest on 19 test cases                     │
│  - All 19/19 tests PASS                                │
│  - Verify response schemas and state changes           │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─ Verification Gate 3: MyPy --strict Type Checking ─────┐
│  - Initialize Python venv                              │
│  - Install dependencies                                │
│  - Run: uv run mypy backend/app --strict               │
│  - Exit code: 0 (0 errors)                             │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─ Verification Gate 4: Compileall Verification ─────────┐
│  - Run: python -m compileall backend/app               │
│  - Exit code: 0                                        │
│  - All modules compile to .pyc bytecode                │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─ Security Review: Token Rotation Concurrency ──────────┐
│  - Review database atomicity of refresh flow           │
│  - Test concurrent refresh with same token            │
│  - Verify row-level locking prevents double-use        │
│  - Confirm TokenRevokedError on second request        │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─ Certification: Complete Security Checklist ───────────┐
│  - All gates pass ✓                                    │
│  - All security properties verified ✓                 │
│  - Update status → COMPLETE & VERIFIED ✓              │
└─────────────────────────────────────────────────────────┘
```

---

## Verification Gate 1: PostgreSQL Infrastructure Setup

### Objective

Provision PostgreSQL database and initialize test database schema so integration tests can execute against a real database.

### Design Decisions

**Database Server Choice:**
- **Option A (Local):** PostgreSQL installed on developer machine or CI runner
  - Pros: Simple, fast, no external dependencies
  - Cons: Requires local setup on each machine
  
- **Option B (Docker Container):** PostgreSQL in Docker container
  - Pros: Reproducible, portable, no local installation needed
  - Cons: Requires Docker to be running
  
- **Recommended:** Option B (Docker) for CI; both acceptable for local development

**Test Database Naming:**
- Database name: `sentinel_test` (separate from `sentinel_dev` or `sentinel_prod`)
- User: `sentinel` (or use existing database user from `.env`)
- Password: Use existing credentials from `.env`

**Schema Initialization:**
- Method: Run Alembic migrations (same as production)
- Command: `alembic upgrade head` (or `uv run alembic upgrade head`)
- Timing: Before first test run; can be cached/reused if schema doesn't change

**Configuration via Environment:**
- `.env` file contains `DATABASE_URL=postgresql://sentinel:password@localhost/sentinel_test`
- Test configuration reads from `.env` (or `.env.test` if override needed)

### Implementation Steps

**Step 1.1: PostgreSQL Server Setup**
```bash
# Option A: Local PostgreSQL
# Install PostgreSQL 14+ on system
# Start PostgreSQL service

# Option B: Docker PostgreSQL
docker run -d \
  --name sentinel_postgres \
  -e POSTGRES_DB=sentinel_test \
  -e POSTGRES_USER=sentinel \
  -e POSTGRES_PASSWORD=<password> \
  -p 5432:5432 \
  postgres:16
```

**Step 1.2: Database & User Creation**
```bash
# If not created by Docker, create database and user manually
createdb -h localhost -U postgres sentinel_test
createuser -h localhost -U postgres sentinel
# Grant permissions:
psql -h localhost -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE sentinel_test TO sentinel;"
```

**Step 1.3: Run Migrations**
```bash
cd /path/to/sentinel
export DATABASE_URL="postgresql://sentinel:password@localhost/sentinel_test"
uv run alembic upgrade head
```

**Step 1.4: Verify Schema**
```bash
psql -h localhost -U sentinel -d sentinel_test -c "\dt"
# Should show: users, refresh_tokens, audit_logs, and other tables
```

---

## Verification Gate 2: Integration Test Execution

### Objective

Execute all 19 integration tests against real database and verify all endpoints work end-to-end.

### Test Execution Flow

```
┌─ Start Test Run ────────────────────────────────┐
│  pytest backend/tests/integration/             │
│  test_auth_routes.py -v --tb=short             │
└────────────────────────────────────────────────┘
         ↓
┌─ TestAuthRegister (6 tests) ────────────────────┐
│  [PASS] test_register_success                   │
│  [PASS] test_register_duplicate_email           │
│  [PASS] test_register_weak_password             │
│  [PASS] test_register_invalid_email             │
│  [PASS] test_register_missing_email             │
│  [PASS] test_register_optional_full_name        │
└────────────────────────────────────────────────┘
         ↓
┌─ TestAuthLogin (4 tests) ───────────────────────┐
│  [PASS] test_login_success                      │
│  [PASS] test_login_wrong_password               │
│  [PASS] test_login_user_not_found               │
│  [PASS] test_login_missing_credentials          │
└────────────────────────────────────────────────┘
         ↓
┌─ TestAuthRefresh (3 tests) ─────────────────────┐
│  [PASS] test_refresh_success                    │
│  [PASS] test_refresh_invalid_token              │
│  [PASS] test_refresh_missing_token              │
└────────────────────────────────────────────────┘
         ↓
┌─ TestAuthLogout (3 tests) ──────────────────────┐
│  [PASS] test_logout_device_specific             │
│  [PASS] test_logout_missing_auth_header         │
│  [PASS] test_logout_invalid_token               │
└────────────────────────────────────────────────┘
         ↓
┌─ TestAuthMe (3 tests) ───────────────────────────┐
│  [PASS] test_get_me_success                     │
│  [PASS] test_get_me_missing_token               │
│  [PASS] test_get_me_invalid_token               │
└────────────────────────────────────────────────┘
         ↓
┌─ Test Summary ──────────────────────────────────┐
│  19 passed in 12.34s                            │
│  Exit code: 0                                   │
└────────────────────────────────────────────────┘
```

### Test Configuration

**Pytest Configuration (pytest.ini or pyproject.toml):**
```ini
[tool:pytest]
testpaths = backend/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
# Optional: markers for integration vs unit
markers =
    integration: Integration tests (require database)
    unit: Unit tests (mocked)
```

**Database Fixture Pattern:**
```python
@pytest.fixture(scope="function")
def client():
    """Provide FastAPI test client with fresh database state."""
    # 1. Create app
    app = create_app()
    # 2. Optionally clean/reset database before each test
    # db.clear_all_tables()  # Or use transaction rollback
    # 3. Return test client
    return TestClient(app)
```

### Expected Test Results

All tests should execute and pass **without modification** to the test code itself. If tests fail, the implementation has bugs (not the tests).

**Example Success Output:**
```
backend/tests/integration/test_auth_routes.py::TestAuthRegister::test_register_success PASSED [  5%]
backend/tests/integration/test_auth_routes.py::TestAuthRegister::test_register_duplicate_email PASSED [ 10%]
...
backend/tests/integration/test_auth_routes.py::TestAuthMe::test_get_me_invalid_token PASSED [100%]

======================== 19 passed in 12.34s =========================
```

---

## Verification Gate 3: MyPy --strict Type Checking

### Objective

Formally verify that all code is correctly typed with no implicit `Any` types.

### MyPy Configuration

**Recommended config (pyproject.toml or mypy.ini):**
```ini
[tool.mypy]
python_version = "3.12"
strict = true
# Individual strict settings (explicitly set by --strict):
warn_unused_configs = true
disallow_any_explicit = true
disallow_any_generics = true
disallow_any_unimported = true
disallow_untyped_calls = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_return_any = true
warn_unreachable = true
# Exclude test files if desired
exclude = "tests/"
```

### Execution & Verification

**Run MyPy:**
```bash
cd /path/to/sentinel
uv run mypy backend/app --strict
```

**Expected Output (Success):**
```
Success: no issues found in 47 source files
Exit code: 0
```

**If Errors Found:**
```
backend/app/infrastructure/security/jwt.py:45: error: Function is missing a type annotation for one or more arguments [no-untyped-def]
backend/app/api/v1/routes/auth.py:23: error: Incompatible return value type (got "Any", expected "UserSchema") [return-value]
...
Found 5 errors in 2 files (checked 47 source files)
Exit code: 1
```

**Error Resolution:**
1. Read error message and line number
2. Add type hint or fix incompatible type
3. Re-run MyPy
4. Repeat until exit code 0

**Critical Modules (Must Have 0 Errors):**
- `backend/app/infrastructure/security/password.py`
- `backend/app/infrastructure/security/jwt.py`
- `backend/app/api/v1/dependencies/auth.py`
- `backend/app/application/services/auth_service.py`
- `backend/app/domain/entities/user.py`

---

## Verification Gate 4: Compileall Verification

### Objective

Verify all Python modules can compile to bytecode without syntax errors.

### Execution & Verification

**Run Compileall:**
```bash
python -m compileall backend/app
```

**Expected Output (Success):**
```
Listing backend/app ...
Compiling backend/app/main.py ...
Compiling backend/app/domain/entities/user.py ...
... (40+ files compiled)
Listing backend/app/__pycache__ ...
Exit code: 0
```

**If Errors Found:**
```
Sorry: SyntaxError: ('invalid syntax', ('/path/to/file.py', 23, 15, 'invalid_code_here\n'))
Exit code: 1
```

**Note:** If Ruff and MyPy both pass, Compileall should pass automatically (syntax errors would be caught earlier).

---

## Security Review: Token Rotation Concurrency

### Objective

Verify that concurrent refresh requests with the same refresh token are atomically handled (only one succeeds, the other fails).

### Vulnerability Scenario

**Attack:** User's refresh token is stolen. Attacker attempts concurrent refresh from two machines:

```
Time T0.000: Attacker Request A: POST /auth/refresh with token X
Time T0.001: Attacker Request B: POST /auth/refresh with token X (same token, milliseconds later)

Vulnerable Outcome:
  - Both requests read: token X, is_revoked=False
  - Both requests proceed to issue new tokens
  - Both return success with different token pairs
  - BOTH token pairs are valid!
  - Attacker can use either pair to impersonate user

Secure Outcome:
  - Request A acquires row lock on token X
  - Request A marks token X as revoked
  - Request A issues new token pair A'
  - Request B attempts to acquire lock on token X (waits for A to complete)
  - Request B reads: token X, is_revoked=True
  - Request B returns 401 Unauthorized (TokenRevokedError)
  - Only Request A's token pair is valid
```

### Design: Atomic Refresh Operation

**Database Operation (Pseudocode):**
```sql
BEGIN TRANSACTION;

-- Step 1: Acquire row lock (SELECT ... FOR UPDATE)
SELECT id, is_revoked FROM refresh_tokens 
  WHERE jti = ? 
  FOR UPDATE;

-- Step 2: Check if revoked
IF is_revoked THEN
  ROLLBACK;
  RAISE TokenRevokedError;
END IF;

-- Step 3: Revoke old token
UPDATE refresh_tokens 
  SET is_revoked = TRUE, updated_at = NOW() 
  WHERE jti = ?;

-- Step 4: Insert new tokens
INSERT INTO refresh_tokens (user_id, jti, is_revoked, created_at, updated_at)
  VALUES (?, NEW_JTI, FALSE, NOW(), NOW());

COMMIT;
```

**Key Points:**
- `SELECT ... FOR UPDATE` acquires row-level lock (exclusive)
- Lock prevents concurrent transaction from reading old state
- Transaction is atomic: all-or-nothing
- Isolation level: READ COMMITTED (PostgreSQL default) with explicit locking suffices

### Concurrency Test

**Test Code Location:** `backend/tests/integration/test_auth_routes.py` (new test class)

**Test Implementation:**
```python
@pytest.mark.asyncio
async def test_concurrent_refresh_same_token_blocked():
    """
    Verify that concurrent refresh with same token only succeeds once.
    The second request should fail with TokenRevokedError.
    """
    # Setup
    client = TestClient(app)
    
    # Register and login
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "concurrent@test.local",
            "password": "P@ssword123456",
        },
    )
    assert reg_resp.status_code == 201
    
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "concurrent@test.local",
            "password": "P@ssword123456",
        },
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refreshToken"]
    
    # Concurrent refresh: both use same token
    import asyncio
    
    async def do_refresh():
        return client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
    
    # Execute both concurrently
    results = await asyncio.gather(
        asyncio.to_thread(do_refresh),
        asyncio.to_thread(do_refresh),
    )
    
    # Verify one succeeded, one failed
    statuses = [r.status_code for r in results]
    
    # Expected: [200, 401] or [401, 200]
    assert 200 in statuses, "One refresh should succeed"
    assert 401 in statuses, "One refresh should fail"
    assert statuses.count(200) == 1, "Only one refresh should succeed"
    assert statuses.count(401) == 1, "Exactly one refresh should fail"
    
    # Verify failed response is TokenRevokedError
    failed_resp = [r for r in results if r.status_code == 401][0]
    failed_data = failed_resp.json()
    assert "error" in failed_data
    assert "revoked" in failed_data["error"]["detail"].lower()
```

### Verification Steps

1. **Code Review:** Check that `refresh()` method uses `SELECT ... FOR UPDATE` or equivalent database locking
2. **Test Execution:** Run concurrency test above; verify it passes (one success, one failure)
3. **Database Log:** Check PostgreSQL query log to confirm row lock was used
4. **Stress Test:** Optionally run test multiple times (10–100 iterations) to catch race conditions

---

## Security & Quality Certification Checklist

### Checklist Items

**Quality Gates:**
- [ ] Ruff: `uv run ruff check backend/app` → 0 violations
- [ ] MyPy --strict: `uv run mypy backend/app --strict` → 0 errors
- [ ] Compileall: `python -m compileall backend/app` → Exit 0
- [ ] Integration Tests: `pytest backend/tests/integration/test_auth_routes.py -v` → 19/19 pass

**Security Properties:**
- [ ] Password Hashing: Argon2id/bcrypt with constant-time verification
- [ ] JWT Claims: sub, exp, iat, jti, role (access only) all present
- [ ] Token Lifetimes: Access 15min, Refresh 30days
- [ ] Token Revocation: Checked on every refresh, never cached
- [ ] RBAC: Role from JWT only, never from request body
- [ ] Enumeration Prevention: 404 returned for both "not found" and "forbidden"
- [ ] Audit Logging: All auth/authz events logged
- [ ] Soft-Delete: Inactive users filtered from all queries
- [ ] Token Rotation Concurrency: Atomic; one concurrent refresh succeeds, other fails

**Requirements Traceability:**
- [ ] Requirement 1–10 all implemented and working
- [ ] E4.T1–E4.T11 all marked complete
- [ ] No gaps or deviations from specification

**Code Quality:**
- [ ] No passwords/hashes in logs or responses
- [ ] No hard-coded secrets in code
- [ ] All errors use RFC 7807 format
- [ ] All endpoints have exception handling
- [ ] Type hints complete

**Test Coverage:**
- [ ] 19 integration tests written and passing
- [ ] Happy paths tested
- [ ] Error cases tested
- [ ] Multi-device sessions tested
- [ ] Token rotation tested
- [ ] RBAC enforcement tested

**Documentation:**
- [ ] Audit report updated
- [ ] Verification roadmap documented
- [ ] No blocking issues remain

### Certification Process

1. **Execute all gates** in order (PostgreSQL → Integration → MyPy → Compileall)
2. **Collect results** (pass/fail for each gate)
3. **Review security properties** manually (code inspection)
4. **Run concurrency test** (token rotation)
5. **Complete checklist** (mark all items ✓)
6. **Document results** in verification report
7. **Sign off** (Epic 4 → COMPLETE & VERIFIED)

---

## Failure Scenarios & Recovery

### Scenario 1: PostgreSQL Connection Fails

**Symptom:** Integration tests fail immediately with connection error

**Recovery:**
1. Verify PostgreSQL is running: `psql -h localhost -U sentinel -d sentinel_test -c "SELECT 1"`
2. Check DATABASE_URL in `.env`: `echo $DATABASE_URL`
3. If missing, set: `export DATABASE_URL="postgresql://sentinel:password@localhost/sentinel_test"`
4. Restart test container if using Docker

### Scenario 2: Integration Tests Fail

**Symptom:** One or more of 19 tests fail with endpoint error (e.g., 404, 500)

**Recovery:**
1. Read test output to identify which test failed
2. Check error message: Is it a code bug, database schema issue, or test configuration?
3. If code bug: Fix implementation and re-run tests
4. If schema issue: Run `alembic upgrade head` to migrate schema
5. If configuration: Check `.env` and DATABASE_URL

### Scenario 3: MyPy Errors Found

**Symptom:** `uv run mypy backend/app --strict` returns errors

**Recovery:**
1. Read error message and file:line number
2. Add type hint or fix incompatible assignment
3. Re-run MyPy
4. Repeat until exit code 0
5. If library types incomplete: Use `cast()` or `# type: ignore` (with comment)

### Scenario 4: Concurrency Test Fails

**Symptom:** Both concurrent refresh requests succeed (double-use vulnerability)

**Recovery:**
1. Check `RefreshTokenRepository.get_by_jti()` method
2. Verify it uses `SELECT ... FOR UPDATE` or equivalent row locking
3. Add row lock if missing:
   ```python
   # Before: vulnerable
   token = session.query(RefreshToken).filter(RefreshToken.jti == jti).first()
   
   # After: safe
   token = session.query(RefreshToken).filter(
       RefreshToken.jti == jti
   ).with_for_update().first()
   ```
4. Re-run test

---

## Success Criteria

Verification Closure is **COMPLETE** when:

1. ✅ All 4 quality gates **PASS** (Ruff, MyPy, Compileall, Integration Tests)
2. ✅ All security properties **VERIFIED** (no timing attacks, RBAC working, etc.)
3. ✅ Concurrency test **PASSES** (token rotation atomic, single success)
4. ✅ Certification checklist **100% COMPLETE** (all items ✓)
5. ✅ Verification report **CREATED** with final status and sign-off
6. ✅ Epic 4 status updated to **🟢 COMPLETE & VERIFIED**

**Next Milestone:** Epic 5 (Audit Logging & Compliance) can begin.

</content>
