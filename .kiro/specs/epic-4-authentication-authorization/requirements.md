# Requirements Document

## Epic 4: Authentication & Authorization

**Objective:** Implement JWT-based authentication, role-based access control (RBAC), user management endpoints, and audit logging for security-relevant actions.

**Status:** Requirements Phase  
**Backlog Reference:** docs/22-Engineering-Backlog.md § E4 (E4.T1–E4.T11)  
**Priority:** P0 (foundation for all access control)  
**Architectural Owner:** Backend Platform Engineering (Security Architecture Function)  
**Dependencies:** E3 (Database Foundation), E2 (Backend Foundation)

---

## Introduction

Epic 4 establishes the authentication and authorization layer required by the Product Requirements Document (01-PRD.md) and Security Architecture Document (08-Security-Architecture.md). The platform's value proposition depends on trust, which in turn depends on proving that:

1. **Authentication is reliable** — only legitimate users can access their own data
2. **Authorization is complete** — role-based access control prevents privilege escalation and unauthorized resource access
3. **All security-relevant actions are audited** — audit logs provide accountability and forensic capability

This epic delivers:

- **User Domain Entity** with immutable email, role-based permissions, and password hashing
- **Password Hashing Service** using adaptive cryptographic algorithms to protect user credentials
- **JWT Token Service** with short-lived access tokens and longer-lived refresh tokens for session management
- **Authentication Middleware** that validates credentials on every request
- **User Management Endpoints** for user creation, profile updates, role assignment, and soft-delete
- **Auth Endpoints** for login, logout, token refresh, and session lifecycle
- **RBAC Enforcement** across all endpoints (admin, analyst, viewer roles)
- **Audit Logging** for all authentication and authorization events

All acceptance criteria reference approved architecture documents (02-Domain-Model.md §3, 04-Database-Design.md §9–10, 05-API-Specification.md §2–3, 08-Security-Architecture.md §4–5) to ensure consistency and traceability.

---

## Glossary

| Term | Definition |
|------|-----------|
| **User** | A domain entity representing a platform user with unique email, hashed password, role, and profile information |
| **JWT (JSON Web Token)** | A stateless credential containing user identity, role, and cryptographic signature; used for request authentication |
| **Access Token** | Short-lived JWT (15 minutes) used for authenticating individual requests |
| **Refresh Token** | Long-lived JWT (30 days) used only to obtain new access tokens; revocable server-side |
| **Role** | One of three permission levels: `admin`, `analyst`, `viewer` (defined in 02-Domain-Model.md §3) |
| **RBAC** | Role-Based Access Control; permission model where coarse-grained roles determine what actions a user can perform |
| **Password Hashing** | One-way transformation of plaintext password using adaptive algorithm (bcrypt/argon2id) |
| **Audit Log** | Immutable, append-only record of security-relevant actions (login, logout, role change, user deactivation) |
| **Bearer Token** | HTTP Authorization header pattern: `Authorization: Bearer <token>` |
| **Idempotency** | Property where repeated identical requests produce the same result without side effects |
| **Soft Delete** | Marking a record as inactive (`deleted_at` timestamp) rather than physically removing it from the database |
| **JTI (JWT ID)** | Unique identifier for each JWT token, used for token revocation tracking |
| **Timing Attack** | Cryptographic vulnerability where execution time varies based on secret value; mitigated via constant-time comparison |



---

## Requirements

### Requirement 1: User Domain Entity

**User Story:**  
As a user, I want my credentials and profile to be securely stored so that I can authenticate to the platform while being confident my password is not stored in plaintext.

#### Acceptance Criteria

1. THE User Entity SHALL require an `email` attribute that uniquely identifies the user and cannot be changed after creation
2. THE User Entity SHALL require a `password_hash` attribute that is never equal to the plaintext password (verified via hashing algorithm, never substring match)
3. WHEN a User Entity is created with an invalid email format, THE Entity SHALL reject it with a clear validation error
4. WHEN a User Entity is created with an invalid role (not one of: admin, analyst, viewer), THE Entity SHALL reject it with a clear validation error
5. THE User Entity SHALL store a `role` attribute as one of exactly three values: `admin`, `analyst`, `viewer` (per 02-Domain-Model.md §3)
6. THE User Entity SHALL support in-place mutation of non-identifying fields (`full_name`, `is_active`, `role` when authorized) after creation (unlike other domain entities which are immutable)
7. WHEN a User's `is_active` field is set to False, THE User SHALL be excluded from all authentication and authorization checks (soft-delete behavior)
8. THE User Entity SHALL store a `created_at` timestamp set to the current time at creation and never modified
9. WHERE role is mutable (admin-only change), THE User Entity's validation SHALL prevent a user from modifying their own role through the User object directly (authorization boundary, not entity responsibility)

