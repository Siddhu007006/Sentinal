# Requirements Document

## Epic 4 Verification Closure

**Objective:** Close the three remaining verification gates (PostgreSQL integration testing, MyPy --strict type checking, compileall verification) and perform focused security review of token rotation concurrency semantics.

**Status:** Requirements Phase (Entry Point)
**Backlog Reference:** Continuation of Epic 4 (Authentication & Authorization)
**Priority:** P0 (blocks Epic 5 start)
**Architectural Owner:** Backend Platform Engineering (Security Architecture Function)
**Dependencies:** Epic 4 implementation complete (all E4.T1–E4.T11 tasks completed)

**Date:** August 2026
**Classification:** 🟡 IMPLEMENTATION COMPLETE / VERIFICATION PENDING

---

## Introduction

Epic 4 implementation is architecturally sound and substantially complete. However, three critical verification gates remain unclosed:

1. **PostgreSQL Integration Test Execution** — Tests written (19 test cases) but cannot execute without database infrastructure
2. **MyPy --strict Type Checking** — Environment issue (Python venv not initialized); code verified correct but not formally certified
3. **Compileall Verification** — Environment issue; code syntax verified but not formally compiled

Additionally, **token rotation concurrency semantics** require focused review to ensure that concurrent refresh requests with the same refresh token are atomically handled (preventing double-use vulnerability).

This epic delivers the verification infrastructure, test execution, type certification, and focused security review needed to formally close Epic 4 and enable Epic 5 start.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Verification Gate** | A quality checkpoint that must pass before epic can be declared complete/verified |
| **Integration Test** | End-to-end test exercising full HTTP stack, database, and service dependencies |
| **MyPy --strict** | Type checker with maximum strictness; catches any untyped code or type inconsistencies |
| **Compileall** | Python bytecode compiler; verifies all modules can compile without syntax errors |
| **Token Rotation Concurrency** | Race condition where same refresh token used twice simultaneously; must be blocked by atomic database operations |
| **Atomic Operation** | Database transaction that cannot be partially executed; all-or-nothing semantic |
| **Fail-Safe** | System design where failures result in secure state (e.g., token rejected rather than accepted) |

---

## Requirements

### Requirement 1: PostgreSQL Infrastructure Setup & Database Initialization

**User Story:**  
As a verification engineer, I want PostgreSQL to be running with test database initialized so that integration tests can execute against a real database and verify all HTTP endpoints work end-to-end.

#### Acceptance Criteria

1. WHEN the verification suite is started, A PostgreSQL database server SHALL be available (local or CI environment)
2. WHEN the test suite runs, A test database named `sentinel_test` SHALL be initialized with schema matching production migrations
3. WHERE Alembic migrations exist, THE test database SHALL be populated by running all migrations from `alembic/versions/`
4. WHEN `.env` or test configuration is loaded, THE DATABASE_URL environment variable SHALL point to the test database (e.g., `postgresql://localhost/sentinel_test`)
5. WHEN integration tests execute, THE test database SHALL be cleaned/reset between test runs (start each test with known state)
6. WHERE database fixtures are needed, THEY SHALL be idempotent (can be run multiple times without failing)

#### Architectural Notes

- Test database must be separate from development database (prevents test pollution of dev data)
- Test database initialization via Alembic ensures schema consistency with production
- Connection pooling may not work for tests (set pool size to 1 or disable connection pooling for tests)

---

### Requirement 2: Integration Test Execution (19 test cases)

**User Story:**  
As a QA engineer, I want all integration tests to execute against the real database and pass, verifying that all authentication endpoints work correctly in realistic conditions.

#### Acceptance Criteria

1. WHEN `pytest backend/tests/integration/test_auth_routes.py -v` is executed, ALL 19 test cases SHALL pass
2. THE 19 test cases SHALL include:
   - ✅ 6 registration tests (success, duplicate, weak password, invalid email, missing email, optional fullname)
   - ✅ 4 login tests (success, wrong password, user not found, missing credentials)
   - ✅ 3 refresh tests (success with rotation, invalid token, missing token)
   - ✅ 3 logout tests (device-specific, missing header, invalid token)
   - ✅ 3 profile tests (get authenticated profile, missing token, invalid token)
