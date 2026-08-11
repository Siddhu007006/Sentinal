# Tasks: Epic 4 - Authentication & Authorization

## Overview

Epic 4 consists of 11 implementation tasks (E4.T1–E4.T11) corresponding to the 10 requirements plus infrastructure/refactoring work.

**Backlog Reference:** docs/22-Engineering-Backlog.md § E4  
**Spec Files:** requirements.md, design.md  
**Dependencies:** Epic 3 (database foundation complete)  
**Quality Gates:**
- Ruff: 0 violations
- MyPy --strict: 0 errors
- Pytest: All unit and integration tests pass
- Compileall: Success

---

## Task Dependencies

```
E4.T1 (User Entity) → E4.T2 (Password Hasher) → E4.T3 (Token Service)
                                                 ↓
                                    E4.T4 (Auth Service)
                                                 ↓
                                    E4.T5 (Auth Middleware)
                                                 ↓
E4.T6 (Auth Routes) ← E4.T7 (User Mgmt Routes) ← E4.T8 (RBAC)
    ↓
E4.T9 (Audit Logging) → E4.T10 (Session Mgmt) → E4.T11 (Integration)
```

---

## Task Definitions

### E4.T1: User Domain Entity

**Objective:** Implement the User domain entity with validation, role-based permissions, and support for profile mutation.

**Requirements Traceability:** Requirement 1 (User Domain Entity)

**Design Reference:** design.md § Core Components → User Domain Entity

**Acceptance Criteria:**

1. User entity created at `app/domain/entities/user.py`
2. User has immutable fields: `id`, `email`, `created_at`
3. User has mutable fields: `full_name`, `role`, `is_active`, `updated_at`, `deleted_at`
4. UserRole enum with exactly three values: `ADMIN`, `ANALYST`, `VIEWER`
5. Email validation enforces valid format (contains @, non-empty parts)
6. Role validation enforces UserRole enum values only
7. `password_hash` is never plaintext; verified via hashing algorithm only
8. Soft-delete via `deactivate()` method sets `is_active=False` and `deleted_at=<now>`
9. Profile update methods: `update_profile(full_name)`, `update_role(new_role)`
10. All invariants verified in `validate()` method
11. Unit tests pass: `test_user_entity.py` (all tests, no skips)

**Implementation Steps:**

1. Define UserRole enum with three string values (admin, analyst, viewer)
2. Define User dataclass with all fields per design.md
3. Implement validate() method with email format and role checks
4. Implement deactivate(), update_profile(), update_role() methods
5. Write unit tests: creation, validation, role checks, soft-delete, profile updates
6. Run Ruff, MyPy --strict, compileall

**Subtasks:**

- [x] Create user.py with UserRole enum and User class
- [x] Write unit tests for User entity
- [x] Verify design.md constraints

---

### E4.T2: Password Hashing Service

**Objective:** Implement adaptive password hashing with constant-time verification to prevent timing attacks.

**Requirements Traceability:** Requirement 2 (Password Hashing Service)

**Design Reference:** design.md § Core Components → Password Hashing Service

**Acceptance Criteria:**

1. PasswordHasherInterface created with abstract methods
2. ArgonPasswordHasher implementation using argon2id (default)
3. BcryptPasswordHasher implementation as alternative
4. Both implementations use constant-time comparison (never `==` on secrets)
5. hash_password(plaintext) produces non-reversible hash
6. Same plaintext hashed twice produces different hashes (due to salt)
7. verify_password(plaintext, hash) returns True on match, False on mismatch
8. Execution time of verify_password() does NOT vary based on mismatch position
9. Passwords/hashes NEVER appear in logs
10. get_password_hasher() factory selects algorithm from settings (default argon2id)
11. Work factor tuned for ~100ms computation on modern CPU
12. Unit tests pass: `test_password_hasher.py` (all tests)

**Implementation Steps:**

