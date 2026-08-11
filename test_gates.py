import subprocess
import sys
import os

os.chdir("backend")

# Gate 2
print("\nGATE 2: Auth Tests")
r = subprocess.run([sys.executable, "-m", "pytest", "tests/integration/test_auth_routes.py", "-q"], capture_output=True, text=True)
g2 = r.returncode == 0
print("PASS" if g2 else "FAIL")

# Gate 3  
print("\nGATE 3: MyPy")
r = subprocess.run([sys.executable, "-m", "mypy", "--strict", "app/"], capture_output=True, text=True)
g3 = r.returncode == 0 and "no issues" in r.stdout
print("PASS" if g3 else "FAIL")

# Gate 4
print("\nGATE 4: Compile")
r = subprocess.run([sys.executable, "-m", "compileall", "app/", "-q"], capture_output=True, text=True)
g4 = r.returncode == 0
print("PASS" if g4 else "FAIL")

# Gate 5
print("\nGATE 5: Concurrency")
r = subprocess.run([sys.executable, "-m", "pytest", "tests/integration/test_token_concurrency_fix.py", "-q"], capture_output=True, text=True)
g5 = r.returncode == 0
print("PASS" if g5 else "FAIL")

print(f"\nAll pass: {all([g2, g3, g4, g5])}")