#### Architectural Notes

- Traces to: 02-Domain-Model.md §3 (User entity definition)
- Traces to: 04-Database-Design.md §5.1 (users table definition)
- Traces to: 08-Security-Architecture.md §4 (credential handling)
- **Immutability Exception**: User is deliberately mutable (unlike DigitalAsset/Analysis which are immutable). This is a deliberate domain design choice per 02-Domain-Model.md.
- **Security**: Password is never accessible as a property; only `password_hash` is stored; plaintext comparison is prevented by using verify_password() function externally.

---

### Requirement 2: Password Hashing Service

**User Story:**  
As a security engineer, I want password hashing to use a modern, adaptive algorithm so that even a full database compromise does not yield usable passwords without substantial computational cost.

#### Acceptance Criteria

1. THE PasswordHasher SHALL use bcrypt or argon2id algorithm (per 08-Security-Architecture.md §4, settable via configuration)
2. WHEN PasswordHasher.hash_password(plaintext) is called, THE result SHALL be a non-reversible hash
3. WHEN the same plaintext password is hashed twice, THE two hashes SHALL be different (due to salting)
4. WHEN PasswordHasher.verify_password(plaintext, hash) is called with correct password, THE result SHALL be True
5. WHEN PasswordHasher.verify_password(plaintext, hash) is called with incorrect password, THE result SHALL be False
6. WHEN PasswordHasher.verify_password() compares any two inputs, THE execution time SHALL NOT vary based on where the first mismatch occurs (constant-time comparison to prevent timing attacks per 08-Security-Architecture.md §4)
7. THE PasswordHasher SHALL never store or log plaintext passwords, hashes, or intermediate states in any log output
8. WHERE the algorithm's work factor is configurable, THE default work factor SHALL be tuned for approximately 100ms hash computation time on a modern CPU (per 07-Backend-Development-Standards.md §11)

#### Architectural Notes

- Traces to: 08-Security-Architecture.md §4 (password hashing)
- Traces to: 07-Backend-Development-Standards.md §11 (algorithm selection)
- **Cryptographic Correctness**: Constant-time comparison is mandatory. Use `hmac.compare_digest()` or library-provided constant-time comparison, never `==` operator.
- **No Logging**: Passwords and hashes MUST NEVER appear in logs, error messages, or debug output.

---

### Requirement 3: JWT Token Service

**User Story:**  
As a developer, I want JWT tokens to be cryptographically signed and include all necessary claims so that tokens can be validated without database lookups and tampered tokens can be detected.

#### Acceptance Criteria

1. WHEN TokenService.create_access_token(user_id, role) is called, THE result SHALL be a JWT string
2. THE access token's JWT payload SHALL include all of: `sub` (user_id), `role`, `exp` (expiration time), `iat` (issued at), `jti` (unique token ID)
3. THE access token's expiration time SHALL be exactly 15 minutes from issuance (per 05-API-Specification.md §2 assumption)
4. WHEN TokenService.create_refresh_token(user_id) is called, THE result SHALL be a JWT string
5. THE refresh token's JWT payload SHALL include: `sub` (user_id), `exp`, `iat`, `jti`
6. THE refresh token's expiration time SHALL be exactly 30 days from issuance (per 05-API-Specification.md §2 assumption)
7. WHEN TokenService.decode_token(token) receives a valid, unexpired token, THE result SHALL be a TokenPayload object with all claims
8. WHEN TokenService.decode_token(token) receives an expired token, THE result SHALL raise TokenExpiredError and NOT return a TokenPayload
9. WHEN TokenService.decode_token(token) receives a token with invalid signature, THE result SHALL raise InvalidTokenError and NOT return a TokenPayload
10. WHEN TokenService.decode_token(token) receives a token missing required claims, THE result SHALL raise InvalidTokenError
11. THE token signing algorithm SHALL be configured in settings (per 07-Backend-Development-Standards.md §11) and MUST be HS256 or RS256 (industry standard, not custom/weak algorithms)
12. THE signing key SHALL be sourced from environment configuration (JWT_SECRET_KEY setting) and MUST be at least 32 bytes for HS256 or a valid RSA private key for RS256

#### Architectural Notes

- Traces to: 08-Security-Architecture.md §4 (JWT authentication)
- Traces to: 05-API-Specification.md §2 (token lifetimes)
- Traces to: 07-Backend-Development-Standards.md §11 (key management)
- **Token Lifetime Justification**: Short access token (15min) bounds damage window if stolen; longer refresh token (30d) reduces login friction but is revocable server-side.
- **Unique JTI**: Each token MUST have a unique `jti` claim to enable revocation tracking (refresh token revocation list checked at refresh time).
- **Algorithm**: HS256 (HMAC) is simpler; RS256 (RSA) supports key rotation without exposing private key to microservices. Both acceptable per architecture.

