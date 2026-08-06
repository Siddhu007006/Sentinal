# E3.T10 — Domain Repository Interfaces

## Specification Document

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-repository-interfaces-t10/requirements.md |
| **Feature** | domain-repository-interfaces-t10 |
| **Status** | In Review |
| **Owner** | Engineering Team |
| **Traces to** | 22-Engineering-Backlog E3.T10 |
| **Dependencies** | E3.T1-E3.T9 (all domain models and migrations) |

---

## Introduction

E3.T10 defines abstract repository interfaces that establish the contract between the domain layer and the persistence layer.

This task focuses on:
1. Creating abstract base classes (ABC) for each repository
2. Defining pure method signatures with no implementation
3. Establishing repository patterns for CRUD and domain-specific queries
4. Creating the foundation for E3.T11 (PostgreSQL implementations)

**Scope Boundary:**
- ✅ Abstract repository base classes in `app/domain/repositories/`
- ✅ Method signatures for all CRUD operations (create, read, update, delete)
- ✅ Domain-specific query signatures (filtering, sorting, pagination)
- ✅ Soft-delete interface patterns
- ✅ Type hints and docstrings
- ✅ Repository registration and dependency injection setup
- ❌ PostgreSQL implementation (belongs in E3.T11)
- ❌ Redis caching (future: caching layer)
- ❌ Query optimization (E3.T11: implementation details)

---

## Requirements

### Requirement 1: Repository Abstract Base Classes

**User Story:** As an architect, I want abstract repository interfaces so that domain logic depends on contracts, not implementations, enabling testing and future storage backend changes.

**Description:**

Each repository must:
- Inherit from `abc.ABC` (Python abstract base class)
- Define pure method signatures with `@abstractmethod` decorator
- Include type hints for all parameters and return types
- Include docstrings explaining each method's contract
- Support CRUD operations (create, read, update, delete)
- Support listing with pagination
- Support soft-delete queries
- Support transaction-scoped operations (async sessions)

**Rationale:**

Repository pattern decouples domain logic from persistence. Abstract interfaces ensure that:
- Business logic depends on the contract, not PostgreSQL specifics
- Implementations can be swapped (e.g., testing with in-memory store, production with PostgreSQL)
- Changes to persistence don't ripple through the domain
- Multiple implementations can coexist (caching, read replicas, etc.)

**Acceptance Criteria:**

1. ✅ Abstract repository base classes created in `backend/app/domain/repositories/`
2. ✅ Directory structure:
   - `backend/app/domain/repositories/__init__.py` (exports all interfaces)
   - `backend/app/domain/repositories/user_repository.py` (UserRepository ABC)
   - `backend/app/domain/repositories/upload_repository.py` (UploadRepository ABC)
   - `backend/app/domain/repositories/digital_asset_repository.py` (DigitalAssetRepository ABC)
   - `backend/app/domain/repositories/analysis_repository.py` (AnalysisRepository ABC)
   - `backend/app/domain/repositories/report_repository.py` (ReportRepository ABC)
   - `backend/app/domain/repositories/audit_log_repository.py` (AuditLogRepository ABC)
3. ✅ Each repository inherits from `abc.ABC`
4. ✅ Each repository uses `@abstractmethod` for all methods
5. ✅ No implementation code in abstract classes (pure contracts)
6. ✅ All methods have type hints for parameters and return types
7. ✅ All methods have comprehensive docstrings explaining:
   - Purpose of the method
   - Parameters and their semantics
   - Return type and semantics
   - Exceptions that may be raised
   - Side effects (e.g., database transaction commit)
8. ✅ Method names follow consistent naming convention (create, read, read_by_*, list, update, delete, soft_delete)
9. ✅ All repositories can be imported: `from app.domain.repositories import UserRepository`
10. ✅ Syntax check passes: `python -m py_compile app/domain/repositories/*.py`

**Architectural Notes:**
- Traces to: 06-Repository-Structure (repository pattern and organization)
- Traces to: 03-Architecture §4 (Modular Monolith layers: Domain, Infrastructure)
- Traces to: 07-Backend-Development-Standards §9 (repository patterns)

**Out of Scope:**
- ❌ PostgreSQL implementation (belongs in E3.T11)
- ❌ Query optimization (implementation detail)
- ❌ Caching (future: caching layer)

---

### Requirement 2: CRUD Operation Signatures

**User Story:** As a developer, I want consistent method signatures across all repositories so that domain logic can treat all entities uniformly.

**Description:**

