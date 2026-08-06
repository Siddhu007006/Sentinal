# E3.T7 — Repository Pattern & Query Optimization — Requirements Specification

## Document Information

| Field | Value |
|---|---|
| **Feature Name** | epic-3-database-foundation-repositories-t7 |
| **Task ID** | E3.T7 |
| **Specification Version** | 1.0.0 |
| **Status** | Draft (Awaiting Review) |
| **Owner** | Engineering Team |
| **Audience** | Engineers, Code Reviewers, Architects |
| **Dependencies** | E3.T1–E3.T6 (all ORM models complete), 03-Architecture §4 (Domain layer), 04-Database-Design §11 (Query Patterns) |
| **Last Updated** | 2026-08-02 |

---

## 1. Introduction

### 1.1 Purpose

This specification defines requirements for implementing the **Repository Pattern** and **Query Optimization Layer** for the Sentinel persistence architecture.

The Repository Pattern creates an abstraction boundary between the Domain/Application layers and the Infrastructure (database) layer. It provides:
- **CRUD Abstraction:** Create, Read, Update, Delete operations behind a simple interface
- **Query Encapsulation:** Complex queries (with N+1 prevention, pagination, sorting) defined in one place
- **Testing Enablement:** Mock repositories allow testing business logic without a database
- **Database Agnosticism:** Domain layer has no SQLAlchemy imports; can swap implementations

This task implements repository interfaces (Domain layer) and PostgreSQL implementations (Infrastructure layer) for four core entities with ORM models (User, Upload, DigitalAsset, Analysis). It also establishes query optimization patterns (eager loading strategies, batch operations, index utilization) to prevent performance degradation as data grows. Report and RefreshToken repositories are deferred to E3.T8–E3.T9 when their ORM models are introduced.

### 1.2 Scope

**In Scope (Phase A — E3.T7):**
- 4 repository interface definitions for entities with existing ORM models (User, Upload, DigitalAsset, Analysis)
- 4 PostgreSQL repository implementations using SQLAlchemy async sessions
- Query optimization patterns (eager loading, selectin loading, batch operations)
- Pagination and sorting implementations
- Soft-delete filtering for User and DigitalAsset
- N+1 query prevention via lazy loading strategies and explicit loading
- Transaction demarcation and rollback safety
- Error mapping (database exceptions → domain exceptions)

**Future Scope (Phase B — E3.T8–E3.T9, when ORM models created):**
- Report repository (deferred until Report ORM model exists)
- RefreshToken repository (deferred until RefreshToken ORM model exists)

**Out of Scope:**
- Application services or use cases (covered in E4)
- API endpoint implementations (covered in E4)
- Cache layer (Redis caching, if added, is future work)
- Read replicas or query optimization beyond single-instance PostgreSQL
- Audit logging queries (covered in E3.T8)

---

## 2. Glossary

| Term | Definition |
|---|---|
| **Repository** | An abstraction representing a collection of entities. CRUD operations go through the repository interface, not direct ORM access. |
| **Repository Interface** | Abstract base class (ABC) defining methods the Domain layer needs. Lives in `domain/repositories/`. |
| **Repository Implementation** | Concrete class using SQLAlchemy implementing the interface. Lives in `infrastructure/database/repositories/`. |
| **Query Optimization** | Techniques to prevent performance degradation: eager loading (joinedload/selectin), batch operations, index utilization. |
| **N+1 Query Problem** | Anti-pattern where fetching a collection of entities leads to 1 query for the collection + N queries for related objects. Solution: eager loading. |
| **Lazy Loading** | Deferring the load of related objects until accessed. SQLAlchemy's `relationship(lazy='select')` by default. |
| **Eager Loading** | Loading related objects in the same query as the parent. SQLAlchemy's `joinedload()` or `selectin()`. |
| **Pagination** | Returning results in pages (limit, offset). Necessary for large result sets (e.g., 1M analyses). |
| **Soft-Delete** | Marking records as deleted (deleted_at column) rather than removing from DB. Enables audit trails and recovery. |
| **Idempotency** | Repeated operations produce the same result. Repositories support this by checking uniqueness before insert. |
| **Transaction Scope** | ACID transaction boundary: begins on request start, commits on success, rolls back on exception. Per-request via FastAPI dependency. |
| **Domain Exception** | Exception defined in domain/ layer (e.g., `UserNotFound`, `AnalysisAlreadyExists`). Infrastructure catches DB exceptions and converts to domain exceptions. |