---

### Requirement 4: Authentication Middleware

**User Story:**  
As a route handler developer, I want authentication to be declarative and reusable so that I can protect endpoints with a simple dependency injection without duplicating auth logic across routes.

#### Acceptance Criteria

1. THE `get_current_user` FastAPI dependency SHALL extract the Bearer token from the Authorization header
2. WHEN the Authorization header is missing, THE dependency SHALL raise 401 Unauthorized
3. WHEN the Authorization header format is invalid (not "Bearer <token>"), THE dependency SHALL raise 401 Unauthorized
4. WHEN the token is expired, THE dependency SHALL raise 401 Unauthorized
5. WHEN the token has an invalid signature, THE dependency SHALL raise 401 Unauthorized
6. WHEN the token is valid and unexpired, THE dependency SHALL load the User from the repository by user_id
7. WHEN the User is not found (user_id in token does not exist), THE dependency SHALL raise 401 Unauthorized
8. WHEN the User's `is_active` is False, THE dependency SHALL raise 401 Unauthorized (inactive users cannot authenticate)
9. WHEN the token is valid and the User is active, THE dependency SHALL return the User object injected into the handler
10. THE `require_role(role)` factory SHALL return a dependency that checks the authenticated user's role
11. WHEN the authenticated user's role does not match the required role, THE `require_role()` dependency SHALL raise 403 Forbidden
12. WHERE multiple roles are acceptable (e.g., admin OR analyst), THE `require_role(["admin", "analyst"])` dependency SHALL accept a list and permit any role in the list

#### Architectural Notes

- Traces to: 07-Backend-Development-Standards.md §4 (dependency injection)
- Traces to: 08-Security-Architecture.md §5 (authorization checks at application layer)
- **Re-Check Pattern**: Even though token validation happens here, user existence and is_active status MUST be re-checked (do not trust token claims alone).
- **Defense in Depth**: Authorization is also re-checked in route handlers and business logic (application layer), not just in middleware.



---

### Requirement 5: Auth Service (Login, Register, Refresh, Logout)

**User Story:**  
As a user, I want to register with an email and password, log in, manage my session across multiple devices, and explicitly log out when done, with each action creating an audit record.

#### Acceptance Criteria

1. WHEN AuthService.register(email, password, full_name) is called with a unique email, THE result SHALL be a new User entity with hashed password, role defaulting to `viewer`, is_active=True
2. WHEN AuthService.register(email, password, full_name) is called with a duplicate email, THE result SHALL raise a DuplicateEmailError without creating a User
3. WHEN AuthService.register(email, password, full_name) is called with invalid email format, THE result SHALL raise ValidationError
4. WHEN AuthService.register(email, password, full_name) is called with weak password (< 12 characters), THE result SHALL raise PasswordTooWeakError
5. WHEN AuthService.login(email, password) is called with correct credentials, THE result SHALL be TokenPair (access_token, refresh_token) with valid JWT signatures
6. WHEN AuthService.login(email, password) is called with incorrect password, THE result SHALL raise InvalidCredentialsError (without revealing whether email exists)
7. WHEN AuthService.login(email, password) is called for an inactive user (is_active=False), THE result SHALL raise InvalidCredentialsError (inactive users cannot log in)
8. WHEN AuthService.refresh(refresh_token) is called with a valid, unexpired refresh token, THE result SHALL be a new TokenPair with fresh access and refresh tokens
9. WHEN AuthService.refresh(refresh_token) is called with a refresh token that has been revoked, THE result SHALL raise TokenRevokedError and return 401
10. WHEN AuthService.refresh(refresh_token) is called with an expired refresh token, THE result SHALL raise TokenExpiredError and return 401
11. WHEN AuthService.refresh(refresh_token) succeeds, THE old refresh token SHALL be revoked immediately (added to revocation list) so it cannot be used again (token rotation per 08-Security-Architecture.md §4)
12. WHEN AuthService.logout(refresh_token) is called or AuthService.logout_all_sessions(user_id) is called, ALL refresh tokens for that user SHALL be added to the revocation list and subsequent refresh attempts with those tokens SHALL fail
13. WHEN any of register, login, refresh, or logout succeeds, THE operation SHALL create an AuditLog entry with action, user_id, and result

#### Architectural Notes

