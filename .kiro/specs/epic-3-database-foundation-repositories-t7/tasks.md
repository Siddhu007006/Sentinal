# E3.T7 — Repository Pattern & Query Optimization — Tasks Specification

## Document Information

| Field | Value |
|---|---|
| **Feature Name** | epic-3-database-foundation-repositories-t7 |
| **Task ID** | E3.T7 |
| **Specification Version** | 1.0.0 |
| **Status** | Tasks Phase (Ready for Implementation) |
| **Owner** | Engineering Team |
| **Audience** | Engineers, Code Reviewers, QA |
| **Dependencies** | Requirements.md approved, Design.md approved, E3.T1–E3.T6 complete |
| **Last Updated** | 2026-08-02 |

---

## 1. Purpose, Scope, Dependencies

### 1.1 Purpose

This Tasks specification breaks down E3.T7 implementation into 9 sequential, independently verifiable tasks. Each task has a clear objective, measurable acceptance criteria, and traceability to requirements and design.

### 1.2 Scope

**In Scope:**
- 9 implementation tasks (T1–T9)
- Task dependency graph (DAG)
- Acceptance criteria for each task
- Verification procedures

**Out of Scope:**
- Actual code implementation (done in each task)
- Code review (separate workflow)

### 1.3 Dependencies

| Dependency | Status | Note |
|---|---|---|
| Requirements.md | ✅ Approved | Business requirements frozen |
| Design.md | ✅ Approved | Technical design frozen |
| E3.T1–T6 | ✅ Complete | ORM models ready |
| FastAPI | ✅ Available | Dependency injection |
| SQLAlchemy 2.0+ | ✅ Available | Async ORM |
| asyncpg | ✅ Available | PostgreSQL driver |

---

## 2. Task Dependency Graph (DAG)

**Phase A (E3.T7 Scope):**

```
T1: Domain Exceptions
  ↓
T2: Base Repository Interface & Error Mapping
  ↓
T3: Specific Repository Interfaces (4 entities: User, Upload, DigitalAsset, Analysis)
  ↓
T4: Base PostgreSQL Repository Implementation
  ↓
T5: UserRepository Implementation
  ↓
T6: AnalysisRepository Implementation (most complex)
  ↓
T7: UploadRepository & DigitalAssetRepository (2 remaining Phase A repositories)
  ↓
T8: Dependency Injection & FastAPI Integration
  ↓
T9: Repository Unit Tests & Integration Tests
  ↓
[COMPLETE — Phase A Ready]
  ↓
[Phase B DEFERRED to E3.T8–E3.T9: Report & RefreshToken repositories]
```

**Parallelizable Tasks:** 
- T5, T6, T7 can run in parallel after T4 (each is independent repository)
- But sequential execution recommended for clarity

**Critical Path:** All 9 Phase A tasks on critical path (no slack).

---

## 3. Task Breakdown

### Task T1: Implement Domain Exceptions

**Objective:** Create exception types used by repositories to signal errors in domain language.

**Dependencies:** None (first task).

**Implementation Steps:**

1. Create file: `backend/app/domain/exceptions.py`
2. Define exception hierarchy:
   - `RepositoryException` (base)
   - `NotFound` (entity not found in `get_by_id()`)
   - `AlreadyExists` (unique constraint violation in `create()`)
   - `ConstraintViolation` (FK or CHECK constraint violation)
   - `ConflictError` (other data integrity violations)
3. Add docstrings explaining when each exception is raised
4. Run linting: `ruff check app/domain/exceptions.py`

**Verification Steps:**

1. Import all exceptions: `from app.domain.exceptions import NotFound, AlreadyExists, ...`
2. Verify each exception is a proper Exception subclass
3. Verify exception messages are domain-focused (not SQLAlchemy-specific)
4. Verify no imports from infrastructure or ORM

**Acceptance Criteria:**

- [x] All 5 exception types defined in `domain/exceptions.py`
- [x] Each exception has a docstring
- [x] No infrastructure imports (no SQLAlchemy)
- [x] No linting errors

**Definition of Done:**

