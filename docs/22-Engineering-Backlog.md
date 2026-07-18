# Sentinel — Engineering Backlog

## Document Information

| Field | Value |
|---|---|
| Document | docs/22-Engineering-Backlog.md |
| Version | 1.0.1 |
| Status | Final |
| Owner | Engineering Director |
| Audience | Engineers, engineering managers, TPMs |
| Dependencies | 21-Implementation-Roadmap, all approved documents (00–20), backend/openapi.yaml |

---

## How to Use This Document

This is the master engineering execution backlog. Every task is derived from the approved architecture (Documents 00–20 and backend/openapi.yaml). No task introduces undocumented features or architectural changes.

**Task sizing:** Each task targets 2–8 hours of implementation effort. Tasks exceeding this range should be split before starting.

**Task IDs:** Format is `E{epic}.T{task}` (e.g., `E1.T3` = Epic 1, Task 3). IDs are stable references for dependency tracking and code review comments.

**Priority levels:** P0 (blocker — unblocks other tasks), P1 (critical path), P2 (important but not blocking), P3 (can be deferred within the phase).

**Implementation order:** Within each epic, tasks are listed in suggested implementation order. Dependencies between tasks are explicit.

---

### Backlog maintenance cadence

The backlog is reviewed after every completed epic and after any approved architectural change. Tasks may be split, reordered within dependency constraints, or refined, but no task may introduce behavior that contradicts the approved architecture without an approved ADR/RFC.

## Epic 1: Repository Foundation

**Objective:** Establish the physical project structure, tooling, and CI skeleton that all subsequent development depends on.

**Architectural Owner:** Infrastructure Lead (owns 06-Repository-Structure, 09-Deployment-Architecture, 12-CI-CD-Architecture)

**Dependencies:** None.

**Deliverables:** Working local dev environment, CI pipeline, directory structure matching 06-Repository-Structure.

**Definition of Done:** `docker compose up` produces a working environment; CI is green; a new engineer can start contributing without verbal instructions.

**Risks:** Dependency version conflicts; Docker networking across OS variants.

---

### E1.T1 — Create Backend Directory Structure

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | None |
| **Estimated Effort** | 2h |
| **Description** | Create the complete backend directory tree matching 06-Repository-Structure §2–§3: `backend/app/{api/v1/routes,api/v1/dependencies,api/v1/middleware,api/v1/exception_handlers,application/services,application/use_cases,application/commands,application/queries,domain/entities,domain/value_objects,domain/repositories,domain/services,domain/events,infrastructure/database,infrastructure/storage,infrastructure/queue,infrastructure/ai_providers,infrastructure/email,infrastructure/logging,infrastructure/config,workers/analysis_worker,workers/retry_worker,workers/scheduled,analyzers/base,analyzers/registry,models,schemas,core,utils}`, `backend/tests/{unit,integration,api,workers,fixtures,mocks}`, `backend/migrations/`. Add `__init__.py` files to make every directory a Python package. |
| **Acceptance Criteria** | Directory tree matches 06-Repository-Structure §3 exactly. All directories contain `__init__.py`. No files exist outside the defined structure. |
| **Definition of Done** | Merged to `main`, verified by listing comparison against spec. |

### E1.T2 — Initialize Python Project Configuration

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E1.T1 |
| **Estimated Effort** | 3h |
| **Description** | Create `pyproject.toml` with: project metadata, pinned production dependencies (FastAPI, uvicorn, SQLAlchemy[asyncio], asyncpg, alembic, celery, redis, pydantic, pydantic-settings, python-jose[cryptography], passlib[bcrypt], python-multipart, httpx, boto3/aioboto3), pinned dev dependencies (pytest, pytest-asyncio, pytest-cov, ruff, mypy, httpx, factory-boy, testcontainers). Configure ruff per 07-Backend-Development-Standards §12 rules. Configure mypy in strict mode. Configure pytest with `tests/` as the test root. |
| **Acceptance Criteria** | `pip install -e ".[dev]"` succeeds. `ruff check .` exits 0. `mypy .` exits 0. `pytest` discovers the test directory (0 tests collected, 0 errors). |
| **Definition of Done** | Merged to `main`, all tools run clean. |

### E1.T3 — Create Environment Variable Template

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E1.T2 |
| **Estimated Effort** | 2h |
| **Description** | Create `.env.example` documenting every environment variable the application will need per 07-Backend-Development-Standards §11: `DATABASE_URL`, `REDIS_URL`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_NAME`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`, `CORS_ORIGINS`, `LOG_LEVEL`, `ENVIRONMENT` (development/staging/production). Each variable includes a comment explaining its purpose and a safe default for local development. |
| **Acceptance Criteria** | Every variable has a comment. Copying `.env.example` to `.env` produces a valid local configuration. No real secrets in the template. |
| **Definition of Done** | Merged to `main`, `.env.example` present at repository root. |

### E1.T4 — Create Docker Compose for Local Development

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E1.T3 |
| **Estimated Effort** | 4h |
| **Description** | Create `docker-compose.yml` per 09-Deployment-Architecture with services: PostgreSQL 16 (port 5432, persistent volume, health check), Redis 7 (port 6379, health check), MinIO (ports 9000/9001, health check, auto-create default bucket via `mc`). Create `docker/Dockerfile.backend` with multi-stage build (builder + runtime) using Python 3.12 slim base. Ensure environment parity per 09-Deployment-Architecture §2. |
| **Acceptance Criteria** | `docker compose up -d` starts all services. `docker compose ps` shows all healthy. PostgreSQL accepts connections on 5432. MinIO console accessible on 9001. Redis responds to PING. |
| **Definition of Done** | Merged to `main`, tested on at least one OS. |

### E1.T5 — Configure Pre-commit Hooks

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E1.T2 |
| **Estimated Effort** | 2h |
| **Description** | Create `.pre-commit-config.yaml` with hooks: ruff (lint + format), mypy (type check), trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files (per 07-Backend-Development-Standards §12). Document hook installation in README. |
| **Acceptance Criteria** | `pre-commit run --all-files` exits 0 on the current codebase. Commit with a lint violation is rejected locally. |
| **Definition of Done** | Merged to `main`, documented in README. |

### E1.T6 — Create GitHub Actions CI Pipeline Skeleton

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E1.T4, E1.T5 |
| **Estimated Effort** | 4h |
| **Description** | Create `.github/workflows/ci.yml` per 12-CI-CD-Architecture §3: trigger on push to `main` and PR. Stages: (1) lint + format check (ruff), (2) type check (mypy), (3) test (pytest with containerized PostgreSQL, Redis, MinIO services). Cache pip dependencies. Fail fast on first stage failure. Add `.github/PULL_REQUEST_TEMPLATE.md` per 19-Contributor-Guide with checklist: tests pass, documentation updated, no self-merge. Add issue templates. |
| **Acceptance Criteria** | CI triggers on PR. Empty test suite produces green build. Lint failure produces red build. PR template renders correctly. |
| **Definition of Done** | CI green on `main` after merge. PR template enforced. |

### E1.T7 — Update Repository README

| Field | Value |
|---|---|
| **Priority** | P2 |
| **Dependencies** | E1.T4 |
| **Estimated Effort** | 2h |
| **Description** | Update `README.md` per 06-Repository-Structure §2: link to docs/00-Project-Context as entry point. Add sections: Prerequisites (Python 3.12, Docker), Quick Start (`docker compose up`, install, run), Project Structure overview, Contributing (link to 19-Contributor-Guide), Documentation (link to docs/ reading order per 00-Project-Context §12). |
| **Acceptance Criteria** | A new engineer can follow README instructions to set up the project without additional guidance. All links resolve. |
| **Definition of Done** | Merged to `main`. |

---

### Definition of Ready

Before implementation begins, each task must have satisfied dependencies, a stable architectural reference, clear acceptance criteria, and testability. Blocked tasks are not started until blockers are removed.

## Epic 2: Backend Core

**Objective:** FastAPI application factory, middleware stack, configuration, structured logging, and health check — the runtime skeleton.

**Architectural Owner:** Backend Lead (owns 03-Architecture, 07-Backend-Development-Standards, 10-Observability-Architecture)

**Dependencies:** Epic 1.

**Deliverables:** Running FastAPI application with health endpoint, structured logging, middleware, error handling.

**Definition of Done:** `GET /health` returns 200; structured JSON logs operational; middleware stack validated by tests.

**Risks:** Middleware ordering conflicts; settings validation across environments.

---