- Traces to: 08-Security-Architecture.md §4 (session lifecycle)
- Traces to: 04-Database-Design.md §10 (audit logging)
- **Token Rotation**: On refresh, old token is revoked. This bounds damage if old token is captured but not yet used.
- **Generic Errors**: Login failure does not distinguish between "email not found" and "wrong password" (prevents email enumeration attack).
- **Audit Trail**: All auth operations are audited for forensics (Section 11 requirement).

---

### Requirement 6: Auth Route Handlers

**User Story:**  
As a frontend developer, I want well-defined REST endpoints for authentication so I can implement login, registration, logout, and token refresh with predictable request/response contracts.

#### Acceptance Criteria

1. `POST /auth/register` (public, no authentication required) SHALL accept email, password, full_name and return User object or error per openapi.yaml schema
2. WHEN `POST /auth/register` succeeds, THE response SHALL include user_id, email, full_name, role, created_at and SHALL NOT include password or password_hash
3. `POST /auth/login` (public, no authentication required) SHALL accept email, password and return TokenPair (access_token, refresh_token) per openapi.yaml
4. `POST /auth/refresh` (refresh-token authenticated) SHALL accept refresh_token and return new TokenPair per openapi.yaml
5. `POST /auth/logout` (access-token authenticated) SHALL accept optional refresh_token; if provided, revoke that token; if not provided, revoke all tokens for the user
6. WHEN `POST /auth/logout` succeeds, THE response SHALL be 204 No Content (no body)
7. `GET /auth/me` (access-token authenticated) SHALL return the authenticated user's profile (user_id, email, full_name, role, created_at)
8. WHERE error occurs on any endpoint, THE response SHALL use RFC 7807 Problem Details format (application/problem+json) with status, title, detail, and instance fields per openapi.yaml
9. WHEN any endpoint receives malformed input (invalid JSON, missing required field), THE response SHALL be 400 Bad Request with RFC 7807 format and detail describing the validation failure
10. WHEN access to a protected endpoint is attempted without authentication, THE response SHALL be 401 Unauthorized per RFC 7807

#### Architectural Notes

- Traces to: 05-API-Specification.md §2–3 (endpoint definitions)
- Traces to: 07-Backend-Development-Standards.md §4 (request/response schemas)
- **Response Format**: All errors use RFC 7807 (Problem Details) for consistency with platform API.
- **No Password in Responses**: Password and password_hash MUST NEVER be included in any response.

---

### Requirement 7: User Management Routes (List, Get, Update, Soft-Delete)

**User Story:**  
As an admin, I want to list all users, view user profiles, update roles and profile information, and deactivate users, with all changes audited and role changes properly authorized.

#### Acceptance Criteria

1. `GET /users` (admin-only) SHALL return a paginated list of all Users with pagination metadata (per openapi.yaml)
2. WHEN `GET /users` is called by a non-admin user, THE response SHALL be 403 Forbidden
3. `GET /users/{userId}` (admin or the user themselves) SHALL return the User's profile
4. WHEN `GET /users/{userId}` is called by a user who is neither the owner nor admin, THE response SHALL be 404 Not Found (prevent resource enumeration per 08-Security-Architecture.md §5)
5. `PATCH /users/{userId}` (admin or the user themselves) SHALL accept updates to full_name and profile fields
6. WHERE the user is not an admin, `PATCH /users/{userId}` SHALL reject any attempt to modify the `role` field (return 403 Forbidden if role is included in request)
7. WHERE the user is an admin, `PATCH /users/{userId}` SHALL permit modification of the `role` field for other users
8. WHERE an admin attempts to modify their own role, THE request SHALL be accepted if the change is syntactically valid (authorization check is at application boundary, not domain level)
9. `DELETE /users/{userId}` (admin-only) SHALL perform soft-delete by setting `is_active=False` and `deleted_at=<current-time>`
10. WHEN `DELETE /users/{userId}` succeeds, THE response SHALL be 204 No Content
11. WHEN a soft-deleted user (is_active=False) is queried via `GET /users/{userId}`, THE response SHALL be 404 Not Found (deleted users are invisible in queries unless explicitly requested)
12. WHERE role is modified via `PATCH /users/{userId}`, AN audit log entry SHALL be created with user_id, action="role_changed", old_role, new_role
13. WHERE a user is deactivated via `DELETE /users/{userId}`, AN audit log entry SHALL be created with user_id, action="user_deactivated"

#### Architectural Notes

- Traces to: 08-Security-Architecture.md §5 (RBAC, resource-level authorization, ownership validation)
- Traces to: 04-Database-Design.md §10 (soft delete strategy)
- **404 on Forbidden Access**: Non-authorized users receive 404 (not found) rather than 403 (forbidden) to prevent resource enumeration per Principle of Fail Safe.
- **Audit on Role Change**: Role modifications are audited for accountability.



