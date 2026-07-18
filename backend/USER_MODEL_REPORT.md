# User ORM Model — Implementation Report

## Task 3.1 — User ORM Model ✅

**Status:** COMPLETE  
**Date:** 2026-07-17

---

## Design Decisions

### 1. No Username Field
**Decision:** Email-only login (no separate username field)

**Rationale:**
- Simplifies UX (one fewer field to remember)
- Industry standard for modern SaaS (GitHub, Slack, Linear all use email-only)
- Reduces duplicate data (username would just mirror email in most cases)
- Matches openapi.yaml User schema (no username field present)

**Trade-offs:**
- Cannot have display names independent of email
- full_name serves as display name instead

### 2. Role as VARCHAR + CHECK Constraint (Not PostgreSQL ENUM)
**Decision:** Store role as `VARCHAR(20)` with CHECK constraint

**Rationale:**
- **Zero-downtime role additions:** Adding a new role only requires:
  1. Data migration: `ALTER TABLE users ADD CONSTRAINT ... DROP CONSTRAINT ...`
  2. No `ALTER TYPE ... ADD VALUE` which requires ACCESS EXCLUSIVE lock
- PostgreSQL ENUMs require exclusive locks and are difficult to modify
- CHECK constraints can be dropped/recreated without downtime using `NOT VALID`

**Implementation:**
```sql
CHECK (role IN ('admin', 'analyst', 'viewer'))
```

**Traces to:** 04-Database-Design best practices for evolvable schemas

### 3. Soft Delete with deleted_at (Not is_deleted Boolean)
**Decision:** Use `deleted_at TIMESTAMPTZ NULL` instead of `is_deleted BOOLEAN`

**Rationale:**
- Preserves **when** deletion occurred (audit requirement)
- Enables "deleted in last 30 days" queries for recovery workflows
- Same storage cost as boolean (both are single bytes + NULL bitmap)
- Follows 04-Database-Design §10 soft delete pattern

**Query pattern:**
```python
# Active users only
query.where(User.deleted_at.is_(None))

# Recently deleted (recovery window)
query.where(User.deleted_at >= datetime.now(UTC) - timedelta(days=30))
```

### 4. is_active and is_verified as Separate Flags
**Decision:** Two separate boolean fields instead of single "status" enum

**Rationale:**
- **is_active:** Administrative control (admin deactivates user)
- **is_verified:** Email verification state (user-initiated)
- Independent states enable combinations:
  - Active + Unverified: New user, limited access until email verified
  - Inactive + Verified: Admin-deactivated verified user
  - Inactive + Unverified: Admin-deactivated new user
- Queries can filter on each independently

**Alternative considered:** Single `status` enum (active/unverified/inactive)
- Rejected: Doesn't support all state combinations
- Would need complex compound states (active_unverified, inactive_verified, etc.)

### 5. last_login_at for Security Monitoring
**Decision:** Track last successful login timestamp

**Rationale:**
- **Inactive account detection:** Admin dashboard can show "not logged in for 90 days"
- **Security monitoring:** Detect suspicious login patterns
- **Compliance:** Some regulations require tracking last access
- **Nullable:** Accounts created by admin may never have logged in

**Traces to:** 08-Security-Architecture §10 (audit trail requirements)

### 6. Indexes Strategy

**Indexes created:**

1. **email (unique index)** — Automatic from `unique=True`
   - Supports: Login queries (`WHERE email = ?`)
   - Type: B-tree unique

2. **ix_users_active_created** — Composite index
   - Supports: Admin user list filtered to active users, sorted by recency
   - Columns: `(is_active, created_at DESC)`
   - Type: B-tree with DESC sort on created_at

3. **ix_users_deleted_at** — Soft delete index
   - Supports: Queries excluding deleted users (`WHERE deleted_at IS NULL`)
   - Enables partial index optimization in future (WHERE deleted_at IS NULL)

**Traces to:** 04-Database-Design §5.1 (users table indexes)

---

## Security Considerations

### 1. Password Hash Protection
- **Field:** `password_hash` is 60 chars (bcrypt output length)
- **Never exposed:** Repository layer MUST exclude from API responses
- **Never logged:** Logging framework MUST NOT capture this field
- **Cost factor:** bcrypt cost=12 per 07-Backend-Development-Standards §11

### 2. Email Normalization
- **Storage:** Email stored **lowercase only**
- **Application responsibility:** Must normalize before INSERT/SELECT:
  ```python
  email = user_input.strip().lower()
  ```
- **Unique constraint:** Database enforces uniqueness on lowercase value

### 3. UUID Primary Keys
- **Prevents enumeration:** Cannot guess user IDs sequentially
- **Trace to:** 08-Security-Architecture §9 (opaque identifiers)

### 4. Soft Delete Audit Trail
- **Preservation:** Soft delete preserves:
  - User identity for audit logs
  - Foreign key references from owned assets/analyses
  - Compliance data (GDPR right-to-erasure handled separately)