### E2.T1 — Implement Settings Management

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E1.T3 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/core/settings.py` using Pydantic `BaseSettings` per 07-Backend-Development-Standards §11. Define all settings from `.env.example` as typed fields with validators. Implement environment-aware loading (`ENVIRONMENT` field controls defaults). Include `model_config` for `.env` file loading. Settings instance created once at startup (singleton via DI). |
| **Acceptance Criteria** | Settings load from `.env` file. Missing required variable raises `ValidationError` at startup (fail fast). Type validation catches invalid values. Settings are immutable after construction. |
| **Definition of Done** | Unit tests for: valid config, missing required field, invalid type. Merged. |

### E2.T2 — Implement FastAPI Application Factory

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T1 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/main.py` with `create_app()` factory function per 07-Backend-Development-Standards §3. Register startup/shutdown lifecycle hooks (database pool, Redis connection, S3 client — stubs for now). Include API router with `/api/v1/` prefix per 06-Repository-Structure §4. Configure OpenAPI metadata from settings. |
| **Acceptance Criteria** | `uvicorn app.main:app` starts without errors. OpenAPI docs accessible at `/docs`. Startup/shutdown hooks execute in correct order. |
| **Definition of Done** | Unit test for app factory. Application starts in Docker. Merged. |

### E2.T3 — Implement Structured Logging

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T1 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/infrastructure/logging/` per 07-Backend-Development-Standards §10, 10-Observability-Architecture §2. Configure `structlog` or equivalent for JSON output. Every log entry includes: `timestamp` (UTC ISO-8601), `level`, `logger`, `message`, `request_id` (from context), `environment`. Suppress default uvicorn access logs in favor of structured middleware logging. |
| **Acceptance Criteria** | All log output is valid JSON, parseable by `jq`. Correlation ID appears in every log entry within a request context. Log level configurable via `LOG_LEVEL` setting. |
| **Definition of Done** | Unit test for log format. Integration test: request produces correlated log entries. Merged. |

### E2.T4 — Implement Request ID Middleware

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T2, E2.T3 |
| **Estimated Effort** | 2h |
| **Description** | Create middleware in `app/api/v1/middleware/` per 08-Security-Architecture §7, 10-Observability-Architecture §2. Generate UUID4 if `X-Request-ID` header not provided; echo it in the response. Store in context variable accessible throughout the request lifecycle. Log request start and completion with request ID, method, path, status code, duration. |
| **Acceptance Criteria** | Response includes `X-Request-ID` header. Provided `X-Request-ID` is echoed back. Generated IDs are valid UUID4. All request logs include the ID. |
| **Definition of Done** | API tests for: no header provided, header provided. Log correlation verified. Merged. |

### E2.T5 — Implement Global Exception Handlers

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T2 |
| **Estimated Effort** | 3h |
| **Description** | Create handlers in `app/api/v1/exception_handlers/` per 05-API-Specification error schema. Handle: `RequestValidationError` → 422, `HTTPException` → appropriate status, unhandled `Exception` → 500. All responses follow RFC 7807 format: `{"type", "title", "status", "detail", "instance"}`. Internal details never leaked in 500 responses (per 08-Security-Architecture §10). Log full exception with stack trace at ERROR level server-side. |
| **Acceptance Criteria** | Validation error returns 422 with RFC 7807 body. Unknown exception returns 500 with generic message (no stack trace in response). All errors include `request_id` in response body. |
| **Definition of Done** | Unit tests for each exception type. API test for 422, 500 responses. Merged. |

### E2.T6 — Implement CORS Middleware

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E2.T2 |
| **Estimated Effort** | 2h |
| **Description** | Configure CORS middleware per 08-Security-Architecture §7. Origins loaded from `CORS_ORIGINS` setting (list). Default to closed (no origins allowed) per secure-by-default principle. Allow methods: GET, POST, PATCH, DELETE, OPTIONS. Allow headers: Authorization, Content-Type, X-Request-ID, Idempotency-Key. |
| **Acceptance Criteria** | Preflight request from allowed origin succeeds. Request from disallowed origin is rejected. Default configuration allows no origins. |
| **Definition of Done** | API tests for allowed and rejected origins. Merged. |

### E2.T7 — Implement Rate Limiting Middleware

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E2.T2 |
| **Estimated Effort** | 4h |
| **Description** | Implement per-IP or per-user rate limiting per 08-Security-Architecture §7 and openapi.yaml (429 + `Retry-After`). Use Redis as the backing store (sliding window or token bucket). Configurable limits per endpoint group (auth endpoints stricter than read endpoints). Return `429 Too Many Requests` with `Retry-After` header indicating seconds until reset. |
| **Acceptance Criteria** | Exceeding rate limit returns 429 with `Retry-After`. Within-limit requests succeed normally. Rate limit state survives across API process restarts (Redis-backed). |
| **Definition of Done** | Integration tests with Redis. API test for 429 response. Merged. |

### E2.T8 — Implement Health Check Endpoint

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T2 |
| **Estimated Effort** | 2h |
| **Description** | Create `app/api/v1/routes/health.py` per openapi.yaml `GET /health`. Return `{"status": "healthy", "version": "...", "timestamp": "..."}`. Check database connectivity, Redis connectivity, and object storage connectivity. Return 200 if all healthy, 503 if any component is degraded. No authentication required. |
| **Acceptance Criteria** | Returns 200 when all dependencies are up. Returns 503 with failing component identified when any dependency is down. Response matches openapi.yaml schema. |
| **Definition of Done** | API test with all dependencies up and with simulated failures. Merged. |

### E2.T9 — Implement Base Pydantic Schemas

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E2.T2 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/schemas/` with base schemas per 05-API-Specification: `PaginatedResponse` (items, total, page, pageSize, totalPages), `ErrorResponse` (RFC 7807), `TimestampMixin` (createdAt, updatedAt as UTC datetime), `SortParam`, `FilterParam`. All datetime fields serialize to ISO-8601 UTC. All UUIDs serialize as strings. Configure Pydantic `model_config` for camelCase alias generation (API uses camelCase, Python uses snake_case). |
| **Acceptance Criteria** | Schemas serialize/deserialize correctly. CamelCase aliases work in both directions. Datetime fields are always UTC ISO-8601. |
| **Definition of Done** | Unit tests for serialization, validation, alias generation. Merged. |

---

## Epic 3: Database & Persistence

**Objective:** Database schema, ORM models, Alembic migrations, and the repository pattern.

**Architectural Owner:** Data Lead (owns 04-Database-Design, 02-Domain-Model entity-to-table mapping)

**Dependencies:** Epic 2.

**Deliverables:** All tables from 04-Database-Design created via Alembic; repository interfaces and implementations operational.

**Definition of Done:** All constraints enforced; integration tests pass against real PostgreSQL; no ORM leakage into Domain layer.

**Risks:** Migration ordering; Alembic autogenerate gaps; connection pool sizing.

---

### E3.T1 — Configure Database Connection and Session Management

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T1 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/infrastructure/database/session.py` per 07-Backend-Development-Standards §7. Configure async SQLAlchemy engine from `DATABASE_URL` setting. Implement async session factory with connection pooling (pool_size, max_overflow, pool_timeout from settings). Create FastAPI dependency for request-scoped session injection. Implement session lifecycle: acquire on request start, commit on success, rollback on exception, close always. |
| **Acceptance Criteria** | Session acquired per-request via DI. Transaction commits on success, rolls back on exception. Pool metrics observable. Connection to containerized PostgreSQL works. |
| **Definition of Done** | Integration test against real PostgreSQL. Merged. |

### E3.T2 — Configure Alembic

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T1 |
| **Estimated Effort** | 2h |
| **Description** | Initialize Alembic in `backend/migrations/` per 06-Repository-Structure §3. Configure `alembic.ini` to read `DATABASE_URL` from environment. Configure `env.py` to import all ORM models for autogenerate support. Add CI step: `alembic upgrade head` → tests → `alembic downgrade base`. |
| **Acceptance Criteria** | `alembic revision --autogenerate` creates migration from model changes. `alembic upgrade head` and `alembic downgrade base` succeed on clean database. |
| **Definition of Done** | CI integration verified. Merged. |

### E3.T3 — Implement Users ORM Model and Migration

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T2 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/models/user.py` per 04-Database-Design §3: `id` (UUID PK, server default), `email` (unique, not null), `full_name` (not null), `password_hash` (not null), `role` (enum: admin/analyst/viewer, default viewer), `is_active` (boolean, default true), `created_at` (timestamptz, server default), `updated_at` (timestamptz, server default + on update), `deleted_at` (nullable timestamptz). Generate Alembic migration. |
| **Acceptance Criteria** | Migration creates `users` table with all columns, constraints, and indexes. Email uniqueness enforced at database level. Role enum enforced at database level. |
| **Definition of Done** | Integration test: insert valid user, reject duplicate email, reject invalid role. Merged. |