---

### Requirement 8: Audit Logging for Authentication & Authorization

**User Story:**  
As a compliance officer, I want all authentication and authorization events logged immutably so that I can audit who logged in, when, which roles were changed, and when users were deactivated for forensic and compliance purposes.

#### Acceptance Criteria

1. WHEN any authentication event occurs (register, login, logout, refresh), AN AuditLog entry SHALL be created with action, user_id, timestamp, and result (success/failure)
2. WHEN any authorization event occurs (user update, role change, user deactivation), AN AuditLog entry SHALL be created with action, actor_id (admin performing the action), target_user_id (user being modified), change details
3. WHERE login fails (wrong password, user inactive), AN AuditLog entry SHALL be created with action="login_failed", email (not user_id, since user may not exist or be inactive), reason (e.g., "invalid_password", "user_inactive")
4. THE AuditLog entity SHALL be immutable: no update or delete endpoints exist; only creation is permitted
5. `GET /audit-logs` (admin-only, paginated) SHALL return AuditLog entries filterable by user_id, action, date_range per openapi.yaml
6. `GET /audit-logs/{auditLogId}` (admin-only) SHALL return a single AuditLog entry
7. WHEN `GET /audit-logs` is called by a non-admin user, THE response SHALL be 403 Forbidden (audit logs are admin-only per 08-Security-Architecture.md §5)
8. WHERE an AuditLog is created, THE entry SHALL include: user_id (or email if user lookup fails), action, resource_type, resource_id, timestamp (server time, never client-supplied), ip_address (source IP), status (success/failure), details (structured JSON with relevant context)
9. THE AuditLog storage SHALL guarantee ordering: queries ordered by timestamp are reliable for forensic reconstruction
10. WHERE audit log creation fails for any reason, THE application SHALL log the failure but SHALL NOT prevent the security operation itself from completing (fail-safe: do not let audit failure block auth)

#### Architectural Notes

- Traces to: 08-Security-Architecture.md §2 (Immutable Audit Trails, Separation of Duties)
- Traces to: 04-Database-Design.md §9–10 (audit table design)
- Traces to: 10-Observability-Architecture §2 (structured logging)
- **Immutability Guarantee**: AuditLog is append-only; no application code path permits UPDATE or DELETE.
- **Forensic Reliability**: Timestamps use server time (not client-supplied) to prevent tampering.
- **Fail-Safe**: Auth must succeed even if audit log write fails (audit failure does not block platform operation, but IS logged in structured logs for ops visibility).

---

### Requirement 9: Role-Based Access Control (RBAC) Enforcement

**User Story:**  
As a system architect, I want role-based access control to be enforced consistently across all endpoints so that viewers cannot trigger analyses, analysts cannot manage users, and only admins can access audit logs.

#### Acceptance Criteria

1. THE three roles defined SHALL be exactly: `admin`, `analyst`, `viewer` (per 02-Domain-Model.md §3)
2. WHERE an endpoint requires a specific role, THE route definition SHALL explicitly declare `Depends(require_role("admin"))` or equivalent
3. THE `admin` role SHALL permit: user management (list, get, update, deactivate), audit log access, any analyst or viewer capability
4. THE `analyst` role SHALL permit: upload files, request analyses, view own uploads/analyses/reports, view shared reports
5. THE `viewer` role SHALL permit: view shared reports, view shared analyses, view their own profile only
6. WHEN a non-admin user attempts to access an admin-only endpoint, THE response SHALL be 403 Forbidden or 404 Not Found (per resource ownership rules in Requirement 7)
7. WHERE a resource is owned by a user, only the owner (or an admin) SHALL be able to access it; non-owners receive 404 (per 08-Security-Architecture.md §5)
8. WHEN authorization fails due to insufficient role, THE response SHALL include X-Request-ID header (for traceability in logs per 08-Security-Architecture.md §7)
9. WHERE RBAC enforcement is needed, THE check SHALL occur at the application layer (route handler or business service), not solely at the domain layer, so that internal service-to-service calls also enforce RBAC
10. THE authorization logic SHALL NOT accept role as a client-supplied parameter; role is loaded from the validated JWT and never overridable by request body

#### Architectural Notes

- Traces to: 08-Security-Architecture.md §5 (RBAC definition)
- Traces to: 07-Backend-Development-Standards.md §5 (authorization at application layer)
- **Least Privilege**: Each role gets the minimum set of capabilities; expansion requires explicit architectural decision.
- **Ownership + Role**: Access control combines two checks: (1) is the user's role sufficient? (2) does the user own the resource (or is the user admin)?

---

### Requirement 10: Session and Token Lifecycle Management