Each repository must define abstract methods for:
- **Create**: INSERT a new entity, return created entity with populated ID
- **Read**: SELECT a single entity by ID, return entity or raise NotFound
- **List**: SELECT multiple entities with pagination and filtering
- **Update**: UPDATE an entity, return updated entity or raise NotFound
- **Delete**: Hard delete an entity (for transient data like audit logs cleanup)
- **Soft Delete**: Mark entity as deleted without removing row (users, assets, reports)
- **Exists**: Check if entity exists by ID

**Rationale:**

Consistent method signatures make it easy to:
- Write generic domain logic that works with any entity
- Test repositories with mock implementations
- Onboard new developers (predictable interface)
- Change implementations without breaking callers

**Acceptance Criteria:**

1. ✅ All repositories define `create(entity)` → entity with ID populated
2. ✅ All repositories define `read(id)` → entity or raise RepositoryError(NotFound)
3. ✅ All repositories define `list(skip, limit, filters)` → List[entity], total_count
4. ✅ All repositories define `update(id, updates)` → updated entity or raise RepositoryError(NotFound)
5. ✅ All repositories define `delete(id)` → None or raise RepositoryError(NotFound)
6. ✅ Repositories with soft-delete semantics define `soft_delete(id)` → entity with deleted_at set
7. ✅ All repositories define `exists(id)` → bool
8. ✅ All repositories define `count(filters)` → int (total matching count)
9. ✅ All methods include type hints: `async def create(self, entity: DomainEntity) -> DomainEntity`
10. ✅ All methods include docstrings with parameter and return documentation
11. ✅ All repositories define `close()` or `__aexit__()` for resource cleanup
12. ✅ No implementation code in any method (all methods raise NotImplementedError or use `pass`)

**Architectural Notes:**
- Traces to: 06-Repository-Structure (CRUD interface specification)
- Traces to: 07-Backend-Development-Standards §9 (repository method conventions)

---

### Requirement 3: Domain-Specific Query Signatures

**User Story:** As a domain developer, I want domain-specific query methods so that application logic doesn't need to construct raw queries.

**Description:**

Each repository must define query methods for common access patterns specific to that entity:

- **UserRepository**: find_by_email(email), find_active_users(), find_admin_users()
- **UploadRepository**: find_by_user(user_id), find_pending_uploads(), find_by_status(status)
- **DigitalAssetRepository**: find_by_user(user_id), find_by_upload(upload_id), find_by_type(asset_type), find_active_assets()
- **AnalysisRepository**: find_by_asset(asset_id), find_by_status(status), find_pending_analyses(), find_by_requested_user(user_id)
- **ReportRepository**: find_by_user(user_id), find_active_reports()
- **AuditLogRepository**: find_by_actor(actor_id), find_by_resource(resource_type, resource_id), find_by_date_range(start, end)

**Rationale:**

Domain-specific queries encapsulate access patterns. This:
- Makes domain logic more expressive (read: "find active reports for user" not "select where is_active and user_id")
- Centralizes query logic (easier to optimize or change later)
- Reduces SQL exposure in domain code
- Makes tests easier to mock (mock these specific queries)

**Acceptance Criteria:**

1. ✅ UserRepository defines all user-specific queries (find_by_email, find_active_users, etc.)
2. ✅ UploadRepository defines upload-specific queries (find_by_user, find_pending_uploads, etc.)
3. ✅ DigitalAssetRepository defines asset-specific queries (find_by_user, find_by_type, etc.)
4. ✅ AnalysisRepository defines analysis-specific queries (find_by_asset, find_pending_analyses, etc.)
5. ✅ ReportRepository defines report-specific queries (find_by_user, find_active_reports, etc.)
6. ✅ AuditLogRepository defines audit-specific queries (find_by_actor, find_by_resource, etc.)
7. ✅ All query methods marked with `@abstractmethod`
8. ✅ All query methods have type hints and return pagination results (List[entity], total_count)
9. ✅ All query methods include docstrings with business semantics
10. ✅ Query methods support filtering: `find_by_user(user_id, skip=0, limit=20, filters={})`
11. ✅ All methods are async: `async def find_by_email(self, email: str) -> User | None`

**Architectural Notes:**
- Traces to: 06-Repository-Structure (domain-specific query patterns)
- Traces to: 02-Domain-Model (entity access patterns)

---

### Requirement 4: Pagination and Filtering Support

**User Story:** As a backend developer, I want standardized pagination and filtering so that all repositories handle large result sets consistently.

**Description:**

All `list` and domain-specific query methods must support:
- **Pagination**: `skip` (offset) and `limit` (page size)
- **Sorting**: `order_by` list of (column, direction) tuples
- **Filtering**: `filters` dict with column conditions
- **Return format**: Tuple of (results: List[entity], total_count: int)