### E3.T4 — Implement Uploads ORM Model and Migration

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T3 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/models/upload.py` per 04-Database-Design §4: `id` (UUID PK), `user_id` (FK → users), `status` (enum: pending/processing/completed/failed), `original_filename`, `content_type`, `size_bytes`, `storage_key` (nullable), `digital_asset_id` (FK → digital_assets, nullable), `checksum` (nullable), `error_message` (nullable), `idempotency_key` (unique, nullable), `created_at`, `updated_at`. Generate migration. |
| **Acceptance Criteria** | FK to users enforced. Status enum enforced. Idempotency key unique constraint works. Nullable fields behave correctly per lifecycle state. |
| **Definition of Done** | Integration tests for constraints. Merged. |

### E3.T5 — Implement Digital Assets ORM Model and Migration

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T4 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/models/digital_asset.py` per 04-Database-Design §5: `id` (UUID PK), `sha256_hash` (unique, not null), `mime_type`, `size_bytes`, `storage_key`, `original_filename`, `is_active` (default true), `created_at`, `deleted_at` (nullable). SHA-256 hash is the domain identity per 02-Domain-Model. Generate migration. |
| **Acceptance Criteria** | SHA-256 hash unique constraint rejects duplicate inserts. This is the single most important constraint test in the entire system. |
| **Definition of Done** | Integration test: insert asset, attempt duplicate hash → unique violation. Merged. |

### E3.T6 — Implement Analyses ORM Model and Migration

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T5 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/models/analysis.py` per 04-Database-Design §6: `id` (UUID PK), `digital_asset_id` (FK → digital_assets), `analyzer_key`, `analyzer_version`, `status` (enum: pending/running/completed/failed/cancelled), `result` (JSONB, nullable), `error_message` (nullable), `started_at` (nullable), `completed_at` (nullable), `created_at`. Add partial unique index on (digital_asset_id, analyzer_key, analyzer_version) for completed analyses per 02-Domain-Model invariant 6. Generate migration. |
| **Acceptance Criteria** | FK to digital_assets enforced. Status enum enforced. Idempotency index prevents duplicate completed analyses for same asset + analyzer version. |
| **Definition of Done** | Integration tests for FK, status enum, idempotency constraint. Merged. |

### E3.T7 — Implement Reports ORM Model and Migration

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E3.T6 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/models/report.py` per 04-Database-Design §7: `id` (UUID PK), `digital_asset_id` (FK → digital_assets), `status` (enum: draft/rendering/rendered/failed), `storage_key` (nullable — PDF location), `created_at`, `updated_at`, `deleted_at` (nullable). Create `app/models/report_analysis.py` junction table per 04-Database-Design §7: `report_id` (FK → reports), `analysis_id` (FK → analyses), composite PK. Generate migration. |
| **Acceptance Criteria** | FK constraints enforced. Report-Analysis many-to-many relationship operational. Soft-delete filter works. |
| **Definition of Done** | Integration tests for constraints and junction table operations. Merged. |

### E3.T8 — Implement Audit Logs ORM Model and Migration

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E3.T3 |
| **Estimated Effort** | 2h |
| **Description** | Create `app/models/audit_log.py` per 04-Database-Design §8: `id` (UUID PK), `user_id` (FK → users, nullable for system actions), `action` (string), `resource_type` (string), `resource_id` (UUID), `details` (JSONB), `ip_address` (nullable), `created_at`. No UPDATE or DELETE permitted at application level per 08-Security-Architecture §2. Generate migration. |
| **Acceptance Criteria** | Audit log records can be inserted. Application code has no update or delete path for audit logs. Index on `created_at` for time-range queries. |
| **Definition of Done** | Integration test for insert. Verify no ORM relationship allows cascade delete. Merged. |

### E3.T9 — Implement Refresh Tokens ORM Model and Migration

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E3.T3 |
| **Estimated Effort** | 2h |
| **Description** | Create `app/models/refresh_token.py` per 04-Database-Design: `id` (UUID PK), `user_id` (FK → users), `token_hash` (unique, not null — store hash, never raw token), `expires_at`, `revoked_at` (nullable), `created_at`. Generate migration. |
| **Acceptance Criteria** | Token hash unique. Expired and revoked tokens queryable. FK cascade on user deletion. |
| **Definition of Done** | Integration tests for constraints. Merged. |

### E3.T10 — Implement Domain Repository Interfaces

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T3 |
| **Estimated Effort** | 4h |
| **Description** | Create abstract base classes in `app/domain/repositories/` per 06-Repository-Structure §7: `UserRepository`, `UploadRepository`, `DigitalAssetRepository`, `AnalysisRepository`, `ReportRepository`, `AuditLogRepository`. Each defines the methods the Domain and Application layers depend on (CRUD + domain-specific queries). Use Python `abc.ABC` with `@abstractmethod`. No implementation details — pure contracts. |
| **Acceptance Criteria** | All repository interfaces define the methods needed by the Domain Model. No interface imports from `infrastructure/` or `models/`. |
| **Definition of Done** | Interfaces reviewed against 04-Database-Design query patterns. Merged. |

### E3.T11 — Implement PostgreSQL Repository Implementations

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T10, E3.T3–E3.T9 |
| **Estimated Effort** | 6h |
| **Description** | Create concrete implementations in `app/infrastructure/database/repositories/` per 06-Repository-Structure §8. Each implements the corresponding Domain interface using SQLAlchemy async sessions. Implement soft-delete filtering (`WHERE deleted_at IS NULL`) as a default query scope per 04-Database-Design §10. Implement pagination per 05-API-Specification patterns. |
| **Acceptance Criteria** | Every abstract method has a concrete implementation. Soft-delete filter applies to all list/get queries by default. Pagination returns correct totals and page metadata. |
| **Definition of Done** | Integration tests for each repository method against real PostgreSQL. Merged. |

---

## Epic 4: Authentication & Authorization

**Objective:** JWT authentication, RBAC, user management endpoints, audit logging.

**Architectural Owner:** Security Lead (owns 08-Security-Architecture §4–§5)

**Dependencies:** Epic 3.

**Deliverables:** All `/auth/*` and `/users/*` endpoints operational per openapi.yaml.

**Definition of Done:** RBAC enforced on every protected endpoint; audit trail for all auth events; no credential leakage.

**Risks:** JWT secret management; timing attacks; refresh token storage.

---

### E4.T1 — Implement User Domain Entity

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T10 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/domain/entities/user.py` per 02-Domain-Model. Enforce invariants: email is required and unique (validated, not just constrained), role must be one of admin/analyst/viewer. Include factory method for user creation with password hashing. User entity is the only entity that supports in-place mutation (profile fields). |
| **Acceptance Criteria** | Entity rejects invalid email format. Entity rejects invalid roles. Password is never stored as plaintext on the entity. |
| **Definition of Done** | Unit tests for all invariants. Merged. |

### E4.T2 — Implement Password Hashing Service

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T1 |
| **Estimated Effort** | 2h |
| **Description** | Create `app/infrastructure/security/password.py` per 08-Security-Architecture §4. Use bcrypt or argon2id with configurable work factor. Implement `hash_password(plain: str) -> str` and `verify_password(plain: str, hashed: str) -> bool`. Constant-time comparison to prevent timing attacks. |
| **Acceptance Criteria** | Hash is non-reversible. Verify succeeds for correct password, fails for wrong password. Timing does not vary based on input length. |
| **Definition of Done** | Unit tests. Merged. |

### E4.T3 — Implement JWT Token Service

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T1 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/infrastructure/security/jwt.py` per 08-Security-Architecture §4. Implement `create_access_token(user_id, role) -> str`, `create_refresh_token(user_id) -> str`, `decode_token(token) -> TokenPayload`. Access token includes: sub (user_id), role, exp, iat, jti. Refresh token includes: sub, exp, iat, jti. Token signing uses algorithm from settings. |
| **Acceptance Criteria** | Access token expires at configured time. Decode rejects expired tokens. Decode rejects tampered tokens (invalid signature). Token contains all required claims. |
| **Definition of Done** | Unit tests for: create, decode valid, decode expired, decode tampered. Merged. |