**User Story:**  
As a user, I want to manage my active sessions across multiple devices so that I can log out from all devices if I suspect compromise, or log out from a specific device without affecting others.

#### Acceptance Criteria

1. WHEN a user logs in from one device, A refresh token is issued and stored in the `refresh_tokens` table with state=`active`
2. WHEN the same user logs in from a second device, A new, independent refresh token is issued (does not affect the token from the first device)
3. WHEN `POST /auth/logout` is called with a specific refresh_token, ONLY that refresh token is revoked (state set to `revoked`, or removed)
4. WHEN `POST /auth/logout` is called without a specific refresh_token (logout all sessions), ALL refresh tokens for that user are revoked
5. WHEN `POST /auth/refresh` is called with a revoked refresh token, THE response SHALL be 401 Unauthorized (refresh fails)
6. WHEN a refresh token is successfully used via `POST /auth/refresh`, THE new access token has a new `jti` claim (different from prior access token)
7. WHERE a user's account is deactivated (`DELETE /users/{userId}`), ALL refresh tokens for that user are immediately revoked and cannot be used for refresh
8. THE refresh token revocation list (or state table) SHALL be checked on every `POST /auth/refresh` call (cannot be cached or assumed valid without re-check)

#### Architectural Notes

- Traces to: 08-Security-Architecture.md §4 (multi-device sessions, token revocation)
- **Per-Device Session**: Each login creates an independent session; logout from one device does not affect others.
- **Refresh Token Rotation**: Each refresh call should rotate the token (issue new token, revoke old one) per 08-Security-Architecture.md §4 for added security.

---

## Definition of Done

The Epic is complete when ALL of the following are verified:

1. ✅ User Domain Entity created per Requirement 1 with all invariants tested
2. ✅ Password Hashing Service created per Requirement 2 with constant-time verification and timing attack prevention
3. ✅ JWT Token Service created per Requirement 3 with all claim validations tested
4. ✅ Authentication Middleware created per Requirement 4 with dependency injection
5. ✅ Auth Service (login, register, refresh, logout) created per Requirement 5 with audit logging
6. ✅ Auth Route Handlers created per Requirement 6 with RFC 7807 error responses
7. ✅ User Management Routes created per Requirement 7 with RBAC enforcement
8. ✅ Audit Logging implemented per Requirement 8 with immutability guarantee
9. ✅ RBAC consistently enforced across all endpoints per Requirement 9
10. ✅ Session lifecycle management implemented per Requirement 10 with multi-device support
11. ✅ All E4.T1–E4.T11 tasks in 22-Engineering-Backlog.md can be implemented from these requirements
12. ✅ All quality gates pass:
    - Ruff: 0 violations (app code)
    - MyPy --strict: 0 errors
    - Pytest: All tests pass (unit, integration, API contract tests)
    - Compileall: Success
13. ✅ Security review completed: no credential leaks, constant-time comparisons verified, JWT validation confirmed
14. ✅ All responses validated against openapi.yaml contract



---

## Risk Assessment

### Security Risks (Primary Concerns for E4)

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| **Timing Attack on Password Verification** | Medium | An attacker could measure response time to narrow password space | Use constant-time comparison (hmac.compare_digest); verify password verification time does not vary |
| **JWT Secret Exposed** | Medium | All tokens become compromised if secret is leaked | Store JWT_SECRET_KEY in environment only; rotate key via versioning with kid header |
| **Token Theft via Interception** | Medium | If token is captured in transit, attacker impersonates user | Enforce HTTPS for all endpoints; HTTPS is non-negotiable per 08-Security-Architecture.md §7 |
| **Refresh Token Not Revoked** | Medium | User logs out but old refresh token still valid (session lingers) | Test that logout revokes token; test that refresh checks revocation list before issuing new access token |
| **Privilege Escalation via Role Injection** | Low | Non-admin modifies role field and is granted admin access | Never trust role from request body; load role from JWT (derived from validated database state) |
| **Audit Log Tampering** | Low | If audit logs are mutable, forensic trail is unreliable | Enforce immutability: no UPDATE/DELETE on audit log table; implement at schema constraint and application level |
| **Inactive User Can Still Authenticate** | Low | User is deactivated but old token still works until expiry | On every request, re-check user.is_active in addition to token expiry; reject inactive users immediately |
| **Email Enumeration via Registration** | Low | Attacker learns which emails are registered by probing /auth/register | Return generic error "Email already registered" without revealing whether email exists for non-existent vs. duplicate |
| **Brute Force on /auth/login** | Medium | Attacker tries many passwords on a known email | Implement rate limiting per user + per IP; return 429 Too Many Requests after threshold |

