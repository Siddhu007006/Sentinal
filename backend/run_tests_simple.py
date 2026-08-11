import subprocess
import json

result = subprocess.run(
    ["python", "-m", "pytest", 
     "tests/integration/test_auth_routes.py", 
     "-v", "--tb=short", "--json-report", "--json-report-file=report.json"],
    capture_output=False
)

exit(result.returncode)