- Code passes linting
- Imports succeed
- Ready for T2

**Traceability:**

- R8 (Error Handling) → Exception types defined

---

### Task T2: Implement Base Repository Interface & Error Mapping

**Objective:** Create the abstract base repository interface and the error mapping function.

**Dependencies:** T1 (exceptions).

**Implementation Steps:**

1. Create `backend/app/domain/repositories/base.py`
   - Define `BaseRepository[T]` ABC with generic type parameter
   - Define abstract methods: `create()`, `get_by_id()`, `list()`, `update()`, `delete()`
   - Add type hints for all methods
   - Each method has a docstring

2. Create `backend/app/infrastructure/database/repositories/exceptions.py`
   - Implement `map_db_exception()` function
   - Catch SQLAlchemy exceptions (IntegrityError, NoResultFound, etc.)
   - Convert to domain exceptions (NotFound, AlreadyExists, etc.)
   - Preserve error messages

3. Run mypy and linting

**Verification Steps:**

1. Import BaseRepository: `from app.domain.repositories import BaseRepository`
2. Verify all abstract methods are present
3. Test error mapping function:
   - `map_db_exception(NoResultFound()) → NotFound`
   - `map_db_exception(IntegrityError(...)) → AlreadyExists (for UNIQUE)`
   - `map_db_exception(IntegrityError(...)) → ConstraintViolation (for FK)`

**Acceptance Criteria:**

- [x] BaseRepository ABC created with 5 abstract methods
- [x] All methods have type hints and docstrings
- [x] Error mapping function handles 3+ SQLAlchemy exception types
- [x] Error messages are domain-focused
- [x] No linting/type errors

**Definition of Done:**

- Interfaces pass type checking
- Error mapping tested
- Ready for T3

**Traceability:**

- R1 (Domain Interfaces) → BaseRepository ABC
- R8 (Error Handling) → Exception mapping

---

### Task T3: Implement Specific Repository Interfaces

**Objective:** Create repository interfaces for 4 core entities with ORM models (User, Upload, DigitalAsset, Analysis).

**Dependencies:** T2 (Base interface).

**Implementation Steps:**

1. Create 4 files in `backend/app/domain/repositories/` (Phase A):
   - `user.py` → UserRepository (with `get_by_email()`, `list_active_users()`)
   - `upload.py` → UploadRepository
   - `digital_asset.py` → DigitalAssetRepository
   - `analysis.py` → AnalysisRepository (with `get_completed_analysis()`, `list_by_asset()`, `list_pending_for_worker()`)

2. Each interface:
   - Inherits from `BaseRepository[EntityType]`
   - Defines domain-specific query methods
   - All methods have type hints and docstrings
   - No SQLAlchemy imports

3. **Future Phase B (E3.T8–E3.T9, when ORM models created):**
   - ReportRepository (after Report ORM model exists)
   - RefreshTokenRepository (after RefreshToken ORM model exists)
   - Same pattern, added to `backend/app/domain/repositories/` when ready

4. Create `backend/app/domain/repositories/__init__.py` to export all Phase A interfaces

5. Run mypy and linting

**Verification Steps:**

1. Import all 4 Phase A repositories: `from app.domain.repositories import UserRepository, AnalysisRepository, UploadRepository, DigitalAssetRepository`
2. Verify each repository has 5+ domain-specific query methods
3. Verify all methods have return type hints
4. Verify no infrastructure imports

**Acceptance Criteria:**

- [x] 4 repository interfaces created (Phase A: User, Upload, DigitalAsset, Analysis)
- [x] Report and RefreshToken repositories explicitly deferred to Phase B
- [x] Each interface defines domain-specific query methods per Design §4
- [x] All methods have type hints and docstrings
- [x] No SQLAlchemy imports in any interface
- [x] No linting/type errors

**Definition of Done:**

- All interfaces pass type checking
- Interfaces define contracts for E4 services
- Ready for T4

**Traceability:**

- R1 (Domain Interfaces) → 6 repository interfaces
- R4 (Domain-Specific Queries) → Query methods defined

