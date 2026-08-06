# E3.T9 — Refresh Tokens ORM Model and Migration

## Specification Document

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-refresh-tokens-t9/requirements.md |
| **Feature** | refresh-tokens-orm-model-t9 |
| **Status** | In Review |
| **Owner** | Engineering Team |
| **Traces to** | 22-Engineering-Backlog E3.T9 |
| **Dependencies** | E3.T1 (Database Foundation), E3.T2 (Alembic Configuration), E3.T3 (User ORM Model) |

---

## Introduction

E3.T9 creates the **RefreshToken** ORM model, which manages server-side refresh token state for session control and revocation.

This task focuses on:
1. Defining the RefreshToken ORM model with token lifecycle fields
2. Generating the Alembic migration for the `user_refresh_tokens` table
3. Supporting session revocation without invalidating all user sessions
4. Establishing the token rotation pattern

**Scope Boundary:**
- ✅ RefreshToken ORM model definition (fields, token_hash, expiry, revocation)
- ✅ Alembic migration for `user_refresh_tokens` table creation
- ✅ Indexes for efficient token lookups and session management
- ✅ ORM model tests (token fields, revocation semantics)
- ❌ Token hashing or generation (E4.T2: Token Service)
- ❌ JWT validation or token lifecycle service (E4.T2: Authentication Service)
- ❌ Session management API (E4+: Route handlers)
- ❌ Token cleanup jobs (future: background workers)

---

## Requirements

### Requirement 1: RefreshToken ORM Model Definition

**User Story:** As a security engineer, I want a server-side refresh token store that enables selective session revocation so that logging out or revoking access on one device does not affect other active sessions.

**Description:**

The RefreshToken model must:
- Inherit from BaseModel (providing UUID PK, timestamps)
- Define all fields required by Database Design spec (04-Database-Design §4 ERD)
- Store the SHA-256 hash of the opaque token value (never the raw token)
- Track expiry, revocation status, and revocation timestamp
- Capture session context (user agent, IP address)
- Support cascading deletion when a user is deleted
- Enable efficient lookup by token_hash for validation

**Rationale:**

The access token is stateless (15-minute lifetime). The refresh token is the server-side control point for session management. Storing only the hash (not the raw token) means a database breach does not immediately compromise active sessions. Revocation enables logout, password reset, and admin session termination on per-device granularity.

**Acceptance Criteria:**

1. ✅ RefreshToken model defined in `backend/app/models/refresh_token.py`
2. ✅ RefreshToken inherits from BaseModel (not Base directly)
3. ✅ All required fields present with correct types:
   - `id` (Mapped[UUID], PK, auto-generated)
   - `user_id` (Mapped[UUID], FK → users, not nullable, ON DELETE CASCADE)
   - `token_hash` (Mapped[str], unique, not null, SHA-256 hash)
   - `expires_at` (Mapped[datetime], absolute expiry timestamp)
   - `is_revoked` (Mapped[bool], default false, revocation flag)
   - `user_agent` (Mapped[str | None], nullable, client context)
   - `ip_address` (Mapped[str | None], inet type, nullable)
   - `created_at` (Mapped[datetime], auto-set on insert)
   - `revoked_at` (Mapped[datetime | None], nullable, set on revocation)
4. ✅ RefreshToken class has `__tablename__ = "user_refresh_tokens"`
5. ✅ RefreshToken class has `__repr__()` that does NOT expose token_hash
6. ✅ Model includes docstring explaining token_hash security (hash, never raw token)
7. ✅ Model file has comprehensive docstrings
8. ✅ RefreshToken exported from `backend/app/models/__init__.py` for Alembic discovery
9. ✅ Model passes syntax check: `python -m py_compile app/models/refresh_token.py`
10. ✅ No circular imports: `python -c "from app.models import RefreshToken; print(RefreshToken)"`

**Architectural Notes:**
- Traces to: 04-Database-Design §4 ERD (user_refresh_tokens table specification)
- Traces to: 04-Database-Design §3.2 (Refresh tokens as server-side session control)
- Traces to: 08-Security-Architecture §5 (JWT and refresh token lifecycle)
- Traces to: 07-Backend-Development-Standards §8 (ORM model conventions)

**Out of Scope:**
- ❌ Token generation or hashing (belongs in E4.T2)
- ❌ Token validation logic (belongs in E4: Authentication Service)
- ❌ Session API endpoints (belongs in E4: Route handlers)
- ❌ Token cleanup jobs (future: background workers)

---

### Requirement 2: Database Constraints and Indexes

**User Story:** As an operator, I want efficient token lookups and automatic cascade deletion so that sessions are revoked quickly and user deletion does not leave orphaned tokens.

**Description:**