### Regression Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| **Import Circular Dependency** | Low | Auth module cannot be imported; application fails to start | Test: `from app.infrastructure.security.password import PasswordHasher` succeeds |
| **Missing Dependency Injection** | Low | Route handlers cannot request authenticated user; 500 error | Test: Use auth-protected route in test; verify user is injected |
| **Token Validation Skipped** | Medium | Unauthenticated request reaches protected handler | Test: Send request without Authorization header; verify 401 Unauthorized |
| **Soft Delete Not Enforced** | Low | Deleted users appear in list queries | Test: Delete user, query /users, verify deleted user absent |

### Mitigation Strategy

1. **Constant-Time Verification Test**: Measure timing of password verification for correct and incorrect passwords; ensure variance < 5% (statistical test)
2. **Token Revocation Test**: Login → logout → retry refresh with old token → verify 401 response
3. **Rate Limit Test**: Send 50 login attempts from same IP; verify 429 response after threshold
4. **Soft Delete Test**: Create user → delete → query all users → verify absent; query by ID → verify 404
5. **JWT Secret Rotation Test**: Manually rotate JWT_SECRET_KEY in env; verify new tokens issued with new key; old tokens still validate during rotation window
6. **Audit Immutability Test**: Attempt UPDATE on audit log table; verify constraint prevents modification
7. **Inactive User Test**: Create user → set is_active=False → attempt to login → verify 401 Unauthorized

---

## Acceptance Criteria Summary

| Requirement | Status | Evidence |
|-------------|--------|----------|
| User Entity | Pending | Unit tests for all invariants, email validation, role validation |
| Password Hashing | Pending | Timing attack test, correctness test (hash/verify), no plaintext in logs |
| JWT Token Service | Pending | Token creation test, expiry test, signature validation test, claim validation test |
| Auth Middleware | Pending | Integration test for 401/403 scenarios, user injection test, role check test |
| Auth Service | Pending | Integration tests for register, login, refresh, logout with audit logging |
| Auth Routes | Pending | API tests matching openapi.yaml contract, error format validation (RFC 7807) |
| User Management Routes | Pending | RBAC tests (admin can modify role, non-admin cannot), soft delete test |
| Audit Logging | Pending | Immutability test, filtration test, admin-only access test |
| RBAC Enforcement | Pending | Role-based endpoint access tests for each role |
| Session Lifecycle | Pending | Multi-device login test, per-device logout test, revocation list test |

---

## Out of Scope (For Later Epics)

- ❌ Multi-factor authentication (MFA) — deferred to future roadmap (08-Security-Architecture.md §15)
- ❌ OAuth2/OpenID Connect third-party authentication — future roadmap
- ❌ Password reset flow — deferred pending endpoint addition to API Specification
- ❌ Email verification for new registrations — future roadmap (currently assumed admin-created users)
- ❌ Organization/tenant isolation — no multi-tenancy in current Domain Model (04-Database-Design.md §19)
- ❌ API key authentication (for service-to-service) — future roadmap

---

## Key Decisions

### 1. JWT (Stateless) vs. Session (Stateful) Authentication

**Decision:** Use JWT with refresh token rotation and server-side revocation list for refresh tokens.

**Rationale:**
- JWTs are stateless (no session server required) and scale horizontally without session store
- Refresh tokens are longer-lived but rotated and revocable (server-side state is minimal — just revocation list, not full sessions)
- Hybrid approach balances scalability with instant revocation capability per 08-Security-Architecture.md §4

### 2. Three Roles vs. Fine-Grained Permissions

**Decision:** Implement RBAC with exactly three roles (admin, analyst, viewer), not a fine-grained permission system.

**Rationale:**
- Product Requirements define exactly three roles with clear boundaries (02-Domain-Model.md §3, 05-API-Specification.md §1)
- Introducing fine-grained permissions is premature complexity without requirement
- Can be evolved to permission-based ABAC in future without breaking JWT model

### 3. Soft Delete for Users

**Decision:** Soft-delete users (set is_active=False, deleted_at timestamp) rather than hard-delete.