1. Create `app/infrastructure/security/password.py`
2. Define PasswordHasherInterface with hash_password(), verify_password(), needs_rehash()
3. Implement ArgonPasswordHasher with argon2id (time_cost=2, memory=65536MB, parallelism=4)
4. Implement BcryptPasswordHasher with cost=12
5. Implement get_password_hasher() factory that reads settings.PASSWORD_HASHING_ALGORITHM
6. Add PASSWORD_HASHING_ALGORITHM setting (default "argon2id")
7. Write unit tests: hash uniqueness, verification correctness, timing attack resistance
8. Run Ruff, MyPy --strict, compileall

**Subtasks:**

- [x] Create password.py with PasswordHasherInterface
- [x] Implement ArgonPasswordHasher
- [x] Implement BcryptPasswordHasher
- [x] Write unit tests for password hashing
- [x] Verify constant-time comparison logic

---

### E4.T3: JWT Token Service

**Objective:** Implement JWT creation, validation, and claim verification with HS256/RS256 algorithm support.

**Requirements Traceability:** Requirement 3 (JWT Token Service)

**Design Reference:** design.md § Core Components → JWT Token Service

**Acceptance Criteria:**

1. TokenPayload class created with sub, role, exp, iat, jti fields
2. TokenExpiredError and InvalidTokenError exception classes defined
3. TokenService class created with create_access_token(), create_refresh_token(), decode_token()
4. Access token lifetime: exactly 15 minutes from issuance
5. Refresh token lifetime: exactly 30 days from issuance
6. Each token includes unique jti (JWT ID) for revocation tracking
7. Access tokens include `role` claim; refresh tokens do not
8. decode_token() returns TokenPayload on valid, unexpired token
9. decode_token() raises TokenExpiredError on expired token
10. decode_token() raises InvalidTokenError on invalid signature or missing claims
11. Algorithm configurable via settings (HS256 default, RS256 supported)
12. Secret key sourced from JWT_SECRET_KEY setting (>= 32 bytes for HS256)
13. Unit tests pass: `test_token_service.py` (all tests)

**Implementation Steps:**

1. Create `app/infrastructure/security/jwt.py`
2. Define TokenPayload dataclass with all required claims
3. Define exception classes (TokenExpiredError, InvalidTokenError)
4. Implement TokenService with algorithm/key configuration from settings
5. Implement create_access_token(user_id, role) → JWT string with 15min exp
6. Implement create_refresh_token(user_id) → JWT string with 30day exp
7. Implement decode_token(token) with claim validation and expiry check
8. Add JWT_ALGORITHM, JWT_SECRET_KEY settings (HS256, at least 32 bytes)
9. Write unit tests: token creation, expiry, signature validation, claim validation
10. Run Ruff, MyPy --strict, compileall

**Subtasks:**

- [x] Create jwt.py with TokenPayload and TokenService
- [x] Implement token creation with correct lifetimes
- [x] Implement token decoding with claim validation
- [x] Write unit tests for token lifecycle
- [x] Verify algorithm and key configuration

---

### E4.T4: Authentication Service (Core Logic)

**Objective:** Implement high-level authentication orchestration: register, login, refresh, logout with audit logging integration.

**Requirements Traceability:** Requirement 5 (Auth Service)

**Design Reference:** design.md § Core Components → Authentication Service

**Acceptance Criteria:**

1. AuthService class created in `app/application/services/auth_service.py`
2. register(email, password, full_name) → User (creates new user with VIEWER role)
3. register() raises DuplicateEmailError if email exists
4. register() raises ValidationError on invalid email format
5. register() raises PasswordTooWeakError if password < 12 characters
6. login(email, password) → TokenPair (access_token, refresh_token)
7. login() raises InvalidCredentialsError on wrong password (no email enumeration)
8. login() raises InvalidCredentialsError if user inactive
9. refresh(refresh_token) → TokenPair (new access + refresh with token rotation)
10. refresh() raises TokenExpiredError on expired token
11. refresh() raises TokenRevokedError if token revoked
12. refresh() revokes old token immediately and stores new token
13. logout(user_id, refresh_token) or logout_all_sessions(user_id)
14. All operations create AuditLog entries (register, login, logout, refresh)
15. Unit tests pass: `test_auth_service.py` (all tests)

**Implementation Steps:**

