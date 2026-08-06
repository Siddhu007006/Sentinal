# E3.T11 — PostgreSQL Repository Implementations

## Specification Document

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-repository-implementations-t11/requirements.md |
| **Feature** | postgresql-repository-implementations-t11 |
| **Status** | In Review |
| **Owner** | Engineering Team |
| **Traces to** | 22-Engineering-Backlog E3.T11 |
| **Dependencies** | E3.T1-E3.T10 (all ORM models, migrations, repository interfaces) |

---

## Introduction

E3.T11 implements the abstract repository interfaces (E3.T10) with concrete PostgreSQL queries using SQLAlchemy async.

This task focuses on:
1. Creating concrete repository implementations that inherit from abstract interfaces
2. Implementing all CRUD operations and domain-specific queries in SQL
3. Supporting soft-delete filtering, pagination, and transaction scoping
4. Establishing the persistence layer for all domain entities

**Scope Boundary:**
- ✅ PostgreSQL repository implementations in `app/infrastructure/database/repositories/`
- ✅ Async SQLAlchemy queries for all CRUD operations
- ✅ Domain-specific query implementations with filters and pagination
- ✅ Soft-delete query filtering
- ✅ Transaction and session management
- ✅ Query result mapping to ORM models
- ✅ Integration tests with PostgreSQL container
- ❌ Query optimization / index tuning (belongs in performance work)
- ❌ Caching layer (future: caching layer)
- ❌ Read replicas (future: scaling work)

---

## Requirements

### Requirement 1: PostgreSQL Repository Base Implementation

**User Story:** As a developer, I want PostgreSQL repository implementations that inherit from abstract interfaces so that domain logic can use concrete database operations.

**Description:**

Each repository must:
- Inherit from the corresponding abstract repository interface
- Implement all abstract methods with PostgreSQL queries
- Accept AsyncSession parameter for transaction management
- Support soft-delete filtering
- Implement all CRUD operations (create, read, update, delete, soft_delete)
- Implement all domain-specific query methods
- Use SQLAlchemy ORM for all queries (no raw SQL except migrations)

**Rationale:**

Concrete repository implementations bridge the gap between domain interfaces and database operations. Using SQLAlchemy ORM ensures:
- Type safety (column definitions are checked at runtime)
- Security (no raw SQL injection)
- Consistency (same query patterns across all repositories)
- Testability (easy to mock in unit tests)

**Acceptance Criteria:**

1. ✅ Repository implementations created in `backend/app/infrastructure/database/repositories/`
2. ✅ Directory structure:
   - `backend/app/infrastructure/database/repositories/__init__.py` (factory/dependency injection)
   - `backend/app/infrastructure/database/repositories/user_repository.py` (UserRepository impl)
   - `backend/app/infrastructure/database/repositories/upload_repository.py` (UploadRepository impl)
   - `backend/app/infrastructure/database/repositories/digital_asset_repository.py` (DigitalAssetRepository impl)
   - `backend/app/infrastructure/database/repositories/analysis_repository.py` (AnalysisRepository impl)
   - `backend/app/infrastructure/database/repositories/report_repository.py` (ReportRepository impl)
   - `backend/app/infrastructure/database/repositories/audit_log_repository.py` (AuditLogRepository impl)
3. ✅ Each repository class inherits from its abstract interface:
   ```python
   class PostgreSQLUserRepository(UserRepository):
       def __init__(self, session: AsyncSession):
           self.session = session
   ```
4. ✅ All abstract methods implemented with SQLAlchemy queries
5. ✅ No raw SQL used (except in custom migration scripts)
6. ✅ All methods are async: `async def create(self, entity: Entity) -> Entity`
7. ✅ All methods return correct types matching abstract interface
8. ✅ All methods raise correct exceptions (NotFoundError, UniqueConstraintError, etc.)
9. ✅ All implementations can be imported: `from app.infrastructure.database.repositories import PostgreSQLUserRepository`
10. ✅ Syntax check passes: `python -m py_compile app/infrastructure/database/repositories/*.py`
11. ✅ No circular imports

