-- PostgreSQL Post-Migration Permission Fix: audit_logs SELECT+INSERT only
-- Purpose: Restrict sentinel_api to SELECT+INSERT on audit_logs (append-only)
-- Idempotency: REVOKE/GRANT operations are safe to run multiple times

-- Verify audit_logs table exists
SELECT 'Checking audit_logs table...' as step;
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public' AND tablename = 'audit_logs';

-- Revoke all existing privileges from sentinel_api
REVOKE ALL PRIVILEGES ON TABLE public.audit_logs FROM sentinel_api;

-- Grant SELECT and INSERT only (append-only for audit records)
GRANT SELECT ON TABLE public.audit_logs TO sentinel_api;
GRANT INSERT ON TABLE public.audit_logs TO sentinel_api;

-- Verify the result: should show exactly 2 privileges
SELECT 'Verification: sentinel_api privileges on audit_logs' as step;
SELECT grantee, privilege_type 
FROM information_schema.role_table_grants
WHERE table_schema = 'public' AND table_name = 'audit_logs' AND grantee = 'sentinel_api'
ORDER BY privilege_type;

-- Verify no forbidden privileges exist
SELECT 'Checking for forbidden privileges...' as step;
SELECT COUNT(*) as forbidden_count
FROM information_schema.role_table_grants
WHERE table_schema = 'public' AND table_name = 'audit_logs' AND grantee = 'sentinel_api'
AND privilege_type IN ('UPDATE', 'DELETE', 'TRUNCATE');