1. Create auth_service.py with AuthService class
2. Implement register() with email validation, password strength check, duplicate email detection
3. Implement login() with password verification (constant-time), token creation, token storage
4. Implement refresh() with token rotation: decode old, verify not revoked, issue new pair, revoke old
5. Implement logout() with per-token or all-sessions revocation
6. Integrate with PasswordHasher, TokenService, UserRepository, RefreshTokenRepository, AuditService
7. Write unit tests: register success/fail cases, login success/fail, refresh, logout, audit creation
8. Run Ruff, MyPy --strict, compileall

**Subtasks:**

- [x] Create auth_service.py with core methods
- [x] Implement register with validations
- [x] Implement login with constant-time verification
- [x] Implement refresh with token rotation
- [x] Implement logout with revocation
- [x] Write unit tests for all paths

---

### E4.T5: Authentication Middleware (FastAPI Dependencies)

**Objective:** Implement declarative authentication/authorization middleware via FastAPI dependency injection.

**Requirements Traceability:** Requirement 4 (Authentication Middleware)

**Design Reference:** design.md § Core Components → Authentication Middleware

**Acceptance Criteria:**

1. `get_current_user(Authorization header)` FastAPI dependency created
2. Extracts Bearer token from Authorization header
3. Raises 401 Unauthorized if header missing or malformed
4. Raises 401 Unauthorized if token expired or signature invalid
5. Loads User from repository by user_id from token
6. Raises 401 Unauthorized if user not found or is_active=False
7. Returns User object injected into route handler
8. `require_role(role)` factory returns dependency checking user.role
9. require_role() raises 403 Forbidden if role mismatch
10. require_role() accepts single role string or list of roles (any match permitted)
11. Dependency created at `app/api/v1/dependencies/auth.py`
12. Unit tests pass: `test_auth_middleware.py` (all tests)

**Implementation Steps:**

1. Create dependencies/auth.py with get_current_user() and require_role() factories
2. Implement get_current_user() dependency: extract header, decode token, load user, re-check is_active
3. Implement require_role() factory returning dependency that validates user.role
4. Add proper exception handling: 401 Unauthorized, 403 Forbidden
5. Write unit tests: valid token, expired token, missing header, user not found, role mismatch
6. Run Ruff, MyPy --strict, compileall

**Subtasks:**

- [x] Create dependencies/auth.py with core dependencies
- [x] Implement get_current_user with header parsing and token validation
- [x] Implement require_role factory
- [x] Write unit tests for dependencies
- [x] Test error cases (missing token, invalid sig, user not found)

---

### E4.T6: Auth Route Handlers (Login, Register, Refresh, Logout)

**Objective:** Implement REST endpoints for authentication (register, login, refresh, logout, profile).

**Requirements Traceability:** Requirement 6 (Auth Route Handlers)

**Design Reference:** design.md § Auth Flows

**Acceptance Criteria:**

1. `POST /auth/register` endpoint (public, no auth required)
2. Accepts JSON: {email, password, full_name}
3. Returns: {user_id, email, full_name, role, created_at} (no password/hash)
4. `POST /auth/login` endpoint (public, no auth required)
5. Accepts JSON: {email, password}
6. Returns: {access_token, refresh_token} (TokenPair)
7. `POST /auth/refresh` endpoint (requires valid refresh token)
8. Accepts JSON: {refresh_token}
9. Returns: {access_token, refresh_token} (new TokenPair)
10. `POST /auth/logout` endpoint (requires access token)
11. Accepts JSON: {refresh_token} (optional); or ?logout_all=true
12. Returns 204 No Content on success
13. `GET /auth/me` endpoint (requires access token)
14. Returns authenticated user's profile: {user_id, email, full_name, role, created_at}
15. All errors use RFC 7807 Problem Details format (application/problem+json)
16. Malformed input → 400 Bad Request with RFC 7807 detail
17. Missing auth header → 401 Unauthorized
18. Integration tests pass: `test_auth_routes.py` (all tests)

**Implementation Steps:**