**Architectural Notes:**
- Traces to: 06-Repository-Structure (repository implementation organization)
- Traces to: 03-Architecture §4 (Infrastructure layer: database implementations)
- Traces to: 07-Backend-Development-Standards §9 (repository implementation patterns)

---

### Requirement 2: CRUD Operation Implementations

**User Story:** As a developer, I want CRUD operations implemented in SQL so that domain logic can create, read, update, and delete entities.

**Description:**

Each repository must implement:
- **Create**: `INSERT INTO table VALUES (...) RETURNING *`
- **Read**: `SELECT FROM table WHERE id = ? LIMIT 1`
- **List**: `SELECT FROM table WHERE filters ORDER BY ? LIMIT ? OFFSET ?`
- **Update**: `UPDATE table SET ... WHERE id = ? RETURNING *`
- **Delete**: `DELETE FROM table WHERE id = ?` (hard delete)
- **Soft Delete**: `UPDATE table SET deleted_at = now() WHERE id = ? RETURNING *`
- **Exists**: `SELECT 1 FROM table WHERE id = ? LIMIT 1`
- **Count**: `SELECT COUNT(*) FROM table WHERE filters`

**Rationale:**

Standard CRUD operations are the foundation of all repository operations. Correct implementation ensures data consistency and predictable behavior.

**Acceptance Criteria:**

1. ✅ All repositories implement `async def create(self, entity: Entity) -> Entity`
   - INSERT with all fields (id auto-generated if UUID PK)
   - Return inserted entity with ID populated
   - Raise UniqueConstraintError on duplicate key
   - Raise ForeignKeyError on invalid FK
2. ✅ All repositories implement `async def read(self, id: UUID) -> Entity | None`
   - SELECT by ID
   - Return entity or raise NotFoundError
3. ✅ All repositories implement `async def list(...) -> tuple[list[Entity], int]`
   - SELECT with filters, sorting, pagination
   - Return (results, total_count)
4. ✅ All repositories implement `async def update(self, id: UUID, updates: dict) -> Entity`
   - UPDATE specific fields
   - Return updated entity or raise NotFoundError
   - Validate FK references
5. ✅ All repositories implement `async def delete(self, id: UUID) -> None`
   - Hard DELETE (removes row)
   - Raise NotFoundError on missing ID
6. ✅ Soft-delete repositories implement `async def soft_delete(self, id: UUID) -> Entity`
   - UPDATE deleted_at = now()
   - Return entity with deleted_at populated
7. ✅ All repositories implement `async def exists(self, id: UUID) -> bool`
   - SELECT 1 or EXISTS clause
   - Return True/False
8. ✅ All repositories implement `async def count(self, filters: dict | None = None) -> int`
   - SELECT COUNT(*)
   - Apply filters
   - Return total count

**Architectural Notes:**
- Traces to: 06-Repository-Structure (CRUD implementation patterns)
- Traces to: 07-Backend-Development-Standards §9 (repository method conventions)

---

### Requirement 3: Domain-Specific Query Implementations

**User Story:** As a developer, I want domain-specific queries implemented so that application logic can fetch entities using business terms.

**Description:**

Each repository must implement all domain-specific queries defined in E3.T10 abstract interface:

- **UserRepository**: find_by_email, find_active_users, find_admin_users
- **UploadRepository**: find_by_user, find_pending_uploads, find_by_status
- **DigitalAssetRepository**: find_by_user, find_by_upload, find_by_type, find_active_assets
- **AnalysisRepository**: find_by_asset, find_by_status, find_pending_analyses, find_by_requested_user
- **ReportRepository**: find_by_user, find_active_reports
- **AuditLogRepository**: find_by_actor, find_by_resource, find_by_date_range