---

## 3. Requirements

### Requirement R1: Domain Repository Interfaces

**User Story:** As a Domain layer developer, I need repository interfaces so that business logic depends on abstract contracts, not concrete SQLAlchemy implementations.

#### Acceptance Criteria

1. Repository interfaces exist for 4 entities with ORM models: User, Upload, DigitalAsset, Analysis (Phase A)
2. Each interface is an abstract base class (Python `abc.ABC`) with `@abstractmethod` decorators
3. Interfaces live in `backend/app/domain/repositories/` (Domain layer, not Infrastructure)
4. Interfaces do NOT import SQLAlchemy, ORM models, or infrastructure code
5. Each interface defines all CRUD operations: `create()`, `get_by_id()`, `list()`, `update()`, `delete()`
6. Each interface defines domain-specific query methods (e.g., `UserRepository.get_by_email()`)
7. All methods have type hints with domain entity types (not ORM models)
8. All methods define their exception contract (e.g., `get_by_id()` raises `NotFound` if entity not found)

---

### Requirement R2: PostgreSQL Repository Implementations

**User Story:** As an Infrastructure developer, I need concrete repository implementations so that CRUD operations execute against PostgreSQL without leaking database details to the Domain layer.

#### Acceptance Criteria

1. PostgreSQL implementations exist for 4 repositories in `backend/app/infrastructure/database/repositories/`: User, Upload, DigitalAsset, Analysis (Phase A)
2. Each implementation inherits from its corresponding Domain interface
3. Each implementation receives an `AsyncSession` via constructor injection (not global/singleton)
4. All implementations follow async/await pattern (async methods, await database calls)
5. All CRUD methods are implemented: `create()`, `get_by_id()`, `list()`, `update()`, `delete()`
6. All domain-specific queries are implemented
7. All methods return domain entity types (not ORM models) or raise domain exceptions
8. Database exceptions (IntegrityError, NoResultFound) are caught and converted to domain exceptions
9. Soft-delete filtering is applied by default to `list()` and `get_by_id()` for entities with soft-delete support (User, DigitalAsset)

---

### Requirement R3: CRUD Operations

**User Story:** As a service developer, I need repository CRUD operations to persist and retrieve entities without writing SQL or ORM code directly.

#### Acceptance Criteria

1. `create(entity) -> Entity` — Inserts a new entity, returns the persisted entity with generated ID and timestamps
2. `get_by_id(id: UUID) -> Entity` — Retrieves entity by ID; raises `NotFound` if not found
3. `list(skip: int, limit: int, **filters) -> List[Entity]` — Returns paginated results with optional filters
4. `update(id: UUID, updates: dict) -> Entity` — Updates entity fields, returns updated entity
5. `delete(id: UUID) -> None` — Soft-deletes (sets deleted_at) for soft-delete entities; hard-deletes for audit logs
6. All CRUD methods respect the per-request transaction scope (commit/rollback handled by caller, not repository)
7. All CRUD methods are idempotent where applicable (e.g., delete on non-existent entity is no-op, not error)

---

### Requirement R4: Domain-Specific Query Methods

**User Story:** As a service developer, I need efficient queries for common business operations so that I don't have to construct complex SQLAlchemy queries in the application layer.

#### Acceptance Criteria

**Phase A (E3.T7):**

1. **UserRepository:**
   - `get_by_email(email: str) -> User` — Case-insensitive email lookup
   - `list_active_users(skip, limit) -> List[User]` — Filter by is_active=true