### E4.T4 — Implement Authentication Middleware

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E4.T3 |
| **Estimated Effort** | 3h |
| **Description** | Create FastAPI dependency in `app/api/v1/dependencies/auth.py` per 08-Security-Architecture §4. Extract Bearer token from Authorization header. Decode and validate JWT. Load user from repository. Reject if user is inactive. Inject authenticated user into request context. Create role-checking dependency factory: `require_role(role)`. |
| **Acceptance Criteria** | Missing token → 401. Invalid token → 401. Expired token → 401. Inactive user → 401. Wrong role → 403. Valid token → user injected into handler. |
| **Definition of Done** | Unit tests for each rejection case. API tests for protected endpoints. Merged. |

### E4.T5 — Implement Auth Service

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E4.T1, E4.T2, E4.T3 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/application/services/auth_service.py` per 06-Repository-Structure §6. Implement: `register(email, password, full_name) -> User`, `login(email, password) -> TokenPair`, `refresh(refresh_token) -> TokenPair`, `logout(refresh_token or all)`. Registration checks email uniqueness. Login validates password. Refresh rotates tokens (old refresh token invalidated). Logout revokes refresh tokens. All operations produce audit log entries. |
| **Acceptance Criteria** | Registration with duplicate email fails cleanly. Login with wrong password returns 401. Refresh with revoked token returns 401. All operations are audited. |
| **Definition of Done** | Unit tests with mocked repositories. Integration tests with real DB. Merged. |

### E4.T6 — Implement Auth Route Handlers

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E4.T4, E4.T5 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/api/v1/routes/auth.py` per openapi.yaml. Implement: `POST /auth/register` (public), `POST /auth/login` (public), `POST /auth/refresh` (refresh token auth), `POST /auth/logout` (access token auth), `GET /auth/me` (access token auth). Create Pydantic request/response schemas matching openapi.yaml exactly. Route handlers call AuthService only — no business logic in routes. |
| **Acceptance Criteria** | Every response matches openapi.yaml schema. Error responses use RFC 7807 format. No password fields in any response. |
| **Definition of Done** | API tests for every endpoint (happy + error paths). Contract test against openapi.yaml. Merged. |

### E4.T7 — Implement User Management Routes

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E4.T4, E4.T5 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/api/v1/routes/users.py` per openapi.yaml. Implement: `GET /users` (admin only, paginated), `GET /users/{userId}` (admin or self), `PATCH /users/{userId}` (admin can change role; users can update own profile but not own role per 08-Security-Architecture §5), `DELETE /users/{userId}` (admin only, soft-delete). Create corresponding UserService in Application layer. |
| **Acceptance Criteria** | Non-admin cannot list users. Non-admin cannot change their own role. Admin can deactivate users. Soft-delete excludes user from lists. All operations audited. |
| **Definition of Done** | API tests for RBAC on every endpoint. Merged. |

### E4.T8 — Implement Audit Log Service and Routes

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E3.T8, E4.T4 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/application/services/audit_service.py` and `app/api/v1/routes/audit_logs.py` per openapi.yaml. `POST` audit entries are created internally (no public create endpoint). `GET /audit-logs` (admin only, paginated, filterable by user, action, resource, date range), `GET /audit-logs/{auditLogId}` (admin only). Audit logs are immutable — no update or delete endpoints. |
| **Acceptance Criteria** | Non-admin cannot access audit logs (403). Logs are paginated and filterable. No endpoint allows modification of audit records. |
| **Definition of Done** | API tests for access control and filtering. Merged. |

---

## Epic 5: Asset Upload & Management

**Objective:** File upload pipeline, Digital Asset lifecycle, object storage integration, deduplication.

**Architectural Owner:** Backend Lead (owns 02-Domain-Model Digital Asset invariants, 08-Security-Architecture §6)

**Dependencies:** Epic 4.

**Deliverables:** All `/uploads/*` and `/assets/*` endpoints operational. Files stored in S3-compatible storage.

**Definition of Done:** Upload → hash → deduplicate → store pipeline works end-to-end; idempotency enforced; soft-delete operational.

**Risks:** Memory pressure from large uploads; race conditions in dedup; partial writes.

---

### E5.T1 — Implement Object Storage Adapter

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T1, E1.T4 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/infrastructure/storage/s3_adapter.py` per 06-Repository-Structure §8. Implement abstract `StorageAdapter` interface in Domain layer. Concrete implementation uses boto3/aioboto3 for S3-compatible API. Methods: `upload_stream(key, stream, content_type) -> str`, `download_stream(key) -> AsyncIterator`, `delete(key)`, `generate_presigned_url(key, expiry) -> str`, `exists(key) -> bool`. Configure from settings (endpoint, bucket, credentials). |
| **Acceptance Criteria** | Upload to MinIO succeeds. Download returns the same bytes. Delete removes the object. Presigned URL is valid and time-limited. Connection failure raises structured exception. |
| **Definition of Done** | Integration tests against MinIO. All operations verified. Merged. |

### E5.T2 — Implement Digital Asset Domain Entity

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T10 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/domain/entities/digital_asset.py` per 02-Domain-Model. Enforce invariants: SHA-256 hash is required and immutable (set at creation, never modified). `mime_type` and `size_bytes` are required. Factory method `create(sha256_hash, mime_type, size_bytes, storage_key)` — no field is modifiable after creation. Implement hash-based identity: two DigitalAssets with the same hash are the same entity per 02-Domain-Model. |
| **Acceptance Criteria** | Entity is immutable after creation (attempt to modify raises error). Hash equality determines entity identity. Invalid hash format rejected. |
| **Definition of Done** | Unit tests for every invariant. Merged. |

### E5.T3 — Implement Upload Domain Entity

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T10 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/domain/entities/upload.py` per 02-Domain-Model. Implement state machine: pending → processing → completed/failed per 04-Database-Design §9.1. `digital_asset_id` is null until status is `completed` (invariant). Immutable after reaching terminal state. Enforce: always belongs to exactly one User. |
| **Acceptance Criteria** | State transitions enforce valid paths only (e.g., cannot go from failed to completed). `digital_asset_id` is null when not completed. Terminal states reject further modification. |
| **Definition of Done** | Unit tests for state machine, invariants. Merged. |

### E5.T4 — Implement Upload Service

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E5.T1, E5.T2, E5.T3 |
| **Estimated Effort** | 6h |
| **Description** | Create `app/application/services/upload_service.py`. Orchestrate the upload pipeline per openapi.yaml and 02-Domain-Model: (1) validate file (size ≤ 100MB, MIME in allow-list, magic-byte verification), (2) create Upload record (pending), (3) stream file to S3 while computing SHA-256 hash concurrently (never buffer entire file in memory), (4) check for existing DigitalAsset by hash (deduplication), (5) create or resolve DigitalAsset, (6) transition Upload to completed, (7) audit log. Handle Idempotency-Key: if key exists and matches prior upload, return existing result. |
| **Acceptance Criteria** | File streams to S3 without full memory buffering. SHA-256 computed during streaming. Duplicate hash resolves to existing asset. Idempotency key prevents duplicate uploads. Invalid files rejected before S3 write. |
| **Definition of Done** | Unit tests (mocked infra). Integration tests (real S3 + PostgreSQL). 100MB file upload test (memory check). Merged. |

### E5.T5 — Implement File Validation Utilities

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | None |
| **Estimated Effort** | 3h |
| **Description** | Create `app/utils/file_validation.py` per 08-Security-Architecture §6. Implement: MIME allow-list check (configurable list of allowed types), magic-byte verification (check actual file header bytes, not client-provided Content-Type), size limit enforcement (streaming check, reject before consuming full body). Support: PDF, common images (JPEG, PNG, GIF, WebP), ZIP, common documents (DOCX, XLSX, PPTX). |
| **Acceptance Criteria** | Correctly identifies file type from magic bytes regardless of declared Content-Type. Rejects oversized files at stream boundary. Rejects files not in allow-list. |
| **Definition of Done** | Unit tests with real file samples. Tests for MIME mismatch (declared vs. actual). Merged. |

### E5.T6 — Implement Upload Route Handlers

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E5.T4, E4.T4 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/api/v1/routes/uploads.py` per openapi.yaml. `POST /uploads` (authenticated, multipart file upload, Idempotency-Key header), `GET /uploads` (authenticated, paginated, user-scoped), `GET /uploads/{uploadId}` (authenticated, owner or admin). Create Pydantic schemas matching openapi.yaml. Route handlers delegate to UploadService. |
| **Acceptance Criteria** | Upload returns Upload object with status. List returns user's uploads only (not other users'). Detail returns full upload info with asset reference if completed. |
| **Definition of Done** | API tests for upload, list, detail. Idempotency test. Merged. |

