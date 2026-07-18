# E2.T9 Phase 1 Audit — Base Pydantic Schemas

**Date**: 2025-01-28
**Task**: Base Pydantic Schemas Implementation
**Workflow**: Requirements-First

---

## Executive Summary

The schemas directory contains **partial schema infrastructure** with patterns established but **no centralized base configuration**. Current state:

✅ **Existing Infrastructure**:
- Schema directory structure (`app/schemas/`)
- Basic error and health schemas implemented
- CamelCase aliasing partially used (ErrorResponse only)
- RFC 7807 error envelope pattern established
- Datetime handling implemented (ISO 8601 UTC)

❌ **Missing Infrastructure**:
- No base schema class for consistent configuration
- No shared model_config pattern
- No centralized alias generation strategy
- No PaginatedResponse schema
- No TimestampMixin for reusable timestamp fields
- No SortParam / FilterParam schemas
- Duplicate model_config across schemas
- No comprehensive schema tests

---

## Verification Point Summary

| # | Verification Point | Status | Findings |
|---|---|---|---|
| 1 | Schema directory exists | ✅ PASS | `backend/app/schemas/` exists with __init__.py |
| 2 | Base schema class exists | ❌ MISSING | No BaseSchema or similar base class |
| 3 | Model configuration centralized | ❌ MISSING | Each schema defines its own config (no inheritance) |
| 4 | CamelCase alias generation | ⏳ PARTIAL | Manual field-by-field aliasing in ErrorResponse only |
| 5 | ErrorResponse implemented | ✅ PASS | RFC 7807 compliant, includes requestId alias |
| 6 | HealthResponse implemented | ⏳ PARTIAL | No model_config, no aliasing |
| 7 | PaginatedResponse schema | ❌ MISSING | Not implemented |
| 8 | TimestampMixin | ❌ MISSING | Not implemented |
| 9 | SortParam schema | ❌ MISSING | Not implemented |
| 10 | FilterParam schema | ❌ MISSING | Not implemented |
| 11 | Datetime serialization | ✅ PASS | UTC ISO 8601 format in ErrorResponse |
| 12 | UUID serialization | ✅ PASS | UUIDs serialized as strings (ErrorResponse.request_id) |
| 13 | Enum serialization | ⏳ PARTIAL | UserRole (ORM) is enum, but not tested in schemas |
| 14 | Existing schema tests | ⏳ PARTIAL | Exception handlers test ErrorResponse aliasing (2 tests) |
| 15 | populate_by_name | ✅ PARTIAL | ErrorResponse has it, others missing |

---

## Detailed Findings

### 1. Schema Directory Structure ✅ PASS

**Location**: `backend/app/schemas/`

**Current contents**:
```
backend/app/schemas/
├── __init__.py
├── error.py          (ErrorDetail, ErrorBody, ErrorResponse)
├── health.py         (HealthResponse)
└── __pycache__/
```

**Status**: Directory exists with proper initialization.

---

### 2. Base Schema Class ❌ MISSING

**Status**: No base schema exists

Currently, each schema independently defines:
- Imports
- Field configurations
- Serialization rules

**What's needed**:
- A base schema class (e.g., `BaseSchema`) that all other schemas inherit from
- Central location for Pydantic configuration
- Shared alias generation strategy
- Common serialization handlers

**Example pattern needed**:
```python
class BaseSchema(BaseModel):
    """Base schema for all API models."""
    
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        # Alias generation logic here
    )
```

---

### 3. Model Configuration ❌ MISSING (Centralized)

**Current state** (ErrorResponse):
```python
model_config = {"populate_by_name": True}
```

**Current state** (HealthResponse):
```python
# No model_config defined
```

**Issues identified**:
1. Only ErrorResponse has config
2. Configuration is duplicated if/when added to other schemas
3. No central place to manage configuration across all schemas
4. No field serializer for datetime → ISO 8601
5. No field serializer for UUID → string

**What's needed**:
- Centralized `model_config` in BaseSchema
- Consistent `populate_by_name=True` everywhere
- Shared datetime and UUID serializers

---

### 4. CamelCase Alias Generation ⏳ PARTIAL