2. **UploadRepository:**
   - `get_by_storage_key(storage_key: str) -> Upload` — Query by storage location
   - `list_by_user(user_id: UUID, skip, limit) -> List[Upload]` — User's uploads
   - `list_by_status(status: str, skip, limit) -> List[Upload]` — Filter by upload status

3. **DigitalAssetRepository:**
   - `get_by_hash(sha256_hash: str) -> DigitalAsset` — Content-addressed lookup (primary query pattern)
   - `list_by_user(user_id: UUID, skip, limit) -> List[DigitalAsset]` — User's assets
   - `get_by_normalized_value(asset_type: str, value: str) -> DigitalAsset` — URL/IP/domain/file deduplication

4. **AnalysisRepository:**
   - `get_completed_analysis(asset_id: UUID, analyzer_key: str, analyzer_version: str) -> Analysis` — Idempotency check
   - `list_by_asset(asset_id: UUID, skip, limit) -> List[Analysis]` — All analyses for an asset
   - `list_by_status(status: str, skip, limit) -> List[Analysis]` — Filter by status (pending, running, completed, failed)
   - `list_pending_for_worker(limit: int) -> List[Analysis]` — Worker job queue (oldest pending first)
   - `list_by_user(user_id: UUID, skip, limit) -> List[Analysis]` — User's analysis history

**Phase B (E3.T8–E3.T9, deferred):**
- ReportRepository methods (when ORM model created)
- RefreshTokenRepository methods (when ORM model created)

---

### Requirement R5: Query Optimization - N+1 Prevention

**User Story:** As a performance engineer, I need N+1 prevention patterns so that fetching a list of entities doesn't trigger cascading queries.

#### Acceptance Criteria

1. When `AnalysisRepository.list_by_asset(asset_id)` retrieves 100 analyses, the query should NOT result in 101 database calls (1 for analyses + 100 for related assets)
2. Lazy loading strategies from E3.T5/E3.T6 designs are applied (selectin for FK relationships by default)
3. Repository methods can explicitly override lazy loading for specific use cases (e.g., `joinedload()` for performance-critical paths that always need relationships)
4. Batch operations are used where applicable (e.g., `SELECT IN` for fetching multiple related objects)
5. Result of `list_by_asset()` includes DigitalAsset relationship without additional queries (via selectin or joinedload per design)

---

### Requirement R6: Pagination and Sorting

**User Story:** As an API developer, I need pagination and sorting so that endpoints can return large result sets in manageable pages without memory overload.

#### Acceptance Criteria

1. All `list_*()` methods accept `skip` (offset) and `limit` (per-page count) parameters
2. Pagination returns not just the page of results, but also total count for UI pagination controls
3. All `list_*()` methods support sorting (e.g., `sort_by`, `sort_order: asc|desc`)
4. Default sort order is `created_at DESC` (newest first) where applicable
5. Sorting is applied at the database level (via ORDER BY), not in Python
6. Limit is enforced at database level (LIMIT clause), not in application code

---

### Requirement R7: Soft-Delete Handling

**User Story:** As a compliance officer, I need soft-delete support so that deleted records are preserved for audit trails and can potentially be restored.

#### Acceptance Criteria

1. Soft-delete filtering is applied by default to User and DigitalAsset repositories
2. `UserRepository.list()` and `DigitalAsset.list()` implicitly filter `WHERE deleted_at IS NULL`
3. `UserRepository.get_by_id()` and `DigitalAsset.get_by_id()` implicitly filter by soft-delete
4. `get_by_email()` and other domain-specific queries also filter by soft-delete
5. Hard-delete repositories (AuditLog, RefreshToken) do NOT filter soft-delete
6. If a user needs to retrieve soft-deleted records, an explicit method `list_all_including_deleted()` exists (for administrative use)
7. On `delete(id)`, soft-delete entities have `deleted_at = now()` set; hard-delete entities are removed entirely

---

### Requirement R8: Error Handling and Domain Exceptions