**Rationale:**

Domain-specific queries encapsulate common access patterns. Implementing them in the repository ensures:
- Queries are optimized with correct indexes
- Logic is centralized (not scattered across services)
- Tests can mock these specific queries
- Application code stays business-focused

**Acceptance Criteria:**

1. ✅ UserRepository implements `find_by_email(email: str) -> User | None`
   - SELECT WHERE email = ? (case-insensitive)
   - Return entity or None
   - Uses unique email index
2. ✅ UserRepository implements `find_active_users(skip, limit) -> tuple[list[User], int]`
   - SELECT WHERE is_active = true
   - Paginate
3. ✅ UserRepository implements `find_admin_users(skip, limit) -> tuple[list[User], int]`
   - SELECT WHERE role = 'admin'
   - Paginate
4. ✅ UploadRepository implements `find_by_user(user_id, skip, limit) -> tuple[list[Upload], int]`
   - SELECT WHERE user_id = ?
   - Paginate, sort by created_at DESC
5. ✅ UploadRepository implements `find_pending_uploads(skip, limit) -> tuple[list[Upload], int]`
   - SELECT WHERE status = 'PENDING'
   - Paginate
6. ✅ UploadRepository implements `find_by_status(status, skip, limit) -> tuple[list[Upload], int]`
   - SELECT WHERE status = ?
7. ✅ DigitalAssetRepository implements `find_by_user(user_id, skip, limit, include_deleted) -> tuple[list[DigitalAsset], int]`
   - SELECT WHERE user_id = ? AND (include_deleted OR deleted_at IS NULL)
   - Paginate
8. ✅ DigitalAssetRepository implements `find_by_type(asset_type, skip, limit, include_deleted) -> tuple[list[DigitalAsset], int]`
   - SELECT WHERE asset_type = ? AND (include_deleted OR deleted_at IS NULL)
9. ✅ DigitalAssetRepository implements `find_by_upload(upload_id) -> tuple[list[DigitalAsset], int]`
   - SELECT WHERE upload_id = ?
10. ✅ DigitalAssetRepository implements `find_active_assets(skip, limit) -> tuple[list[DigitalAsset], int]`
    - SELECT WHERE deleted_at IS NULL
11. ✅ AnalysisRepository implements `find_by_asset(asset_id, skip, limit) -> tuple[list[Analysis], int]`
    - SELECT WHERE digital_asset_id = ?
12. ✅ AnalysisRepository implements `find_by_status(status, skip, limit) -> tuple[list[Analysis], int]`
    - SELECT WHERE status = ?
13. ✅ AnalysisRepository implements `find_pending_analyses(skip, limit) -> tuple[list[Analysis], int]`
    - SELECT WHERE status = 'PENDING'
14. ✅ AnalysisRepository implements `find_by_requested_user(user_id, skip, limit) -> tuple[list[Analysis], int]`
    - SELECT WHERE requested_by = ?
15. ✅ ReportRepository implements `find_by_user(user_id, skip, limit, include_deleted) -> tuple[list[Report], int]`
    - SELECT WHERE user_id = ? AND (include_deleted OR deleted_at IS NULL)
16. ✅ ReportRepository implements `find_active_reports(skip, limit) -> tuple[list[Report], int]`
    - SELECT WHERE deleted_at IS NULL
17. ✅ AuditLogRepository implements `find_by_actor(actor_id, skip, limit) -> tuple[list[AuditLog], int]`
    - SELECT WHERE actor_id = ?
18. ✅ AuditLogRepository implements `find_by_resource(resource_type, resource_id, skip, limit) -> tuple[list[AuditLog], int]`
    - SELECT WHERE resource_type = ? AND resource_id = ?
19. ✅ AuditLogRepository implements `find_by_date_range(start_date, end_date, skip, limit) -> tuple[list[AuditLog], int]`
    - SELECT WHERE occurred_at BETWEEN ? AND ?