**Current pattern** (ErrorResponse only):
```python
request_id: UUID = Field(..., alias="requestId", ...)
```

**Issues**:
- Requires manual field-by-field aliasing
- No automatic CamelCase conversion
- HealthResponse doesn't use aliases at all
- Not scalable for schemas with many fields

**Backlog requirement**:
> Configure Pydantic `model_config` for camelCase alias generation (API uses camelCase, Python uses snake_case).

**What's needed**:
- Pydantic `AliasGenerator` for automatic snake_case → camelCase conversion
- Applied in base schema so all schemas inherit it
- Override capability for special cases (e.g., `id` stays as `id`)

**Example implementation**:
```python
from pydantic.alias_generators import to_camel_case

class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel_case,
        populate_by_name=True,
    )
```

---

### 5. ErrorResponse ✅ PASS

**Location**: `backend/app/schemas/error.py` (lines 38-54)

**Status**: RFC 7807 compliant

**Implementation**:
- ✅ ErrorDetail class (field-level validation errors)
- ✅ ErrorBody class (code, message, optional details)
- ✅ ErrorResponse class (error envelope with request_id and timestamp)
- ✅ Explicit `requestId` alias for request_id field
- ✅ `populate_by_name=True` allows both snake_case and camelCase input

**Verification**:
```python
error_body: dict[str, Any] = {
    "error": {
        "code": "rate_limited",
        "message": "Too many requests. Please retry later.",
        "details": [],
    },
    "requestId": str(request_id),  # Uses alias in response
    "timestamp": self._get_iso_timestamp(),
}
```

**Test coverage**: 2 tests in test_exception_handlers.py verify camelCase aliasing

---

### 6. HealthResponse ⏳ PARTIAL

**Location**: `backend/app/schemas/health.py` (lines 16-35)

**Status**: Implemented but incomplete

**Current implementation**:
- ✅ Basic schema structure (status, version, timestamp, dependencies)
- ❌ No model_config
- ❌ No field aliases
- ❌ No datetime serializer
- ❌ Dependencies field optional but description says "not populated yet"

**Missing configuration**:
```python
# Currently missing:
model_config = ConfigDict(populate_by_name=True, ...)
```

**Issues**:
- Timestamp field lacks explicit serialization directive
- No camelCase conversion (API spec calls for snake_case in health, but should be consistent)
- Dependencies field is unstructured dict[str, str] (should be typed)

---

### 7. PaginatedResponse ❌ MISSING

**Backlog requirement**:
> PaginatedResponse (items, total, page, pageSize, totalPages)

**Status**: Not implemented

**Typical use case**:
```python
@router.get("/assets")
def list_assets(...) -> PaginatedResponse[AssetSchema]:
    return PaginatedResponse(
        items=[asset1, asset2],
        total=150,
        page=1,
        pageSize=10,
        totalPages=15,
    )
```

**What's needed**:
- Generic PaginatedResponse[T] class
- Fields: items: list[T], total: int, page: int, pageSize: int, totalPages: int
- Proper camelCase aliases (pageSize, totalPages)
- Type-safe list of generic items

---

### 8. TimestampMixin ❌ MISSING

**Backlog requirement**:
> TimestampMixin (createdAt, updatedAt as UTC datetime)

**Status**: Not implemented

**Typical use case**:
```python
class AssetSchema(TimestampMixin):
    id: UUID
    filename: str
    # Inherits created_at and updated_at
```

**What's needed**:
- Mixin class with created_at and updated_at fields
- Both fields: `datetime` type, UTC timezone
- Both fields: ISO 8601 serialization
- Both fields: camelCase aliases (createdAt, updatedAt)
- Optional or required? (Likely required for entities, optional for requests)

---

### 9. SortParam ❌ MISSING

**Backlog requirement**:
> SortParam

**Status**: Not implemented

**Typical use case**:
```python
@router.get("/assets")
def list_assets(sort: SortParam = Query(...)) -> PaginatedResponse[AssetSchema]:
    # sort = "createdAt:desc" or "filename:asc"
    pass
```