**User Story:** As a Domain developer, I need repositories to throw domain exceptions so that I can handle errors using domain language, not database-specific exceptions.

#### Acceptance Criteria

1. Database exceptions (IntegrityError, NoResultFound, etc.) are caught and converted to domain exceptions
2. Domain exceptions are defined in `backend/app/domain/exceptions.py`: `NotFound`, `AlreadyExists`, `ConstraintViolation`, `ConflictError`
3. `get_by_id(id)` raises `NotFound` if entity not found (not empty list, not None)
4. `create()` raises `AlreadyExists` if unique constraint violated (e.g., duplicate email)
5. `create()` raises `ConstraintViolation` if FK or CHECK constraint violated
6. All error messages are domain-focused (e.g., "User with email already exists" not "UNIQUE constraint failed on email")

---

### Requirement R9: Transaction Safety

**User Story:** As a data integrity engineer, I need transaction safety so that all database changes are atomic (all-or-nothing) and consistent.

#### Acceptance Criteria

1. Repositories do NOT manage transaction lifecycle (no `session.commit()` or `session.rollback()` in repository code)
2. Transaction lifecycle is managed by FastAPI dependency (request scope: begin on request start, commit on success, rollback on exception)
3. All repository methods execute within the current transaction context
4. If a repository method raises an exception, the entire transaction is rolled back (automatic via FastAPI session cleanup)
5. Multiple repository operations in a single request are part of the same transaction (atomic)

---

### Requirement R10: Testability

**User Story:** As a test developer, I need repositories to be mockable so that I can test business logic without a database.

#### Acceptance Criteria

1. Repository interfaces are pure Python ABCs (no SQLAlchemy imports)
2. Mock repositories can be implemented for testing without any database setup
3. FastAPI dependency injection allows swapping real repositories with mocks in tests
4. Repository return types are domain entities (not ORM models), making them easy to construct in test fixtures

---

## 4. Entity Dependency Matrix

The following table documents which repositories are in scope for E3.T7 (Phase A) and which are deferred to future tasks (Phase B):

| Repository | ORM Model Exists | E3.T7 Scope | Status | Notes |
|---|---|---|---|---|
| **User** | ✅ Yes (`user.py`) | ✅ Phase A | Ready | Soft-delete support via `deleted_at` field |
| **Upload** | ✅ Yes (`upload.py`) | ✅ Phase A | Ready | Immutable after creation |
| **DigitalAsset** | ✅ Yes (`digital_asset.py`) | ✅ Phase A | Ready | Soft-delete support via `deleted_at` field |
| **Analysis** | ✅ Yes (`analysis.py`) | ✅ Phase A | Ready | Complex N+1 optimization needed |
| **Report** | ❌ Not yet | ⏸️ Phase B | Deferred | ORM model will be created in E3.T8; repository deferred until then |
| **RefreshToken** | ❌ Not yet | ⏸️ Phase B | Deferred | ORM model will be created in E3.T8; repository deferred until then |

**Phase A Deliverables:** 4 repositories (User, Upload, DigitalAsset, Analysis)  
**Phase B Deliverables:** 2 repositories (Report, RefreshToken) — Scheduled for E3.T8–E3.T9

---

## 5. Acceptance Criteria Summary

---

## 5. Acceptance Criteria Summary

| AC Count | Requirement | Domain | Phase |
|---|---|---|---|
| 8 | R1 (Domain Interfaces) | Abstraction & Design | A |
| 9 | R2 (PostgreSQL Implementations) | Persistence & Implementation | A |
| 7 | R3 (CRUD Operations) | Core Operations | A |
| 13 | R4 (Domain-Specific Queries — 4 entities) | Query Patterns | A |
| 5 | R5 (N+1 Prevention) | Performance | A |
| 6 | R6 (Pagination & Sorting) | Scalability | A |
| 7 | R7 (Soft-Delete) | Data Governance | A |
| 6 | R8 (Error Handling) | Reliability | A |
| 5 | R9 (Transaction Safety) | Correctness | A |
| 4 | R10 (Testability) | Quality | A |
| **TOTAL (Phase A)** | **10 Requirements** | **67 Acceptance Criteria** | **Phase A** |
| **FUTURE (Phase B)** | Reports & RefreshToken | 2 additional repositories | E3.T8–E3.T9 |