20. ✅ All query methods support pagination (skip, limit)
21. ✅ All query methods support sorting (order_by parameter where appropriate)
22. ✅ All queries use prepared statements / parameterized queries (SQLAlchemy default)
23. ✅ All queries include appropriate indexes for performance

**Architectural Notes:**
- Traces to: 06-Repository-Structure (query encapsulation patterns)
- Traces to: 04-Database-Design §8 (Indexing Strategy)

---

### Requirement 4: Soft-Delete Filtering

**User Story:** As a developer, I want soft-delete filtering so that queries exclude deleted entities by default but can optionally include them.

**Description:**

Repositories supporting soft-delete must:
- Filter out soft-deleted records by default: `WHERE deleted_at IS NULL`
- Support `include_deleted: bool = False` parameter in list/query methods
- When `include_deleted=True`, return all records (deleted and active)
- Implement `soft_delete(id)` to set deleted_at timestamp

**Rationale:**

Soft-delete filtering ensures:
- Default queries don't return "deleted" entities to users
- Admins can view deleted entities for recovery/audit
- Historical records are preserved
- Compliance queries can show deletion events

**Acceptance Criteria:**

1. ✅ UserRepository `list()` filters `WHERE deleted_at IS NULL` by default
2. ✅ UserRepository `list(include_deleted=True)` returns all users (including deleted)
3. ✅ DigitalAssetRepository `list()` and all queries filter deleted_at by default
4. ✅ ReportRepository `list()` and all queries filter deleted_at by default
5. ✅ AuditLogRepository has NO soft-delete filtering (audit logs are immutable, never deleted)
6. ✅ `soft_delete(id)` sets deleted_at = now() (no other fields changed)
7. ✅ `soft_delete(id)` returns entity with deleted_at populated
8. ✅ `soft_delete(id)` raises NotFoundError if entity not found
9. ✅ `delete()` hard-deletes (removes row)
10. ✅ Query filters applied consistently across all queries

**Architectural Notes:**
- Traces to: 04-Database-Design §10 (Soft Delete Strategy)
- Traces to: 02-Domain-Model (entity lifecycle)

---

### Requirement 5: Pagination Implementation

**User Story:** As a developer, I want pagination implemented so that queries return results in manageable pages.

**Description:**

All `list()` and domain-specific query methods must:
- Accept `skip: int` (offset in results)
- Accept `limit: int` (page size, default 20)
- Return `tuple[list[Entity], int]` (results, total_count)
- Use SQL OFFSET/LIMIT for pagination
- Calculate total_count from query without pagination (SELECT COUNT for efficiency)

**Rationale:**

