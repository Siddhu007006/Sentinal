# CI/CD Troubleshooting Guide

## What Happened

Your PR ran CI/CD checks and **5 checks failed**. This guide will help you identify and fix the issues.

---

## Step 1: Identify Which Checks Failed

### Go to GitHub Actions

1. Visit: https://github.com/Siddhu007006/sentinal/actions
2. Click on the **failed workflow run** (latest)
3. You'll see which jobs failed:

```
Jobs that typically fail:
- lint (Ruff formatting)
- type-check (MyPy static typing)
- test (Pytest)
- build-verification (Project structure)
- status-check (Aggregation of above)
```

---

## Step 2: Read the Error Messages

### Click on Each Failed Job

1. Click the job name (e.g., "lint" or "type-check")
2. Expand to see the error output
3. Look for lines starting with:
   - `Error:`
   - `FAILED`
   - `ERROR:`
   - `FileNotFoundError:`
   - `ImportError:`

---

## Common CI Failures & Fixes

### ❌ Issue 1: Import Error in Analysis Model

**Error Message:**
```
ImportError: cannot import name 'Analysis' from 'app.models'
ModuleNotFoundError: No module named 'app.models.analysis'
```

**Fix:**
```bash
cd backend
# Verify import works locally
python -c "from app.models.analysis import Analysis; print('OK')"

# Check __init__.py exports it
cat app/models/__init__.py
# Should contain: from .analysis import Analysis, AnalysisStatus
```

**Solution:**
Update `backend/app/models/__init__.py`:
```python
from .analysis import Analysis, AnalysisStatus
from .user import User, UserRole
# ... other imports
```

---

### ❌ Issue 2: Ruff Linting Failures

**Error Message:**
```
error: 1 error left in --fix mode: cannot fix line-length [E501]
```

**Fix Locally:**
```bash
cd backend
ruff check app/models/analysis.py --fix
```

**Common Issues:**
- Line too long (> 88 chars)
- Unused imports
- Formatting issues

---

### ❌ Issue 3: MyPy Type Checking Failures

**Error Message:**
```
app/models/analysis.py:XX: error: [assignment] ...
app/models/analysis.py:XX: error: [arg-type] ...
```

**Fix Locally:**
```bash
cd backend
mypy app/models/analysis.py --strict
```

**Common Issues:**
- Missing type hints
- Type mismatches
- Optional types not handled

---

### ❌ Issue 4: Test Failures

**Error Message:**
```
FAILED backend/tests/unit/test_analysis_model.py::test_xxx
ERROR at setup of test_xxx
```

**Fix Locally:**
```bash
cd backend
pytest tests/unit/test_analysis_model.py -v
# or
pytest tests/integration/test_analysis_migration.py -v
```

**Common Issues:**
- Database connection (integration tests)
- Missing fixtures
- Import errors

---

### ❌ Issue 5: Build Verification Failures

**Error Message:**
```
ModuleNotFoundError: No module named 'app.main'
ImportError: cannot import 'Settings'
```

**Fix Locally:**
```bash
cd backend
python -c "from app.main import create_app; print('OK')"
python -c "from app.core.settings import Settings; print('OK')"
python -m compileall app/
```

---

## Step 3: Fix Issues Locally

### 1. Identify the error
- Read the GitHub Actions log message

### 2. Reproduce locally
```bash
cd backend

# Try to import the module
python -c "from app.models.analysis import Analysis"

# Run linting
ruff check app

# Run type checking
mypy app --strict

# Run tests
pytest tests/
```

### 3. Fix the issue
- Update the code
- Test locally again

### 4. Commit and push
```bash
git add -A
git commit -m "fix: resolve CI/CD failures"
git push
```

### 5. GitHub reruns checks automatically ✅

---

## Quick Diagnostic Commands

Run these locally to diagnose issues:

```bash
cd backend

# Check Python version
python --version
# Should be 3.12.x

# Check if packages installed
pip list | grep -E "sqlalchemy|alembic|pytest"

# Test imports
python -c "from app.models.analysis import Analysis, AnalysisStatus; print('✅ OK')"

# Test app factory
python -c "from app.main import create_app; app = create_app(); print('✅ OK')"

# Run linting
ruff check app --show-fixes

# Run type checking
mypy app --strict

# Run unit tests
pytest tests/unit/test_analysis_model.py -v

# Compile all modules
python -m compileall app/
```

---

## Common Missing Exports

If you see import errors, check these files:

### `backend/app/models/__init__.py`

Should have:
```python
from .analysis import Analysis, AnalysisStatus
from .digital_asset import DigitalAsset, AssetType
from .upload import Upload
from .user import User, UserRole

__all__ = [
    "Analysis",
    "AnalysisStatus",
    "DigitalAsset",
    "AssetType",
    "Upload",
    "User",
    "UserRole",
]
```

### `backend/app/__init__.py`

Should have:
```python
from .main import create_app

__all__ = ["create_app"]
```

---

## GitHub Actions Logs

### How to Read the Logs

1. Go to: https://github.com/Siddhu007006/sentinal/actions
2. Click the failed workflow
3. Click the failed job name
4. Scroll down to see the error
5. Look for these indicators:
   - `❌` = Failed step
   - `✅` = Passed step
   - Error text appears in red

### Re-run Failed Checks

You can re-run checks from GitHub:

1. Go to Actions tab
2. Click the workflow run
3. Click **"Re-run failed jobs"** button
4. Wait for workflow to complete

---

## Step-by-Step Fix Process

### 1. Check GitHub Actions for Error
```
Actions tab → Find PR workflow → Click failed job → Read error
```

### 2. Reproduce Locally
```bash
cd backend
# Run the failing command (e.g., ruff, mypy, pytest)
```

### 3. Fix the Issue
```bash
# Edit the file with the error
# Run the command again to verify fix
```

### 4. Push the Fix
```bash
git add -A
git commit -m "fix: resolve [issue]"
git push
```

### 5. Watch GitHub Actions
```
Checks automatically re-run when you push
Watch them pass one by one ✅
```

---

## If You're Stuck

### Create a Diagnostic Report

Run this script locally:

```bash
cd backend

echo "=== Python Version ==="
python --version

echo "=== Imports ==="
python -c "from app.models.analysis import Analysis; print('✅ Analysis OK')" 2>&1

echo "=== Ruff ==="
ruff check app 2>&1 | head -20

echo "=== MyPy ==="
mypy app --strict 2>&1 | head -20

echo "=== Tests ==="
pytest tests/unit/test_analysis_model.py::test_analysis_instantiation -v 2>&1 | head -20

echo "=== Compile Check ==="
python -m compileall app/ 2>&1
```

Share this output and we can diagnose the exact issue.

---

## Most Common Issue: Missing __init__.py Exports

95% of CI failures are due to **missing imports in `__init__.py`**.

### Check Your Exports

```bash
# Does app/models/__init__.py export Analysis?
grep -n "Analysis" backend/app/models/__init__.py

# If not found, add it:
echo "from .analysis import Analysis, AnalysisStatus" >> backend/app/models/__init__.py
```

---

## Summary

| Step | Command | Expected Output |
|---|---|---|
| 1 | Check GitHub Actions | Find error message |
| 2 | `python -c "from app.models.analysis import Analysis"` | No error |
| 3 | `ruff check app` | No errors |
| 4 | `mypy app --strict` | No errors |
| 5 | `pytest tests/` | All pass |
| 6 | `git push` | Auto re-runs checks |

Once all ✅ pass locally, they should pass on GitHub too.

---

## Next Steps

1. **Check GitHub Actions** for the specific error
2. **Tell me the error message** (copy from Actions tab)
3. **I'll provide the exact fix**

Or run the diagnostic commands above and share the output. 🔧