3. WHEN a test passes, IT SHALL verify HTTP status code, response structure, and response content per acceptance criteria in tasks.md
4. WHERE database state is checked (e.g., user created, token revoked), THE test SHALL query the database to verify state change
5. WHERE transactions are involved (e.g., token rotation), THE test SHALL verify atomicity (no partial state)

#### Test Coverage Detail

**Registration Tests (test_auth_routes.py::TestAuthRegister)**
- test_register_success: 201 response with user profile (no password)
- test_register_duplicate_email: 409 Conflict on duplicate
- test_register_weak_password: 400 Bad Request (<12 chars)
- test_register_invalid_email: 400 Bad Request (bad format)
- test_register_missing_email: 422 Unprocessable Entity (missing field)
- test_register_optional_full_name: 201 with fullName=null if omitted

**Login Tests (test_auth_routes.py::TestAuthLogin)**
- test_login_success: 200 with accessToken, refreshToken
- test_login_wrong_password: 401 Unauthorized (no distinction from user not found)
- test_login_user_not_found: 401 Unauthorized (no enumeration)
- test_login_missing_credentials: 422 Unprocessable Entity

**Refresh Tests (test_auth_routes.py::TestAuthRefresh)**
- test_refresh_success: 200 with new token pair (different from old)
- test_refresh_invalid_token: 401 Unauthorized
- test_refresh_missing_token: 422 Unprocessable Entity

**Logout Tests (test_auth_routes.py::TestAuthLogout)**
- test_logout_device_specific: 204 No Content on device-specific logout
- test_logout_missing_auth_header: 401 Unauthorized
- test_logout_invalid_token: 401 Unauthorized

**Profile Tests (test_auth_routes.py::TestAuthMe)**
- test_get_me_success: 200 with authenticated user profile
- test_get_me_missing_token: 401 Unauthorized
- test_get_me_invalid_token: 401 Unauthorized

#### Architectural Notes

- Tests MUST exercise the real HTTP stack (not mocked), so they verify middleware, route dispatch, and exception handling
- Database state must be validated; tests must query the database to ensure side effects occurred (user created, token revoked, etc.)
- Tests should be isolated: each test creates its own users and tokens; no test depends on another test's side effects

---

### Requirement 3: MyPy --strict Type Checking

**User Story:**  
As a type-safety engineer, I want MyPy to formally verify that all code is correctly typed, preventing type errors that could cause runtime failures.

#### Acceptance Criteria

1. WHEN `uv run mypy backend/app --strict` is executed, THE exit code SHALL be 0 (no errors)
2. WHEN the command exits with 0, IT SHALL mean all code in `backend/app/` is correctly typed with no implicit `Any` types
3. WHERE a type error is found (e.g., incompatible assignment, missing type hint), THE error message SHALL be clear and actionable
4. THE following modules are most critical (MUST have 0 errors):
   - `backend/app/infrastructure/security/password.py` (password hashing)
   - `backend/app/infrastructure/security/jwt.py` (token service)
   - `backend/app/api/v1/dependencies/auth.py` (auth middleware)
   - `backend/app/application/services/auth_service.py` (core auth logic)
   - `backend/app/domain/entities/user.py` (user entity)
5. IF mypy fails, THE error SHALL be fixed by:
   - Adding missing type hints to function signatures/variables
   - Using `cast()` or `# type: ignore` comments only as last resort (with explanation)
   - Updating types to match library signatures (e.g., PyJWT, argon2, bcrypt)

#### Architectural Notes

- MyPy --strict is the highest type-checking level; it catches edge cases that default mypy misses
- Some library types may be incomplete; use cast() or type: ignore judiciously
- All function parameters and return types must be annotated in security modules

---

### Requirement 4: Compileall Verification

**User Story:**  
As a deployment engineer, I want Python to formally verify that all modules can compile to bytecode, ensuring no syntax errors are present.

#### Acceptance Criteria