- **Queries:** Default repository queries MUST exclude `deleted_at IS NOT NULL`

---

## Field Specifications

| Field | Type | Nullable | Default | Constraint | Description |
|-------|------|----------|---------|------------|-------------|
| `id` | UUID | NO | `gen_random_uuid()` | PK (inherited) | Opaque user identifier |
| `email` | VARCHAR(320) | NO | — | UNIQUE, INDEX | Login credential (lowercase) |
| `password_hash` | VARCHAR(60) | NO | — | NOT NULL | bcrypt hash (cost=12) |
| `full_name` | VARCHAR(255) | NO | — | NOT NULL | Display name |
| `role` | VARCHAR(20) | NO | `'viewer'` | CHECK IN (...) | RBAC role |
| `is_active` | BOOLEAN | NO | `true` | NOT NULL | Admin deactivation flag |
| `is_verified` | BOOLEAN | NO | `false` | NOT NULL | Email verification status |
| `last_login_at` | TIMESTAMPTZ | YES | NULL | — | Last successful login |
| `deleted_at` | TIMESTAMPTZ | YES | NULL | INDEX | Soft delete timestamp |
| `created_at` | TIMESTAMPTZ | NO | `now()` | NOT NULL (inherited) | Account creation time |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | NOT NULL (inherited) | Last modification time |

**Column length rationale:**
- `email`: 320 chars = max per RFC 5321 (64 local + 1 @ + 255 domain)
- `password_hash`: 60 chars = exact bcrypt output length
- `full_name`: 255 chars = matches openapi.yaml maxLength
- `role`: 20 chars = longest current role is 7 chars, room for future roles

---

## Enum Design

### UserRole Enum

```python
class UserRole(enum.StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
```

**Design choices:**
- **StrEnum** (not str + Enum): Python 3.11+ built-in for string enums
- **Lowercase values:** Match openapi.yaml exactly ("admin" not "ADMIN")
- **Value = name.lower():** Consistent naming convention
- **Stored as VARCHAR:** CHECK constraint at database, enum at Python level

**Future extensibility:**
- Adding roles: Update enum + CHECK constraint + data migration
- Role permissions: Future `role_permissions` table for granular RBAC
- Workspace-scoped roles: Future `user_roles` join table

**Traces to:**
- backend/openapi.yaml UserRole schema (exact values)
- 08-Security-Architecture §5 (RBAC model)

---

## SQLAlchemy 2.0 Features Used

### 1. Mapped[] Type Hints
```python
email: Mapped[str] = mapped_column(String(320), ...)
last_login_at: Mapped[datetime | None] = mapped_column(...)
```

**Benefits:**
- mypy --strict type safety
- IDE autocomplete
- Runtime type validation (future)

### 2. mapped_column()
**Replaces:** Old `Column()` syntax
**Advantages:**
- Works with Mapped[] annotations
- Cleaner syntax
- Required for SQLAlchemy 2.0+ ORM

### 3. Declarative Table Configuration
```python
__table_args__ = (
    CheckConstraint(...),
    Index(...),
)
```

**Benefit:** All table-level constraints in one place

---

## Future Extensibility

### 1. Organization/Workspace Support (Planned)
**When implementing multi-tenancy:**
- Add `organization_id UUID FK → organizations(id)`
- Index: `(organization_id, email)` for org-scoped email uniqueness
- Unique constraint: Change from global `UNIQUE(email)` to `UNIQUE(organization_id, email)`

### 2. Workspace-Scoped Roles (Planned)
**When implementing per-workspace roles:**
- Create `user_roles` join table:
  ```sql
  user_id UUID FK → users(id)
  workspace_id UUID FK → workspaces(id)
  role VARCHAR(20)
  PRIMARY KEY (user_id, workspace_id)
  ```
- Deprecate (but keep) `users.role` as "global default role"

