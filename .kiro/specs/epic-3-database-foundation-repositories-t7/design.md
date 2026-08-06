# E3.T7 — Repository Pattern & Query Optimization — Design Specification

## Document Information

| Field | Value |
|---|---|
| **Feature Name** | epic-3-database-foundation-repositories-t7 |
| **Task ID** | E3.T7 |
| **Specification Version** | 1.0.0 |
| **Status** | Design Phase (Ready for Implementation) |
| **Owner** | Engineering Team |
| **Audience** | Engineers, Code Reviewers, Architects |
| **Dependencies** | E3.T1–E3.T6 complete, Requirements.md approved, 03-Architecture approved |
| **Last Updated** | 2026-08-02 |

---

## 1. Purpose, Scope, Dependencies

### 1.1 Purpose

This Design specification explains **how** the approved E3.T7 requirements will be implemented. It provides the architecture, interface signatures, lazy loading strategies, and implementation patterns for repositories and query optimization.

### 1.2 Scope

**Phase A (E3.T7) — In Scope:**
- Repository interface structure for 4 entities (User, Upload, DigitalAsset, Analysis)
- Repository implementation patterns (PostgreSQL async) for 4 entities
- Query optimization strategy (N+1 prevention)
- Lazy loading strategy decisions
- Error mapping strategy
- Pagination and sorting implementation
- Soft-delete query filtering
- Transaction lifecycle integration with FastAPI

**Phase B (E3.T8–E3.T9) — Out of Scope for E3.T7:**
- Report repository (deferred until Report ORM model created)
- RefreshToken repository (deferred until RefreshToken ORM model created)

**Other Out of Scope:**
- API endpoint implementation (E4)
- Service layer logic (E4)
- Actual test code (covered in Tasks)

### 1.3 Dependencies

| Dependency | Status | Note |
|---|---|---|
| E3.T1–T6 (ORM Models) | ✅ Complete | Repositories wrap these models |
| 03-Architecture | ✅ Approved | Repository layer sits in Infrastructure |
| SQLAlchemy 2.0+ | ✅ Available | Async ORM |
| Python 3.12+ | ✅ Available | Type hints, async/await |

---

## 2. Architecture: Repository Layer Position

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4: APPLICATION                                         │
│ (Services, Use Cases, Business Logic)                        │
│ ← Depends on Domain layer (no database imports)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ LAYER 3: DOMAIN                                              │
│ (Entities, Value Objects, Domain Services, Repository ABCs) │
│ ← Repository interfaces ONLY (no SQLAlchemy)               │
│ ← Thrown exceptions (NotFound, AlreadyExists, etc.)        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ LAYER 2: INFRASTRUCTURE                                      │
│ (PostgreSQL Repositories, Error Mappers, Query Builders)     │
│ ← Repository implementations (SQLAlchemy async)             │
│ ← Exception converters                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ LAYER 1: PERSISTENCE                                         │
│ (PostgreSQL Database, ORM Models, Connection Pool)           │
│ ← E3.T1–T6 ORM models                                       │
└─────────────────────────────────────────────────────────────┘
```

**Key Principle:** Application layer never imports from Infrastructure or Models. Application depends only on Domain layer (entities + repository interfaces).

---

## 3. Domain Repository Interfaces

### 3.1 Base Repository Interface

All repositories inherit from a base interface defining common CRUD contract:

```python
# backend/app/domain/repositories/base.py

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional
from uuid import UUID
from datetime import datetime

T = TypeVar('T')  # Entity type