**Rationale:**

Standardized pagination ensures:
- Predictable memory usage (limits don't explode on large tables)
- Consistent API responses (frontend expects {items: [...], total: 100})
- Easy cursor-based pagination in future (next/previous links)

**Acceptance Criteria:**

1. ✅ All `list()` methods accept `skip: int = 0, limit: int = 20, filters: dict | None = None, order_by: list | None = None`
2. ✅ All `list()` methods return `tuple[list[Entity], int]` (results, total_count)
3. ✅ All domain-specific queries support pagination: `async def find_by_user(self, user_id: UUID, skip: int = 0, limit: int = 20) -> tuple[list[Entity], int]`
4. ✅ Filtering supports: exact match, range (>, <, >=, <=), in, like (for text)
5. ✅ Sorting supports ascending/descending on any indexed column
6. ✅ Default limit is 20 (reasonable page size)
7. ✅ Docstrings explain filter format and sorting options
8. ✅ Type hints clarify pagination and result format

**Architectural Notes:**
- Traces to: 07-Backend-Development-Standards §9 (pagination contract)

---

### Requirement 5: Soft-Delete Semantics

**User Story:** As a developer, I want soft-delete methods that mark entities as deleted without destroying audit history so that compliance audits show the deletion event.

**Description:**

Repositories for soft-deletable entities (users, assets, reports) must:
- Define `soft_delete(id)` method that sets deleted_at timestamp without removing row
- Define list/query methods that filter out soft-deleted records by default
- Support `include_deleted: bool` parameter for admin queries
- Return entity with deleted_at populated

**Rationale:**

Soft delete enables:
- Audit trail preservation (deletion event is recorded)
- Undo capability (restore by clearing deleted_at)
- Compliance (show who deleted what, when)
- Referential integrity (deleted assets still exist for foreign keys)

**Acceptance Criteria:**

1. ✅ UserRepository defines `async def soft_delete(self, id: UUID) -> User`
2. ✅ DigitalAssetRepository defines `async def soft_delete(self, id: UUID) -> DigitalAsset`
3. ✅ ReportRepository defines `async def soft_delete(self, id: UUID) -> Report`
4. ✅ All list/query methods filter where `deleted_at IS NULL` by default
5. ✅ All list/query methods support `include_deleted: bool = False` parameter
6. ✅ When `include_deleted=True`, all deleted entities are included in results
7. ✅ `soft_delete()` sets deleted_at to current timestamp via ORM
8. ✅ `soft_delete()` does NOT call `delete()` (hard delete)
9. ✅ Docstrings clearly explain soft-delete semantics

**Architectural Notes:**
- Traces to: 04-Database-Design §10 (Soft Delete Strategy)
- Traces to: 02-Domain-Model (entity lifecycle)

---

### Requirement 6: Async/Transaction Semantics

**User Story:** As a developer, I want async repository methods that work with FastAPI and SQLAlchemy async so that I can use non-blocking I/O throughout the stack.

**Description:**

All repository methods must:
- Be async methods: `async def method_name(...)`
- Accept `session: AsyncSession` parameter for transaction management
- Support transaction context: operations within a single session commit atomically
- Not manage transactions directly (caller manages via FastAPI dependency injection)
- Support optional session parameter for operations that need to participate in a larger transaction

**Rationale:**

Async repositories enable:
- Non-blocking I/O (FastAPI can handle many concurrent requests)
- Natural transaction boundaries (multiple operations in one session = one transaction)
- Testing with mock async sessions
- Future read replica support (route read queries to replica)

**Acceptance Criteria:**

1. ✅ All repository methods are async: `async def create(...)`
2. ✅ All methods accept session parameter (first param after self): `async def create(self, session: AsyncSession, entity: Entity)`
3. ✅ Session is NOT created by repository (caller provides via dependency injection)
4. ✅ Repository does NOT manage commits/rollbacks (caller manages transaction scope)
5. ✅ Multiple repository operations can share session for atomicity:
   ```python
   async with get_db() as session:
       user_repo.create(session, user)
       asset_repo.create(session, asset)  # same session = same transaction
       # single commit
   ```
6. ✅ All query methods support optional filtering within same session
7. ✅ Type hints show AsyncSession: `def __init__(self, session: AsyncSession | None = None)`
8. ✅ Docstrings explain session parameter and transaction semantics

**Architectural Notes:**
- Traces to: 03-Architecture §4 (async stack: FastAPI, SQLAlchemy async, asyncpg)
- Traces to: 07-Backend-Development-Standards §9 (async repository patterns)

---

### Requirement 7: Repository Error Handling

**User Story:** As a developer, I want standardized repository exceptions so that domain logic can handle errors consistently across all repositories.

**Description:**

Repositories must use standard exception types:
- `RepositoryError` (base class, wraps all repository errors)
- `NotFoundError` (entity does not exist)
- `UniqueConstraintError` (duplicate value violates unique constraint)
- `ForeignKeyError` (referenced entity does not exist)
- `TransactionError` (transaction commit failed)

**Rationale:**

Standardized exceptions allow:
- Domain logic to handle repository errors generically
- Clear error semantics (know what went wrong)
- Consistent HTTP error mapping (404 for NotFound, 409 for Conflict, etc.)
- Testing assertions (mock raises RepositoryError(NotFound))

**Acceptance Criteria:**

1. ✅ Exception classes defined in `backend/app/domain/repositories/exceptions.py`
2. ✅ Base `RepositoryError` exception defined
3. ✅ `NotFoundError` defined (raised by read, update, delete on missing ID)
4. ✅ `UniqueConstraintError` defined (raised by create with duplicate unique field)
5. ✅ `ForeignKeyError` defined (raised by create/update with invalid FK)
6. ✅ `TransactionError` defined (raised on commit failure)
7. ✅ All exceptions inherit from RepositoryError
8. ✅ Docstrings explain when each exception is raised
9. ✅ Abstract methods document which exceptions they raise
10. ✅ Example: `async def read(self, id: UUID) -> Entity: """Raises: NotFoundError if entity not found."""`

**Architectural Notes:**
- Traces to: 07-Backend-Development-Standards §6 (error handling patterns)

---

## Acceptance Criteria Summary

| # | Criterion | Status |
|---|-----------|--------|
| **R1** | Abstract repository base classes created | ⏳ Pending |
| **R2** | CRUD operation signatures defined | ⏳ Pending |
| **R3** | Domain-specific query signatures defined | ⏳ Pending |
| **R4** | Pagination and filtering support defined | ⏳ Pending |
| **R5** | Soft-delete semantics defined | ⏳ Pending |
| **R6** | Async/transaction semantics defined | ⏳ Pending |
| **R7** | Repository error handling defined | ⏳ Pending |

---

## Definition of Ready

Before implementation begins:
- ✅ E3.T1 complete (Database Foundation, fixtures)
- ✅ E3.T3-E3.T9 complete (all ORM models and migrations)
- ✅ Domain Model stable (02-Domain-Model.md)
- ✅ Repository Structure stable (06-Repository-Structure.md)
- ✅ Backend Development Standards stable (07-Backend-Development-Standards.md)

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| **Interfaces too prescriptive** | Implementation difficult | Low | Keep interfaces minimal, add methods only for common patterns |
| **Async/session semantics confusing** | Incorrect usage, transaction bugs | Low | Comprehensive docstrings with examples |
| **Soft-delete inconsistency** | Data visibility bugs | Low | Requirement 5 makes it explicit; tested in E3.T11 |

---

## Dependencies & Sequencing

```
E3.T1-E3.T9 (all ORM models and migrations) ✓
E3.T10 (Domain Repository Interfaces) ← YOU ARE HERE
  ├─ Defines abstract contracts
  └─ Enables: E3.T11 (PostgreSQL implementations)

E3.T11 (PostgreSQL Repository Implementations)
  ├─ Implements all abstract methods
  └─ Enables: E4 (Service layer using repositories)
```

---

## Glossary

| Term | Definition |
|---|---|
| **Repository** | Abstraction layer that mediates between domain logic and persistence |
| **Abstract Base Class (ABC)** | Python class with abstract methods that subclasses must implement |
| **CRUD** | Create, Read, Update, Delete — basic persistence operations |
| **Async Session** | SQLAlchemy AsyncSession enabling non-blocking database operations |
| **Soft Delete** | Marking a row as deleted (deleted_at timestamp) without removing it |
| **Domain-Specific Query** | Method encapsulating a common access pattern for an entity |
| **Pagination** | Returning large result sets in pages (skip/limit) |
| **Filtering** | Querying entities by column conditions |
| **Transaction** | Atomic unit of work (all-or-nothing commit) |

---

## References

- 22-Engineering-Backlog: E3.T10 (Domain Repository Interfaces)
- 06-Repository-Structure: Repository pattern organization and design
- 03-Architecture §4: Modular Monolith layers (Domain, Infrastructure)
- 02-Domain-Model: Entity definitions and access patterns
- 07-Backend-Development-Standards §9: Repository patterns and conventions
- 04-Database-Design §10: Soft Delete Strategy
- E3.T1-E3.T9: ORM models providing entity types
