# PostgreSQL Role Provisioning Implementation Specification

------------------------------------------------------------------------

## Document Information

  -----------------------------------------------------------------------
  Field                               Value
  ----------------------------------- -----------------------------------
  **Version**                         1.0

  **Status**                          Implementation Specification

  **Owner**                           Sentinel Core Team

  **Epic**                            Epic 4 Verification (E4.T5+)

  **References**                      docs/04-Database-Design.md §18.4,
                                      Database Role & Privilege Design
                                      Specification (completed)

  **Target Completion**               Phases 2-6 (implementation roadmap)

  **Audience**                        Backend Engineers, DevOps,
                                      Database Administrators
  -----------------------------------------------------------------------

### Document Purpose

This specification defines the **implementation roadmap** for PostgreSQL role provisioning, which separates migration privileges (schema_owner) from application privileges (sentinel_api). This separation enforces database-level immutability of the audit_logs table against application code defects.

**Epic 4 Violation Fixed:**
- Current state: Single `sentinel` role for migrations and application (violations privilege separation)
- Target state: Two-role architecture per [Database Role & Privilege Design Specification]
  - `schema_owner` role: LOGIN, full DDL/DML privileges (migrations only)
  - `sentinel_api` role: LOGIN, restricted privileges (INSERT-only on audit_logs, SELECT/INSERT/UPDATE on others, SELECT/INSERT/UPDATE/DELETE on most)

------------------------------------------------------------------------

## Table of Contents

