-- ===========================================================================
-- PostgreSQL Role Provisioning Bootstrap Script
-- ===========================================================================
--
-- Purpose:
--   Create database roles and establish privilege boundaries BEFORE Alembic
--   migrations execute. This script is IDEMPOTENT and can safely run multiple
--   times without destroying data or active sessions.
--
-- Architecture:
--   - schema_owner (LOGIN): DDL/migration identity; owns all application tables
--   - sentinel_api (LOGIN): Application runtime identity; restricted privileges
--
-- Security Model:
--   Application runtime MUST use sentinel_api credentials (via DATABASE_URL).
--   Alembic migrations run as schema_owner (via DATABASE_MIGRATION_URL).
--   Database enforces privilege boundaries: sentinel_api cannot modify
--   audit_logs structure or contents (INSERT only).
--
-- Idempotency Guarantee:
--   This script is SAFE to run multiple times without data loss or errors:
--   - Roles are created IF NOT EXISTS (not dropped)
--   - Existing roles keep their passwords unchanged
--   - Table ownership is transferred safely (idempotent ALTER TABLE)
--   - Privilege GRANTs are idempotent (re-granting same privilege is safe)
--   - Privilege REVOKEs only occur if table exists (checked first)
--
-- Execution Order:
--   1. Create roles (if not exist)
--   2. Transfer table ownership (after roles exist)
--   3. Grant default privileges (for future Alembic migrations)
--   4. Grant table-specific privileges (for existing tables if created)
--   5. Grant audit_logs INSERT-ONLY (only after audit_logs table exists)
--   6. Report verification
--
-- Environment Variables (required at execution time):
--   POSTGRESQL_SCHEMA_OWNER_PASSWORD   - Password for schema_owner role
--   POSTGRESQL_SENTINEL_API_PASSWORD   - Password for sentinel_api role
--
-- Reference:
--   docs/04-Database-Design.md §11.1 (Least Privilege)
--   ROLE_PROVISIONING_IMPLEMENTATION.md §2 (Phase 2)
--
-- ===========================================================================


-- ===========================================================================
-- Step 1: Create schema_owner Role (DDL/Migration Identity) — IDEMPOTENT
-- ===========================================================================

\echo ''
\echo 'Provisioning schema_owner role (DDL/migration identity)...'

-- Only create if role does not exist
-- DO NOT use DROP ROLE (destructive on reruns)
DO $$
BEGIN
    -- Check if role exists; if not, create it
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'schema_owner') THEN
        CREATE ROLE schema_owner
            WITH
            LOGIN
            PASSWORD 'POSTGRESQL_SCHEMA_OWNER_PASSWORD'
            CREATEDB
            CREATEROLE
            NOSUPERUSER
            NOINHERIT;
        RAISE NOTICE 'schema_owner role created (new)';
    ELSE
        RAISE NOTICE 'schema_owner role already exists (skipped creation)';
    END IF;
END $$;

-- Update comment (idempotent)
COMMENT ON ROLE schema_owner IS 'DDL/migration identity. Owns application schema and tables. Used by Alembic only. NEVER by application runtime.';

\echo 'schema_owner role provisioned.'


-- ===========================================================================
-- Step 2: Create sentinel_api Role (Application Runtime Identity) — IDEMPOTENT
-- ===========================================================================

\echo ''
\echo 'Provisioning sentinel_api role (application runtime identity)...'

-- Only create if role does not exist
-- DO NOT use DROP ROLE (destructive on reruns)
DO $$
BEGIN
    -- Check if role exists; if not, create it
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sentinel_api') THEN
        CREATE ROLE sentinel_api
            WITH
            LOGIN
            PASSWORD 'POSTGRESQL_SENTINEL_API_PASSWORD'
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT;
        RAISE NOTICE 'sentinel_api role created (new)';
    ELSE
        RAISE NOTICE 'sentinel_api role already exists (skipped creation)';
    END IF;
END $$;

