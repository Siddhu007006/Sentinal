import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", 
     "tests/integration/test_auth_routes.py", "-v", "--tb=short"],
    capture_output=True,
    text=True
)

print("STDOUT:")
print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
print("\nSTDERR:")
print(result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr)
print(f"\nExit code: {result.returncode}")