1. Create routes file at `app/api/v1/routes/auth.py`
2. Implement POST /auth/register handler with input validation
3. Implement POST /auth/login handler with AuthService.login()
4. Implement POST /auth/refresh handler with AuthService.refresh()
5. Implement POST /auth/logout handler with AuthService.logout()
6. Implement GET /auth/me handler with get_current_user dependency
7. Add RFC 7807 error responses via FastAPI exception handlers
8. Write integration tests: register, login, refresh, logout, auth flows
9. Run Ruff, MyPy --strict, compileall

**Subtasks:**

- [x] Create auth.py routes file
- [x] Implement register endpoint
- [x] Implement login endpoint
- [x] Implement refresh endpoint
- [x] Implement logout endpoint
- [x] Implement /auth/me endpoint
- [x] Write integration tests

---

### E4.T7: User Management Routes (List, Get, Update, Delete)

**Objective:** Implement user management endpoints with RBAC enforcement and soft-delete.

**Requirements Traceability:** Requirement 7 (User Management Routes)

**Design Reference:** design.md § Authorization Flows

**Acceptance Criteria:**

1. `GET /users` endpoint (admin-only, paginated list)
2. Returns paginated User list with metadata
3. Non-admin → 403 Forbidden
4. `GET /users/{userId}` endpoint (admin or user themself)
5. Returns User profile; non-owner non-admin → 404 Not Found (no enumeration)
6. `PATCH /users/{userId}` endpoint (admin or user themself)
7. Accepts: {full_name, role (admin only)}
8. Non-admin attempting role change → 403 Forbidden
9. Admin can change role for other users
10. `DELETE /users/{userId}` endpoint (admin-only soft-delete)
11. Sets is_active=False and deleted_at=<now>
12. Returns 204 No Content
13. Soft-deleted users → 404 Not Found in queries
14. Role changes create AuditLog with old_role, new_role
15. User deactivation creates AuditLog with action="user_deactivated"
16. All errors use RFC 7807 format
17. Integration tests pass: `test_user_routes.py` (all tests)

**Implementation Steps:**

1. Create routes file at `app/api/v1/routes/users.py`
2. Implement GET /users with require_role("admin") dependency
3. Implement GET /users/{userId} with ownership or admin check (404 on forbidden)
4. Implement PATCH /users/{userId} with role change logic (403 if non-admin tries role change)
5. Implement DELETE /users/{userId} with soft-delete (is_active=False, deleted_at=now)
6. All endpoints create appropriate audit logs
7. Write integration tests: list, get, update, delete, RBAC checks
8. Run Ruff, MyPy --strict, compileall

**Subtasks:**

- [x] Create users.py routes file
- [x] Implement GET /users (admin-only, paginated)
- [x] Implement GET /users/{userId} (ownership check, 404 on forbidden)
- [x] Implement PATCH /users/{userId} (role change with RBAC)
- [x] Implement DELETE /users/{userId} (soft-delete)
- [ ] Write integration tests

---

### E4.T8: RBAC Enforcement Across Endpoints

**Objective:** Verify role-based access control is consistently enforced across all endpoints.

**Requirements Traceability:** Requirement 9 (RBAC Enforcement)

**Design Reference:** design.md § Authorization Flows

**Acceptance Criteria:**

1. Three roles defined: admin, analyst, viewer (no other values permitted)
2. Admin role permits: user management, audit log access, all analyst/viewer capabilities
3. Analyst role permits: upload files, request analyses, view own uploads/analyses/reports
4. Viewer role permits: view shared reports, view shared analyses, view own profile
5. Non-admin attempting admin endpoints → 403 Forbidden or 404 Not Found (resource ownership)
6. Resource ownership checks: owner or admin can access; non-owner non-admin → 404
7. Authorization failures include X-Request-ID header for traceability
8. Middleware enforces RBAC at application layer (route + business logic)
9. Role never accepted as client-supplied parameter; loaded from JWT only
10. No role overrides via request body
11. Integration tests verify all role combinations and permission boundaries
12. Tests pass: `test_rbac.py` (all tests)

**Implementation Steps:**

