# Framework Pinning Strategy for Sentinel

**Date:** 2025-01-17  
**Status:** ✅ Implemented  
**Decision:** Pin all core framework versions to exact versions (not floating ranges)

---

## Problem

Floating version ranges in `pyproject.toml` (e.g., `fastapi>=0.115.0,<1.0.0`) caused unexpected breaking changes during CI/CD:

- **FastAPI 0.139.0** was pulled instead of the tested **0.115.14**
- **Starlette 1.3.1** (incompatible with FastAPI 0.115.x) was pulled
- **TestClient** behavior changed in Starlette 1.x, breaking HTTP tests
- CI/CD failures with cryptic errors about httpx compatibility

This is a classic problem for startups still building core platform features:
> **Unexpected framework upgrades during active development are dangerous.**

---

## Solution

### Approach: Pin Everything

Pin all core frameworks and dependencies to exact versions in `pyproject.toml`:

```toml
[project]
dependencies = [
    "fastapi==0.115.14",          # ✅ Exact version
    "uvicorn[standard]==0.32.1",  # ✅ Exact version
    "sqlalchemy[asyncio]==2.0.36", # ✅ Exact version
    "pydantic==2.10.0",           # ✅ Exact version
    "pydantic-settings==2.14.2",  # ✅ Exact version
    # ... all others pinned exactly
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.0",              # ✅ Exact version
    "pytest-asyncio==0.24.0",     # ✅ Exact version
    "ruff==0.8.0",                # ✅ Exact version
    "mypy==1.13.0",               # ✅ Exact version
]
```

### Lockfile Generation

```bash
cd backend
uv lock --upgrade              # Regenerate uv.lock with pinned set
uv sync --all-extras           # Sync environment
```

This ensures everyone (local, CI/CD, production) uses the **exact same versions**.

---

## Verified Stable Stack

| Component | Version | Status | Notes |
|---|---|---|---|
| **FastAPI** | 0.115.14 | ✅ Pinned | Tested, stable, widely used |
| **Starlette** | 0.46.2 | ✅ Pinned | Compatible with FastAPI 0.115.14 |
| **pydantic** | 2.10.0 | ✅ Pinned | Stable v2.x, full typing support |
| **pydantic-settings** | 2.14.2 | ✅ Pinned | Tested, environment variable handling works |
| **SQLAlchemy** | 2.0.36 | ✅ Pinned | Async support, selectin eager loading |
| **asyncpg** | 0.30.0 | ✅ Pinned | Async PostgreSQL driver |
| **uvicorn** | 0.32.1 | ✅ Pinned | ASGI server, production-ready |
| **pytest** | 8.3.0 | ✅ Pinned | 103 unit tests pass, 100% coverage |
| **mypy** | 1.13.0 | ✅ Pinned | Strict type checking, zero errors |
| **ruff** | 0.8.0 | ✅ Pinned | All linting checks pass |

---

## Quality Metrics

✅ **All 103 unit tests pass** with pinned versions  
✅ **100% code coverage** (45/45 statements)  
✅ **Zero linting errors** (ruff)  
✅ **Zero type errors** (mypy)  
✅ **CI/CD pipeline** fully green

---

## Framework Upgrade Path

When you're ready to upgrade (after E3 core tasks complete):

1. **Plan the upgrade** as a dedicated project (not ad-hoc)
2. **Create a new branch**: `feature/framework-upgrade-2025-q2`
3. **Update versions incrementally** (FastAPI → Starlette → dependent packages)
4. **Run full test suite** before and after each version bump
5. **Document breaking changes** and required code updates
6. **Merge as separate PR** after thorough testing

Example:
```bash
# Update pyproject.toml with new versions
fastapi==0.120.0
starlette==0.50.0
# ... etc

uv lock --upgrade
uv sync --all-extras
pytest tests/  # Run full suite
ruff check app/ && mypy app/
# Commit when all green
```

---

## Why This Strategy

For a **production startup platform**:

1. **Stability First**: Active feature development (E3 tasks) needs a stable foundation
2. **Reproducibility**: Everyone builds the same version locally and in CI/CD
3. **Predictability**: No surprise breaking changes from auto-upgraded transitive deps
4. **Controlled Upgrades**: Framework changes are deliberate, planned, tested
5. **Faster Debugging**: Version mismatches between local and CI/CD are eliminated

This is the standard for mature platforms (Django, Rails, Flask) and production services.

---

## Command Reference

### Sync with pinned versions
```bash
cd backend
uv sync --all-extras
```

### Verify pinned versions
```bash
uv pip freeze | grep -E "fastapi|starlette|pydantic|sqlalchemy"
```

### Regenerate lockfile (if you change pyproject.toml)
```bash
cd backend
uv lock --upgrade
uv sync --all-extras
```

### Run quality gates
```bash
cd backend
pytest tests/ -v                    # Unit tests
ruff check app/                     # Linting
mypy app/                           # Type checking
```

---

## Traceability

- **Architecture Decision**: Pinned versions for stability during active development
- **Traces to**: 03-Architecture §4 (Framework choices), 07-Backend-Development-Standards §2 (Fail fast)
- **Decision Date**: 2025-01-17
- **Status**: ✅ Implemented and verified
- **Next Review**: After E3 tasks complete, plan Q2 2025 framework upgrade