---

### Task T4: Implement Base PostgreSQL Repository

**Objective:** Create the abstract base class for PostgreSQL repository implementations with common CRUD logic.

**Dependencies:** T2 (error mapping), T3 (interfaces).

**Implementation Steps:**

1. Create `backend/app/infrastructure/database/repositories/base.py`
2. Define `PostgreSQLRepository[T](BaseRepository[T])` ABC
3. Implement common methods:
   - `create()` → INSERT, flush, return domain entity
   - `get_by_id()` → SELECT WHERE id, raise NotFound
   - `list()` → SELECT with WHERE, ORDER BY, LIMIT/OFFSET
   - `update()` → UPDATE fields, return domain entity
   - `delete()` → SET deleted_at or DELETE based on entity type
4. Add abstract methods for subclasses:
   - `_build_where_clauses(**filters)` → construct WHERE clauses
   - `_apply_eager_loading(stmt)` → add joinedload/selectin
   - `_to_orm(entity)` → convert domain entity to ORM model
   - `_to_domain(orm_obj)` → convert ORM model to domain entity
5. Wrap all database operations in error mapping: `try/except map_db_exception()`

**Verification Steps:**

1. Verify base class has all 5 CRUD methods implemented
2. Verify error mapping is used (try/except around all DB calls)
3. Verify soft-delete filtering can be applied via `_build_where_clauses()`
4. Verify pagination returns (results, total_count) tuple

**Acceptance Criteria:**

- [x] PostgreSQLRepository ABC created with 5 implemented CRUD methods
- [x] All database operations wrapped in error mapping
- [x] Soft-delete filtering hook available
- [x] Pagination logic implemented
- [x] Eager loading hook available
- [x] No type errors

**Definition of Done:**

- Base repository passes linting
- Ready for T5 (first concrete repository)

**Traceability:**

- R2 (PostgreSQL Implementations) → Base class
- R3 (CRUD Operations) → Implemented in base
- R5 (N+1 Prevention) → Eager loading hooks
- R8 (Error Handling) → Exception mapping in base

---

### Task T5: Implement UserRepository

**Objective:** Implement PostgreSQL UserRepository with user-specific query methods.

**Dependencies:** T4 (base class).

**Implementation Steps:**

1. Create `backend/app/infrastructure/database/repositories/user.py`
2. Class: `PostgreSQLUserRepository(PostgreSQLRepository[User])`
3. Implement abstract methods from base:
   - `_to_orm()` → User → UserORM
   - `_to_domain()` → UserORM → User
   - `_build_where_clauses()` → Handle filters (email, is_active, deleted_at)
   - `_apply_eager_loading()` → No relationships to eager load for User
4. Implement UserRepository-specific methods:
   - `get_by_email(email)` → SELECT WHERE email (case-insensitive) AND deleted_at IS NULL
   - `list_active_users()` → SELECT WHERE is_active=true AND deleted_at IS NULL
5. Constructor takes `AsyncSession` parameter

**Verification Steps:**

1. Create test User, verify `create()` works
2. Retrieve by ID, verify `get_by_id()` works
3. Query by email, verify case-insensitivity
4. Verify soft-delete filtering (deleted_at IS NULL applied)
5. Verify error mapping (duplicate email → AlreadyExists)

**Acceptance Criteria:**

- [x] UserRepository class created in `infrastructure/database/repositories/user.py`
- [x] Inherits from PostgreSQLRepository
- [x] All UserRepository abstract methods implemented
- [x] `get_by_email()` is case-insensitive
- [x] Soft-delete filtering applied to `list()` and `get_by_id()`
- [x] Error mapping converts constraint violations to domain exceptions
- [x] No type errors

**Definition of Done:**

- UserRepository passes linting and type checking
- Basic CRUD integration tests pass
- Ready for T6

**Traceability:**

- R2 (PostgreSQL Implementations) → UserRepository
- R4 (Domain-Specific Queries) → `get_by_email()`, `list_active_users()`
- R7 (Soft-Delete) → Applied to list/get_by_id

---