1. Define RBAC matrix per Requirement 9 (admin, analyst, viewer capabilities)
2. Audit existing E4.T6-E4.T7 routes to ensure require_role() calls are correct
3. Add X-Request-ID header to all error responses (for traceability)
4. Verify role comes from JWT TokenPayload, never from request
5. Write integration tests: each role attempting each endpoint (should succeed/fail per matrix)
6. Test privilege escalation prevention (non-admin cannot modify role in request)
7. Run Ruff, MyPy --strict, compileall

**Subtasks:**

- [x] Document RBAC matrix per requirements
- [x] Audit E4.T6-E4.T7 route role decorators
- [x] Add X-Request-ID to error responses
- [x] Write comprehensive RBAC tests
- [x] Verify role is never client-supplied

---

### E4.T9: Audit Logging for Auth/Authz Events

**Objective:** Implement immutable, append-only audit logging for all authentication and authorization events.

**Requirements Traceability:** Requirement 8 (Audit Logging)

**Design Reference:** design.md; depends on E3.T8 AuditLog model

**Acceptance Criteria:**

1. AuditLog entity immutable: no UPDATE/DELETE endpoints exist
2. All auth events logged: register, login, logout, refresh, login_failed
3. All authz events logged: user deactivation, role changes
4. Login failures logged with email (not user_id, since user may not exist)
5. Login failures include reason: invalid_password, user_inactive, user_not_found
6. AuditLog includes: user_id, action, resource_type, resource_id, timestamp, ip_address, status, details (JSON)
7. Timestamps use server time (never client-supplied)
8. `GET /audit-logs` endpoint (admin-only, paginated)
9. Filterable by user_id, action, date_range
10. `GET /audit-logs/{auditLogId}` endpoint (admin-only)
11. Non-admin accessing audit logs → 403 Forbidden
12. Audit log creation fails gracefully: does not block auth operations
13. Failed audit writes logged to structured logs for ops visibility
14. Integration tests pass: `test_audit_logging.py` (all tests)

**Implementation Steps:**

1. Verify E3.T8 AuditLog model exists and is immutable (no UPDATE/DELETE)
2. Integrate AuditService into AuthService: log all auth events
3. Integrate AuditService into user management routes: log all authz events
4. Create GET /audit-logs endpoint (admin-only, paginated, filterable)
5. Create GET /audit-logs/{auditLogId} endpoint (admin-only)
6. Implement fail-safe: if audit write fails, log error but do not block auth
7. Write integration tests: audit events created for all auth/authz operations
8. Test that failed audit writes do not prevent login/logout
9. Run Ruff, MyPy --strict, compileall

**Subtasks:**

- [x] Verify E3.T8 AuditLog model is immutable
- [x] Integrate AuditService logging into AuthService
- [x] Add audit logging to user management routes
- [x] Implement GET /audit-logs endpoints
- [x] Write integration tests for audit logging
- [x] Test fail-safe behavior

---

### E4.T10: Session & Token Lifecycle Management

**Objective:** Implement multi-device session management with per-device logout and login-all revocation.

**Requirements Traceability:** Requirement 10 (Session & Token Lifecycle)

**Design Reference:** design.md § Token Lifecycle Flows

**Acceptance Criteria:**

1. Each login creates independent refresh token (separate session)
2. User can log in from multiple devices simultaneously
3. logout(refresh_token) revokes only that token (device-specific)
4. logout_all_sessions(user_id) revokes all tokens for user
5. Refresh of revoked token → 401 Unauthorized
6. Refresh issues new access token with new jti claim
7. User deactivation (DELETE /users/{userId}) immediately revokes all refresh tokens
8. Revocation list checked on every refresh (not cached)
9. Integration tests verify multi-device scenarios
10. Tests pass: `test_session_lifecycle.py` (all tests)

**Implementation Steps:**

1. Verify RefreshTokenRepository supports per-token and all-tokens revocation
2. Verify refresh endpoint checks revocation list before issuing new tokens
3. Verify logout endpoint revokes specific token or all tokens per parameter
4. Verify user deactivation calls revoke_all_for_user()
5. Write integration tests: login from 2 devices, logout from 1, verify other device still works
6. Write test: logout_all revokes all devices
7. Write test: deactivation revokes all tokens
8. Run Ruff, MyPy --strict, compileall

**Subtasks:**

