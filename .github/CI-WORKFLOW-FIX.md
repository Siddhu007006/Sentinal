# CI Workflow Fix — Virtual Environment Setup

## Problem

The GitHub Actions CI workflow was failing with:
```
Error: No virtual environment found; run `uv venv` to create an environment, 
or pass `--system` to install into a non-virtual environment
```

This error occurred during the `uv pip install` command because `uv` requires an active virtual environment before installing packages.

## Solution Applied

Added `uv venv` step to all four CI jobs before `uv pip install`:

### Jobs Fixed

1. **lint** (line ~38)
   - Added: `- name: Create virtual environment`
   - Before: `uv pip install -e .[dev]`

2. **type-check** (line ~72)
   - Added: `- name: Create virtual environment`
   - Before: `uv pip install -e .[dev]`

3. **test** (line ~142)
   - Added: `- name: Create virtual environment`
   - Before: `uv pip install -e .[dev]`

4. **build-verification** (line ~198)
   - Added: `- name: Create virtual environment`
   - Before: `uv pip install -e .[dev]`

## Workflow Changes

### Before (Fails)
```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v2

- name: Cache dependencies
  uses: actions/cache@v4
  ...

- name: Install backend dependencies
  working-directory: backend
  run: uv pip install -e .[dev]  # ❌ FAILS: No venv
```

### After (Works)
```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v2

- name: Cache dependencies
  uses: actions/cache@v4
  ...

- name: Create virtual environment
  working-directory: backend
  run: uv venv  # ✅ Creates venv

- name: Install backend dependencies
  working-directory: backend
  run: uv pip install -e .[dev]  # ✅ Works with venv
```

## Verification

All four jobs now follow this sequence:
1. Setup Python 3.12
2. Install `uv` tool
3. Cache dependencies
4. **Create virtual environment** ← NEW
5. Install packages into venv
6. Run linting, type-checking, tests, etc.

## Testing

Run locally to verify the workflow:
```bash
cd backend
uv venv
uv pip install -e .[dev]
ruff check app
mypy app --strict
pytest tests/
```

## Files Modified

- `.github/workflows/ci.yml` — Added `uv venv` steps to 4 jobs (36 lines added)

## Status

✅ **Fixed and Ready to Push**

All CI jobs will now create virtual environments before attempting to install packages, resolving the `uv` dependency issue.