**What's needed**:
- Schema for sort parameters
- Support format: `field:direction` (e.g., `createdAt:desc`)
- Validate field names against allowed sortable fields
- Validate direction (asc/desc)
- May be query parameter parser or schema

---

### 10. FilterParam ❌ MISSING

**Backlog requirement**:
> FilterParam

**Status**: Not implemented

**Typical use case**:
```python
@router.get("/assets")
def list_assets(filter: FilterParam = Query(...)) -> PaginatedResponse[AssetSchema]:
    # filter = "status:active,created_after:2025-01-01"
    pass
```

**What's needed**:
- Schema for filter parameters
- Support multiple filter conditions
- Common filters: status, created_after, created_before, search term (q)
- Type validation for each filter type (dates, enums, strings)
- May be query parameter parser or schema

---

### 11. Datetime Serialization ✅ PASS

**Current state**:
- ErrorResponse uses datetime
- Health Response has datetime timestamp
- Both expected to serialize as ISO 8601 UTC

**Verification** (from error.py):
```python
timestamp: datetime = Field(..., examples=["2024-02-10T08:00:00Z"])
```

**Status**: Format specified, but no explicit field_serializer

**What's needed**:
- Explicit field_serializer for datetime → ISO 8601 with microseconds
- Ensure UTC timezone is enforced
- Format: `YYYY-MM-DDTHH:mm:ss.ffffffZ` (microseconds + Z suffix)

---

### 12. UUID Serialization ✅ PASS

**Current state** (ErrorResponse):
```python
request_id: UUID = Field(
    ..., alias="requestId", examples=["5b6c7d8e-9f01-4a2b-8c3d-4e5f60718293"]
)
```

**Status**: UUID serializes as string by default in Pydantic v2

**Verification**: Tests in test_exception_handlers.py confirm UUIDs appear as strings in JSON

---

### 13. Enum Serialization ⏳ PARTIAL

**Current state**:
- UserRole enum exists in app/models/user.py (StrEnum)
- No schema-layer enum serialization tested

**Status**: Not tested for schema serialization

**What's needed**:
- Schemas that use enums (UploadStatus, AnalysisStatus, UserRole, etc.)
- Ensure enums serialize as strings (not enum names)
- Tests for enum serialization

---

### 14. Existing Schema Tests ⏳ PARTIAL

**Current test coverage**:

**From `test_exception_handlers.py`**:
- `TestErrorResponseCamelCaseAliasing` (2 tests)
  - `test_request_id_aliased_as_request_id_in_json` ✅
  - `test_error_response_schema_includes_all_fields` (implied) ✅

**From other tests**: None found

**What's needed**:
- Dedicated test file: `backend/tests/unit/test_schemas.py`
- Tests for base schema class
- Tests for each concrete schema
- Tests for serialization, deserialization, aliasing
- Tests for datetime UTC handling
- Tests for UUID string conversion
- Tests for enum handling
- Tests for PaginatedResponse generics
- Tests for SortParam/FilterParam validation

---

### 15. populate_by_name ✅ PARTIAL

**Current state** (ErrorResponse):
```python
model_config = {"populate_by_name": True}
```

**Effect**: Allows both `request_id` (snake_case) and `requestId` (camelCase) in request bodies

**Status**: Implemented in ErrorResponse only

**What's needed**:
- Move to BaseSchema so all schemas inherit it
- Ensures flexible input parsing (clients can use either naming style)

---

## Backlog Requirements Mapping

| Requirement | Status | Where |
|---|---|---|
| Create `app/schemas/` directory | ✅ DONE | `backend/app/schemas/` |
| PaginatedResponse schema | ❌ TODO | Not implemented |
| ErrorResponse (RFC 7807) | ✅ PARTIAL | Implemented, needs inheritance from base |
| TimestampMixin (createdAt, updatedAt) | ❌ TODO | Not implemented |
| SortParam schema | ❌ TODO | Not implemented |
| FilterParam schema | ❌ TODO | Not implemented |
| CamelCase alias generation | ⏳ PARTIAL | Manual only, needs AliasGenerator |
| Datetime fields → ISO 8601 UTC | ✅ PARTIAL | Format specified, no serializer |
| UUIDs → strings | ✅ PARTIAL | Default behavior, no tests |
| Pydantic model_config centralized | ❌ TODO | Not in base schema |
| Unit tests for schemas | ⏳ PARTIAL | Only exception handler aliasing tests |