1. WHEN `python -m compileall backend/app` is executed, THE exit code SHALL be 0
2. WHEN the command exits with 0, IT SHALL mean all `.py` files in `backend/app/` compile successfully to `.pyc` bytecode
3. WHERE compilation fails (syntax error), THE error message SHALL indicate the file and line number
4. WHERE errors are found, THEY SHALL be syntax issues that were missed by linting (should not happen if Ruff checks are passing)

#### Architectural Notes

- Compileall is a low-level check; if Ruff and MyPy pass, compileall should pass automatically
- Useful as a final verification that Python interpreter accepts the code

---

### Requirement 5: Token Rotation Concurrency Review

**User Story:**  
As a security architect, I want to verify that token rotation (refresh endpoint) is immune to race conditions where the same refresh token is used concurrently, preventing double-use vulnerability.

#### Acceptance Criteria

1. WHEN two concurrent `POST /auth/refresh` requests arrive with the SAME refresh token, EXACTLY ONE SHALL succeed and return a new token pair
2. THE other request SHALL fail with 401 Unauthorized (TokenRevokedError or TokenExpiredError)
3. THE database refresh token entry SHALL show state=`revoked` after the first request succeeds
4. THE successful response SHALL contain a new refreshToken with unique `jti` claim (different from both prior refresh tokens)
5. WHERE the first refresh transaction is: [check_revoked] → [revoke_old_token] → [issue_new_tokens] → [store_new_token] → [commit]
6. THE transaction isolation level SHALL be sufficient to prevent both requests from simultaneously reading is_revoked=False and both succeeding
7. WHERE database uses READ COMMITTED isolation (PostgreSQL default), ROW-LEVEL LOCKING with `SELECT ... FOR UPDATE` SHALL be used in [check_revoked] step to prevent race condition

#### Concurrency Test Scenario

```python
async def test_concurrent_refresh_same_token_blocked():
    """
    Verify that refreshing with the same token twice concurrently
    only succeeds once; the other is rejected.
    """
    # Setup: create user and get initial tokens
    user = await auth_service.register(
        email="concurrent@test.local",
        password="P@ssword123456",
    )
    _, refresh_token_1 = await auth_service.login(
        email="concurrent@test.local",
        password="P@ssword123456",
    )
    
    # Concurrent refresh: both requests use same refresh_token_1
    task_1 = asyncio.create_task(
        auth_service.refresh(refresh_token_1)
    )
    task_2 = asyncio.create_task(
        auth_service.refresh(refresh_token_1)
    )
    
    results = await asyncio.gather(task_1, task_2, return_exceptions=True)
    
    # Expected: one succeeds, one fails
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, (TokenRevokedError, TokenExpiredError))]
    
    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected 1 failure, got {len(failures)}"
    
    # Verify both returned pairs are different (no shared state)
    if len(successes) == 2:
        pair_1, pair_2 = successes[0], successes[1]
        # VULNERABILITY: both succeeded!
        pytest.fail("Concurrent refresh should not both succeed")
```

#### Architectural Notes

- This is a critical security test; must verify with database locked (not just in-memory cache)
- PostgreSQL `SELECT ... FOR UPDATE` prevents race condition by acquiring row lock
- Test must be async/concurrent; sequential test would pass even if code is vulnerable
- Scenario: If user's token is stolen and attacker attempts double-use, system must detect and reject

---

### Requirement 6: Security & Quality Certification Checklist

**User Story:**  
As an engineering lead, I want a formal checklist verifying all security properties, quality gates, and design requirements have been met before Epic 4 is declared "COMPLETE & VERIFIED".

#### Acceptance Criteria

1. ✅ All quality gates PASS:
   - [ ] Ruff: `uv run ruff check backend/app` → Exit 0, 0 violations
   - [ ] MyPy --strict: `uv run mypy backend/app --strict` → Exit 0, 0 errors
   - [ ] Compileall: `python -m compileall backend/app` → Exit 0
   - [ ] Integration Tests: `pytest backend/tests/integration/test_auth_routes.py -v` → 19/19 pass