The user_refresh_tokens table must:
- Enforce unique constraint on `token_hash` (O(1) validation lookup)
- Enforce unique constraint on `user_id, created_at` for session uniqueness (optional per-device tracking)
- Enforce NOT NULL constraints on required fields (user_id, token_hash, expires_at)
- Enforce foreign key ON DELETE CASCADE to user (user deletion removes tokens)
- Provide indexes for efficient queries:
  - Unique index on token_hash (validation lookup)
  - Index on user_id (session listing for a user)
  - Partial index on (expires_at) where is_revoked=false (cleanup queries)

**Rationale:**

Unique index on token_hash enables O(1) token validation during API requests. ON DELETE CASCADE ensures tokens are hard-deleted when a user is deleted. Partial index on expired tokens supports efficient cleanup jobs.

**Acceptance Criteria:**

1. ✅ Unique constraint on token_hash enforced (cannot insert duplicate hashes)
2. ✅ NOT NULL constraints on user_id, token_hash, expires_at, is_revoked
3. ✅ Foreign key on user_id with ON DELETE CASCADE enforced
4. ✅ Primary key index on id (automatic)
5. ✅ Unique index on token_hash (automatic from unique=True)
6. ✅ Index on user_id for session list queries
7. ✅ Partial index on (expires_at) where is_revoked=false for cleanup
8. ✅ Constraints named following convention (pk_, uq_, fk_, ix_) for clarity
9. ✅ Integration test: insert valid token succeeds
10. ✅ Integration test: insert duplicate token_hash raises unique constraint error
11. ✅ Integration test: delete user cascades to delete their refresh tokens
12. ✅ Integration test: query tokens by user_id succeeds

**Architectural Notes:**
- Traces to: 04-Database-Design §4 (constraints and indexes specification)
- Traces to: 08-Security-Architecture §5 (token lifecycle management)

---

### Requirement 3: Alembic Migration for RefreshToken

**User Story:** As a developer, I want the refresh_tokens table migration to be automatically generated and validated so that the schema is version-controlled and reversible.

**Description:**

The migration must:
- Be generated via `alembic revision --autogenerate`
- Create the `user_refresh_tokens` table with all columns, constraints, and indexes
- Define foreign key ON DELETE CASCADE to enforce token cleanup on user deletion
- Be syntactically valid Python
- Include comprehensive docstrings and metadata

**Rationale:**

Alembic autogenerate detects schema changes from the ORM model and generates migration scripts. The migration serves as the single source of truth for schema evolution.

**Acceptance Criteria:**

1. ✅ Migration file created in `backend/migrations/versions/`
2. ✅ Migration file named with timestamp pattern: YYYYMMDD_HHMM_<rev>_<slug>.py
3. ✅ Migration file is syntactically valid Python
4. ✅ upgrade() function creates user_refresh_tokens table with all columns
5. ✅ upgrade() function creates UNIQUE constraint on token_hash
6. ✅ upgrade() function creates FOREIGN KEY on user_id with ON DELETE CASCADE
7. ✅ upgrade() function creates NOT NULL constraints on required fields
8. ✅ upgrade() function creates indexes:
   - Unique index on token_hash
   - Index on user_id
   - Partial index on (expires_at) where is_revoked=false
9. ✅ upgrade() function creates any CHECK constraints (e.g., expires_at > created_at)
10. ✅ downgrade() function drops user_refresh_tokens table
11. ✅ Migration can be imported without errors
12. ✅ **CRITICAL: Migration has been manually reviewed** before commit
13. ✅ No regressions in E3.T1-E3.T8 tests after migration

**Architectural Notes:**
- Traces to: 22-Engineering-Backlog E3.T2 (migration workflow)
- Traces to: 07-Backend-Development-Standards §8 (migration standards)

---

### Requirement 4: Migration Validation

**User Story:** As a DBA, I want the migration to be manually reviewed and validated to ensure CASCADE deletion works correctly before deployment.

**Description:**

The migration must:
- Have all generated SQL manually reviewed for accuracy
- Verify table names and column types match the ORM model
- Verify indexes match requirements
- Verify CASCADE deletion is configured correctly
- Verify defaults and constraints are correct
- Pass upgrade/downgrade cycle testing
- Pass CI validation stages

**Rationale:**

Manual review is essential for foreign key migrations. CASCADE deletion must be verified to avoid accidental data loss.

**Acceptance Criteria:**

1. ✅ Migration code reviewed for accuracy and completeness
2. ✅ Table name is "user_refresh_tokens" (matches __tablename__)
3. ✅ All columns present with correct types (uuid, text, timestamptz, boolean, inet)
4. ✅ All column defaults correct (gen_random_uuid() for id, now() for created_at, false for is_revoked)
5. ✅ Nullable/not-null flags correct (all NOT NULL except user_agent, ip_address, revoked_at)
6. ✅ Unique constraint on token_hash present
7. ✅ Foreign key on user_id with ON DELETE CASCADE present
8. ✅ All indexes present (unique token_hash, index user_id, partial expires_at)
9. ✅ downgrade() reverses all changes
10. ✅ Migration passes upgrade/downgrade cycle: `alembic upgrade head && alembic downgrade base` succeeds
11. ✅ Migration passes CI pipeline validation
12. ✅ No regressions in prior test suites (E3.T3-E3.T8)