### E5.T7 — Implement Asset Route Handlers

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E5.T4, E4.T4 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/api/v1/routes/assets.py` per openapi.yaml. `GET /assets` (authenticated, paginated), `GET /assets/{assetId}` (authenticated), `DELETE /assets/{assetId}` (authenticated, owner or admin, soft-delete). Create Pydantic schemas matching openapi.yaml. Assets belong to the user who first uploaded them. Soft-deleted assets excluded from list/get queries. |
| **Acceptance Criteria** | List returns only active assets. Detail returns asset with all metadata. Delete sets `deleted_at` without removing from DB. Deleted assets invisible to all user queries. |
| **Definition of Done** | API tests for CRUD operations and soft-delete behavior. Merged. |

### E5.T8 — Implement Abandoned Upload Cleanup Job

| Field | Value |
|---|---|
| **Priority** | P2 |
| **Dependencies** | E5.T4 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/workers/scheduled/upload_cleanup.py` per 04-Database-Design §9.1. Daily job: find uploads in `pending` state older than 24 hours, transition to `failed`, delete partial S3 objects if `storage_key` is set. Log cleanup results with count of cleaned uploads. |
| **Acceptance Criteria** | Pending uploads older than 24h are transitioned to failed. Partial S3 objects are cleaned up. Recent pending uploads are not affected. |
| **Definition of Done** | Integration test with time-manipulated test data. Merged. |

---

## Epic 6: Analysis Engine

**Objective:** Async analysis pipeline — queue, workers, analyzer interface, first analyzer, job lifecycle.

**Architectural Owner:** Backend Lead (owns 03-Architecture §5 async pipeline, 02-Domain-Model Analysis entity)

**Dependencies:** Epic 5.

**Deliverables:** All `/analyses/*` and `/analyzers/*` endpoints. Worker processing jobs from queue.

**Definition of Done:** Request → queue → worker → analyzer → result pipeline operational end-to-end.

**Risks:** Concurrent job claims; stuck jobs; memory leaks in workers.

---

### E6.T1 — Implement Queue Infrastructure Adapter

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T1 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/infrastructure/queue/` per 06-Repository-Structure §8. Implement abstract `QueueAdapter` interface in Domain layer. Concrete implementation using either Celery+Redis or PostgreSQL `FOR UPDATE SKIP LOCKED` per 03-Architecture §5. Methods: `publish(job_type, payload)`, `claim() -> Job`, `ack(job_id)`, `nack(job_id)`. |
| **Acceptance Criteria** | Published job is claimable by a worker. Claimed job is not visible to other workers. Acked job is permanently removed from queue. Nacked job is retryable. |
| **Definition of Done** | Integration tests under concurrent claim load. Merged. |

### E6.T2 — Implement Analysis Domain Entity

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T10 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/domain/entities/analysis.py` per 02-Domain-Model. Enforce invariants: always references one DigitalAsset, append-only (no modification after terminal state), result must include verdict + evidence + confidence + recommendation per openapi.yaml invariant 4. State machine: pending → running → completed/failed/cancelled per 04-Database-Design §9.3. Idempotency check: (digital_asset_id, analyzer_key, analyzer_version) per invariant 6. |
| **Acceptance Criteria** | Entity rejects modification in terminal state. State transitions enforce valid paths. Result schema validated. |
| **Definition of Done** | Unit tests for invariants, state machine, idempotency logic. Merged. |

### E6.T3 — Implement Analyzer Base Interface and Registry

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E5.T2 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/analyzers/base/analyzer.py` with abstract base class per 06-Repository-Structure §10: `key: str`, `version: str`, `async analyze(asset: DigitalAsset, content_stream) -> AnalysisResult`. Create `app/analyzers/registry/registry.py`: register analyzers by key, look up by key, list available analyzers. AnalysisResult value object: `verdict`, `evidence`, `confidence`, `recommendation`. |
| **Acceptance Criteria** | Analyzer base class enforces the analyze contract. Registry can register and retrieve analyzers by key. All analyzers return AnalysisResult with required fields. |
| **Definition of Done** | Unit tests for registry and result validation. Merged. |

### E6.T4 — Implement Metadata Analyzer

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E6.T3 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/analyzers/metadata_analyzer/` per 06-Repository-Structure §10. The simplest concrete analyzer: extracts file type, size, MIME type, hash, basic properties (page count for PDFs, dimensions for images). Produces AnalysisResult with verdict (informational), evidence (extracted metadata), confidence (1.0 for deterministic extraction), recommendation. No external API calls. |
| **Acceptance Criteria** | Extracts correct metadata from PDF, JPEG, PNG test files. Returns valid AnalysisResult schema. Handles corrupt or empty files gracefully (failed analysis, not crash). |
| **Definition of Done** | Unit tests with real file fixtures. Merged. |

### E6.T5 — Implement Analysis Worker

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E6.T1, E6.T3 |
| **Estimated Effort** | 6h |
| **Description** | Create `app/workers/analysis_worker/worker.py` per 06-Repository-Structure §9. Worker loop: claim job from queue → load Analysis record (set to running) → retrieve asset content from S3 → look up analyzer from registry → execute analyzer → save result (set to completed or failed) → ack job. Implement: configurable timeout per analysis, max retries, error message capture. Worker runs as a separate process from the API per 09-Deployment-Architecture. |
| **Acceptance Criteria** | Worker picks up queued job and executes analyzer. Successful analysis transitions to completed with result. Failed analysis transitions to failed with error message. Worker timeout prevents stuck jobs. Worker crash does not leave job in unrecoverable state. |
| **Definition of Done** | Worker tests against real PostgreSQL and S3. Concurrent worker test. Timeout test. Merged. |

