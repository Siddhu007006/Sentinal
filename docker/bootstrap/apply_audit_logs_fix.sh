#!/bin/sh
set -e

echo ""
echo "=========================================="
echo "Post-Migration Permission Fix"
echo "=========================================="
echo ""

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
ATTEMPTS=0
until pg_isready -h postgres -U postgres >/dev/null 2>&1; do
  if [ $ATTEMPTS -ge 30 ]; then
    echo "ERROR: PostgreSQL did not become ready"
    exit 1
  fi
  sleep 1
  ATTEMPTS=$((ATTEMPTS + 1))
done
echo "OK: PostgreSQL is ready"
echo ""

# Wait for Alembic by checking alembic_version existence
echo "Waiting for Alembic migrations..."
ATTEMPTS=0
MAX_ATTEMPTS=60
while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
  # Try to access alembic_version - if it fails, migrations not done
  if psql -h postgres -U postgres -d sentinel -c "SELECT 1 FROM alembic_version LIMIT 1" >/dev/null 2>&1; then
    echo "OK: Alembic migrations completed"
    break
  fi
  
  sleep 2
  ATTEMPTS=$((ATTEMPTS + 2))
done

if [ $ATTEMPTS -ge $MAX_ATTEMPTS ]; then
  echo "ERROR: Timeout waiting for Alembic migrations"
  exit 1
fi
echo ""

# Apply post-migration permission fix
echo "Applying audit_logs permission fix..."
if ! psql -h postgres -U postgres -d sentinel -v ON_ERROR_STOP=1 \
   -f /tmp/fix_audit_logs_post_migration.sql >/dev/null 2>&1; then
  echo "ERROR: SQL execution failed"
  psql -h postgres -U postgres -d sentinel -f /tmp/fix_audit_logs_post_migration.sql
  exit 1
fi
echo "OK: Fix applied"
echo ""

# Verify 1: exactly 2 privileges
echo "Verifying permissions..."
COUNT=$(psql -h postgres -U postgres -d sentinel -t -c \
  "SELECT COUNT(*) FROM information_schema.role_table_grants \
   WHERE table_schema='public' AND table_name='audit_logs' AND grantee='sentinel_api'" 2>/dev/null | tr -d ' ')

if [ "$COUNT" != "2" ]; then
  echo "ERROR: Wrong privilege count (expected 2, got $COUNT)"
  exit 1
fi
echo "OK: Exactly 2 privileges"

# Verify 2: no forbidden privileges
FORBIDDEN=$(psql -h postgres -U postgres -d sentinel -t -c \
  "SELECT COUNT(*) FROM information_schema.role_table_grants \
   WHERE table_schema='public' AND table_name='audit_logs' AND grantee='sentinel_api' \
   AND privilege_type IN ('UPDATE','DELETE','TRUNCATE')" 2>/dev/null | tr -d ' ')

if [ "$FORBIDDEN" != "0" ]; then
  echo "ERROR: Forbidden privileges found"
  exit 1
fi
echo "OK: No UPDATE/DELETE/TRUNCATE"

# Show final state
echo ""
echo "Final permissions on audit_logs:"
psql -h postgres -U postgres -d sentinel -c \
  "SELECT grantee, privilege_type FROM information_schema.role_table_grants \
   WHERE table_schema='public' AND table_name='audit_logs' \
   ORDER BY grantee, privilege_type;"

echo ""
echo "=========================================="
echo "SUCCESS: audit_logs is SELECT+INSERT only"
echo "=========================================="
echo ""
exit 0