-- Update comment (idempotent)
COMMENT ON ROLE sentinel_api IS 'Application runtime identity. Restricted privileges on tables. NEVER grants DDL or schema ownership.';

\echo 'sentinel_api role provisioned.'


-- ===========================================================================
-- Step 3: Transfer Table Ownership to schema_owner (IDEMPOTENT)
-- ===========================================================================

\echo ''
\echo 'Transferring table ownership to schema_owner (if needed)...'

-- Only transfer if tables exist and are not already owned by schema_owner
DO $$
DECLARE
    tbl RECORD;
    transfer_count INTEGER := 0;
BEGIN
    FOR tbl IN 
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' AND tableowner != 'schema_owner'
    LOOP
        EXECUTE 'ALTER TABLE public.' || quote_ident(tbl.tablename) || ' OWNER TO schema_owner';
        transfer_count := transfer_count + 1;
    END LOOP;
    
    IF transfer_count > 0 THEN
        RAISE NOTICE 'Transferred ownership: % tables', transfer_count;
    ELSE
        RAISE NOTICE 'Table ownership: no changes needed (already owned by schema_owner or no tables exist yet)';
    END IF;
END $$;

\echo 'Table ownership transfer complete.'


-- ===========================================================================
-- Step 4: Grant Default Privileges for Future Tables (IDEMPOTENT)
-- ===========================================================================
--
-- IMPORTANT: audit_logs requires special handling (INSERT-ONLY)
--
-- DEFAULT PRIVILEGES grants SELECT, INSERT, UPDATE, DELETE to all future
-- tables created by schema_owner. This is correct for most application
-- tables but NOT correct for audit_logs, which must be immutable.
--
-- PostgreSQL DEFAULT PRIVILEGES cannot express conditional rules like:
-- "grant full DML to all tables EXCEPT audit_logs, which gets INSERT-only".
--
-- Solution: This script grants full DML as DEFAULT. Then, AFTER Alembic
-- creates audit_logs, a separate post-migration script (fix_audit_logs_post_migration.sql)
-- fixes the permissions by revoking UPDATE/DELETE from sentinel_api.
--
-- Order of Execution:
--   1. Bootstrap (THIS SCRIPT): Set DEFAULT PRIVILEGES for full DML
--   2. Alembic migrations: Create all tables including audit_logs
--   3. Post-migration fix: Run fix_audit_logs_post_migration.sql
--      to restrict sentinel_api to INSERT-only on audit_logs
--
-- This ensures:
--   ✓ Application tables get full DML from DEFAULT PRIVILEGES
--   ✓ audit_logs is created with full DML (inherited from defaults)
--   ✓ audit_logs is then restricted to INSERT-only by post-migration script
--   ✓ Immutability is guaranteed: sentinel_api cannot UPDATE/DELETE audit records
--
-- See: docker/bootstrap/fix_audit_logs_post_migration.sql
--      for the post-migration permission fix script
--

\echo ''
\echo 'Configuring default privileges for future tables...'

-- These are idempotent: re-granting same privilege to same role is safe
ALTER DEFAULT PRIVILEGES FOR USER schema_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sentinel_api;

ALTER DEFAULT PRIVILEGES FOR USER schema_owner IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO sentinel_api;

ALTER DEFAULT PRIVILEGES FOR USER schema_owner IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO sentinel_api;

\echo 'Default privileges configured.'


-- ===========================================================================
-- Step 5: Grant Schema-Level Privileges (IDEMPOTENT)
-- ===========================================================================

\echo ''
\echo 'Granting schema-level privileges...'

-- These are idempotent: re-granting same privilege to same role is safe
GRANT USAGE ON SCHEMA public TO schema_owner;
GRANT CREATE ON SCHEMA public TO schema_owner;
GRANT USAGE ON SCHEMA public TO sentinel_api;

\echo 'Schema privileges granted.'


-- ===========================================================================
-- Step 6: Grant Table-Specific Privileges to sentinel_api (IDEMPOTENT)
-- ===========================================================================

\echo ''
\echo 'Configuring table-specific privileges for sentinel_api...'