### Task T6: Implement AnalysisRepository

**Objective:** Implement AnalysisRepository with query optimization (selectin loading, partial indexes).

**Dependencies:** T4 (base), T5 (reference implementation).

**Implementation Steps:**

1. Create `backend/app/infrastructure/database/repositories/analysis.py`
2. Class: `PostgreSQLAnalysisRepository(PostgreSQLRepository[Analysis])`
3. Implement abstract methods:
   - `_to_orm()` → Analysis → AnalysisORM
   - `_to_domain()` → AnalysisORM → Analysis
   - `_build_where_clauses()` → Filter by status, asset_id, etc.
   - `_apply_eager_loading()` → **CRITICAL:** Use `selectinload(AnalysisORM.digital_asset)` per Design §5.1
4. Implement AnalysisRepository-specific methods:
   - `get_completed_analysis(asset_id, analyzer_key, analyzer_version)` → Returns Optional[Analysis] (not raising NotFound)
   - `list_by_asset(asset_id)` → SELECT WHERE asset_id + eager load digital_asset
   - `list_by_status(status)` → SELECT WHERE status
   - `list_pending_for_worker(limit)` → SELECT WHERE status='pending' ORDER BY created_at ASC LIMIT
5. **Key:** All methods use `_apply_eager_loading()` to add selectin for digital_asset relationship

**Verification Steps:**

1. Create asset and analyses, verify `list_by_asset()` returns correct count
2. Verify idempotency: `get_completed_analysis()` returns existing, not new
3. **CRITICAL:** Test N+1 prevention:
   - Create 100 analyses
   - Call `list_by_asset()` and iterate accessing `analysis.digital_asset`
   - Verify only 2 DB queries (analyses + digital_assets via selectin), not 101
4. Verify error mapping (duplicate completed analysis → ConflictError or ignored idempotently)

**Acceptance Criteria:**

- [x] AnalysisRepository class created
- [x] All Analysis-specific query methods implemented per R4
- [x] Selectin loading applied for digital_asset relationship
- [x] `list_pending_for_worker()` returns oldest first (FIFO)
- [x] `get_completed_analysis()` returns Optional (no exception on not found)
- [x] N+1 query prevention verified (max 2 queries for list_by_asset)
- [x] No type errors

**Definition of Done:**

- AnalysisRepository passes linting and type checking
- Integration tests verify N+1 prevention
- Ready for T7

**Traceability:**

- R2 (PostgreSQL Implementations) → AnalysisRepository
- R4 (Domain-Specific Queries) → `list_by_asset()`, `list_pending_for_worker()`, etc.
- R5 (N+1 Prevention) → Selectin loading verified

---

### Task T7: (Removed — No additional repositories in Phase A)

**Status:** Consolidation complete. T6 is the final Phase A repository implementation.

After T6 (AnalysisRepository), proceed directly to T8 (Dependency Injection).

**Rationale:**
- Phase A covers 4 repositories: User (T5), Upload (T7a), DigitalAsset (T7b), Analysis (T6)
- Wait, let me clarify: T5 is User, T6 is Analysis. T7 originally covered Upload, DigitalAsset, Report, RefreshToken.
- **CORRECTION:** T7 now covers only Upload and DigitalAsset (2 remaining Phase A repositories)
- Report and RefreshToken deferred to Phase B (E3.T8–E3.T9) when their ORM models exist

### Task T7 (Revised): Implement Remaining Phase A Repositories (Upload, DigitalAsset)

**Objective:** Implement 2 remaining Phase A repositories following the same pattern as UserRepository and AnalysisRepository.

**Dependencies:** T4 (base), T5 (reference), T6 (complex reference).

**Implementation Steps:**

1. **UploadRepository** (`backend/app/infrastructure/database/repositories/upload.py`)
   - Query methods: `get_by_storage_key()`, `list_by_user()`, `list_by_status()`
   - No eager loading needed (no FK relationships of interest)

2. **DigitalAssetRepository** (`backend/app/infrastructure/database/repositories/digital_asset.py`)
   - Query methods: `get_by_hash()`, `list_by_user()`, `get_by_normalized_value()`
   - Soft-delete filtering applied (assets can be soft-deleted)
   - No eager loading needed