2. ✅ Security properties VERIFIED:
   - [ ] Password Hashing: Argon2id/bcrypt constant-time verification
   - [ ] JWT Claims: All required claims present (sub, exp, iat, jti, role for access)
   - [ ] Token Lifetimes: Access 15min, Refresh 30days
   - [ ] Token Revocation: Checked on every refresh, not cached
   - [ ] RBAC: Role sourced from JWT only, never from request body
   - [ ] Enumeration Prevention: 404 on both "not found" and "forbidden"
   - [ ] Audit Logging: All auth/authz events logged
   - [ ] Soft-Delete: Inactive users filtered from queries
   - [ ] Token Rotation Concurrency: Single refresh token cannot be used twice concurrently

3. ✅ Requirements Traceability:
   - [ ] All Requirement 1–10 acceptance criteria implemented
   - [ ] All E4.T1–E4.T11 tasks marked complete
   - [ ] No functionality gaps identified

4. ✅ Code Quality:
   - [ ] No passwords/hashes in logs or responses
   - [ ] No hard-coded secrets in code
   - [ ] All error responses use RFC 7807 format
   - [ ] All endpoints have proper exception handling
   - [ ] Type hints complete in security modules

5. ✅ Test Coverage:
   - [ ] All test cases written and executable
   - [ ] Happy paths and error cases tested
   - [ ] Multi-device session scenarios tested
   - [ ] Token rotation scenarios tested
   - [ ] RBAC enforcement tested

6. ✅ Documentation:
   - [ ] Audit report created (EPIC_4_COMPREHENSIVE_AUDIT_REPORT.md)
   - [ ] Verification roadmap documented
   - [ ] Concurrency review completed
   - [ ] No issues blocking Epic 4 closure

#### Architectural Notes

- This checklist is the formal gate; Epic 4 is not released until all items pass
- Each item must be independently verifiable (not subjective)
- If any item fails, Epic 4 remains in VERIFICATION PENDING status

---

## Definition of Done

Epic 4 Verification Closure is **COMPLETE** when ALL of the following are verified:

1. ✅ PostgreSQL database running and test database initialized per Requirement 1
2. ✅ All 19 integration tests pass per Requirement 2
3. ✅ MyPy --strict exits with 0 errors per Requirement 3
4. ✅ Compileall exits with 0 errors per Requirement 4
5. ✅ Token rotation concurrency reviewed and verified per Requirement 5
6. ✅ Security & Quality Certification Checklist all items verified per Requirement 6
7. ✅ Audit report updated with final status: **COMPLETE & VERIFIED**
8. ✅ No blocking issues remain
9. ✅ Epic 5 entry point clear and ready

**Final Status Classification:** 🟢 **IMPLEMENTATION COMPLETE & VERIFIED**

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| **PostgreSQL not available** | Medium | Integration tests cannot execute; verification gate blocked | Set up PostgreSQL container (Docker) or use CI database provisioning |
| **MyPy errors in security modules** | Low | Type unsafety could cause runtime errors | Review errors and add type hints; use cast() only as fallback |
| **Concurrency vulnerability in token rotation** | Low | Same token could be used twice; session hijacking | Use database row locking (SELECT FOR UPDATE) in refresh logic |
| **Integration tests fail** | Medium | Endpoint contracts broken; requires code fixes | Review test failures and fix implementation bugs |
| **Alembic migrations not complete** | Low | Test database schema incomplete; tests fail unexpectedly | Run all migrations before test execution |

---

## Success Criteria

The verification suite is successful when:

1. 🟢 All 4 quality gates pass (Ruff, MyPy, Compileall, Integration Tests)
2. 🟢 All security properties verified (no timing attacks, RBAC working, audit logged, etc.)
3. 🟢 No blocking issues or vulnerabilities discovered
4. 🟢 Concurrency review confirms token rotation is atomic and race-condition-free
5. 🟢 Verification checklist 100% complete
6. 🟢 Epic 4 status updated to: 🟢 **COMPLETE & VERIFIED**

Once verified, **Epic 5 can begin**.

</content>