**Architectural Notes:**
- Traces to: 12-CI-CD-Architecture §3 (migration validation in CI)
- Traces to: 04-Database-Design §5.2 (RefreshToken schema specification)

---

### Requirement 5: ORM Model Test Coverage

**User Story:** As a developer, I want comprehensive tests for the RefreshToken model to ensure it correctly manages token lifecycle and supports revocation.

**Description:**

Tests must cover:
- Model instantiation with valid data
- Default values and server-side defaults
- Field type validation
- Token hash never exposed in __repr__()
- Unique constraint on token_hash
- Foreign key cascade deletion
- Revocation semantics (is_revoked, revoked_at)
- Timestamp auto-population

**Rationale:**

Unit tests validate that the ORM model and database schema correctly enforce token management constraints.

**Acceptance Criteria:**

1. ✅ Test file created: `backend/tests/unit/test_refresh_token_model.py`
2. ✅ Test: instantiate RefreshToken with valid data (user_id, token_hash, expires_at) succeeds
3. ✅ Test: default values correct (is_revoked=false, revoked_at=None)
4. ✅ Test: created_at is set on creation
5. ✅ Test: model __repr__() does not expose token_hash
6. ✅ Test: insert valid token via ORM succeeds
7. ✅ Integration test: insert token with duplicate token_hash raises unique constraint error
8. ✅ Integration test: delete user cascades to delete their tokens
9. ✅ Integration test: query tokens by user_id succeeds
10. ✅ Integration test: update token to set is_revoked=true and revoked_at succeeds
11. ✅ Integration test: query active tokens (WHERE is_revoked=false) succeeds
12. ✅ All tests pass: `pytest tests/unit/test_refresh_token_model.py -v`

**Architectural Notes:**
- Traces to: 07-Backend-Development-Standards §7 (ORM testing patterns)
- Traces to: 08-Security-Architecture §5 (token lifecycle validation)

---

## Acceptance Criteria Summary

| # | Criterion | Status |
|---|-----------|--------|
| **R1** | RefreshToken ORM model defined and exported | ⏳ Pending |
| **R2** | Database constraints and indexes configured | ⏳ Pending |
| **R3** | Alembic migration generated and validated | ⏳ Pending |
| **R4** | Migration manually reviewed | ⏳ Pending |
| **R5** | ORM model test coverage complete | ⏳ Pending |

---

## Definition of Ready

Before implementation begins:
- ✅ E3.T1 complete (Database Foundation, fixtures, engine disposal)
- ✅ E3.T2 complete (Alembic Configuration, migration workflow)
- ✅ E3.T3 complete (User ORM Model, first migration pattern established)
- ✅ PostgreSQL 16 container operational
- ✅ Alembic ready to generate migrations
- ✅ CI pipeline ready to validate migrations

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| **CASCADE deletion unintended** | User deletion removes tokens (expected) | Very Low | Manual review of foreign key definition (R4 AC #1) |
| **Token hash collision** | Extremely rare; collision resistant | Negligible | Use SHA-256 (cryptographically secure) |
| **Generated migration has errors** | Schema corruption | Low | Manual review and testing (R4) |
| **Indexes insufficient** | Poor token lookup performance | Low | Review indexes match requirements |

---

## Dependencies & Sequencing

```
E3.T1 (Database Foundation)
E3.T2 (Alembic Configuration)
E3.T3 (User ORM Model) ✓
  ├─ Provides User entity and FK reference
  └─ Enables: E3.T9 ✓

E3.T9 (Refresh Tokens ORM Model & Migration) ← YOU ARE HERE
  ├─ Defines server-side token management
  ├─ Establishes CASCADE deletion pattern
  └─ Enables: E3.T10+ (repository interfaces)
```

---

## Glossary

| Term | Definition |
|---|---|
| **Refresh Token** | Long-lived token used to obtain new access tokens without re-authentication |
| **Token Hash** | SHA-256 hash of the opaque token value; stored in database (not raw token) |
| **Revocation** | Marking a token as invalid (is_revoked=true) without deleting the record |
| **Session** | Active authenticated user connection; managed by refresh token record |
| **Cascade Deletion** | Database constraint that deletes child records when parent is deleted |
| **On Delete Cascade** | Foreign key rule: when user is deleted, all their refresh tokens are deleted |

---

## References

- 22-Engineering-Backlog: E3.T9 (Refresh Tokens ORM Model and Migration)
- 04-Database-Design §4: ERD (user_refresh_tokens table specification)
- 04-Database-Design §5.2: RefreshToken schema specification
- 04-Database-Design §3.2: Refresh tokens as server-side session control
- 02-Domain-Model: Session lifecycle
- 06-Repository-Structure §6: models/ directory organization
- 07-Backend-Development-Standards §8: ORM model conventions
- 08-Security-Architecture §5: JWT and refresh token lifecycle
- E3.T3 Completion: User ORM Model (FK reference)
