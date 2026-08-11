import sys
sys.path.insert(0, '.')

# Try to run the auth test directly
import pytest

exit_code = pytest.main([
    'tests/integration/test_auth_routes.py',
    '-v',
    '--tb=short'
])

print(f"\nTest exit code: {exit_code}")
sys.exit(exit_code)
