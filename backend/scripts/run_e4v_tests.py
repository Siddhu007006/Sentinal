#!/usr/bin/env python
"""
E4V Regression Test Suite Runner
Runs pytest with proper environment configuration for role provisioning tests.
"""
import os
import sys
import subprocess

# Set environment variables
os.environ["DATABASE_URL"] = "postgresql+asyncpg://sentinel_api:sentinel_api_password@localhost:5432/sentinel_test"
os.environ["DATABASE_MIGRATION_URL"] = "postgresql://schema_owner:schema_owner_password@localhost:5432/sentinel_test"
os.environ["ENVIRONMENT"] = "test"

# Run pytest
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/integration/", "-v", "--tb=short"],
    cwd=os.path.dirname(os.path.abspath(__file__)),
)

sys.exit(result.returncode)
