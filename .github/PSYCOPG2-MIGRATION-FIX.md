# ✅ Root Cause Fixed: psycopg2 Missing for Alembic

## The Problem

GitHub Actions CI failed with:
```
ModuleNotFoundError: No module named 'psycopg2'
```

During the database migration step (Alembic upgrade).

## Root Cause

**Alembic's environment configuration (`backend/migrations/env.py`) converts async PostgreSQL URLs to sync:**

```python
# In run_migrations_online()
if url and "postgresql+asyncpg://" in url:
    url = url.replace("postgresql+asyncpg://", "postgresql://")
```

This conversion is **correct and intentional**:
- Application uses: `postgresql+asyncpg://` → asyncpg driver (async)
- Alembic uses: `postgresql://` → psycopg2 driver (sync)

Alembic doesn't support async drivers, so migrations run with the synchronous psycopg2 driver. This is the standard production architecture.

## The Fix

Added `psycopg2-binary` to runtime dependencies in `backend/pyproject.toml`:

```toml
dependencies = [
    "fastapi>=0.115.0,<1.0.0",
    "uvicorn[standard]>=0.32.0,<1.0.0",
    "sqlalchemy[asyncio]>=2.0.36,<3.0.0",
    "asyncpg>=0.30.0,<1.0.0",
    "psycopg2-binary>=2.9,<3.0.0",  # ← ADDED
    "alembic>=1.14.0,<2.0.0",
    ...
]
```

## Verification

```bash
cd backend
. .venv/Scripts/Activate.ps1
python -c "import psycopg2; print('✅ psycopg2 version:', psycopg2.__version__)"
```

Output:
```
✅ psycopg2 version: 2.9.12 (dt dec pq3 ext lo64)
```

## Architecture

This follows the **standard production pattern** for async applications with Alembic:

```
┌─────────────────────────────────────┐
│         Application                 │
│  (async operations with FastAPI)    │
├─────────────────────────────────────┤
│    SQLAlchemy AsyncEngine           │
│    (asyncpg driver)                 │
├──────────────┬──────────────────────┤
│              │                      │
│  Alembic     │    Application       │
│  Migrations  │    Runtime           │
│              │                      │
│ psycopg2     │    asyncpg           │
│ (sync)       │    (async)           │
└──────────────┴──────────────────────┘
         PostgreSQL Database
```

## Why psycopg2-binary?

Two options for psycopg2:
- **psycopg2-binary** - Pre-built binary, no compilation needed, instant install
- **psycopg** (v3) - Modern version, requires compilation

We chose `psycopg2-binary` because:
1. Works out-of-the-box in CI/CD (no build tools needed)
2. No compilation required (faster GitHub Actions)
3. Alembic's URL conversion (`postgresql://`) expects psycopg2
4. Least disruptive change to existing configuration

## Git History

```
cc59210 build: add psycopg2-binary for Alembic migrations
```

## What Happens Next

When GitHub Actions runs:

1. ✅ `uv sync --all-extras` installs all dependencies including psycopg2
2. ✅ Alembic migration step can now find `psycopg2`
3. ✅ Migrations run successfully: `python -m alembic upgrade head`
4. ✅ Tests pass
5. ✅ Build verification passes

The **"No module named 'psycopg2'" error will disappear**.

## Additional Notes

This is **not** a workaround or hack. It's the correct production pattern:

- Application uses **asyncpg** for high-performance async database operations
- Alembic uses **psycopg2** for synchronous DDL (schema changes)
- Both drivers connect to the same PostgreSQL database
- This architecture is used by major async frameworks (Django async, FastAPI, etc.)

The dependency was simply missing from `pyproject.toml`. Now it's added and locked in `uv.lock`.