3. **Deferred to Phase B (E3.T8–E3.T9):**
   - ReportRepository (after Report ORM model created)
   - RefreshTokenRepository (after RefreshToken ORM model created)

4. Create `backend/app/infrastructure/database/repositories/__init__.py` to export all Phase A repositories

**Verification Steps:**

1. Import Phase A repositories without errors: `from app.infrastructure.database.repositories import UploadRepository, DigitalAssetRepository`
2. For each, verify basic CRUD works (create, get, list, delete)
3. Verify domain-specific queries return correct results
4. Verify soft-delete filtering for DigitalAsset

**Acceptance Criteria:**

- [x] 2 Phase A repository implementations created (Upload, DigitalAsset)
- [x] Each inherits from PostgreSQLRepository
- [x] Each implements all abstract methods + domain-specific queries
- [x] Soft-delete filtering applied to DigitalAsset per R7
- [x] Error mapping used for all DB exceptions
- [x] Report and RefreshToken repositories explicitly deferred
- [x] No type errors across all Phase A repositories

**Definition of Done:**

- All 4 repositories pass linting and type checking
- Basic integration tests pass
- Ready for T8 (DI integration)

**Traceability:**

- R2 (PostgreSQL Implementations) → All 4 repositories
- R4 (Domain-Specific Queries) → Query methods implemented
- R7 (Soft-Delete) → Applied correctly

---

### Task T8: Dependency Injection & FastAPI Integration

**Objective:** Wire Phase A repositories (4 total) into FastAPI dependency injection so they're available to services.

**Dependencies:** T7 (all Phase A repositories implemented).

**Implementation Steps:**

1. Create/update `backend/app/core/dependencies.py`:
   - For each Phase A repository (4 total), create a dependency function:
     ```python
     async def get_user_repository(
         session: AsyncSession = Depends(get_db)
     ) -> UserRepository:
         return PostgreSQLUserRepository(session)
     ```
   - Phase A repositories: User, Upload, DigitalAsset, Analysis
   - Phase B repositories (Report, RefreshToken) deferred until their ORM models exist

2. Update `backend/app/main.py`:
   - Register dependencies in FastAPI container (if using dependency container pattern)
   - Or leave as-is if relying on function-based DI via `Depends()`

3. Create sample service using DI:
   ```python
   async def request_analysis(
       asset_id: UUID,
       analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
       asset_repo: DigitalAssetRepository = Depends(get_digital_asset_repository),
       session: AsyncSession = Depends(get_db)
   ):
       # Service can use repositories
       asset = await asset_repo.get_by_id(asset_id)
       analysis = await analysis_repo.create(...)
   ```

4. Verify dependencies are in correct layer (core/dependencies, not domain)

**Verification Steps:**

1. Start FastAPI app: `uvicorn app.main:app`
2. Verify `/docs` loads without errors
3. Test dependency injection in a simple endpoint (e.g., health check with repo dependency)
4. Verify session lifecycle (request-scoped, commits on success, rolls back on error)

**Acceptance Criteria:**

- [x] Dependency functions created for all 4 Phase A repositories
- [x] Repositories injected via FastAPI `Depends()`
- [x] Per-request session lifecycle verified
- [x] Sample endpoint using repository works
- [x] No startup errors
- [x] Phase B repositories (Report, RefreshToken) deferred in dependency configuration

**Definition of Done:**

- FastAPI app starts and DI works
- Ready for T9 (testing)

**Traceability:**

- R9 (Transaction Safety) → Per-request session lifecycle
- R3 (CRUD Operations) → Available via DI

---

### Task T9: Repository Unit Tests & Integration Tests

**Objective:** Comprehensive test coverage for all Phase A repositories (4 total).

**Dependencies:** T8 (DI integrated).

**Implementation Steps:**

1. Create `backend/tests/unit/test_repositories_mock.py`:
   - Mock implementations of 4 Phase A repositories (for service testing)
   - Verify services can be tested without database