- [x] Verify RefreshTokenRepository per-device revocation
- [x] Verify logout-specific and logout-all logic
- [x] Verify user deactivation revokes all tokens
- [x] Write multi-device session tests
- [x] Test all-sessions logout
- [x] Test deactivation revokes tokens

---

### E4.T11: Integration & Quality Assurance

**Objective:** End-to-end testing, security verification, and quality gate validation for Epic 4.

**Requirements Traceability:** All Requirements (integration test)

**Design Reference:** design.md (all sections)

**Acceptance Criteria:**

1. All unit tests pass (E4.T1–E4.T10): `pytest backend/tests/unit -q`
2. All integration tests pass: `pytest backend/tests/integration -q`
3. All API contract tests pass against openapi.yaml
4. Ruff: 0 violations for app code: `uv run ruff check backend/app`
5. MyPy --strict: 0 errors for app code: `mypy backend/app --strict`
6. Compileall: Success: `python -m compileall backend/app`
7. Coverage: >= 85% for authentication/authorization modules
8. Security review: 
   - No passwords/hashes in logs ✓
   - Constant-time password comparison verified ✓
   - JWT validation confirmed ✓
   - Token revocation checked on refresh ✓
   - RBAC enforced on all protected endpoints ✓
9. End-to-end flow tests: register → login → token refresh → logout
10. Multi-user scenarios: concurrent logins, role changes, deactivation
11. All acceptance criteria from Requirements 1–10 verified
12. Final verification report created

**Implementation Steps:**

1. Run all unit tests; fix any failures
2. Run all integration tests; fix any failures
3. Run Ruff check on backend/app; fix violations
4. Run MyPy --strict on backend/app; fix errors
5. Run compileall on backend/app; verify success
6. Measure coverage; ensure >= 85%
7. Security checklist: password verification, JWT validation, revocation, RBAC
8. Run end-to-end scenarios (register → login → refresh → logout)
9. Create final verification report with all test results
10. Update project status to "Epic 4 complete" only if all gates pass

**Subtasks:**

- [x] Run full unit test suite and fix failures
- [x] Run full integration test suite and fix failures
- [x] Run Ruff check and fix violations
- [x] Run MyPy --strict and fix errors
- [x] Run compileall and verify success
- [x] Measure and verify coverage >= 85%
- [x] Perform security review and verification
- [x] Create final verification report

---

## Completion Criteria

Epic 4 is **COMPLETE** when:

1. ✅ All E4.T1–E4.T11 tasks have `status=completed`
2. ✅ All unit tests pass with 0 failures: `pytest backend/tests/unit -q` → all pass
3. ✅ All integration tests pass: `pytest backend/tests/integration -q` → all pass
4. ✅ Ruff: 0 violations: `uv run ruff check backend/app`
5. ✅ MyPy --strict: 0 errors: `mypy backend/app --strict`
6. ✅ Compileall: Success: `python -m compileall backend/app`
7. ✅ Coverage: >= 85% for auth modules
8. ✅ Security review checklist passed
9. ✅ Final verification report generated
10. ✅ Commit pushed to GitHub with message: "Epic 4: Authentication & Authorization complete"

---

## Notes

- **Wave-Based Scheduling**: Tasks are structured to allow parallel execution within dependency constraints:
  - Wave 1: E4.T1, E4.T2 (foundation)
  - Wave 2: E4.T3, E4.T4 (depend on Waves 1)
  - Wave 3: E4.T5, E4.T6, E4.T7 (depend on Wave 2)
  - Wave 4: E4.T8, E4.T9, E4.T10 (depend on Wave 3)
  - Wave 5: E4.T11 (integration, final wave)

- **RFC 7807 Format**: All error responses follow Problem Details standard (application/problem+json):
  - `status`: HTTP status code
  - `title`: Short error title
  - `detail`: Descriptive error message
  - `instance`: Request ID for traceability

- **Audit Logging Fail-Safe**: Auth must succeed even if audit write fails. Audit failures are logged to structured logs for ops visibility, not to the critical path.

- **Security by Default**: All endpoints require explicit authentication (no default "public"). RBAC is checked at route + business logic layers (defense in depth).