Pagination ensures:
- Memory-efficient queries (don't load million rows)
- Predictable API responses (consistent page size)
- UI-friendly (easy next/previous pagination)

**Acceptance Criteria:**

1. ✅ All `list()` methods accept `skip: int = 0, limit: int = 20`
2. ✅ All `list()` methods return `tuple[list[Entity], int]` (results, total_count)
3. ✅ All domain-specific queries support pagination parameters
4. ✅ All queries use SQL `LIMIT ? OFFSET ?`
5. ✅ Total count calculated efficiently: execute COUNT query without LIMIT/OFFSET
6. ✅ Default limit is 20 (reasonable page size)
7. ✅ Skip/limit validation (no negative values, reasonable max)
8. ✅ Example: `results, total = await user_repo.list(skip=0, limit=20)` returns (20 users, total_count)

**Architectural Notes:**
- Traces to: 07-Backend-Development-Standards §9 (pagination patterns)

---

### Requirement 6: Filtering Implementation

**User Story:** As a developer, I want filter support so that queries can search by multiple conditions.

**Description:**

List and query methods must support filtering via `filters` dict:
- Simple equality: `filters = {"status": "PENDING"}` → `WHERE status = 'PENDING'`
- Range: `filters = {"threat_score__gte": 0.7}` → `WHERE threat_score >= 0.7`
- IN clause: `filters = {"role__in": ["admin", "analyst"]}` → `WHERE role IN ('admin', 'analyst')`
- LIKE for text: `filters = {"email__ilike": "%@example.com"}` → `WHERE email ILIKE '%@example.com%'`
- Between: `filters = {"created_at__range": (start, end)}` → `WHERE created_at BETWEEN ? AND ?`

**Rationale:**

Flexible filtering enables:
- Dashboard queries (filter by status, date range, etc.)
- Search functionality
- Admin queries (complex multi-field filters)
- Single query method to handle many search patterns

**Acceptance Criteria:**

1. ✅ All `list()` methods accept `filters: dict | None = None`
2. ✅ Filter format: `{"field__operator": value}` (double-underscore notation)
3. ✅ Supported operators: `eq` (equality), `ne` (not equal), `gt`, `gte`, `lt`, `lte`, `in`, `ilike`, `range`
4. ✅ Example: `list(filters={"status": "PENDING", "threat_score__gte": 0.7})` works
5. ✅ Filters combined with AND: all conditions must match
6. ✅ Invalid filter operators ignored (fail safely)
7. ✅ Parameterized queries prevent SQL injection
8. ✅ Docstrings document filter format for each repository

**Architectural Notes:**
- Traces to: 07-Backend-Development-Standards §9 (query patterns)

---

### Requirement 7: Sorting Implementation

**User Story:** As a developer, I want sorting support so that query results can be ordered by any column.

**Description:**

List and query methods must support sorting via `order_by` parameter:
- Format: `order_by = [("created_at", "desc"), ("name", "asc")]`
- Support ascending (asc) and descending (desc) order
- Default sort: created_at DESC (newest first)
- Validate field names against model columns (prevent SQL injection)

**Rationale:**

Sorting enables:
- List newest-first or oldest-first
- Sort by relevance, score, or other criteria
- Deterministic pagination (combine with sort for consistent results)

**Acceptance Criteria:**

1. ✅ All `list()` methods accept `order_by: list[tuple[str, str]] | None = None`
2. ✅ Default sort: `("created_at", "desc")` (newest first)
3. ✅ Format: `[("column1", "asc"), ("column2", "desc")]`
4. ✅ Validate column names against ORM model (prevent SQL injection)
5. ✅ Invalid column names raise ValueError
6. ✅ Parameterized sort (column name validation, not raw SQL)
7. ✅ Multiple sort columns create composite sort (first column primary, second tiebreaker)
8. ✅ Docstrings document sort format

**Architectural Notes:**
- Traces to: 07-Backend-Development-Standards §9 (query patterns)

---

### Requirement 8: Transaction and Session Management

**User Story:** As a developer, I want repositories to work within transaction scopes so that multiple operations commit atomically.

**Description:**

Repositories must:
- Accept `session: AsyncSession` in constructor or each method
- Not manage session lifecycle (caller provides)
- Support operations within the same session (same transaction)
- Not commit or rollback (caller manages transaction)

**Rationale:**

Session management in repositories ensures:
- Multiple operations can commit atomically (all-or-nothing)
- Caller controls transaction boundaries (FastAPI dependency injection)
- Testable with mock sessions
- Production code and tests use same session pattern

**Acceptance Criteria:**

1. ✅ All repositories accept `session: AsyncSession` in constructor: `def __init__(self, session: AsyncSession)`
2. ✅ All methods use the session provided in constructor
3. ✅ Repositories do NOT create their own sessions
4. ✅ Repositories do NOT commit, rollback, or close sessions
5. ✅ Multiple operations can share session for atomicity:
   ```python
   async with get_db_session() as session:
       user_repo = PostgreSQLUserRepository(session)
       user = await user_repo.create(user_entity)
       asset_repo = PostgreSQLDigitalAssetRepository(session)
       asset = await asset_repo.create(asset_entity)
       # single commit on exit
   ```
6. ✅ Caller manages transaction scope (via FastAPI dependency injection)
7. ✅ Docstrings explain session parameter and transaction semantics

**Architectural Notes:**
- Traces to: 03-Architecture §4 (async stack)
- Traces to: 07-Backend-Development-Standards §9 (transaction patterns)

---

### Requirement 9: Error Handling and Exceptions

**User Story:** As a developer, I want repositories to raise standard exceptions so that domain logic can handle errors consistently.

**Description:**

Repositories must:
- Catch SQLAlchemy exceptions and wrap in standard exceptions
- Raise `NotFoundError` when entity not found
- Raise `UniqueConstraintError` on duplicate unique field
- Raise `ForeignKeyError` on invalid FK reference
- Raise `TransactionError` on commit failure
- Include descriptive error messages

**Rationale:**

Standard exception types enable:
- Domain logic to handle errors generically
- Consistent HTTP status code mapping
- Clear error semantics
- Testable error conditions

**Acceptance Criteria:**

1. ✅ `read(id)` raises `NotFoundError` if entity not found
2. ✅ `update(id, updates)` raises `NotFoundError` if entity not found
3. ✅ `delete(id)` raises `NotFoundError` if entity not found
4. ✅ `soft_delete(id)` raises `NotFoundError` if entity not found
5. ✅ `create(entity)` raises `UniqueConstraintError` on duplicate unique field
6. ✅ `create(entity)` raises `ForeignKeyError` on invalid FK reference
7. ✅ `update(id, updates)` raises `ForeignKeyError` on invalid FK reference
8. ✅ All exceptions include descriptive message: `NotFoundError("User with id {id} not found")`
9. ✅ Exception handling:
   ```python
   try:
       await session.execute(...)
   except IntegrityError as e:
       if "unique constraint" in str(e):
           raise UniqueConstraintError(...)
   ```
10. ✅ All exceptions inherit from `RepositoryError`

**Architectural Notes:**
- Traces to: 07-Backend-Development-Standards §6 (error handling)

---

### Requirement 10: Integration Testing

**User Story:** As a developer, I want integration tests so that repositories work correctly with PostgreSQL.

**Description:**

Integration tests must:
- Use actual PostgreSQL container (from E3.T1 fixtures)
- Test all CRUD operations with real database
- Test soft-delete filtering
- Test pagination and filtering
- Test error conditions (duplicate key, foreign key, not found)
- Test transaction atomicity (multiple operations)

**Rationale:**

Integration tests ensure:
- SQL queries are syntactically correct
- Queries work with actual PostgreSQL
- Error handling works
- Transactions commit correctly

**Acceptance Criteria:**

1. ✅ Integration tests created in `backend/tests/integration/test_repositories.py` or separate files per repository
2. ✅ Tests use PostgreSQL container from E3.T1 fixtures
3. ✅ CRUD test for each repository:
   - Create entity
   - Read entity
   - Update entity
   - Delete entity
4. ✅ Soft-delete tests:
   - Soft-delete entity
   - Query filters out deleted entity by default
   - Query includes deleted entity when `include_deleted=True`
5. ✅ Pagination tests:
   - Query with skip/limit
   - Verify results and total_count
   - Verify correct page size
6. ✅ Filtering tests:
   - Query with filters
   - Verify correct results
   - Test multiple filter types (equality, range, in, like)
7. ✅ Error condition tests:
   - Create with duplicate unique field → UniqueConstraintError
   - Create with invalid FK → ForeignKeyError
   - Read non-existent ID → NotFoundError
   - Update non-existent ID → NotFoundError
8. ✅ Transaction atomicity tests:
   - Multiple operations in same session
   - Verify single commit
   - Verify rollback on error
9. ✅ All tests pass: `pytest tests/integration/test_repositories.py -v`
10. ✅ Tests pass in CI pipeline with PostgreSQL container

**Architectural Notes:**
- Traces to: 07-Backend-Development-Standards §7 (integration testing patterns)
- Traces to: 12-CI-CD-Architecture §2 (test validation)

---

## Acceptance Criteria Summary

| # | Criterion | Status |
|---|-----------|--------|
| **R1** | PostgreSQL repository base implementation | ⏳ Pending |
| **R2** | CRUD operation implementations | ⏳ Pending |
| **R3** | Domain-specific query implementations | ⏳ Pending |
| **R4** | Soft-delete filtering implemented | ⏳ Pending |
| **R5** | Pagination implemented | ⏳ Pending |
| **R6** | Filtering implemented | ⏳ Pending |
| **R7** | Sorting implemented | ⏳ Pending |
| **R8** | Transaction and session management | ⏳ Pending |
| **R9** | Error handling and exceptions | ⏳ Pending |
| **R10** | Integration testing | ⏳ Pending |

---

## Definition of Ready

Before implementation begins:
- ✅ E3.T1 complete (Database Foundation, fixtures, async session)
- ✅ E3.T3-E3.T9 complete (all ORM models and migrations)
- ✅ E3.T10 complete (abstract repository interfaces)
- ✅ PostgreSQL 16 container operational
- ✅ All migrations applied to test database
- ✅ SQLAlchemy async and asyncpg installed
- ✅ CI pipeline supports integration tests with PostgreSQL container

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| **SQL queries incorrect** | Wrong results, data corruption | Low | Comprehensive integration tests (R10) |
| **Session management bugs** | Transaction issues, stale data | Low | Clear session scoping, tested in R8 |
| **Soft-delete filtering inconsistent** | Data visibility bugs | Low | Consistent filter application (R4), tested in R10 |
| **Performance issues** | Slow queries | Low | Proper indexing (covered in E3.T3-T9 migrations) |
| **Error handling incomplete** | Unhandled exceptions in domain layer | Low | Complete exception wrapping (R9) |

---

## Dependencies & Sequencing

```
E3.T1 (Database Foundation)
E3.T2 (Alembic Configuration)
E3.T3-E3.T9 (ORM models and migrations) ✓
E3.T10 (Abstract repository interfaces) ✓
E3.T11 (PostgreSQL Repository Implementations) ← YOU ARE HERE
  ├─ Implements all abstract methods
  ├─ Establishes persistence layer
  └─ Enables: E4 (Service layer using repositories)
```

---

## Glossary

| Term | Definition |
|---|---|
| **AsyncSession** | SQLAlchemy async session enabling non-blocking database operations |
| **SQLAlchemy ORM** | Object-Relational Mapping library for Python database access |
| **Prepared Statement** | SQL query with placeholders preventing SQL injection |
| **OFFSET/LIMIT** | SQL clauses for pagination (skip N rows, return N rows) |
| **Soft Delete** | Marking entity deleted (deleted_at timestamp) without removing row |
| **Hard Delete** | Physically removing row from database |
| **CASCADE** | Foreign key constraint: delete parent → delete children |
| **Transaction** | Atomic unit of work (all-or-nothing commit) |
| **Parameterized Query** | Query with parameters bound separately from SQL (prevents injection) |

---

## References

- 22-Engineering-Backlog: E3.T11 (PostgreSQL Repository Implementations)
- 06-Repository-Structure: Repository implementation organization and patterns
- 03-Architecture §4: Infrastructure layer, async stack
- 02-Domain-Model: Entity definitions
- 07-Backend-Development-Standards §9: Repository implementation conventions
- 04-Database-Design §8: Indexing Strategy (for query performance)
- 04-Database-Design §10: Soft Delete Strategy
- E3.T10 Completion: Abstract repository interfaces (method signatures)
- E3.T3-E3.T9: ORM models providing entity types and FK relationships