---

## 6. Definition of Done

**Requirements Approval Checklist:**
- [ ] All 10 requirements (R1–R10) reviewed and understood
- [ ] 4 core repositories identified (User, Upload, DigitalAsset, Analysis)
- [ ] Report and RefreshToken repositories explicitly deferred to Phase B (E3.T8–E3.T9)
- [ ] Query optimization patterns (N+1 prevention, lazy loading) confirmed
- [ ] Soft-delete behavior for User, DigitalAsset confirmed
- [ ] Domain exception types identified
- [ ] Transaction scope model confirmed (FastAPI request lifecycle)
- [ ] Error handling strategy confirmed
- [ ] Pagination/sorting behavior confirmed
- [ ] Specification approved by user before proceeding to Design phase

---

## 7. Design Decisions Deferred to Design Phase

The following design decisions will be finalized during the Design specification phase:

1. **Query Builder Pattern** — Whether to implement a fluent query builder vs direct method definitions
2. **Eager Loading Trade-offs** — Specific joinedload vs selectin decisions for each repository method
3. **Cache Invalidation** — If caching is added, invalidation strategy (not in scope for E3.T7, but architecture should support)
4. **Batch Operation Optimization** — Specific use of SQLAlchemy bulk operations (bulk_insert_mappings, bulk_update_mappings)
5. **Error Mapping** — Exact mapping between database exceptions and domain exceptions

---

## 8. Requirements Traceability

| Requirement | Traces To |
|---|---|
| R1 — Domain Interfaces | 03-Architecture §4 (Domain layer), 06-Repository-Structure §7 |
| R2 — PostgreSQL Implementations | 03-Architecture §3 (Infrastructure layer), 06-Repository-Structure §8 |
| R3 — CRUD Operations | 04-Database-Design §11 (Query Patterns), 03-Architecture §3 (Infrastructure) |
| R4 — Domain-Specific Queries | 04-Database-Design §11.1–§11.6 (Common query patterns) |
| R5 — N+1 Prevention | 03-Architecture §3 (Design for testability), E3.T5–E3.T6 lazy loading strategies |
| R6 — Pagination & Sorting | 05-API-Specification (pagination schema), 04-Database-Design §11 (offset/limit patterns) |
| R7 — Soft-Delete | 04-Database-Design §10 (Soft-delete strategy), 02-Domain-Model (entity lifecycle) |
| R8 — Error Handling | 05-API-Specification (error codes), 08-Security-Architecture (error message security) |
| R9 — Transaction Safety | 03-Architecture §3 (Transaction boundaries), 07-Backend-Development-Standards §7 |
| R10 — Testability | 11-Testing-Strategy (unit test dependencies), 07-Backend-Development-Standards §8 |

---

## 9. Key Business Rules (Not Implementation Details)

1. **Repository Abstraction:** Repositories are the ONLY way the Domain and Application layers access the database. No direct ORM imports in those layers.
2. **Query Encapsulation:** Complex queries (those touching multiple tables or requiring index optimization) are defined in repositories, not scattered through the codebase.
3. **Soft-Delete Default:** By default, User and DigitalAsset queries filter soft-deleted records. Retrieving deleted records requires explicit opt-in.
4. **Idempotency:** Repositories support idempotent operations (e.g., `delete()` on non-existent entity is safe).
5. **Transaction Isolation:** All database changes within a request are atomic (all commit or all rollback).
6. **Domain Language:** Error messages and exceptions use domain terminology, not database terminology.
7. **No ORM Leakage:** Domain and Application layers have zero imports from SQLAlchemy or `models/`. Only Infrastructure layer imports ORM.

</content>