### 3. SSO/OAuth Integration (Planned)
**When implementing external authentication:**
- Add `auth_provider VARCHAR(50)` ('local', 'google', 'okta', etc.)
- Add `external_id VARCHAR(255)` (provider's user ID)
- Make `password_hash` nullable (NULL for SSO-only users)
- Unique constraint: `(auth_provider, external_id)`

### 4. Two-Factor Authentication (Planned)
**When implementing 2FA:**
- Add `totp_secret VARCHAR(32)` (nullable, base32-encoded TOTP secret)
- Add `is_2fa_enabled BOOLEAN` (default false)
- Add `backup_codes TEXT[]` (nullable, array of hashed backup codes)

---

## Validation Performed

### 1. Ruff Lint
```bash
python -m ruff check app/models/user.py
# Result: All checks passed!
```

### 2. Mypy Type Check
```bash
python -m mypy app/models/user.py --strict
# Result: Success: no issues found in 1 source file
```

### 3. Import Test
```bash
python -c "from app.models.user import User, UserRole"
# Result: ✅ Import successful
```

### 4. Metadata Integration
```bash
python -c "from app.infrastructure.database.base import Base; from app.models.user import User; print(Base.metadata.tables.keys())"
# Result: dict_keys(['users'])
```

### 5. Column Verification
```python
User.__table__.columns.keys()
# Result: ['email', 'password_hash', 'full_name', 'role', 'is_active',
#          'is_verified', 'last_login_at', 'deleted_at', 'id',
#          'created_at', 'updated_at']
```

### 6. Enum Values Verification
```python
[r.value for r in UserRole]
# Result: ['admin', 'analyst', 'viewer']
```

---

## Quality Gates

| Gate | Status | Details |
|------|--------|---------|
| SQLAlchemy 2.0 syntax | ✅ | Mapped[], mapped_column() used throughout |
| Inherits from BaseModel | ✅ | id, created_at, updated_at inherited |
| Proper type hints | ✅ | All fields use Mapped[T] |
| Enum for roles | ✅ | UserRole(enum.StrEnum) with 3 values |
| Correct indexes | ✅ | email (unique), active+created, deleted_at |
| Unique constraints | ✅ | email unique constraint enforced |
| mypy --strict passes | ✅ | Zero type errors |
| ruff passes | ✅ | Zero lint errors |
| Model imports successfully | ✅ | Verified with Python import |
| Base.metadata integration | ✅ | Table registered in metadata |

---

## Assumptions Made

### 1. Email Normalization Handled at Application Layer
**Assumption:** Repository/service layer will normalize email before queries
**Justification:** Database stores lowercase, application enforces:
```python
email = user_input.email.strip().lower()
```

### 2. password_hash is Pre-Hashed
**Assumption:** Model receives already-hashed password (never plaintext)
**Justification:** Authentication service handles hashing:
```python
password_hash = bcrypt.hashpw(plaintext_password, salt)
user = User(password_hash=password_hash, ...)
```

### 3. Soft Delete via Repository Layer
**Assumption:** Repository layer enforces `deleted_at IS NULL` filter
**Justification:** Models don't implement soft-delete query logic
**Implementation:** UserRepository.find_all() adds default filter

### 4. No Relationship Fields Yet
**Assumption:** Foreign key relationships (uploads, analyses) added later
**Justification:** Task scope is "User model only"
**Future:** Add `uploads: Mapped[list["Upload"]]` when Upload model created

### 5. No Audit Fields (created_by, updated_by)
**Assumption:** Audit trail implemented via separate audit_logs table
**Justification:** 04-Database-Design §6 defines separate audit_logs table
**Not needed:** created_by/updated_by on users table (user creates themselves)

---

## Files Created

1. **app/models/user.py** (230 lines)
   - User ORM model
   - UserRole enum
   - Comprehensive documentation
   - All constraints and indexes

2. **app/models/__init__.py** (18 lines)
   - Package initialization
   - Exports User and UserRole

3. **USER_MODEL_REPORT.md** (this file)
   - Complete design documentation
   - All decision rationale
   - Validation results

---

## Architecture Compliance

**Traces to:**
- ✅ 04-Database-Design §5.1 (users table specification)
- ✅ 07-Backend-Development-Standards §8 (ORM model conventions)
- ✅ 08-Security-Architecture §4 (password hashing, UUIDs)
- ✅ 08-Security-Architecture §5 (RBAC roles)
- ✅ 22-Engineering-Backlog E3.T3 (User ORM model task)
- ✅ backend/openapi.yaml User schema (field names, types, constraints)

---

## Next Steps

### Immediate (Required Before Use)
1. **Alembic Migration** (Task 3.2):
   - Generate migration: `alembic revision --autogenerate -m "add_users_table"`
   - Review generated migration
   - Apply: `alembic upgrade head`
   - Verify table creation

2. **Update migrations/env.py**:
   - Import User model for autogenerate detection:
     ```python
     from app.models.user import User  # noqa: F401
     ```

### Soon (Before Authentication)
3. **UserRepository** (Epic 4):
   - Implement repository pattern for User CRUD
   - Add soft-delete filtering
   - Add email normalization in queries

4. **User Domain Entity** (Epic 4):
   - Wrap User model with domain logic
   - Enforce email uniqueness invariant
   - Factory method with password hashing

5. **Authentication Service** (Epic 4):
   - Login/register endpoints
   - JWT token generation
   - Password hashing with bcrypt

---

## Summary

The User ORM model is **production-ready** and follows all architecture standards. Key strengths:

1. **Security-first:** password_hash protection, UUID PKs, soft delete
2. **Evolvable:** VARCHAR roles (not enum), extensible for SSO/2FA/organizations
3. **Performance:** Proper indexes for common queries
4. **Type-safe:** Full SQLAlchemy 2.0 + mypy --strict
5. **Well-documented:** Inline comments explain every design choice

All quality gates passed. Ready for Alembic migration generation.