-- Grant full DML to all application tables (idempotent)
-- Silently skip tables that don''t exist yet (they will get default privileges from Step 4)
DO $$
DECLARE
    tbl RECORD;
    grant_count INTEGER := 0;
BEGIN
    FOR tbl IN (
        SELECT 'users' as tablename UNION ALL
        SELECT 'refresh_tokens' UNION ALL
        SELECT 'uploads' UNION ALL
        SELECT 'digital_assets' UNION ALL
        SELECT 'analyses' UNION ALL
        SELECT 'reports' UNION ALL
        SELECT 'analyzers'
    )
    LOOP
        BEGIN
            -- Re-granting same privileges is safe (idempotent)
            EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.' || quote_ident(tbl.tablename) || ' TO sentinel_api';
            grant_count := grant_count + 1;
        EXCEPTION WHEN undefined_table THEN
            -- Table doesn''t exist yet; default privileges will apply when created
            NULL;
        END;
    END LOOP;
    
    RAISE NOTICE 'Granted DML privileges: % tables', grant_count;
END $$;

\echo 'Full DML privileges configured for application tables.'


-- ===========================================================================
-- Step 7: Grant RESTRICTED Privileges on audit_logs (INSERT-ONLY)
-- ===========================================================================

\echo ''
\echo 'Configuring RESTRICTED privileges for audit_logs (INSERT-ONLY)...'

-- audit_logs is special: sentinel_api gets INSERT-only (append-only audit trail)
-- Only configure if table exists; otherwise default privileges apply
DO $$
BEGIN
    -- Check if audit_logs table exists
    IF EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'audit_logs'
    ) THEN
        -- Table exists; ensure sentinel_api has INSERT-only privileges
        
        -- First, revoke all privileges from PUBLIC (security)
        REVOKE ALL PRIVILEGES ON TABLE public.audit_logs FROM PUBLIC;
        
        -- Then, ensure sentinel_api has ONLY SELECT and INSERT
        -- (REVOKE first to ensure clean state; GRANT is idempotent)
        REVOKE ALL PRIVILEGES ON TABLE public.audit_logs FROM sentinel_api;
        GRANT SELECT ON TABLE public.audit_logs TO sentinel_api;
        GRANT INSERT ON TABLE public.audit_logs TO sentinel_api;
        
        RAISE NOTICE 'audit_logs privileges configured: sentinel_api → SELECT, INSERT (immutability enforced)';
    ELSE
        RAISE NOTICE 'audit_logs table does not exist yet; default privileges will apply when created by Alembic';
    END IF;
END $$;

\echo 'audit_logs privilege configuration complete.'


-- ===========================================================================
-- Step 8: Verification Report
-- ===========================================================================

\echo ''
\echo '===== PROVISIONING VERIFICATION REPORT ====='
\echo ''

\echo 'Roles status:'
SELECT rolname, rolcanlogin, rolcreatedb, rolcreaterole, rolsuper
    FROM pg_roles
    WHERE rolname IN ('schema_owner', 'sentinel_api')
    ORDER BY rolname;

\echo ''
\echo 'Tables in public schema:'
SELECT 
    pt.tablename,
    pg_catalog.pg_get_userbyid(pc.relowner) as owner
FROM pg_tables pt
JOIN pg_class pc ON pt.tablename = pc.relname AND pt.schemaname = 'public'
WHERE pt.schemaname = 'public'
ORDER BY pt.tablename;

\echo ''
\echo 'Privileges on audit_logs (if table exists):'
SELECT grantee, privilege_type
    FROM information_schema.role_table_grants
    WHERE table_name = 'audit_logs' AND table_schema = 'public'
    ORDER BY grantee, privilege_type;

\echo ''
\echo 'Privileges on users (sample):'
SELECT grantee, privilege_type
    FROM information_schema.role_table_grants
    WHERE table_name = 'users' AND table_schema = 'public'
    ORDER BY grantee, privilege_type;

\echo ''
\echo '===== PROVISIONING COMPLETE ====='
\echo ''