**Rationale:**
- Preserves audit trail (user's historical actions remain auditable)
- Allows safe deactivation without breaking foreign keys
- Consistent with soft-delete strategy for other domain entities (04-Database-Design.md §10)

### 4. Refresh Token Revocation Storage

**Decision:** Store refresh token revocation list in database (PostgreSQL `refresh_token_revocations` table) or in-memory cache with database backup.

**Rationale:**
- Refresh tokens are long-lived (30 days); cannot rely on memory-only state (process restart loses revocation)
- Database revocation list is checked on every refresh call (bounded query cost)
- Alternative: Store tokens directly in database with state enum (active/revoked) — simpler but requires query per token

### 5. Audit Log Immutability at Schema Level

**Decision:** Enforce immutability at PostgreSQL schema level (no UPDATE/DELETE permissions on audit table) and application level.

**Rationale:**
- Schema-level constraints survive accidental or malicious SQL access
- Application-level enforcement (no delete endpoint) is first line of defense
- Combination prevents both bugs and insider threats per 08-Security-Architecture.md §2 (Defense in Depth)

---

## Specification Artifacts

**Input Documents:**
- 01-PRD.md (authentication requirements)
- 02-Domain-Model.md §3 (User entity, roles)
- 04-Database-Design.md §9–10 (users table, refresh_tokens table, audit_logs table)
- 05-API-Specification.md §2–3 (auth endpoints, token responses)
- 08-Security-Architecture.md §4–5 (JWT, RBAC, threat model)
- 07-Backend-Development-Standards.md §4, §11 (DI patterns, algorithm selection)
- 22-Engineering-Backlog.md § E4 (task list and effort estimates)

**Implementation will produce:**
- `app/domain/entities/user.py` (User domain entity)
- `app/infrastructure/security/password.py` (PasswordHasher service)
- `app/infrastructure/security/jwt.py` (TokenService)
- `app/api/v1/dependencies/auth.py` (FastAPI dependencies)
- `app/application/services/auth_service.py` (AuthService)
- `app/api/v1/routes/auth.py` (Auth endpoints: register, login, logout, refresh, me)
- `app/api/v1/routes/users.py` (User management: list, get, update, delete)
- `app/application/services/audit_service.py` (AuditService)
- `app/api/v1/routes/audit_logs.py` (Audit log endpoints)
- `app/infrastructure/repositories/user_repository.py` (User persistence)
- `app/infrastructure/repositories/refresh_token_repository.py` (Refresh token storage and revocation)
- `app/infrastructure/repositories/audit_log_repository.py` (Audit log persistence)
- Comprehensive test suite: 80+ unit tests, 30+ integration tests, 20+ API contract tests

---

## Dependency Graph

```
E4 (Authentication & Authorization - THIS EPIC)
├── Dependencies:
│   ├── E2 (Backend Foundation) - FastAPI, Pydantic, DI
│   ├── E3 (Database Foundation) - PostgreSQL, SQLAlchemy async
│   └── 08-Security-Architecture.md (approved architecture)
├── Enables:
│   ├── E5 (Asset Upload & Management) - requires auth for uploads
│   ├── E6 (Analysis Engine) - requires auth for analysis requests
│   └── E7–E11 (all subsequent epics require auth)
└── Blocks:
    └── No feature can be exposed without auth (per PRD)
```

This is a **blocking task** for all future feature work. All endpoints require authentication; no public endpoints (besides /auth/register and /auth/login) exist until E4 is complete.

---

## Next Steps (After Requirements Approval)

Once these requirements are approved:

1. **Design Phase**: Architecture decisions on token storage, revocation patterns, audit schema details
2. **Task Phase**: Break Requirement 1–10 into specific implementation tasks (11 tasks in backlog align well with these 10 requirements)
3. **Execution Phase**: Implement E4.T1–E4.T11 in dependency order
4. **Verification Phase**: Quality gates and security review before merging

---

## Questions for Architectural Review

1. **JWT Algorithm**: Should we use HS256 (HMAC with shared secret) or RS256 (RSA with public/private key pair)? HS256 is simpler; RS256 supports key rotation without exposing secret to all services.
   - **Current Assumption**: HS256, configurable via settings per 07-Backend-Development-Standards.md §11

2. **Refresh Token Storage**: Store full JWT in database (simpler, larger DB) or store only token metadata with jti and lookup JWT in Redis cache (faster, requires cache)?
   - **Current Assumption**: Store full token in PostgreSQL for durability; revocation list checked on every refresh call

3. **Audit Log Retention**: Should audit logs be retained indefinitely or rotated after N days?
   - **Current Assumption**: Retained indefinitely (no deletion endpoint or retention policy defined yet)

---

## Glossary Expansion

| Term | Definition |
|------|-----------|
| **Idempotency Key** | Client-supplied header that allows safe retry of mutating requests (same key = same result, no duplicate side effects) |
| **Revocation List** | Server-side record of tokens (refresh tokens specifically) that have been invalidated and should not be accepted |
| **404 vs. 403** | 404 Not Found = resource does not exist (or user not authorized to know it exists); 403 Forbidden = resource exists but user lacks permission |
| **Bearer Token** | Authentication scheme where credential is a token prefixed with "Bearer" in Authorization header |
| **RFC 7807** | HTTP Problem Details specification for standard error response format with status, title, detail, instance fields |