1. [Overview](#1-overview)
2. [Phase 2: Bootstrap Provisioning SQL Script](#2-phase-2-bootstrap-provisioning-sql-script)
3. [Phase 3: Docker Compose Integration](#3-phase-3-docker-compose-integration)
4. [Phase 4: Alembic Configuration Update](#4-phase-4-alembic-configuration-update)
5. [Phase 5: Security Boundary Tests](#5-phase-5-security-boundary-tests)
6. [Phase 6: Documentation & Deployment](#6-phase-6-documentation--deployment)
7. [Implementation Order & Dependencies](#7-implementation-order--dependencies)
8. [Success Criteria & Verification](#8-success-criteria--verification)
9. [Rollback & Disaster Recovery](#9-rollback--disaster-recovery)
10. [Known Constraints & Assumptions](#10-known-constraints--assumptions)

------------------------------------------------------------------------

## 1. Overview

### 1.1 Security Model

The PostgreSQL role provisioning model implements **defense in depth** for audit immutability:

**Layer 1: Application Logic**
- API cannot UPDATE/DELETE audit_logs due to domain invariants (application-layer enforcement)

**Layer 2: Database-Level Security Boundary** ← **This spec implements this layer**
- API connects as `sentinel_api` role with INSERT-only on audit_logs
- Even if application code defects allow UPDATE/DELETE attempts, database rejects them

**Layer 3: Schema Ownership**
- All tables owned by `schema_owner` role (migration identity only, never used by application)
- Ensures only migration identity (schema_owner) can ALTER TABLE structure
- Prevents application role from accidentally modifying table definitions

### 1.2 Two-Role Architecture

| Role | Type | Privileges | Used By | Environment |
|------|------|-----------|---------|-------------|
| `schema_owner` | LOGIN | Full DDL/DML | Migrations | All (postgres-init → Alembic) |
| `sentinel_api` | LOGIN | Table-specific (see §2.2) | API Server, Tests | All |

**Privilege Matrix for `sentinel_api` (Application Role):**

| Table | Privileges | Rationale |
|-------|-----------|-----------|
| `audit_logs` | INSERT only | Immutable audit trail; API cannot modify history |
| `users` | SELECT, INSERT, UPDATE | User account lifecycle (read, create, update profile/role) |
| `refresh_tokens` | SELECT, INSERT, UPDATE | Token management (create, refresh) |
| `uploads` | SELECT, INSERT, UPDATE, DELETE | File lifecycle (read, create, update, delete) |
| `digital_assets` | SELECT, INSERT, UPDATE, DELETE | Asset lifecycle (read, create, update, delete) |
| `analyses` | SELECT, INSERT, UPDATE, DELETE | Analysis lifecycle (read, create, update, delete) |
| `reports` | SELECT, INSERT, UPDATE, DELETE | Report lifecycle (read, create, update, delete) |
| `analyzers` | SELECT, INSERT, UPDATE, DELETE | Analyzer management |

### 1.3 Canonical References

**Requirement Source:**
- [04-Database-Design.md §11.1: Least Privilege — Database Roles](../04-Database-Design.md#1141-least-privilege--database-roles)

**Related Specifications:**
- Database Role & Privilege Design Specification (completed; canonical design)
- [09-Deployment-Architecture.md §5: Container Architecture](../09-Deployment-Architecture.md#5-container-architecture)
- [07-Backend-Development-Standards.md §11: Database Access](../07-Backend-Development-Standards.md#11-database-access)

### 1.4 Phase Overview & Dependencies

```
Phase 2: Bootstrap SQL Script
    ↓ (creates roles; must run before migrations)
Phase 3: Docker Compose Integration
    ↓ (postgres-init service runs bootstrap)
Phase 4: Alembic Configuration Update
    ↓ (migrations use schema_owner)
Phase 5: Security Boundary Tests
    ↓ (verify database-level enforcement)
Phase 6: Documentation & Deployment
    ↓ (runbooks, operator guides)
Complete: E4.T5 implementation ready for acceptance
```

All phases must complete in order. Phase 3 depends on Phase 2; Phase 4 depends on Phase 3; etc.

------------------------------------------------------------------------

## 2. Phase 2: Bootstrap Provisioning SQL Script

### 2.1 File & Purpose

**File:** `backend/docker/bootstrap/create_roles.sql`

**Purpose:** Create database roles outside Alembic migration system to avoid circular dependency:
- Alembic needs roles to exist before running migrations
- But roles should be created by infrastructure (docker-compose postgres-init), not by application code
- Solution: Standalone SQL bootstrap script, sourced from `postgres-init` init container

**Key Principles:**
- Idempotent: Can run multiple times without errors (uses `IF NOT EXISTS` checks; no destructive DROP ROLE)
- Environment-driven: All passwords sourced from environment variables (never hardcoded)
- Commented: Each step explains rationale and privilege detail
- Logged: Output documents what was created/skipped

### 2.2 Script Requirements & Specification

The `create_roles.sql` script MUST:

#### 2.2.1 Environment Variable Substitution

**Variables required:**
```
$SCHEMA_OWNER_PASSWORD     — schema_owner role password (for Alembic migrations)
$SENTINEL_API_PASSWORD     — sentinel_api role password (for application)
```

**Substitution mechanism:**
- Use PostgreSQL command-line variable substitution: `\set` directive
- Alternative (if docker-compose cannot inject vars): Use `envsubst` preprocessing in docker-compose entrypoint
- **MUST NOT** hardcode passwords in script

**Template example:**
```sql
-- Set password variable from environment
-- Usage: psql ... -f create_roles.sql (requires env vars in shell)
-- OR: envsubst < create_roles.sql | psql ... (preprocessor approach)

-- If using envsubst, template should use bash variables:
-- CREATE ROLE schema_owner PASSWORD '${SCHEMA_OWNER_PASSWORD}' ...
```

#### 2.2.2 Role Creation: `schema_owner`

**Specification:**

```sql
-- Role: schema_owner
-- Type: LOGIN (required for Alembic authentication)
-- Purpose: Migration identity; owns all tables and holds full privileges
-- Connection: Migrations only (via Alembic from DATABASE_MIGRATION_URL)
-- Password: Must be set for Alembic to authenticate
-- Privileges: CREATEDB, CREATE ROLE, all table permissions (see §2.2.3)

CREATE ROLE schema_owner
    WITH
    NOLOGIN
    PASSWORD '${SCHEMA_OWNER_PASSWORD}'
    CREATEDB
    CREATEROLE
    COMMENT 'Migration identity; owns all tables. Used by Alembic only.';
```

**Error Handling:**
```sql
-- Idempotent: Drop if exists, recreate
DROP ROLE IF EXISTS schema_owner;
CREATE ROLE schema_owner ...
```

**Rationale:**
- `LOGIN`: Required for Alembic connection via DATABASE_MIGRATION_URL
- `CREATEDB`: Alembic may need to create tables/indexes
- `CREATEROLE`: Future migrations may need to create additional roles
- Password set: Required for Alembic connection string

#### 2.2.3 Role Creation: `sentinel_api`

**Specification:**

```sql
-- Role: sentinel_api
-- Type: LOGIN (application connections)
-- Purpose: Application identity; restricted privileges per privilege matrix
-- Connection: API server, integration tests (via DATABASE_URL)
-- Password: Must be set for application to authenticate
-- Privileges: Table-specific (INSERT-only on audit_logs, etc.; see privilege matrix)

CREATE ROLE sentinel_api
    WITH
    LOGIN
    PASSWORD '${SENTINEL_API_PASSWORD}'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    COMMENT 'Application identity; restricted privileges for audit immutability.';
```

**Error Handling:**
```sql
-- Idempotent: Drop if exists, recreate
DROP ROLE IF EXISTS sentinel_api;
CREATE ROLE sentinel_api ...
```

**Rationale:**
- `LOGIN`: Application servers connect as this role
- `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`: Least privilege (no superuser powers)
- Password set: Required for application connection string

#### 2.2.4 Table Ownership Transfer

**Specification:**

All existing tables MUST be transferred from `sentinel` role to `schema_owner`:

```sql
-- For each table, transfer ownership to schema_owner
ALTER TABLE users OWNER TO schema_owner;
ALTER TABLE refresh_tokens OWNER TO schema_owner;
ALTER TABLE uploads OWNER TO schema_owner;
ALTER TABLE digital_assets OWNER TO schema_owner;
ALTER TABLE analyses OWNER TO schema_owner;
ALTER TABLE reports OWNER TO schema_owner;
ALTER TABLE analyzers OWNER TO schema_owner;
ALTER TABLE audit_logs OWNER TO schema_owner;
```

**Error Handling:**
- If table doesn't exist yet (first bootstrap run), ALT ER TABLE fails silently → wrap in `DO` block with exception handling or skip if running pre-migration
- **Timing:** This step runs AFTER bootstrap roles created, BEFORE Alembic runs
- If migrations create new tables, Alembic must be configured to create tables as `schema_owner` (see Phase 4)

**Implementation approach:**

```sql
-- Idempotent approach: Try ownership transfer; ignore if table doesn't exist
DO $$
BEGIN
    EXECUTE 'ALTER TABLE users OWNER TO schema_owner';
    EXECUTE 'ALTER TABLE refresh_tokens OWNER TO schema_owner';
    -- ... (all tables)
EXCEPTION WHEN OTHERS THEN
    -- Silently ignore if tables don't exist yet (first run)
    -- Alembic will create them as schema_owner (configured in Phase 4)
END $$;
```

#### 2.2.5 Privilege Grants: `sentinel_api` Role

**Specification:**

Grant table-specific privileges per privilege matrix (§1.2):

**audit_logs table (INSERT-only):**
```sql
-- audit_logs: Immutable audit trail
-- sentinel_api can: INSERT only (append-only)
-- sentinel_api cannot: UPDATE, DELETE, TRUNCATE, ALTER TABLE, DROP TABLE
REVOKE ALL PRIVILEGES ON TABLE audit_logs FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO sentinel_api;
GRANT SELECT, INSERT ON TABLE audit_logs TO sentinel_api;
-- Note: No UPDATE, DELETE, TRUNCATE, or ALTER TABLE privileges granted
COMMENT ON TABLE audit_logs IS 'Audit trail; sentinel_api has INSERT-only privileges';
```

**Other tables (SELECT, INSERT, UPDATE, DELETE):**
```sql
-- users, refresh_tokens, uploads, digital_assets, analyses, reports, analyzers
-- sentinel_api can: SELECT (read), INSERT (create), UPDATE (modify), DELETE (remove)
-- sentinel_api cannot: ALTER TABLE, DROP TABLE, TRUNCATE
GRANT USAGE ON SCHEMA public TO sentinel_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users TO sentinel_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE refresh_tokens TO sentinel_api;
-- ... (all other tables)
-- Note: TRUNCATE and ALTER TABLE not granted (destructive operations)
```

**Sequence Privileges (if applicable):**
```sql
-- For tables using auto-increment IDs:
-- CURRENT STATE: Sentinel uses gen_random_uuid() (no sequence needed)
-- FUTURE: If sequences introduced, grant USAGE:
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sentinel_api;
```

**Default Privileges for Future Tables:**
```sql
-- Ensure any new tables created by schema_owner are accessible to sentinel_api
-- This future-proofs the bootstrap script
ALTER DEFAULT PRIVILEGES FOR USER schema_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sentinel_api;

-- New tables created by Alembic will automatically get these privileges
```

**Comments (required):**

Include inline comments explaining each privilege grant:

```sql
-- audit_logs: Append-only audit trail
--   sentinel_api: INSERT only (create audit records)
--   sentinel_api: DENIED UPDATE, DELETE, TRUNCATE (immutability guarantee)
--   Rationale: Database-level enforcement of audit immutability (E4 requirement)
GRANT INSERT ON TABLE audit_logs TO sentinel_api;
COMMENT ON TABLE audit_logs IS 'Audit trail. sentinel_api: INSERT-only (E4 audit immutability).';

-- users: User account lifecycle
--   sentinel_api: SELECT (read), INSERT (create), UPDATE (profile/role changes)
--   sentinel_api: DENIED TRUNCATE, ALTER TABLE (destructive operations)
--   Rationale: Application manages user lifecycle; cannot destroy schema
GRANT SELECT, INSERT, UPDATE ON TABLE users TO sentinel_api;
```

### 2.3 Error Handling

#### 2.3.1 Role Already Exists

**Problem:** Script runs twice; roles already created

**Solution (idempotent):**
```sql
DROP ROLE IF EXISTS schema_owner;
DROP ROLE IF EXISTS sentinel_api;
CREATE ROLE schema_owner ...;
CREATE ROLE sentinel_api ...;
```

**Alternative (safer in production):**
```sql
-- Check if role exists; skip creation if it does
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'schema_owner') THEN
        CREATE ROLE schema_owner ...;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sentinel_api') THEN
        CREATE ROLE sentinel_api ...;
    END IF;
END $$;
```

#### 2.3.2 Table Ownership Transfer Fails

**Problem:** Table doesn't exist yet (first run; Alembic hasn't run)

**Solution:**
```sql
-- Wrap in DO block; silently ignore errors
DO $$
BEGIN
    ALTER TABLE users OWNER TO schema_owner;
EXCEPTION WHEN undefined_table THEN
    -- Table doesn't exist yet; Alembic will create it
    NULL;
END $$;
```

#### 2.3.3 Logging Output

**Specification:**

Script MUST output verification statements:

```sql
-- Verification: Check what was created
\echo '========== Role Provisioning Verification =========='
\echo 'Checking roles created:'
SELECT rolname, rolcanlogin, rolcreatedb, rolcreaterole 
    FROM pg_roles 
    WHERE rolname IN ('schema_owner', 'sentinel_api');

\echo ''
\echo 'Checking table ownership:'
SELECT tablename, pg_catalog.pg_get_userbyid(relowner) as owner
    FROM pg_tables pt
    JOIN pg_class pc ON pt.tablename = pc.relname
    WHERE schemaname = 'public' AND relowner > 16384;

\echo ''
\echo 'Checking privileges on audit_logs:'
SELECT grantee, privilege_type
    FROM information_schema.role_table_grants
    WHERE table_name = 'audit_logs' AND table_schema = 'public'
    ORDER BY grantee, privilege_type;

\echo '========== Provisioning Complete =========='
```

**Output verification:**
- Operator should see: `schema_owner` and `sentinel_api` roles created
- Operator should see: All tables owned by `schema_owner`
- Operator should see: `sentinel_api` has INSERT on audit_logs; SELECT, INSERT, UPDATE, DELETE on others

### 2.4 Dependencies & Timing

**Must run:**
1. AFTER PostgreSQL container starts (healthcheck passes)
2. BEFORE Alembic migrations run
3. ON EVERY docker-compose up (idempotent; safe to rerun)

**Used by:**
- Phase 3: Docker Compose `postgres-init` service (entrypoint)
- Phase 4: Alembic migrations (requires schema_owner role to exist)
- Production: Infrastructure-as-code (Terraform, etc.; manual provisioning)

------------------------------------------------------------------------
## 3. Phase 3: Docker Compose Integration

### 3.1 Docker Compose Changes

**File:** `docker-compose.yml`

**Purpose:** Add `postgres-init` service that runs bootstrap script before migrations

**Changes required:**

#### 3.1.1 New Service: `postgres-init`

Add this service to `docker-compose.yml`:

```yaml
  # =========================================================================
  # PostgreSQL Role Bootstrap (Initialization)
  # =========================================================================
  # Per 04-Database-Design §11.1: Two-role architecture requires role
  # provisioning outside Alembic to avoid circular dependency.
  #
  # This init container runs create_roles.sql AFTER postgres is healthy
  # and BEFORE migrations run, ensuring schema_owner and sentinel_api roles
  # exist before Alembic attempts DDL operations.
  #
  # Reference: Phase 2 (Bootstrap SQL Script)
  # =========================================================================

  postgres-init:
    image: postgres:16-alpine
    container_name: sentinel-postgres-init
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      PGHOST: postgres
      PGUSER: postgres
      PGPASSWORD: postgres
      PGDATABASE: sentinel
      SCHEMA_OWNER_PASSWORD: ${POSTGRESQL_SCHEMA_OWNER_PASSWORD:-schema_owner_password}
      SENTINEL_API_PASSWORD: ${POSTGRESQL_SENTINEL_API_PASSWORD:-sentinel_api_password}
    volumes:
      # Mount bootstrap script from repository
      - ./docker/bootstrap/create_roles.sql:/docker-entrypoint-initdb.d/create_roles.sql:ro
    entrypoint: |
      /bin/sh -c "
        echo 'Waiting for PostgreSQL to be ready...'
        until pg_isready -h postgres -U postgres; do
          sleep 1
        done
        echo 'PostgreSQL ready. Running role provisioning...'
        envsubst < /docker-entrypoint-initdb.d/create_roles.sql | psql
        echo 'Role provisioning complete.'
      "
    restart: "no"
```

**Key elements:**

| Element | Rationale |
|---------|-----------|
| `image: postgres:16-alpine` | Alpine container has `psql` CLI and `envsubst` for variable substitution |
| `depends_on: postgres (healthcheck)` | Ensures postgres is healthy before running init |
| `PGHOST: postgres` | Internal Docker network DNS (service name) |
| `SCHEMA_OWNER_PASSWORD` env var | Sourced from `.env` (or defaults to hardcoded fallback for dev) |
| `SENTINEL_API_PASSWORD` env var | Sourced from `.env` (or defaults to hardcoded fallback for dev) |
| `entrypoint: envsubst < create_roles.sql \| psql` | Substitute env vars in SQL; pipe to psql for execution |
| `restart: "no"` | Init containers should not auto-restart; run once per `docker-compose up` |

#### 3.1.2 Docker Build Directory Structure

**Create directory:**
```
backend/
  docker/
    bootstrap/
      create_roles.sql         ← (Phase 2 script)
```

**Ensure directory exists:**
```bash
mkdir -p backend/docker/bootstrap
# create_roles.sql populated in Phase 2
```

#### 3.1.3 Environment Variables

**Update `.env.example`:**

Add these variables:

```bash
# ===========================================================================
# PostgreSQL Role Provisioning
# ===========================================================================

# schema_owner role password (for Alembic migrations)
# Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
# Required | Secret
POSTGRESQL_SCHEMA_OWNER_PASSWORD=schema_owner_password_change_me

# sentinel_api role password (for application)
# Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
# Required | Secret
POSTGRESQL_SENTINEL_API_PASSWORD=sentinel_api_password_change_me
```

**Fallback defaults (dev only):**
- If `.env` not present: Uses fallback values in docker-compose (see entrypoint)
- **MUST NOT** use fallbacks in production; require explicit `.env` configuration

### 3.2 Docker Compose Service Dependencies

**Update migration service dependency:**

```yaml
  backend-migrations:
    # (existing migration service)
    depends_on:
      postgres-init:
        condition: service_completed_successfully  # ← NEW: depend on init
      postgres:
        condition: service_healthy
```

**This ensures:**
1. postgres starts → postgres-init waits for postgres healthy
2. postgres-init runs → creates roles
3. backend-migrations runs → uses schema_owner role via Alembic

**Execution order:**
```
postgres (start)
    ↓ (wait for healthy)
postgres-init (run bootstrap)
    ↓ (wait for completion)
backend-migrations (run Alembic)
    ↓ (wait for healthy)
backend (start API)
```

### 3.3 Troubleshooting & Verification

#### 3.3.1 Verify Bootstrap Ran Successfully

```bash
# Check logs
docker logs sentinel-postgres-init

# Expected output:
#   Waiting for PostgreSQL to be ready...
#   PostgreSQL ready. Running role provisioning...
#   ========== Role Provisioning Verification ==========
#   Checking roles created:
#    rolname    | rolcanlogin | rolcreatedb | rolcreaterole
#   -----------+-------------+-------------+---------------
#    schema_owner  | f           | t           | t
#    sentinel_api  | t           | f           | f
#   ...
#   ========== Provisioning Complete ==========

# Check container status
docker compose ps  # sentinel-postgres-init should show "Exited (0)"
```

#### 3.3.2 Debug: Boot strap Script Fails

**Common issues:**

| Issue | Diagnosis | Resolution |
|-------|-----------|-----------|
| `Connection refused` | postgres not ready | Increase `until pg_isready` retries; check postgres healthcheck |
| `Permission denied` | `PGUSER: postgres` insufficient privileges | Verify POSTGRES_PASSWORD matches docker-compose postgres service |
| `Undefined variable` | `${SCHEMA_OWNER_PASSWORD}` not set | Check `.env` file; ensure variables are set in shell before `docker-compose up` |
| `SQL syntax error` | create_roles.sql malformed | Validate SQL syntax; check for shell variable conflicts (e.g., `$1` in SQL) |

**Debug steps:**

```bash
# 1. Check if postgres is healthy
docker exec sentinel-postgres pg_isready -U postgres

# 2. Manually run bootstrap script against running postgres
docker exec sentinel-postgres psql -U postgres -d sentinel \
  -c "SELECT rolname FROM pg_roles WHERE rolname IN ('schema_owner', 'sentinel_api');"

# 3. Examine create_roles.sql for template variables
cat backend/docker/bootstrap/create_roles.sql | grep -E '\$|{{|%'

# 4. Check environment variables are set
env | grep POSTGRESQL
```

#### 3.3.3 Verify Privileges After Bootstrap

Connect to database and verify roles/privileges:

```bash
# Connect as postgres superuser
docker exec sentinel-postgres psql -U postgres -d sentinel -c "
  \du                         -- List all roles
  SELECT * FROM pg_roles WHERE rolname IN ('schema_owner', 'sentinel_api');
  \dp audit_logs              -- Check audit_logs privileges
  \dp users                   -- Check users privileges
"
```

### 3.4 Docker Compose Documentation Update

**Update comments in docker-compose.yml:**

```yaml
# =========================================================================
# Docker Compose Architecture — Local Development
# =========================================================================
#
# Service Order (startup dependency chain):
#   1. postgres               — Database (persists across restarts)
#   2. postgres-init          — Role provisioning (runs once, idempotent)
#   3. backend-migrations     — Schema creation (runs once per deploy)
#   4. redis, minio, minio-init — Queue, object storage
#   5. backend                — API server (depends on all above)
#
# Two-Role Architecture (per 04-Database-Design §11.1):
#   - schema_owner (LOGIN, migration-only) → Migrations (Alembic)
#   - sentinel_api (LOGIN)    → Application (API, tests)
#
# Role provisioning is performed by postgres-init init container
# (Phase 2, Phase 3) BEFORE Alembic runs (Phase 4).
# This avoids circular dependency: Alembic needs roles to exist
# before it runs migrations.
#
# Reference: ROLE_PROVISIONING_IMPLEMENTATION.md (Phase 3)
# =========================================================================
```

------------------------------------------------------------------------

## 4. Phase 4: Alembic Configuration Update

### 4.1 Current State vs. Target State

**Current state:**
```
DATABASE_MIGRATION_URL = postgresql://sentinel:sentinel@localhost/sentinel
    ↓
Alembic connects as `sentinel` role (single role, no privilege separation)
    ↓
All migrations run with sentinel privileges (full DDL/DML)
    ↓
PROBLEM: No privilege boundary; if app code connects as sentinel, it has full access
```

**Target state:**
```
DATABASE_MIGRATION_URL = postgresql://schema_owner:${POSTGRESQL_SCHEMA_OWNER_PASSWORD}@localhost/sentinel
    ↓
Alembic connects as `schema_owner` role (migration identity)
    ↓
All migrations create tables OWNED BY schema_owner
    ↓
Applications connect as sentinel_api (restricted privileges)
    ↓
BENEFIT: Database enforces privilege boundary; audit_logs is INSERT-only for apps
```

### 4.2 Configuration Changes

#### 4.2.1 `.env` & `.env.example` Update

**Current:**
```
DATABASE_MIGRATION_URL=postgresql://sentinel:sentinel@localhost:5432/sentinel_test
```

**Target:**
```
DATABASE_MIGRATION_URL=postgresql://schema_owner:${POSTGRESQL_SCHEMA_OWNER_PASSWORD}@localhost:5432/sentinel_test
# OR, if using env var substitution:
DATABASE_MIGRATION_URL=postgresql://schema_owner:<password-from-env>@localhost:5432/sentinel_test
```

**Rationale:**
- `schema_owner` role: Has CREATEDB, CREATEROLE, DDL privileges
- Password: `${POSTGRESQL_SCHEMA_OWNER_PASSWORD}` (from environment; set by docker-compose or CI/CD)

#### 4.2.2 `backend/migrations/env.py` Update

**Current behavior:**
```python
# env.py reads DATABASE_MIGRATION_URL directly
sqlalchemy_url = config.get_main_option("sqlalchemy.url")
# sqlalchemy_url = postgresql://sentinel:sentinel@localhost/sentinel
```

**Target behavior:**
```python
# env.py reads DATABASE_MIGRATION_URL; ensures connection is as schema_owner
sqlalchemy_url = config.get_main_option("sqlalchemy.url")
# sqlalchemy_url = postgresql://schema_owner:<PASSWORD>@localhost/sentinel

# Add comment explaining role identity:
# Connection identity: schema_owner (LOGIN role for migrations only; never used by application)
# All DDL operations (CREATE TABLE, CREATE INDEX, etc.) run with schema_owner privileges
# Resulting objects are OWNED BY schema_owner
# Application connections (sentinel_api) get restricted privileges via bootstrap
```

**No code changes needed:**
- Alembic automatically uses the connection's role for all DDL operations
- When connected as schema_owner, all CREATE TABLE statements run as schema_owner
- Resulting tables are owned by schema_owner

#### 4.2.3 Migration Template Update (Optional)

**File:** `backend/migrations/script.py.mako` (Alembic template)

Add this comment to new migration files (auto-generated):

```python
# Alembic migration template already comments each operation
# ADD: Note about role identity

"""
Migration: [upgrade description]

Role Identity: schema_owner
- All DDL operations (CREATE, ALTER, DROP) run as schema_owner role
- Resulting tables are OWNED BY schema_owner
- Privileges are granted to sentinel_api via bootstrap (not via migration)

Per: ROLE_PROVISIONING_IMPLEMENTATION.md §4 (Alembic Configuration Update)
     04-Database-Design.md §11.1 (Least Privilege Database Roles)
"""
```

**Alternative:** Document this in `backend/migrations/README.md` instead (see Phase 6)

### 4.3 Migration Behavior with New Configuration

#### 4.3.1 How Alembic Respects Role Identity

**When Alembic connects as schema_owner:**

```python
# In Alembic upgrade():
def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), ...),
        ...
    )
    # Executed as: CREATE TABLE users (...)
    # Connection: schema_owner role
    # Result: Table owned by schema_owner
```

**PostgreSQL behavior:**
- When connected as `schema_owner`, all CREATE TABLE operations create tables owned by `schema_owner`
- No explicit `OWNER TO` needed in migration; role ownership is implicit

**Verification:**
```bash
# After migration runs:
psql -c "SELECT tablename, pg_catalog.pg_get_userbyid(relowner) as owner FROM pg_tables WHERE schemaname = 'public';"

# Expected:
#  tablename     |    owner
# ---------------+---------------
#  users         | schema_owner
#  refresh_tokens | schema_owner
#  audit_logs    | schema_owner
#  ...
```

#### 4.3.2 Index Ownership

**Indexes created by Alembic:**

```python
# In Alembic upgrade():
op.create_index(
    'idx_users_email',
    'users',
    ['email'],
    unique=True
)
```

**Result:**
- Index created as: `CREATE UNIQUE INDEX idx_users_email ON users (email);`
- Index owner: Same as table owner (schema_owner)
- Verified: `\di idx_users_email` shows owner

### 4.4 No Application Code Changes Needed

**Important:** This phase requires NO changes to application code:

- ORM models (`SQLAlchemy` entities) read unchanged
- Queries read unchanged
- Connection strings updated (role + password), but application connects as sentinel_api (via DATABASE_URL)
- Alembic connects separately as schema_owner (via DATABASE_MIGRATION_URL)

**Verify:**
- `backend/app/db/session.py`: Uses `DATABASE_URL` (sentinel_api connection) ✓
- `backend/migrations/env.py`: Uses `DATABASE_MIGRATION_URL` (schema_owner connection) ✓
- Both environment variables configured independently

### 4.5 Configuration Documentation

**Update `backend/migrations/README.md`:**

```markdown
# Alembic Migration System

## Role Identity

Migrations run as the `schema_owner` role (LOGIN, migration identity only).

- Connection: `postgresql://schema_owner:<password>@localhost/sentinel`
- All DDL operations create objects owned by `schema_owner`
- No OWNER TO statements needed in migrations

Application connects as `sentinel_api` role separately.

## Migration Privileges

The `schema_owner` role has CREATEDB and CREATEROLE privileges.
Migrations can:
- CREATE TABLE, CREATE INDEX, CREATE CONSTRAINT
- ALTER TABLE (structure changes)
- Anything else schema_owner is granted

The `sentinel_api` role has restricted table privileges (see audit_logs INSERT-only).
Migrations DO NOT grant privileges to sentinel_api (see bootstrap script).

## Reference

- [ROLE_PROVISIONING_IMPLEMENTATION.md §4](../specs/ROLE_PROVISIONING_IMPLEMENTATION.md#4-phase-4-alembic-configuration-update)
- [04-Database-Design.md §11.1](../../docs/04-Database-Design.md#1141-least-privilege--database-roles)
```

------------------------------------------------------------------------
## 5. Phase 5: Security Boundary Tests

### 5.1 Test File & Purpose

**File:** `backend/tests/security/test_db_role_privileges.py`

**Purpose:** Verify that database-level privilege boundaries are enforced

**Test approach:**
- Connect to database as `sentinel_api` role
- Attempt operations that SHOULD succeed (permitted by privileges)
- Attempt operations that SHOULD fail (denied by privileges)
- Verify failure reason is "permission denied" (database enforcement, not app logic)

**Location in test suite:**
```
backend/tests/
  ├── unit/                    (existing)
  ├── integration/             (existing)
  └── security/                (NEW)
      └── test_db_role_privileges.py
```

### 5.2 Test Cases

#### 5.2.1 audit_logs Immutability Tests

**Test: `test_audit_logs_insert_allowed`**

```python
def test_audit_logs_insert_allowed():
    """
    WHEN sentinel_api role attempts INSERT on audit_logs
    THEN the operation succeeds
    AND audit record is created
    
    Validates: E4.T5 (database-level immutability)
    """
    # Connect as sentinel_api
    conn = psycopg2.connect(
        host='localhost',
        user='sentinel_api',
        password=os.getenv('POSTGRESQL_SENTINEL_API_PASSWORD'),
        dbname='sentinel_test',
        port=5432
    )
    cursor = conn.cursor()
    
    try:
        # INSERT audit record
        cursor.execute("""
            INSERT INTO audit_logs (id, resource_type, resource_id, action, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            uuid.uuid4(),
            'user',
            uuid.uuid4(),
            'created',
            uuid.uuid4(),
            datetime.utcnow()
        ))
        conn.commit()
        
        # Verify insert succeeded
        cursor.execute("SELECT COUNT(*) FROM audit_logs")
        count = cursor.fetchone()[0]
        assert count > 0
    finally:
        conn.close()
```

**Test: `test_audit_logs_update_denied`**

```python
def test_audit_logs_update_denied():
    """
    WHEN sentinel_api role attempts UPDATE on audit_logs
    THEN the operation fails with permission denied
    
    Validates: E4.T5 (database-level immutability enforcement)
    """
    conn = psycopg2.connect(...)
    cursor = conn.cursor()
    
    try:
        # Attempt UPDATE
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute("""
                UPDATE audit_logs 
                SET action = 'modified' 
                WHERE id = %s
            """, (uuid.uuid4(),))
            conn.commit()
    finally:
        conn.close()
```

**Test: `test_audit_logs_delete_denied`**

```python
def test_audit_logs_delete_denied():
    """
    WHEN sentinel_api role attempts DELETE on audit_logs
    THEN the operation fails with permission denied
    """
    # Similar to UPDATE test; expect InsufficientPrivilege
    # cursor.execute("DELETE FROM audit_logs ...")
```

**Test: `test_audit_logs_truncate_denied`**

```python
def test_audit_logs_truncate_denied():
    """
    WHEN sentinel_api role attempts TRUNCATE on audit_logs
    THEN the operation fails with permission denied
    """
    # cursor.execute("TRUNCATE TABLE audit_logs")
```

**Test: `test_audit_logs_alter_table_denied`**

```python
def test_audit_logs_alter_table_denied():
    """
    WHEN sentinel_api role attempts ALTER TABLE on audit_logs
    THEN the operation fails with permission denied
    """
    # cursor.execute("ALTER TABLE audit_logs ADD COLUMN foo text")
```

**Test: `test_audit_logs_drop_table_denied`**

```python
def test_audit_logs_drop_table_denied():
    """
    WHEN sentinel_api role attempts DROP TABLE audit_logs
    THEN the operation fails with permission denied
    """
    # cursor.execute("DROP TABLE audit_logs")
```

#### 5.2.2 Unrestricted Table Privilege Tests

**Test: `test_users_select_allowed`**

```python
def test_users_select_allowed():
    """
    WHEN sentinel_api role attempts SELECT on users
    THEN the operation succeeds
    """
    # Similar structure to audit_logs INSERT test
    # cursor.execute("SELECT * FROM users LIMIT 1")
```

**Test: `test_users_insert_allowed`**

```python
def test_users_insert_allowed():
    """
    WHEN sentinel_api role attempts INSERT on users
    THEN the operation succeeds
    """
    # INSERT user record
```

**Test: `test_users_update_allowed`**

```python
def test_users_update_allowed():
    """
    WHEN sentinel_api role attempts UPDATE on users
    THEN the operation succeeds
    """
    # UPDATE user record
```

**Test: `test_users_delete_allowed`**

```python
def test_users_delete_allowed():
    """
    WHEN sentinel_api role attempts DELETE on users
    THEN the operation succeeds
    """
    # DELETE user record (if exists and not referenced)
```

**Repeat for other unrestricted tables:**
- `refresh_tokens`
- `uploads`
- `digital_assets`
- `analyses`
- `reports`
- `analyzers`

#### 5.2.3 Application Functionality with Restricted Role

**Test: `test_integration_suite_with_sentinel_api_role`**

```python
def test_integration_suite_with_sentinel_api_role():
    """
    WHEN all 19 integration tests run with DATABASE_URL set to sentinel_api role
    THEN all 19 tests PASS
    AND no code changes needed
    
    Validates: Privilege restrictions do not break application
    """
    # Invoke existing integration tests with sentinel_api connection
    # Expected: All 19 integration tests pass (or at least all non-admin tests)
    
    # Implementation approach:
    # 1. Set DATABASE_URL to postgresql+asyncpg://sentinel_api:password@localhost/sentinel_test
    # 2. Run pytest backend/tests/integration/ -v
    # 3. Assert exit code == 0
    # 4. Assert 19/19 tests passed
```

**Note:** This test may be implemented as a CI/CD workflow rather than a unit test:
- CI matrix variable: TEST_WITH_RESTRICTED_ROLE = true
- Override DATABASE_URL in test environment
- Run full integration suite
- Verify all pass

#### 5.2.4 Sequence Privileges (Future-Proofing)

**Current state:** gen_random_uuid() used; no sequences

**Test: `test_sequence_usage_if_added`**

```python
@pytest.mark.skip(reason="No sequences in use; future-proofing only")
def test_sequence_usage_if_added():
    """
    IF sequences are introduced in future migrations:
    WHEN sentinel_api role attempts NEXT VALUE on sequence
    THEN the operation succeeds (USAGE privilege granted)
    
    Note: Currently skipped; enable when sequences are introduced.
    """
    # Implementation placeholder for future
    pass
```

### 5.3 Test Execution & Verification

#### 5.3.1 Running Tests

```bash
# Run all security boundary tests
cd backend
pytest tests/security/test_db_role_privileges.py -v

# Expected output:
# test_audit_logs_insert_allowed PASSED
# test_audit_logs_update_denied PASSED
# test_audit_logs_delete_denied PASSED
# ... (6 audit_logs tests)
# test_users_select_allowed PASSED
# test_users_insert_allowed PASSED
# ... (4 users tests)
# ... (similar for other tables)
# test_integration_suite_with_sentinel_api_role PASSED
#
# ========== 19+ passed in 45.32s ==========
```

#### 5.3.2 Expected Failures

**These are GOOD failures (expected):**

```
test_audit_logs_update_denied:
    InsufficientPrivilege: permission denied for table audit_logs
    ✓ EXPECTED and GOOD (immutability enforced)

test_audit_logs_delete_denied:
    InsufficientPrivilege: permission denied for table audit_logs
    ✓ EXPECTED and GOOD (immutability enforced)
```

**If these SUCCEED when they should FAIL:**
- Bug: Privileges not correctly restricted
- Action: Review bootstrap script; check GRANT statements

#### 5.3.3 Integration with E4V.T2 Test Suite

**Existing test suites:**
- E4V.T2: 19 integration tests (should all pass with sentinel_api role)
- E4V.T3: MyPy strict (should pass; no code changes)
- E4V.T4: Compileall (should pass; no code changes)
- E4V.T5: Concurrency tests (should pass; no code changes)

**New test suite adds:**
- E4.T5+: Security boundary tests (verify database-level enforcement)

### 5.4 Debugging Failed Tests

#### 5.4.1 Insufficient Privileges Not Raised

**Problem:** UPDATE or DELETE on audit_logs succeeds (should fail)

**Diagnosis:**
```bash
# Check privileges granted to sentinel_api
psql -c "
  SELECT grantee, privilege_type 
  FROM information_schema.role_table_grants 
  WHERE table_name = 'audit_logs' 
  ORDER BY privilege_type;
"

# Expected output:
#  grantee      | privilege_type
# ---------------+----------------
#  sentinel_api  | INSERT
#  sentinel_api  | SELECT
# (should NOT show UPDATE, DELETE, TRUNCATE, etc.)
```

**Fix:**
- Re-run bootstrap script: `docker-compose down -v && docker-compose up`
- Or manually fix privileges: `REVOKE UPDATE, DELETE ON audit_logs FROM sentinel_api`

#### 5.4.2 INSERT Fails Unexpectedly

**Problem:** INSERT on audit_logs fails (should succeed)

**Diagnosis:**
```bash
# Check that sentinel_api has INSERT privilege
psql -c "
  SELECT privilege_type 
  FROM information_schema.role_table_grants 
  WHERE table_name = 'audit_logs' AND privilege_type = 'INSERT';
"

# Expected: At least one row with INSERT
```

**Fix:**
- Grant INSERT: `GRANT INSERT ON TABLE audit_logs TO sentinel_api;`

------------------------------------------------------------------------
## 6. Phase 6: Documentation & Deployment

### 6.1 New Documentation Files

#### 6.1.1 `docs/12-PostgreSQL-Role-Architecture.md` (New)

**Purpose:** Canonical architecture documentation for operators and engineers

**Contents:**

```markdown
# 12 --- PostgreSQL Role Architecture

## Overview

Sentinel uses a two-role PostgreSQL architecture to enforce database-level 
immutability of audit_logs and separate migration privileges from application 
privileges.

## Roles

### schema_owner (LOGIN, migration-only)`n- Type: Login role (but used only for migrations; never by application)
- Privileges: CREATEDB, CREATEROLE, full DDL/DML
- Used by: Alembic migrations only
- Connection: DATABASE_MIGRATION_URL (schema_owner identity)
- Password: POSTGRESQL_SCHEMA_OWNER_PASSWORD environment variable

### sentinel_api (LOGIN)
- Type: Login role (application connection)
- Privileges: Table-specific (see Privilege Matrix)
- Used by: API server, tests, background workers
- Connection: DATABASE_URL (sentinel_api identity)
- Password: POSTGRESQL_SENTINEL_API_PASSWORD environment variable

## Privilege Matrix

See [ROLE_PROVISIONING_IMPLEMENTATION.md §1.2](../backend/specs/ROLE_PROVISIONING_IMPLEMENTATION.md#12-two-role-architecture)

Key highlights:
- audit_logs: INSERT-only (immutable audit trail)
- Other tables: SELECT, INSERT, UPDATE, DELETE (full lifecycle)

## Deployment Scenarios

### Local Development (Docker Compose)
- postgres-init service runs create_roles.sql after postgres starts
- Alembic migrations run as schema_owner
- API connects as sentinel_api
- See: docker-compose.yml

### CI/CD (GitHub Actions)
- Pre-migration script runs create_roles.sql
- Migrations run as schema_owner
- Tests run as sentinel_api
- See: .github/workflows/

### Production (Infrastructure-as-Code)
- Terraform / Kubernetes manifests provision roles
- Database backup/restore preserves role definitions
- Emergency runbooks for manual provisioning (if IaC fails)
- See: ROLE_PROVISIONING_README.md

## Backup & Restore Considerations

When backing up/restoring PostgreSQL database:

1. **Backup:** Include role definitions (pg_dump with --globals)
   ```bash
   pg_dump --globals-only sentinel > roles_backup.sql
   ```

2. **Restore:** Apply role backup before application connects
   ```bash
   psql < roles_backup.sql
   ```

3. **Cross-instance restore:** If restoring to different PostgreSQL instance,
   ensure schema_owner and sentinel_api roles are provisioned first.

## Troubleshooting

See: ROLE_PROVISIONING_README.md §3 (Operator Troubleshooting)

## References

- [04-Database-Design.md §11.1: Least Privilege](../04-Database-Design.md#1141-least-privilege--database-roles)
- [ROLE_PROVISIONING_IMPLEMENTATION.md](../backend/specs/ROLE_PROVISIONING_IMPLEMENTATION.md)
- E4 Verification: Database-level audit immutability enforcement
```

#### 6.1.2 `ROLE_PROVISIONING_README.md` (New, Operator Runbook)

**Purpose:** Practical runbook for ops and deployment engineers

**Contents:**

```markdown
# PostgreSQL Role Provisioning — Operator Runbook

## Quick Start

### Local Development

```bash
# 1. Copy .env.example to .env
cp .env.example .env

# 2. Edit .env with strong passwords
POSTGRESQL_SCHEMA_OWNER_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
POSTGRESQL_SENTINEL_API_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
# Update .env with these values

# 3. Start services (includes role provisioning)
docker-compose up -d

# 4. Verify roles created
docker exec sentinel-postgres psql -U postgres -d sentinel -c "
  \du                           -- List roles
  SELECT * FROM pg_roles WHERE rolname IN ('schema_owner', 'sentinel_api');
"
```

### Manual Role Provisioning (if bootstrap fails)

```bash
# Connect as postgres superuser
psql -h localhost -U postgres -d sentinel

# Run create_roles.sql manually
psql -h localhost -U postgres -d sentinel -f backend/docker/bootstrap/create_roles.sql
```

### Production Provisioning (Terraform)

```hcl
# Example Terraform: provision roles in AWS RDS PostgreSQL
resource "postgresql_role" "schema_owner" {
  name           = "schema_owner"
  login          = false
  createdb       = true
  createrole     = true
  password       = var.schema_owner_password
  role_set       = []
}

resource "postgresql_role" "sentinel_api" {
  name       = "sentinel_api"
  login      = true
  password   = var.sentinel_api_password
  roles      = []  # No role inheritance
}
```

## Troubleshooting

### Issue: "FATAL: role 'schema_owner' does not exist"

**Cause:** Alembic attempted to run before bootstrap roles created.

**Fix:**
```bash
# 1. Restart docker-compose (ensures postgres-init runs)
docker-compose down -v
docker-compose up -d

# 2. Verify postgres-init completed
docker logs sentinel-postgres-init

# 3. If still failing, manually provision
docker exec sentinel-postgres psql -U postgres -d sentinel -f backend/docker/bootstrap/create_roles.sql
```

### Issue: "permission denied for table users"

**Cause:** sentinel_api role lacks privileges on users table.

**Fix:**
```bash
# Grant privileges manually
psql -h localhost -U postgres -d sentinel -c "
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users TO sentinel_api;
"
```

### Issue: "Audit logs are modifiable by sentinel_api"

**Cause:** Privileges incorrectly granted; UPDATE/DELETE not revoked.

**Fix:**
```bash
# Revoke destructive privileges
psql -h localhost -U postgres -d sentinel -c "
  REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_logs FROM sentinel_api;
"
```

## Backup & Restore

### Backup Roles

```bash
# Backup role definitions only
pg_dump -h localhost -U postgres --globals-only sentinel > roles_backup.sql

# Backup full database including role definitions
pg_dump -h localhost -U postgres sentinel > full_backup.sql
```

### Restore Roles

```bash
# Restore role definitions before reconnecting applications
psql -h localhost -U postgres < roles_backup.sql
```

## Monitoring & Verification

### Check Role Privileges

```bash
psql -h localhost -U postgres -d sentinel -c "
  SELECT 
    t.tablename,
    r.rolname as granted_to,
    string_agg(acl.privilege_type, ', ' ORDER BY acl.privilege_type) as privileges
  FROM pg_tables t
  JOIN information_schema.role_table_grants acl 
    ON t.tablename = acl.table_name AND t.schemaname = acl.table_schema
  JOIN pg_roles r ON acl.grantee = r.rolname
  WHERE t.schemaname = 'public'
  GROUP BY t.tablename, r.rolname
  ORDER BY t.tablename, r.rolname;
"
```

### Verify Audit Immutability

```bash
# Attempt UPDATE as sentinel_api (should fail)
psql -h localhost -U sentinel_api -d sentinel -c "UPDATE audit_logs SET action = 'hacked';"

# Expected error: "ERROR: permission denied for table audit_logs"
```

## Security Reminders

1. **Never hardcode passwords** in docker-compose.yml or source code
2. **Use environment variables** for all role passwords
3. **Rotate passwords regularly** (update .env, restart services)
4. **Audit role changes** (log all CREATE/DROP/ALTER ROLE commands)
5. **Backup role definitions** before deployment
```

### 6.2 Update Existing Documentation

#### 6.2.1 `.env.example` Update

Add to `.env.example`:

```bash
# ===========================================================================
# PostgreSQL Role Provisioning (NEW)
# ===========================================================================
# Per 04-Database-Design §11.1: Two-role architecture for privilege separation
# and database-level audit immutability enforcement.
#
# These roles are created by docker-compose postgres-init service.
# See: ROLE_PROVISIONING_IMPLEMENTATION.md
#      ROLE_PROVISIONING_README.md
# ===========================================================================

# schema_owner role password (migrations only)
# Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
# MUST be strong and unique per environment
# Required | Secret
POSTGRESQL_SCHEMA_OWNER_PASSWORD=change_me_strong_password_for_migrations

# sentinel_api role password (application connections)
# Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
# MUST be strong and unique per environment
# Required | Secret
POSTGRESQL_SENTINEL_API_PASSWORD=change_me_strong_password_for_app
```

#### 6.2.2 `README.md` Deployment Section Update

Add subsection to README.md:

```markdown
### PostgreSQL Role Architecture

Sentinel uses a two-role PostgreSQL architecture for security:

- **schema_owner**: Migration identity (LOGIN, migration-only); owns all tables
- **sentinel_api**: Application identity (login); restricted privileges

See `docs/12-PostgreSQL-Role-Architecture.md` and `ROLE_PROVISIONING_README.md` for details.

**Local Development Setup:**

```bash
cp .env.example .env
# Edit .env: Set POSTGRESQL_SCHEMA_OWNER_PASSWORD and POSTGRESQL_SENTINEL_API_PASSWORD
docker-compose up -d
```

When `docker-compose up` runs:
1. PostgreSQL starts
2. postgres-init service provisions roles (create_roles.sql)
3. Alembic runs migrations as schema_owner
4. API server connects as sentinel_api
```

#### 6.2.3 `backend/migrations/README.md` Update

Already added in Phase 4 section; ensure it's included.

### 6.3 GitHub Actions / CI/CD Integration (Optional, Not Blocking)

**For CI/CD pipelines that don't use docker-compose:**

```yaml
# .github/workflows/test.yml (relevant section)

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: sentinel
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      
      # NEW: Provision roles before migrations
      - name: Provision PostgreSQL roles
        env:
          PGHOST: localhost
          PGUSER: postgres
          PGPASSWORD: postgres
          PGDATABASE: sentinel
          POSTGRESQL_SCHEMA_OWNER_PASSWORD: ci_schema_owner_password
          POSTGRESQL_SENTINEL_API_PASSWORD: ci_sentinel_api_password
        run: |
          # Substitute environment variables in create_roles.sql
          envsubst < backend/docker/bootstrap/create_roles.sql | psql
      
      # Run Alembic migrations as schema_owner
      - name: Run migrations
        env:
          DATABASE_MIGRATION_URL: postgresql://schema_owner:ci_schema_owner_password@localhost/sentinel
        run: |
          cd backend
          alembic upgrade head
      
      # Run tests as sentinel_api
      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://sentinel_api:ci_sentinel_api_password@localhost/sentinel
        run: |
          cd backend
          pytest tests/
```

------------------------------------------------------------------------

## 7. Implementation Order & Dependencies

### 7.1 Execution Sequence

**Must follow this exact order:**

1. **Phase 2: Bootstrap SQL Script** (create_roles.sql)
   - Creates roles outside Alembic
   - Standalone, can be tested independently
   - Output: `backend/docker/bootstrap/create_roles.sql`

2. **Phase 3: Docker Compose Integration**
   - Adds postgres-init service
   - Wires postgres-init → create_roles.sql execution
   - Makes backend-migrations depend on postgres-init
   - Output: Updated `docker-compose.yml`
   - Dependency: Requires Phase 2 (create_roles.sql must exist)

3. **Phase 4: Alembic Configuration Update**
   - Updates DATABASE_MIGRATION_URL to use schema_owner role
   - Updates .env.example and .env with role passwords
   - No code changes; configuration only
   - Output: Updated `.env.example`, `backend/migrations/env.py` docs
   - Dependency: Requires Phase 3 (roles must exist before Alembic runs)

4. **Phase 5: Security Boundary Tests**
   - Verifies database-level enforcement
   - Tests INSERT allowed on audit_logs; UPDATE/DELETE denied
   - Tests full privileges on other tables
   - Output: `backend/tests/security/test_db_role_privileges.py`
   - Dependency: Requires Phases 2-4 (roles configured; Alembic ready)

5. **Phase 6: Documentation & Deployment**
   - Creates operator runbooks
   - Updates README, .env.example
   - Documents architecture and troubleshooting
   - Output: `docs/12-PostgreSQL-Role-Architecture.md`, `ROLE_PROVISIONING_README.md`
   - Dependency: Non-blocking; can run in parallel with Phase 5

### 7.2 Parallel Work (if multiple engineers)

**Non-blocking parallel tasks:**

- Phase 2 & Phase 6: Bootstrap script and documentation can be developed in parallel
- Phase 4 documentation: Can be drafted while Phase 3 is in progress

**Blocking sequential tasks:**

- Phase 2 → Phase 3 → Phase 4 → Phase 5 (strict dependency chain)

### 7.3 Implementation Checklist

- [ ] Phase 2: `backend/docker/bootstrap/create_roles.sql` created and tested
- [ ] Phase 3: `docker-compose.yml` updated with postgres-init service
- [ ] Phase 3: `.env.example` updated with POSTGRESQL_*_PASSWORD variables
- [ ] Phase 4: DATABASE_MIGRATION_URL updated to use schema_owner role
- [ ] Phase 4: `backend/migrations/README.md` updated
- [ ] Phase 5: `backend/tests/security/test_db_role_privileges.py` created
- [ ] Phase 5: All security tests passing (INSERT allowed, UPDATE/DELETE denied)
- [ ] Phase 6: `docs/12-PostgreSQL-Role-Architecture.md` created
- [ ] Phase 6: `ROLE_PROVISIONING_README.md` created
- [ ] Phase 6: README.md deployment section updated
- [ ] Verification: All 19 integration tests passing with sentinel_api role

------------------------------------------------------------------------

## 8. Success Criteria & Verification

### 8.1 E4V.T2 Integration Tests

**Requirement:** 19/19 integration tests PASS with sentinel_api role

**Verification:**
```bash
cd backend
export DATABASE_URL=postgresql+asyncpg://sentinel_api:<password>@localhost/sentinel
pytest tests/integration/ -v

# Expected output:
# test_1 PASSED
# test_2 PASSED
# ... (19 total)
# ========== 19 passed in X.XXs ==========
```

**Pass criterion:** Exit code 0; 19/19 tests passed

### 8.2 E4V.T3 MyPy Strict

**Requirement:** mypy --strict reports 0 errors (no new type violations from role changes)

**Verification:**
```bash
cd backend
mypy --strict app/

# Expected: Success (exit code 0)
```

**Pass criterion:** Exit code 0; no new type violations

### 8.3 E4V.T4 Compileall

**Requirement:** compileall reports no errors

**Verification:**
```bash
cd backend
python -m compileall app/

# Expected: Success (exit code 0)
```

**Pass criterion:** Exit code 0

### 8.4 E4V.T5 Concurrency Tests

**Requirement:** 3/3 concurrency tests PASS (no regressions from role provisioning)

**Verification:**
```bash
cd backend
pytest tests/integration/test_concurrency.py -v

# Expected output:
# test_concurrent_auth PASSED
# test_concurrent_db_ops PASSED
# test_concurrent_cache PASSED
# ========== 3 passed in X.XXs ==========
```

**Pass criterion:** Exit code 0; 3/3 tests passed

### 8.5 Security Boundary Tests

**Requirement:** All database privilege tests PASS

**Verification:**
```bash
cd backend
pytest tests/security/test_db_role_privileges.py -v

# Expected output shows:
# test_audit_logs_insert_allowed PASSED
# test_audit_logs_update_denied PASSED
# test_audit_logs_delete_denied PASSED
# test_audit_logs_truncate_denied PASSED
# test_audit_logs_alter_table_denied PASSED
# test_audit_logs_drop_table_denied PASSED
# test_users_select_allowed PASSED
# test_users_insert_allowed PASSED
# test_users_update_allowed PASSED
# test_users_delete_allowed PASSED
# ... (similar for other tables)
# ========== 20+ passed in X.XXs ==========
```

**Pass criterion:** Exit code 0; all privilege tests passed

### 8.6 Database Audit: Role Privileges

**Requirement:** Database roles have correct privileges per privilege matrix

**Verification:**
```bash
psql -h localhost -U postgres -d sentinel -c "
  -- Verify sentinel_api has INSERT-only on audit_logs
  SELECT privilege_type 
  FROM information_schema.role_table_grants 
  WHERE table_name = 'audit_logs' AND grantee = 'sentinel_api'
  ORDER BY privilege_type;
"

# Expected:
#  privilege_type
# ----------------
#  INSERT
#  SELECT
# (NOT: UPDATE, DELETE, TRUNCATE, etc.)

# Verify sentinel_api has full privileges on users
psql -h localhost -U postgres -d sentinel -c "
  SELECT privilege_type 
  FROM information_schema.role_table_grants 
  WHERE table_name = 'users' AND grantee = 'sentinel_api'
  ORDER BY privilege_type;
"

# Expected:
#  privilege_type
# ----------------
#  DELETE
#  INSERT
#  SELECT
#  UPDATE
```

**Pass criterion:** audit_logs: INSERT, SELECT only; users: DELETE, INSERT, SELECT, UPDATE; all other tables: full privileges

### 8.7 Table Ownership Audit

**Requirement:** All tables owned by schema_owner

**Verification:**
```bash
psql -h localhost -U postgres -d sentinel -c "
  SELECT tablename, pg_catalog.pg_get_userbyid(relowner) as owner
  FROM pg_tables pt
  JOIN pg_class pc ON pt.tablename = pc.relname
  WHERE schemaname = 'public'
  ORDER BY tablename;
"

# Expected:
#  tablename      |    owner
# -----------------+--------------
#  analyses       | schema_owner
#  analyzers      | schema_owner
#  audit_logs     | schema_owner
#  digital_assets | schema_owner
#  refresh_tokens | schema_owner
#  reports        | schema_owner
#  uploads        | schema_owner
#  users          | schema_owner
```

**Pass criterion:** All 8 tables owned by schema_owner (not sentinel or postgres)

### 8.8 Completion Criteria Summary

| Criterion | Pass | Verification Command |
|-----------|------|----------------------|
| E4V.T2: 19/19 integration tests PASS | ✓ | pytest tests/integration/ -v |
| E4V.T3: MyPy --strict 0 errors | ✓ | mypy --strict app/ |
| E4V.T4: Compileall exit 0 | ✓ | python -m compileall app/ |
| E4V.T5: Concurrency tests 3/3 PASS | ✓ | pytest tests/integration/test_concurrency.py |
| Security boundary tests all PASS | ✓ | pytest tests/security/test_db_role_privileges.py |
| sentinel_api has INSERT-only on audit_logs | ✓ | psql information_schema query |
| All tables owned by schema_owner | ✓ | psql pg_tables query |

------------------------------------------------------------------------

## 9. Rollback & Disaster Recovery

### 9.1 Rollback Procedure (if implementation fails)

**Scenario:** Phase 2-6 implementation causes production issues

**Rollback steps:**

1. **Immediate action:** Revert to single-role architecture

```bash
# Connect as postgres superuser
psql -h prod-db -U postgres -d sentinel

# DROP the new roles (this will fail if objects owned by schema_owner)
-- First, reassign table ownership back to sentinel
DO $$
DECLARE
  tbl RECORD;
BEGIN
  FOR tbl IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE 'ALTER TABLE ' || quote_ident(tbl.tablename) || ' OWNER TO sentinel';
  END LOOP;
END $$;

-- Then drop schema_owner role
DROP ROLE IF EXISTS schema_owner;

-- sentinel_api can remain; it has same privileges as before
-- Or drop it too if completely reverting:
DROP ROLE IF EXISTS sentinel_api;
```

2. **Revert configuration:**
```bash
# Revert DATABASE_MIGRATION_URL to use sentinel
# Update .env:
DATABASE_MIGRATION_URL=postgresql://sentinel:sentinel@localhost:5432/sentinel

# Restart Alembic with old configuration (if migrations need to run)
```

3. **Restore application connections:**
```bash
# Revert DATABASE_URL to use sentinel (if changed)
# Restart API servers with old configuration
```

4. **Verification:**
```bash
# Verify tables owned by sentinel again
psql -c "SELECT tablename, pg_get_userbyid(relowner) FROM pg_tables WHERE schemaname = 'public';"

# Verify API connects successfully
curl http://localhost:8000/health
```

### 9.2 Disaster Recovery: Corrupted Role Definitions

**Scenario:** Roles accidentally dropped or privileges incorrectly granted

**Recovery:**

1. **From backup (preferred):**
```bash
# If database backup exists with role definitions
pg_restore -h prod-db -U postgres -d sentinel /backups/sentinel_backup.sql
```

2. **Manual re-provisioning:**
```bash
# Re-run bootstrap script
psql -h prod-db -U postgres -d sentinel -f backend/docker/bootstrap/create_roles.sql
```

3. **Verify recovery:**
```bash
pytest tests/security/test_db_role_privileges.py -v
# All tests should pass
```

### 9.3 Disaster Recovery: Audit Logs Accidentally Modified

**Scenario:** Security breach detected; audit_logs were UPDATE/DELETE'd despite privilege restrictions

**Likely causes:**
1. Privileges incorrectly granted (check Phase 5 tests)
2. Superuser account compromised (check access logs)
3. sentinel_api connected as postgres (check connection logs)

**Recovery:**

1. **Immediate containment:**
```bash
# REVOKE write privileges immediately
psql -h prod-db -U postgres -c "
  REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM PUBLIC;
  REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM sentinel_api;
"
```

2. **Audit investigation:**
```bash
# Check who modified audit_logs and when
psql -h prod-db -U postgres -d sentinel -c "
  SELECT pg_current_wal_lsn();  -- Get current WAL position
  -- Export WAL logs for forensic analysis
  -- Typically: /var/lib/postgresql/16/main/pg_wal/
"
```

3. **Restore from backup (if available):**
```bash
# If point-in-time recovery is needed, restore to pre-compromise timestamp
pg_basebackup -h prod-db -U postgres -D /recovery -R

# Or restore audit_logs table from backup
psql -h prod-db -U postgres < audit_logs_backup.sql
```

------------------------------------------------------------------------

## 10. Known Constraints & Assumptions

### 10.1 Constraints

1. **Alembic limitation:** Cannot easily run as different roles for different migrations
   - Mitigation: All migrations run as schema_owner (consistent identity)
   - Assumption: No migration needs application-level privileges

2. **PostgreSQL 13+ requirement for DEFAULT PRIVILEGES:**
   - If targeting older PostgreSQL, manual privilege grants needed for future tables
   - Current env: PostgreSQL 16 (alpine) in docker-compose ✓

3. **No ALTER ROLE during runtime:**
   - Role provisioning is one-time (bootstrap)
   - Runtime role changes require database restart or manual provisioning
   - Assumption: Roles don't change after provisioning

4. **Environment variables required:**
   - POSTGRESQL_SCHEMA_OWNER_PASSWORD and POSTGRESQL_SENTINEL_API_PASSWORD must be set
   - Fallback defaults provided for development only (not production-safe)

### 10.2 Assumptions

1. **PostgreSQL superuser available for role provisioning:**
   - Local dev: postgres user (default password) ✓
   - CI/CD: Provisioned by GitHub Actions or similar ✓
   - Production: DBA or infrastructure team provisioning ✓

2. **No concurrent role provisioning:**
   - Assumption: Bootstrap runs once per environment
   - No race conditions between multiple bootstrap attempts
   - Mitigation: Idempotent SQL script (DROP IF EXISTS)

3. **All tables use UUID primary keys:**
   - Current schema: gen_random_uuid() for all IDs ✓
   - No sequence-based auto-increment (avoids SEQUENCE USAGE privilege complexity)
   - If sequences added: Update bootstrap to grant USAGE privilege

4. **Application code does not attempt DDL:**
   - Assumption: Alembic handles all DDL
   - sentinel_api role lacks ALTER TABLE privilege (intentional)
   - If dynamic DDL needed: Create separate role with DDL privileges

5. **Audit logs table never truncated or altered by app:**
   - Assumption: audit_logs is append-only from application perspective
   - DBA can still ALTER TABLE (owns schema_owner role)
   - Tests verify database-level enforcement

### 10.3 Future Considerations

1. **Role-based access control (RBAC):**
   - Current: Two roles (schema_owner, sentinel_api)
   - Future: Add sentinel_worker role for background jobs (different privileges)
   - Implementation: Add new role to bootstrap script; update privilege matrix

2. **Dynamic privilege management:**
   - Current: Static privilege grants via bootstrap
   - Future: Privilege API (if needed) for runtime role management
   - Design: Would require new service; significant complexity

3. **Audit of role changes:**
   - Current: No audit table for role modifications
   - Future: pgaudit extension or role change logging
   - Design: Would require extension installation + configuration

4. **Encryption at rest:**
   - Current: PostgreSQL encryption at rest (not in scope for this spec)
   - Future: Add pgcrypto or TDE for sensitive columns
   - Design: Separate from role provisioning

------------------------------------------------------------------------

## Appendix: Quick Reference

### Environment Variables

| Variable | Purpose | Example Value | Secret |
|----------|---------|----------------|--------|
| POSTGRESQL_SCHEMA_OWNER_PASSWORD | schema_owner role password | `xyz123...` | ✓ Yes |
| POSTGRESQL_SENTINEL_API_PASSWORD | sentinel_api role password | `abc456...` | ✓ Yes |
| DATABASE_URL | App connection (sentinel_api) | `postgresql+asyncpg://...` | ✓ Yes |
| DATABASE_MIGRATION_URL | Migration connection (schema_owner) | `postgresql://...` | ✓ Yes |

### Files Created/Modified

| Phase | File | Action | Type |
|-------|------|--------|------|
| 2 | `backend/docker/bootstrap/create_roles.sql` | Create | SQL script |
| 3 | `docker-compose.yml` | Modify | Docker Compose |
| 3 | `.env.example` | Modify | Config template |
| 4 | `backend/migrations/env.py` | Modify (docs) | Alembic config |
| 5 | `backend/tests/security/test_db_role_privileges.py` | Create | Python test |
| 6 | `docs/12-PostgreSQL-Role-Architecture.md` | Create | Markdown |
| 6 | `ROLE_PROVISIONING_README.md` | Create | Markdown |
| 6 | `README.md` | Modify | Markdown |

### Privilege Matrix Quick Reference

| Table | INSERT | SELECT | UPDATE | DELETE | TRUNCATE | ALTER TABLE |
|-------|--------|--------|--------|--------|----------|-------------|
| audit_logs | ✓ (sentinel_api) | ✓ (sentinel_api) | ✗ | ✗ | ✗ | ✗ |
| users | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| refresh_tokens | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| uploads | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| digital_assets | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| analyses | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| reports | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| analyzers | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |

✓ = Granted to sentinel_api role
✗ = Not granted to sentinel_api role (denied, unless owner or superuser)

------------------------------------------------------------------------

## Document End

**Version:** 1.0  
**Last Updated:** 2025  
**Status:** Implementation Ready  
**Next Steps:** Begin Phase 2 (Bootstrap SQL Script implementation)