class BaseRepository(ABC, Generic[T]):
    """
    Abstract repository interface for CRUD operations.
    Defines the contract all Domain repositories must implement.
    """

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Create a new entity. Returns entity with generated ID and timestamps."""
        pass

    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> T:
        """Retrieve entity by ID. Raises NotFound if not found."""
        pass

    @abstractmethod
    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        **filters
    ) -> tuple[List[T], int]:
        """
        List entities with pagination.
        Returns (results, total_count).
        """
        pass

    @abstractmethod
    async def update(self, entity_id: UUID, updates: dict) -> T:
        """Update entity fields. Returns updated entity."""
        pass

    @abstractmethod
    async def delete(self, entity_id: UUID) -> None:
        """Delete (soft or hard) entity."""
        pass
```

### 3.2 Specific Repository Interfaces

Each entity has a repository interface in `backend/app/domain/repositories/`:

**UserRepository** (`user.py`):
```python
class UserRepository(BaseRepository[User]):
    @abstractmethod
    async def get_by_email(self, email: str) -> User:
        """Retrieve user by email (case-insensitive)."""
        pass

    @abstractmethod
    async def list_active_users(
        self, skip: int = 0, limit: int = 100
    ) -> tuple[List[User], int]:
        """List users with is_active=true."""
        pass
```

**AnalysisRepository** (`analysis.py`):
```python
class AnalysisRepository(BaseRepository[Analysis]):
    @abstractmethod
    async def get_completed_analysis(
        self, asset_id: UUID, analyzer_key: str, analyzer_version: str
    ) -> Optional[Analysis]:
        """
        Retrieve completed analysis for idempotency check.
        Returns None if not found (unlike get_by_id which raises).
        """
        pass

    @abstractmethod
    async def list_by_asset(
        self, asset_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[List[Analysis], int]:
        """List all analyses for an asset."""
        pass

    @abstractmethod
    async def list_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> tuple[List[Analysis], int]:
        """List analyses filtered by status."""
        pass

    @abstractmethod
    async def list_pending_for_worker(self, limit: int) -> List[Analysis]:
        """
        Worker job queue: oldest pending analyses first (FIFO).
        Used by Celery workers to pick up next job.
        """
        pass
```

**Similar patterns for (Phase A):** UploadRepository, DigitalAssetRepository.

**Future Extension (Phase B — E3.T8–E3.T9, when ORM models created):**
- ReportRepository (same pattern)
- RefreshTokenRepository (same pattern with modified lifecycle, no soft-delete)

All interface methods:
- Use async/await
- Take `AsyncSession` at construction time (injected, not global)
- Return domain entities (not ORM models)
- Raise domain exceptions (NotFound, AlreadyExists, etc.)
- Never import SQLAlchemy or infrastructure code

---

## 4. Infrastructure Repository Implementations

### 4.1 PostgreSQL Repository Base

All PostgreSQL repositories inherit from a base:

```python
# backend/app/infrastructure/database/repositories/base.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, and_
from sqlalchemy.exc import IntegrityError, NoResultFound

class PostgreSQLRepository(BaseRepository[T]):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, entity: T) -> T:
        """
        Insert entity, flush to get ID, return domain entity.
        Does NOT commit (transaction managed by FastAPI dependency).
        """
        orm_model = self._to_orm(entity)
        self.session.add(orm_model)
        await self.session.flush()
        return self._to_domain(orm_model)

    async def get_by_id(self, entity_id: UUID) -> T:
        stmt = select(self._model_class).where(self._model_class.id == entity_id)
        orm_obj = await self.session.scalar(stmt)
        if not orm_obj:
            raise NotFound(f"{self._entity_name} with id {entity_id} not found")
        return self._to_domain(orm_obj)

    async def list(
        self, skip: int = 0, limit: int = 100, 
        sort_by: str = "created_at", sort_order: str = "desc",
        **filters
    ) -> tuple[List[T], int]:
        # Build WHERE clause from filters
        stmt = select(self._model_class)
        where_clauses = self._build_where_clauses(**filters)
        if where_clauses:
            stmt = stmt.where(and_(*where_clauses))

        # Count total
        count_stmt = select(func.count()).select_from(self._model_class).where(and_(*where_clauses))
        total = await self.session.scalar(count_stmt)

        # Apply ordering
        order_col = getattr(self._model_class, sort_by)
        if sort_order.lower() == "desc":
            stmt = stmt.order_by(desc(order_col))
        else:
            stmt = stmt.order_by(asc(order_col))

        # Apply pagination
        stmt = stmt.offset(skip).limit(limit)

        # Execute with eager loading for relationships
        stmt = self._apply_eager_loading(stmt)

        results = await self.session.scalars(stmt)
        return ([self._to_domain(orm) for orm in results], total)

    async def delete(self, entity_id: UUID) -> None:
        orm_obj = await self.session.get(self._model_class, entity_id)
        if not orm_obj:
            return  # Idempotent: deleting non-existent entity is no-op
        
        if hasattr(orm_obj, 'deleted_at'):
            orm_obj.deleted_at = datetime.utcnow()
        else:
            await self.session.delete(orm_obj)

    @abstractmethod
    def _build_where_clauses(self, **filters) -> List:
        """Subclasses override to implement filter-specific WHERE clauses."""
        pass

    @abstractmethod
    def _apply_eager_loading(self, stmt):
        """Subclasses override to add joinedload/selectin for relationships."""
        pass

    def _to_orm(self, entity: T) -> Any:
        """Convert domain entity to ORM model."""
        pass  # Implemented in subclasses

    def _to_domain(self, orm_obj: Any) -> T:
        """Convert ORM model to domain entity."""
        pass  # Implemented in subclasses
```

### 4.2 Error Mapping

```python
# backend/app/infrastructure/database/repositories/exceptions.py

from sqlalchemy.exc import IntegrityError, NoResultFound
from app.domain.exceptions import (
    NotFound, AlreadyExists, ConstraintViolation, ConflictError
)

def map_db_exception(exc: Exception) -> Exception:
    """Convert SQLAlchemy exceptions to domain exceptions."""
    if isinstance(exc, NoResultFound):
        return NotFound("Entity not found")
    if isinstance(exc, IntegrityError):
        if "UNIQUE constraint failed" in str(exc):
            return AlreadyExists("Entity with this value already exists")
        if "FOREIGN KEY constraint failed" in str(exc):
            return ConstraintViolation("Invalid reference to related entity")
        return ConflictError("Data integrity violation")
    return exc  # Re-raise unknown exceptions
```

### 4.3 Concrete Repository Example: AnalysisRepository

```python
# backend/app/infrastructure/database/repositories/analysis.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload, joinedload
from app.domain.repositories import AnalysisRepository as IAnalysisRepository
from app.domain.entities import Analysis
from app.infrastructure.models import Analysis as AnalysisORM
from app.infrastructure.models import DigitalAsset as DigitalAssetORM
from app.domain.exceptions import NotFound

class PostgreSQLAnalysisRepository(IAnalysisRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
        self._model_class = AnalysisORM
        self._entity_name = "Analysis"

    async def get_completed_analysis(
        self, asset_id: UUID, analyzer_key: str, analyzer_version: str
    ) -> Optional[Analysis]:
        """
        Retrieve completed analysis for idempotency check.
        Returns None if not found.
        """
        stmt = select(AnalysisORM).where(
            and_(
                AnalysisORM.digital_asset_id == asset_id,
                AnalysisORM.analyzer_key == analyzer_key,
                AnalysisORM.analyzer_version == analyzer_version,
                AnalysisORM.status == "completed"
            )
        )
        orm_obj = await self.session.scalar(stmt)
        return self._to_domain(orm_obj) if orm_obj else None

    async def list_by_asset(
        self, asset_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[List[Analysis], int]:
        """List all analyses for an asset with eager loading."""
        # Query uses selectin for DigitalAsset relationship (per E3.T6 design)
        stmt = select(AnalysisORM).where(
            AnalysisORM.digital_asset_id == asset_id
        ).order_by(
            desc(AnalysisORM.created_at)
        ).offset(skip).limit(limit)

        stmt = stmt.options(selectinload(AnalysisORM.digital_asset))

        results = await self.session.scalars(stmt)
        total = await self.session.scalar(
            select(func.count()).select_from(AnalysisORM).where(
                AnalysisORM.digital_asset_id == asset_id
            )
        )
        return ([self._to_domain(orm) for orm in results], total)

    async def list_pending_for_worker(self, limit: int) -> List[Analysis]:
        """
        Worker job queue: oldest pending analyses first (FIFO).
        No pagination needed (worker is throttled by available resources).
        """
        stmt = select(AnalysisORM).where(
            AnalysisORM.status == "pending"
        ).order_by(
            asc(AnalysisORM.created_at)
        ).limit(limit)

        results = await self.session.scalars(stmt)
        return [self._to_domain(orm) for orm in results]

    def _to_domain(self, orm_obj: AnalysisORM) -> Analysis:
        """Convert ORM to domain entity (constructor call)."""
        return Analysis(
            id=orm_obj.id,
            digital_asset_id=orm_obj.digital_asset_id,
            # ... other fields
        )
```

---

## 5. Query Optimization Strategy

### 5.1 N+1 Prevention: Selectin Loading Strategy

**Problem:** Fetching 100 analyses and accessing `analysis.digital_asset` for each → 101 database queries.

**Solution per E3.T6 Design (§5.1–§5.2):**

```python
# Default: selectin loading (separate SELECT IN query)
stmt = select(AnalysisORM).options(
    selectinload(AnalysisORM.digital_asset)
)

# Result: 2 queries total
# Query 1: SELECT * FROM analyses
# Query 2: SELECT * FROM digital_assets WHERE id IN (asset_id_1, asset_id_2, ...)
```

**Why selectin by default:**
- At 10M rows, JOIN is expensive; SELECT IN is faster
- Separate queries can be cached independently
- Avoids Cartesian product if reverse relationship is accessed

**Explicit joinedload for specific paths:**
- Performance-critical code can use `joinedload()` if profiling shows JOIN is faster
- Example: Dashboard rendering asset + analysis together → joinedload safe (not Cartesian product)

### 5.2 Index Utilization

Repository methods are designed to use indexes defined in E3.T6:

**AnalysisRepository.list_by_asset():**
- Uses `ix_analyses_asset_status` for WHERE digital_asset_id = ?
- Benefited by: (digital_asset_id, status) index

**AnalysisRepository.list_pending_for_worker():**
- Uses `ix_analyses_pending` (partial index WHERE status = 'pending')
- Benefited by: (created_at) partial index reduces index size

**Query planner respects indexes automatically via PostgreSQL query optimizer.**

### 5.3 Batch Operations (Future Optimization)

For bulk inserts (e.g., creating 1000 analyses):

```python
# Bulk insert (future, if needed for performance)
await self.session.execute(
    insert(AnalysisORM),
    [{"id": uuid4(), "digital_asset_id": aid, ...} for aid in asset_ids]
)
```

Not required for E3.T7 (bulk operations are future optimization). Single inserts sufficient for correctness.

---

## 6. Soft-Delete Implementation

Soft-delete repositories (User, DigitalAsset) filter by default:

```python
class PostgreSQLUserRepository(IUserRepository):
    async def list(self, skip: int = 0, limit: int = 100, **filters):
        where_clauses = [
            UserORM.deleted_at.is_(None)  # Soft-delete filter
        ]
        # ... rest of query

    async def get_by_email(self, email: str) -> User:
        stmt = select(UserORM).where(
            and_(
                UserORM.email == email.lower(),
                UserORM.deleted_at.is_(None)  # Soft-delete filter
            )
        )
        # ...
```

Hard-delete repositories (AuditLog) do NOT filter:

```python
class PostgreSQLAuditLogRepository(IAuditLogRepository):
    async def list(self, skip: int = 0, limit: int = 100, **filters):
        # NO soft-delete filter; audit logs are immutable
```

---

## 7. Transaction Lifecycle Integration

Repositories do NOT commit/rollback. Transaction lifecycle is managed by FastAPI:

```python
# backend/app/core/dependencies.py

from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncSession:
    async with get_async_session() as session:
        try:
            yield session
            await session.commit()  # Commit on success
        except Exception:
            await session.rollback()  # Rollback on exception
            raise
        finally:
            await session.close()
```

Repository code:
```python
class PostgreSQLUserRepository(IUserRepository):
    async def create(self, user: User) -> User:
        orm_obj = UserORM(...)
        self.session.add(orm_obj)
        await self.session.flush()  # Flush to get ID, but don't commit
        return self._to_domain(orm_obj)
        # Commit happens in FastAPI dependency, not here
```

**Benefit:** All repository operations in a single request are part of the same transaction (atomic).

---

## 8. Pagination and Sorting

All `list_*()` methods return `(results, total_count)`:

```python
results, total = await user_repo.list(skip=0, limit=50, sort_by="email", sort_order="asc")

# UI can render:
# - Page of results
# - Total count (for "Page 1 of 10" UI)
# - Total pages = ceil(total / limit)
```

Default sort is `created_at DESC` (newest first) across all repositories.

Supported sort columns per repository are defined in repository interfaces.

---

## 9. Testing Strategy

### Unit Tests

Mock repositories implement the interface without hitting the database:

```python
class MockAnalysisRepository(IAnalysisRepository):
    def __init__(self):
        self.storage: dict[UUID, Analysis] = {}

    async def get_by_id(self, entity_id: UUID) -> Analysis:
        if entity_id not in self.storage:
            raise NotFound(f"Analysis {entity_id} not found")
        return self.storage[entity_id]

    # ...
```

Service layer tests inject mock repositories:

```python
def test_request_analysis():
    mock_analysis_repo = MockAnalysisRepository()
    service = AnalysisService(
        analysis_repo=mock_analysis_repo,
        # ...
    )
    # Test business logic without database
```

### Integration Tests

Real repositories tested against containerized PostgreSQL:

```python
async def test_analysis_list_by_asset_with_eager_loading():
    # Create asset and analyses
    asset = await asset_repo.create(DigitalAsset(...))
    for i in range(10):
        await analysis_repo.create(Analysis(digital_asset_id=asset.id, ...))

    # Query
    results, total = await analysis_repo.list_by_asset(asset.id)

    # Verify no N+1: only 2 queries total (analyses + assets via selectin)
    assert len(results) == 10
    assert total == 10
    # Verify relationships are loaded without additional queries
    for analysis in results:
        assert analysis.digital_asset is not None
```

---

## 10. Risk Analysis

### Risk 1: ORM Leakage into Domain Layer

**Risk:** Domain layer imports SQLAlchemy models by mistake.

**Mitigation:** 
- Strict import policy (linting rule)
- Domain layer returns and accepts only domain entities, not ORM models
- Type hints enforce entity types, not ORM types

**Detection:** Linting + type checking catches SQLAlchemy imports in domain/

### Risk 2: N+1 Queries in Production

**Risk:** Missing eager loading causes hidden performance issue.

**Mitigation:**
- Integration tests verify query count (via SQL logging)
- Performance tests run at 100K rows to simulate production scale
- Repository methods document their eager loading strategy

**Detection:** Integration tests with query count assertions

### Risk 3: Constraint Violations Not Caught

**Risk:** Database constraint exception not mapped to domain exception.

**Mitigation:**
- Exception mapping function tested for each constraint type
- Tests verify IntegrityError → AlreadyExists mapping

**Detection:** Error handling tests

---

## 11. Alternatives Considered

### Alternative 1: Active Record (ORM Models Do Their Own CRUD)

**Pro:** Less boilerplate.
**Con:** ORM leaks into Domain layer; violates separation of concerns; hard to mock for testing.
**Chosen:** Repository Pattern (E3.T7); better separation.

### Alternative 2: Manual Query Builder (Custom SQL)

**Pro:** Maximum control; can optimize specific queries.
**Con:** Raw SQL is error-prone; harder to refactor; loses type safety of ORM.
**Chosen:** SQLAlchemy ORM (E3.T1–E3.T6); framework handles safety.

### Alternative 3: Eager Load Everything

**Pro:** Simple; no N+1 issues.
**Con:** At 10M rows, loading all relationships kills performance.
**Chosen:** Selective eager loading (selectin by default, joinedload for specific paths).

---

## 12. Traceability Matrix

| Requirement | Design Section(s) |
|---|---|
| R1 – Domain Interfaces | §3 (Interface Design) |
| R2 – PostgreSQL Implementations | §4 (Implementation Patterns) |
| R3 – CRUD Operations | §4.1 (Base Repository) |
| R4 – Domain-Specific Queries | §4.3 (Concrete Examples) |
| R5 – N+1 Prevention | §5.1 (Selectin Loading) |
| R6 – Pagination & Sorting | §8 (Pagination) |
| R7 – Soft-Delete | §6 (Soft-Delete Filtering) |
| R8 – Error Handling | §4.2 (Exception Mapping) |
| R9 – Transaction Safety | §7 (Transaction Lifecycle) |
| R10 – Testability | §9 (Testing Strategy) |

---

## Design Review Checklist

- [x] Repository pattern separates Domain from Infrastructure
- [x] Interfaces are pure Python ABCs (no SQLAlchemy)
- [x] Implementations handle async/await correctly
- [x] N+1 prevention strategy (selectin by default)
- [x] Soft-delete filtering applied by default
- [x] Error mapping converts DB exceptions to domain exceptions
- [x] Transaction lifecycle managed by FastAPI, not repositories
- [x] Pagination returns (results, total_count) tuple
- [x] Testing strategy enables mocking and integration tests
- [x] Lazy loading strategies from E3.T5/E3.T6 implemented
- [x] Ready for implementation

---

## Sign-Off

**Design Specification:**
- Version: 1.0.0 (Final)
- Status: **READY FOR IMPLEMENTATION**
- Location: `.kiro/specs/epic-3-database-foundation-repository-t7/design.md`

**Next Steps:** Proceed to Task Specification (tasks.md) with implementation breakdown.