---

## Current Architecture State

### What Exists
- ✅ Schema directory structure
- ✅ ErrorResponse (RFC 7807 compliant)
- ✅ HealthResponse (partial)
- ✅ Basic field aliasing patterns
- ✅ populate_by_name in ErrorResponse
- ✅ Datetime and UUID examples

### What's Missing
- ❌ BaseSchema class with shared configuration
- ❌ Centralized model_config
- ❌ Automatic camelCase alias generation
- ❌ PaginatedResponse schema
- ❌ TimestampMixin
- ❌ SortParam and FilterParam
- ❌ Explicit datetime field_serializer
- ❌ Comprehensive schema tests
- ❌ Schema inheritance patterns

---

## Phase 2 Implementation Plan

### Priority 1: Foundation
1. **Create BaseSchema class**
   - Inherit from Pydantic BaseModel
   - Central model_config with:
     - `populate_by_name=True`
     - `alias_generator=to_camel_case`
   - Explicit datetime field_serializer (ISO 8601 UTC)
   - All schemas inherit from BaseSchema

2. **Create TimestampMixin**
   - Fields: created_at, updated_at (both datetime)
   - Both use camelCase aliases
   - Both required

3. **Update existing schemas**
   - ErrorResponse inherit from BaseSchema (remove duplicate config)
   - HealthResponse inherit from BaseSchema (add config)
   - Verify aliasing works automatically

### Priority 2: Pagination & Filtering
4. **Create PaginatedResponse[T]**
   - Generic with items: list[T]
   - Fields: total, page, pageSize, totalPages
   - All numeric, no datetime needed

5. **Create SortParam**
   - Parse and validate sort expressions
   - Format: "field:direction"

6. **Create FilterParam**
   - Parse and validate filter expressions
   - Support common filter types

### Priority 3: Validation
7. **Write comprehensive test suite**
   - Serialization/deserialization
   - Alias generation (both directions)
   - Datetime UTC handling
   - UUID string conversion
   - Generic types for pagination
   - Enum serialization

---

## Environment Variables & Configuration

**No new environment variables needed for base schemas.**

All schema configuration is:
- Compile-time (Pydantic model_config)
- In Python code (not environment-driven)
- Inherited by all schema subclasses

---

## Dependencies & Blockers

### Internal Dependencies
- **E2.T2** (Settings Management) — ✅ Complete (no schema dependency)
- **E2.T3** (Structured Logging) — ✅ Complete (no schema dependency)
- **E2.T5** (Exception Handlers) — ✅ Complete (ErrorResponse used)

### External Dependencies
- **Pydantic v2** — ✅ Available (already used in ErrorResponse, settings)
- **Python 3.12+** — ✅ Available (AliasGenerator available)

### No Blockers Identified
Can proceed independently.

---

## Risk Assessment

### Low Risk
- Pydantic is already used (no new dependency)
- BaseSchema inheritance is low-impact (backward compatible)
- Existing ErrorResponse tests verify aliasing

### Medium Risk
- Automatic camelCase generation might conflict with API if not all endpoints use camelCase
- PaginatedResponse generics need careful typing
- Existing schemas will need updates to inherit from BaseSchema

### Testing Risk
- Enum serialization needs coverage
- Generic types (PaginatedResponse[T]) need careful testing
- Datetime UTC precision needs verification

---

## Conclusion

**Base Pydantic schemas are partially in place** but lack centralized configuration. Implementation requires:

1. Creating BaseSchema with centralized model_config
2. Refactoring existing schemas to inherit from base
3. Implementing PaginatedResponse, TimestampMixin, SortParam, FilterParam
4. Creating comprehensive test suite

**Estimated Phase 2 effort**: 3-4 hours
- BaseSchema + existing schema updates: 1h
- New schemas (Paginated, Timestamp, Sort, Filter): 1.5h
- Tests: 1.5h

**Recommendation**: Proceed to Phase 2 implementation.

---

*End of Phase 1 Audit Report*