### E6.T6 — Implement Analysis Service

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E6.T2, E6.T5 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/application/services/analysis_service.py`. Methods: `request_analysis(asset_id, analyzer_key) -> Analysis` (idempotency check: if completed analysis exists for same asset + analyzer version, return existing), `cancel_analysis(analysis_id)`, `get_analysis(analysis_id) -> Analysis`, `list_analyses(filters) -> PaginatedResult`. Audit log all operations. |
| **Acceptance Criteria** | Duplicate analysis request returns existing record. New analysis creates pending record and publishes to queue. Cancel transitions analysis from pending/running to cancelled. |
| **Definition of Done** | Unit tests. Integration tests. Merged. |

### E6.T7 — Implement Analysis Route Handlers

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E6.T6, E4.T4 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/api/v1/routes/analyses.py` per openapi.yaml. `POST /assets/{assetId}/analyses` (request analysis), `GET /assets/{assetId}/analyses` (list analyses for asset), `GET /analyses` (list all user's analyses), `GET /analyses/{analysisId}` (detail), `POST /analyses/{analysisId}/cancel` (cancel). Idempotency-Key support on POST. |
| **Acceptance Criteria** | All responses match openapi.yaml schemas. Analysis result includes verdict, evidence, confidence, recommendation. |
| **Definition of Done** | API tests for all endpoints. End-to-end test: request → worker processes → result visible via API. Merged. |

### E6.T8 — Implement Analyzers Route Handlers

| Field | Value |
|---|---|
| **Priority** | P2 |
| **Dependencies** | E6.T3, E4.T4 |
| **Estimated Effort** | 2h |
| **Description** | Create `app/api/v1/routes/analyzers.py` per openapi.yaml. `GET /analyzers` (list registered analyzers with key, version, description), `GET /analyzers/{analyzerId}` (detail). Read-only — analyzers are registered in code, not via API. |
| **Acceptance Criteria** | Returns list of registered analyzers. Detail returns analyzer metadata. |
| **Definition of Done** | API tests. Merged. |

---

## Epic 7: AI Providers & Advanced Analyzers

**Objective:** AI provider adapter infrastructure and AI-powered analyzers.

**Architectural Owner:** AI/ML Lead (owns 08-Security-Architecture §8 prompt injection, AI provider adapter contracts)

**Dependencies:** Epic 6.

**Deliverables:** AI Document Analyzer, Security Analyzer, OCR Analyzer, Image Analyzer.

**Definition of Done:** At least two analyzers producing valid results; prompt injection mitigated; provider failures handled gracefully.

**Risks:** Cost overruns; prompt injection; provider latency/availability.

---

### E7.T1 — Implement AI Provider Adapter Interface

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T1 |
| **Estimated Effort** | 3h |
| **Description** | Create abstract `AIProviderAdapter` in `app/infrastructure/ai_providers/` per 06-Repository-Structure §8. Methods: `async complete(system_prompt, user_content, model, max_tokens, temperature) -> ProviderResponse`. ProviderResponse includes: content, usage (tokens), model, finish_reason. Configure timeout, retry count, and rate limiting from settings. |
| **Acceptance Criteria** | Interface is clean enough that swapping providers requires only a new concrete implementation. Timeout and retry configurable. |
| **Definition of Done** | Interface reviewed. Unit tests for timeout/retry logic (mock provider). Merged. |

### E7.T2 — Implement OpenAI Provider Adapter

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E7.T1 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/infrastructure/ai_providers/openai_adapter.py`. Implement AIProviderAdapter using OpenAI Python SDK. Handle: authentication via API key from settings, timeout handling, rate limit responses (429 → retry with backoff), malformed responses, token counting. Log provider call latency and token usage (never log prompt content containing user data). |
| **Acceptance Criteria** | Successful call returns structured ProviderResponse. Timeout returns structured error (not a hang). Rate limit triggers automatic retry. API key never logged. |
| **Definition of Done** | Integration test against OpenAI (or mock). Timeout and rate limit tests. Merged. |

### E7.T3 — Implement AI Document Analyzer

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E6.T3, E7.T2 |
| **Estimated Effort** | 6h |
| **Description** | Create `app/analyzers/ai_document_analyzer/` per 06-Repository-Structure §10. Constructs prompt with strict system/user separation per 08-Security-Architecture §8: system prompt defines the analysis task and output schema, user content is the extracted document text (treated as untrusted data, never as instructions). Parses AI response and validates against AnalysisResult schema. Handles: AI refusal, malformed output, token limit exceeded. |
| **Acceptance Criteria** | Produces valid AnalysisResult with verdict, evidence, confidence, recommendation. Embedded prompt injection attempts in document content do not alter system behavior. Malformed AI output produces failed analysis with error, not a crash. |
| **Definition of Done** | Unit tests for prompt construction and output parsing. Prompt injection test cases. Integration test with real/mock AI provider. Security review of prompt template. Merged. |

### E7.T4 — Implement Security Analyzer

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E6.T3 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/analyzers/security_analyzer/`. Static analysis analyzer: check file hash against known-bad hash lists, analyze file structure for common malware indicators (suspicious macros in Office docs, JavaScript in PDFs, embedded executables in archives), check file entropy for encryption/packing indicators. No external API calls (v1). Produce AnalysisResult with security-specific evidence. |
| **Acceptance Criteria** | Identifies known-bad hashes. Detects suspicious structures in test files. Produces structured evidence explaining findings. Handles all supported MIME types. |
| **Definition of Done** | Unit tests with malicious and benign test file fixtures. Merged. |

### E7.T5 — Implement OCR Analyzer

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E6.T3 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/analyzers/ocr_analyzer/`. Text extraction from images and PDFs. Use appropriate library (pytesseract, pdfplumber, or equivalent). Extract text content and include in analysis result evidence. Verdict is informational (text extraction, not judgment). Handle: corrupt images, password-protected PDFs (fail gracefully), large documents (page limit). |
| **Acceptance Criteria** | Extracts text from PDF and image test files. Handles corrupt/empty files without crashing. Respects page limits for large documents. |
| **Definition of Done** | Unit tests with varied test files. Merged. |

### E7.T6 — Implement Image Analyzer

| Field | Value |
|---|---|
| **Priority** | P2 |
| **Dependencies** | E6.T3, E7.T1 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/analyzers/image_analyzer/`. Image-specific analysis: EXIF metadata extraction, steganography indicators, image dimension/format validation. Optionally integrates with AI provider for visual content analysis. Produce AnalysisResult with image-specific evidence. |
| **Acceptance Criteria** | Extracts EXIF from JPEG. Validates image dimensions and format. Handles non-image files gracefully (skip or fail). |
| **Definition of Done** | Unit tests with varied image files. Merged. |

---

## Epic 8: Reporting

**Objective:** Report generation, PDF rendering, download endpoints.

**Architectural Owner:** Backend Lead (owns 02-Domain-Model Report entity, 04-Database-Design §9.4)

**Dependencies:** Epic 6.

**Deliverables:** All `/reports/*` endpoints. PDF generation and storage.

**Definition of Done:** Reports generated from analyses; PDFs stored in S3 and downloadable.

**Risks:** PDF library memory; concurrent generation; large report files.

---

### E8.T1 — Implement Report Domain Entity

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T10 |
| **Estimated Effort** | 3h |
| **Description** | Create `app/domain/entities/report.py` per 02-Domain-Model. Enforce invariants: references at least one Analysis, all referenced Analyses must belong to the same DigitalAsset (invariant 7), immutable once generated (state machine: draft → rendering → rendered/failed per 04-Database-Design §9.4). Soft-delete with 90-day retention. |
| **Acceptance Criteria** | Entity rejects analyses from different assets. Entity is immutable after rendering. State transitions enforce valid paths. |
| **Definition of Done** | Unit tests for all invariants. Merged. |

### E8.T2 — Implement PDF Generation Service

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E5.T1 |
| **Estimated Effort** | 6h |
| **Description** | Create `app/infrastructure/pdf/` (or `app/application/services/report_generator.py`). Generate PDF from Report data: title, asset metadata, verdict for each analysis, evidence details, confidence scores, recommendations. Use appropriate library (WeasyPrint, reportlab, or equivalent). Upload generated PDF to S3. Store S3 key on Report record. Handle generation failures: transition report to failed state. |
| **Acceptance Criteria** | Generated PDF is readable and well-formatted. PDF contains all analysis verdicts, evidence, and recommendations. PDF stored in S3 and retrievable. Generation failure transitions report to failed with error. |
| **Definition of Done** | Integration test: create report → generate PDF → download and verify content. Merged. |

### E8.T3 — Implement Report Service

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E8.T1, E8.T2 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/application/services/report_service.py`. Methods: `create_report(analysis_id) -> Report` (creates report from analysis, triggers PDF generation), `get_report(report_id)`, `list_reports(filters)`, `delete_report(report_id)` (soft-delete), `get_download_url(report_id) -> str` (presigned S3 URL). Cross-asset validation at Application layer. Audit log all operations. |
| **Acceptance Criteria** | Report creation validates all analyses reference the same asset. PDF generation is triggered on creation. Download URL is time-limited. Soft-delete excludes from queries. |
| **Definition of Done** | Unit tests. Integration tests. Merged. |

### E8.T4 — Implement Report Route Handlers

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E8.T3, E4.T4 |
| **Estimated Effort** | 4h |
| **Description** | Create `app/api/v1/routes/reports.py` per openapi.yaml. `POST /analyses/{analysisId}/report` (create from analysis), `GET /reports` (list, paginated), `GET /reports/{reportId}` (detail), `GET /reports/{reportId}/download` (redirect to presigned S3 URL or stream), `DELETE /reports/{reportId}` (soft-delete). |
| **Acceptance Criteria** | All responses match openapi.yaml schemas. Download returns PDF with correct content type. |
| **Definition of Done** | API tests for all endpoints. End-to-end: create report → download PDF. Merged. |

---

## Epic 9: Frontend

**Objective:** React client application for all user-facing workflows.

**Architectural Owner:** Frontend Lead (owns 06-Repository-Structure §15, UI/UX decisions)

**Dependencies:** Epics 4–8 (all backend APIs).

**Deliverables:** Working frontend application covering all Core Use Cases from 01-Product-Requirements §6.

**Definition of Done:** All user flows operational; E2E tests passing; accessibility baseline met.

**Risks:** Token refresh races; large upload UX; framework upgrade conflicts.

---

### E9.T1 — Initialize React Application

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E1.T1 |
| **Estimated Effort** | 3h |
| **Description** | Set up React application in `frontend/` per 06-Repository-Structure §15. Use Vite or equivalent build tool. Configure: TypeScript, ESLint, Prettier, CSS modules or equivalent. Set up API client module that points to backend URL from environment. Configure proxy for local development. |
| **Acceptance Criteria** | `npm run dev` serves the application. TypeScript compiles without errors. ESLint passes. API requests proxy to backend in development. |
| **Definition of Done** | Build succeeds. Merged. |

### E9.T2 — Implement Authentication UI

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E9.T1 |
| **Estimated Effort** | 6h |
| **Description** | Create: registration form, login form, logout button, auth context/provider. Implement JWT storage (httpOnly cookie or secure localStorage), automatic token refresh before expiry, redirect to login on 401. Protected route wrapper that redirects unauthenticated users. Display current user info from `GET /auth/me`. |
| **Acceptance Criteria** | User can register, login, and logout. Token refresh happens transparently. Expired session redirects to login. Protected pages inaccessible without auth. |
| **Definition of Done** | E2E test for auth flow. Merged. |

### E9.T3 — Implement Dashboard View

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E9.T2 |
| **Estimated Effort** | 4h |
| **Description** | Create dashboard showing: recent uploads (status), recent analyses (status, verdict), asset count, quick-action buttons (upload, view assets). Fetch data from `GET /uploads`, `GET /analyses`, `GET /assets`. Loading, empty, and error states for each section. |
| **Acceptance Criteria** | Dashboard renders with real data. Loading states shown during API calls. Empty state shown for new users. Error state shown if API fails. |
| **Definition of Done** | Visual review. E2E test for dashboard load. Merged. |

### E9.T4 — Implement Upload UI

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E9.T2 |
| **Estimated Effort** | 6h |
| **Description** | Create: drag-and-drop upload zone, file type validation (client-side per allow-list), size validation (client-side 100MB check), upload progress indicator, upload status display (pending → completed/failed). Use `POST /uploads` with multipart form data. Handle: multiple file upload, retry on failure, idempotency key generation. |
| **Acceptance Criteria** | Files can be dragged and dropped or selected via file picker. Invalid files rejected before upload. Progress shown during upload. Status updates to completed/failed. Duplicate files show deduplication result. |
| **Definition of Done** | E2E test for upload flow. Merged. |

### E9.T5 — Implement Asset Management UI

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E9.T2 |
| **Estimated Effort** | 4h |
| **Description** | Create: asset list view (paginated, searchable), asset detail view (metadata, linked uploads, linked analyses), delete confirmation dialog (soft-delete). Fetch from `GET /assets`, `GET /assets/{assetId}`. |
| **Acceptance Criteria** | Assets listed with pagination. Detail shows all metadata. Delete requires confirmation. Deleted assets disappear from list. |
| **Definition of Done** | E2E test for asset CRUD. Merged. |

### E9.T6 — Implement Analysis UI

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E9.T5 |
| **Estimated Effort** | 6h |
| **Description** | Create: "Analyze" button on asset detail, analyzer selection (from `GET /analyzers`), analysis status tracking (polling or SSE), analysis result display (verdict, evidence, confidence, recommendation with structured formatting), analysis list per asset. Cancel button for pending/running analyses. |
| **Acceptance Criteria** | User can select analyzer and request analysis. Status updates shown until completion. Result displays verdict, evidence, confidence, recommendation clearly. Cancel works for non-terminal analyses. |
| **Definition of Done** | E2E test for analysis flow. Merged. |

### E9.T7 — Implement Report UI

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E9.T6 |
| **Estimated Effort** | 4h |
| **Description** | Create: "Generate Report" button from analysis result, report list view, report status tracking, PDF download button. Fetch from `GET /reports`, `POST /analyses/{analysisId}/report`, `GET /reports/{reportId}/download`. |
| **Acceptance Criteria** | Report generated from analysis. Status shown during PDF generation. Download triggers PDF save. Report list shows all user reports. |
| **Definition of Done** | E2E test for report generation and download. Merged. |

### E9.T8 — Implement Admin UI

| Field | Value |
|---|---|
| **Priority** | P2 |
| **Dependencies** | E9.T2 |
| **Estimated Effort** | 4h |
| **Description** | Create admin-only views (hidden for non-admin users): user management (list, view, update role, deactivate), audit log viewer (list, filter by user/action/date range, detail). Fetch from `GET /users`, `GET /audit-logs`. |
| **Acceptance Criteria** | Admin views visible only to admin role. User management operations work correctly. Audit log filterable and paginated. Non-admin users see no admin UI elements. |
| **Definition of Done** | E2E test for admin access control. Merged. |

---

## Epic 10: Deployment & CI/CD

**Objective:** Production deployment pipeline, IaC, environment promotion, secrets management.

**Architectural Owner:** Infrastructure Lead (owns 09-Deployment-Architecture, 12-CI-CD-Architecture, 13-Release-Engineering)

**Dependencies:** Epics 1–8.

**Deliverables:** Automated pipeline: commit → build → test → staging → production.

**Definition of Done:** Zero-downtime deployment verified; rollback tested; secrets management operational.

**Risks:** Migration failures during deploy; secret rotation; IaC state drift.

---

### E10.T1 — Implement Multi-stage Docker Build

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E1.T4 |
| **Estimated Effort** | 3h |
| **Description** | Finalize `docker/Dockerfile.backend` per 12-CI-CD-Architecture §3. Multi-stage: (1) builder stage installs dependencies, (2) runtime stage copies only installed packages and app code. Minimal base image (python:3.12-slim). Non-root user. Health check instruction. Build args for version tagging. |
| **Acceptance Criteria** | Built image runs application correctly. Image size minimized (< 500MB). Runs as non-root. Health check works in Docker. |
| **Definition of Done** | CI builds and pushes image. Merged. |

### E10.T2 — Implement CI/CD Pipeline (Full)

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E1.T6 |
| **Estimated Effort** | 6h |
| **Description** | Extend `.github/workflows/ci.yml` per 12-CI-CD-Architecture §3–§6. Full pipeline: lint → type-check → unit tests → integration tests (containerized services) → API tests → build Docker image → push to registry → deploy to staging (automatic on main) → smoke tests → deploy to production (manual approval). Implement build-once-deploy-many: tag image with commit SHA, promote same image across environments. |
| **Acceptance Criteria** | Pipeline runs fully on merge to main. Staging deployment is automatic. Production deployment requires manual approval. Same image artifact promoted through environments. |
| **Definition of Done** | Full pipeline green. Deployment verified. Merged. |

### E10.T3 — Implement Infrastructure-as-Code

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | None |
| **Estimated Effort** | 8h |
| **Description** | Create `infrastructure/` per 06-Repository-Structure §12, 09-Deployment-Architecture §2. Define: VPC/network, PostgreSQL instance, Redis instance, S3 bucket, container orchestration (ECS/Cloud Run/equivalent), load balancer, DNS. Use Terraform or equivalent. Environment-specific configurations via variable files. |
| **Acceptance Criteria** | `terraform plan` produces clean plan. `terraform apply` creates working infrastructure. Environment parity between staging and production (same topology, different scale). |
| **Definition of Done** | Staging environment provisioned from IaC. Production environment provisioned from IaC. Merged. |

### E10.T4 — Implement Secrets Management

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E10.T3 |
| **Estimated Effort** | 4h |
| **Description** | Per 08-Security-Architecture §11. Store all secrets in cloud provider secret manager (AWS Secrets Manager, GCP Secret Manager, or equivalent). Application reads secrets at startup. No secrets in source control, Docker images, or environment files committed to git. Configure secret rotation for database credentials and JWT signing key. |
| **Acceptance Criteria** | Application starts and reads secrets from secret manager. No secrets in git history. Rotation procedure documented and tested. |
| **Definition of Done** | Security review: no secrets in code/images/logs. Merged. |

### E10.T5 — Implement Database Migration Pipeline

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E3.T2, E10.T2 |
| **Estimated Effort** | 4h |
| **Description** | Per 12-CI-CD-Architecture §4. Migrations run as a pre-deployment step (init container or migration job), not during application startup. Implement expand-and-contract pattern for zero-downtime migrations. Migration failure blocks deployment. Rollback procedure: downgrade migration + redeploy previous image. |
| **Acceptance Criteria** | Migrations run before new application version starts. Migration failure prevents deployment. Application starts cleanly against migrated schema. |
| **Definition of Done** | Tested with a real schema change through the pipeline. Merged. |

### E10.T6 — Implement Rollback Procedure

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E10.T2 |
| **Estimated Effort** | 3h |
| **Description** | Per 13-Release-Engineering §5. Document and automate: redeploy previous container image, downgrade database migration if needed, verify rollback health. Rollback must complete within 5 minutes. Create runbook entry per 20-Operations-Runbook. |
| **Acceptance Criteria** | Rollback to previous version completes within 5 minutes. Health check passes after rollback. No data loss during rollback. |
| **Definition of Done** | Rollback executed and verified at least once. Runbook documented. Merged. |

---

## Epic 11: Observability

**Objective:** Structured logging, metrics, tracing, alerting, dashboards.

**Architectural Owner:** Infrastructure Lead (owns 10-Observability-Architecture)

**Dependencies:** Epics 2–8 (instrumentation added to existing code).

**Deliverables:** Full observability stack per 10-Observability-Architecture.

**Definition of Done:** Every endpoint and worker emits metrics; traces span the full pipeline; alerts fire on SLO breach.

**Risks:** Performance overhead; alert fatigue; tooling costs.

---

### E11.T1 — Implement Metrics Collection

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E2.T2 |
| **Estimated Effort** | 4h |
| **Description** | Per 10-Observability-Architecture §5. Integrate Prometheus client. Instrument: HTTP request count/latency/status (middleware), worker job count/duration/outcome, queue depth gauge, database query duration, S3 operation duration. Expose `/metrics` endpoint (no auth, internal-only via network policy). |
| **Acceptance Criteria** | `/metrics` returns Prometheus-format metrics. All instrumented operations produce data under load. |
| **Definition of Done** | Metrics verified with test requests. Merged. |

### E11.T2 — Implement Distributed Tracing

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E2.T4 |
| **Estimated Effort** | 4h |
| **Description** | Per 10-Observability-Architecture §6. Integrate OpenTelemetry SDK. Instrument: API request spans, database query spans, S3 operation spans, queue publish/claim spans, analyzer execution spans. Propagate trace context from API → queue → worker via `X-Request-ID`. Configure sampling rate from settings. Export to Jaeger or equivalent. |
| **Acceptance Criteria** | A single API request produces a trace with spans across all touched components. Worker jobs carry the originating trace context. Sampling rate is configurable. |
| **Definition of Done** | End-to-end trace verified for upload → analyze flow. Merged. |

### E11.T3 — Implement Alerting Rules

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E11.T1 |
| **Estimated Effort** | 4h |
| **Description** | Per 10-Observability-Architecture §8. Define Prometheus alerting rules: API error rate > 1% for 5 minutes, API p95 latency > 2s for 5 minutes, queue depth growing for 10 minutes, worker failure rate > 5%, database connection pool exhaustion, disk usage > 80%. Configure notification channels (email, Slack, PagerDuty). |
| **Acceptance Criteria** | Rules fire correctly when thresholds are breached (tested with synthetic failure). Rules resolve when condition clears. |
| **Definition of Done** | All rules tested with synthetic failures. Merged. |

### E11.T4 — Create Observability Dashboards

| Field | Value |
|---|---|
| **Priority** | P2 |
| **Dependencies** | E11.T1 |
| **Estimated Effort** | 4h |
| **Description** | Create Grafana dashboards (or equivalent) per 10-Observability-Architecture: API overview (request rate, latency percentiles, error rate, status code distribution), Worker overview (job rate, duration, outcome, queue depth), Infrastructure (DB connections, query latency, S3 latency, Redis operations), Business metrics (uploads per day, analyses per day, active users). |
| **Acceptance Criteria** | Dashboards load with real data. Time range selection works. Panels refresh automatically. |
| **Definition of Done** | Dashboards deployed to staging. Merged. |

---

## Epic 12: Production Hardening

**Objective:** Security hardening, load testing, backup/restore, on-call readiness.

**Architectural Owner:** Security Lead + Infrastructure Lead (joint ownership: 08-Security-Architecture §12–14, 14-Performance-and-Scalability, 15-Disaster-Recovery)

**Dependencies:** Epics 10–11.

**Deliverables:** Security scan clean, load test baseline, backup/restore verified, runbooks validated.

**Definition of Done:** 14-day stability window met; SLOs sustained; on-call operational.

**Risks:** Unexpected traffic patterns; novel failure modes; alert fatigue.

---

### E12.T1 — Run Dependency Vulnerability Scan

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E1.T2 |
| **Estimated Effort** | 3h |
| **Description** | Per 08-Security-Architecture §12. Configure automated dependency scanning (Dependabot, Snyk, or pip-audit) in CI. Run scan against all Python and Node.js dependencies. Fix or document all high/critical findings. Add container image scanning (Trivy or equivalent). |
| **Acceptance Criteria** | Scan runs in CI on every PR. Zero high/critical findings in current dependencies. Container image scan clean. |
| **Definition of Done** | CI integration verified. All findings addressed. Merged. |

### E12.T2 — Implement Secret Scanning

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | None |
| **Estimated Effort** | 2h |
| **Description** | Per 08-Security-Architecture §12. Configure GitHub secret scanning and/or gitleaks in pre-commit hooks. Scan git history for accidentally committed secrets. |
| **Acceptance Criteria** | Commit containing a secret pattern is blocked. Historical scan produces no findings (or findings are remediated). |
| **Definition of Done** | Pre-commit hook active. CI check active. Merged. |

### E12.T3 — Execute Load Testing

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E10.T2 |
| **Estimated Effort** | 6h |
| **Description** | Per 14-Performance-and-Scalability-Architecture. Define load test scenarios: concurrent uploads, concurrent analysis requests, concurrent report downloads, mixed workload. Use k6, locust, or equivalent. Run against staging environment. Establish baseline metrics: p50/p95/p99 latency, throughput, error rate under load. Test 10x expected peak load. |
| **Acceptance Criteria** | System handles 10x expected load without error rate exceeding 1%. p95 API latency under 2s under load. No OOM kills under load. Results documented with graphs and analysis. |
| **Definition of Done** | Load test report produced. Bottlenecks identified and addressed (or documented as accepted risk). Merged. |

### E12.T4 — Implement Backup and Restore

| Field | Value |
|---|---|
| **Priority** | P0 |
| **Dependencies** | E10.T3 |
| **Estimated Effort** | 4h |
| **Description** | Per 15-Disaster-Recovery §3–§5. Configure automated PostgreSQL backups (daily full + WAL archiving for PITR). Document restore procedure. Test restore to a clean instance. Configure S3 bucket versioning for object storage durability. |
| **Acceptance Criteria** | Backup completes automatically on schedule. Restore to clean instance produces a working system with all data. PITR recovery to specific timestamp verified. |
| **Definition of Done** | Restore tested end-to-end. Runbook documented. Merged. |

### E12.T5 — Implement Data Retention Jobs

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E5.T8 |
| **Estimated Effort** | 4h |
| **Description** | Per 04-Database-Design §9.5–§9.6. Implement scheduled jobs: hard-delete soft-deleted assets/reports after 90-day retention window, purge expired refresh tokens daily, archive analyses and audit logs older than 2 years to Parquet format in S3 before hard-deleting from PostgreSQL. |
| **Acceptance Criteria** | Retention windows enforced correctly. Archived data accessible from S3. Active data unaffected. |
| **Definition of Done** | Integration tests with time-manipulated data. Merged. |

### E12.T6 — Validate Operational Runbooks

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E10.T6 |
| **Estimated Effort** | 4h |
| **Description** | Per 20-Operations-Runbook. Execute each documented runbook against the production-like staging environment: deployment, rollback, database restore, incident response, secret rotation, scaling workers. Fix any runbook that doesn't work as documented. |
| **Acceptance Criteria** | Every runbook procedure is executable as written. No undocumented prerequisites or missing steps. |
| **Definition of Done** | All runbooks validated. Fixes merged. |

### E12.T7 — Establish On-Call and Incident Response

| Field | Value |
|---|---|
| **Priority** | P1 |
| **Dependencies** | E11.T3 |
| **Estimated Effort** | 3h |
| **Description** | Per 15-Disaster-Recovery §7, 20-Operations-Runbook. Set up on-call rotation (PagerDuty or equivalent). Configure alert routing. Define escalation policy. Conduct at least one incident response drill (simulated failure). |
| **Acceptance Criteria** | On-call engineer receives alerts within 5 minutes. Escalation policy documented. At least one drill completed. |
| **Definition of Done** | Rotation staffed. Drill report documented. Merged. |

---

## Task Summary

| Epic | Task Count | Total Estimated Effort |
|---|---|---|
| E1: Repository Foundation | 7 | ~19h |
| E2: Backend Core | 9 | ~25h |
| E3: Database & Persistence | 11 | ~34h |
| E4: Authentication & Authorization | 8 | ~26h |
| E5: Asset Upload & Management | 8 | ~30h |
| E6: Analysis Engine | 8 | ~30h |
| E7: AI Providers & Analyzers | 6 | ~25h |
| E8: Reporting | 4 | ~17h |
| E9: Frontend | 8 | ~37h |
| E10: Deployment & CI/CD | 6 | ~28h |
| E11: Observability | 4 | ~16h |
| E12: Production Hardening | 7 | ~26h |
| **Total** | **86** | **~313h** |

---

*This backlog is derived entirely from the approved architecture (Documents 00–20 and backend/openapi.yaml). Every task traces to a specific document section. No task introduces undocumented features or architectural changes. An engineering team can begin implementation immediately from this backlog without creating additional planning documents.*


---

## Backlog Traceability

Every completed backlog task should be traceable to the originating architecture documents, OpenAPI contract, implementation commit(s), automated tests, and verification evidence. This maintains end-to-end auditability throughout the project lifecycle.