2. Create `backend/tests/integration/test_user_repository.py`:
   - Test CRUD: create, get_by_id, list, update, delete
   - Test soft-delete filtering
   - Test error mapping (duplicate email → AlreadyExists)
   - Test `get_by_email()` case-insensitivity

3. Create `backend/tests/integration/test_analysis_repository.py`:
   - **CRITICAL N+1 TEST:**
     ```python
     async def test_list_by_asset_no_n_plus_one():
         # Create 100 analyses for one asset
         # Call list_by_asset(asset_id, limit=100)
         # Verify only 2 queries: analyses + digital_assets via selectin
         # (use SQLAlchemy query logging to verify)
     ```
   - Test idempotency: `get_completed_analysis()` returns existing
   - Test job queue: `list_pending_for_worker()` FIFO order
   - Test error mapping (duplicate completed → handled)

4. Create `backend/tests/integration/test_all_repositories.py`:
   - For each Phase A repository: basic CRUD tests
   - For soft-delete repos (User, DigitalAsset): verify filtering

5. Run tests against containerized PostgreSQL:
   ```bash
   docker compose up -d postgres
   pytest backend/tests/integration/
   ```

**Acceptance Criteria:**

- [x] Unit tests for mock repositories (10+ tests)
- [x] Integration tests for all 4 Phase A repositories (50+ tests total)
- [x] N+1 prevention explicitly tested (query count verified)
- [x] Soft-delete filtering tested
- [x] Error mapping tested (3+ exception types)
- [x] Test coverage > 90% for Phase A repository code
- [x] All tests pass against PostgreSQL
- [x] Phase B repositories (Report, RefreshToken) noted as deferred

**Definition of Done:**

- All tests pass
- Coverage > 90%
- N+1 prevention verified
- Ready for code review / E4 (API endpoints)

**Traceability:**

- R5 (N+1 Prevention) → N+1 test explicitly verifies selectin loading
- R7 (Soft-Delete) → Soft-delete filtering tested
- R8 (Error Handling) → Error mapping tested
- R10 (Testability) → Mocks and integration tests demonstrate testability

---

## 4. Quality Gates

**All Tasks:** Before merge to `main`:
- [x] All tests pass
- [x] Linting passes (ruff check)
- [x] Type checking passes (mypy --strict)
- [x] Code coverage > 90% for new code
- [x] No ORM imports in `domain/` layer
- [x] Repositories only used via `Depends()` in FastAPI
- [x] No hardcoded database URLs or credentials

---

## 5. Completion Criteria

**E3.T7 Complete when (Phase A):**
- [x] All 9 tasks completed
- [x] All 4 Phase A repositories implemented (User, Upload, DigitalAsset, Analysis)
- [x] All tests passing
- [x] Code review approved
- [x] Ready for E4 (API endpoints)
- [x] Phase B repositories (Report, RefreshToken) deferred and documented in E3.T8 specification

**Deliverables (Phase A):**
- 4 repository interfaces (Domain layer)
- 4 repository implementations (Infrastructure layer)
- Dependency injection wired for Phase A
- Comprehensive tests for Phase A
- Zero ORM leakage into Domain layer

**Phase B (Deferred to E3.T8–E3.T9):**
- Report repository (after Report ORM model created)
- RefreshToken repository (after RefreshToken ORM model created)
- Same patterns applied

---

## Sign-Off

**Tasks Specification (Phase A):**
- Version: 1.0.0 (Final, Phase A Complete)
- Status: **READY FOR IMPLEMENTATION**
- Location: `.kiro/specs/epic-3-database-foundation-repository-t7/tasks.md`
- Scope: 4 repositories (User, Upload, DigitalAsset, Analysis)
- Deferral: Report and RefreshToken repositories deferred to E3.T8–E3.T9

**Next Steps after E3.T7 Phase A:** 
1. Proceed to E4 (API Endpoints) with Phase A repositories available for service layer use.
2. When Report and RefreshToken ORM models are created (E3.T8), create Phase B repositories using the same design patterns.
