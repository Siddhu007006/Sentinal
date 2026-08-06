# E3.T8 — Audit Logs ORM Model and Migration — Design Document

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-audit-logs-t8/design.md |
| **Feature** | audit-logs-orm-model-t8 |
| **Status** | In Design |
| **Owner** | Engineering Team |
| **Traces to** | 22-Engineering-Backlog E3.T8 |

---

## Executive Summary

This design document specifies the implementation of the AuditLog ORM model and its database migration. The AuditLog model is an immutable entity that records every state-changing operation in Sentinel for compliance, forensics, and security analysis.

**Key Design Decisions:**
1. AuditLog inherits from BaseModel (provides UUID PK, created_at, updated_at)
2. Immutability enforced at both ORM and database layers (no update/delete methods)
3. JSONB for before_state and after_state to capture full entity snapshots
4. Nullable actor_id to support system-initiated audit events
5. Unique constraint on (actor_id, resource_id, occurred_at) to prevent duplicates
6. Role-based access control (RBAC) at database level to prevent unauthorized modification

---

## 1. Audit Log ORM Model Design

### 1.1 Model Structure

**File:** `backend/app/models/audit_log.py`

**Base Class:** BaseModel (provides id, created_at, updated_at, deleted_at)

**Table Name:** `audit_logs`

### 1.2 Field Specifications

| Field | Type | Constraints | Purpose | Default |
|---|---|---|---|---|
| **id** | UUID | PK, auto-generated | Unique audit record identifier | uuid.uuid4() |
| **actor_id** | UUID \| None | FK → users.id, nullable | Who performed the action (None = system action) | None |
| **actor_role** | str | VARCHAR(20), NOT NULL | Role of actor at time of action (snapshot for audit trail) | N/A |
| **action** | str | VARCHAR(100), NOT NULL | Operation type (e.g., "CREATE_ASSET", "DELETE_REPORT") | N/A |
| **resource_type** | str | VARCHAR(100), NOT NULL | Entity type affected (e.g., "DigitalAsset", "Report") | N/A |
| **resource_id** | UUID | NOT NULL | ID of entity affected | N/A |
| **before_state** | dict \| None | JSONB, nullable | Full entity state before operation (null for creates) | None |
| **after_state** | dict \| None | JSONB, nullable | Full entity state after operation (null for deletes) | None |
| **ip_address** | str \| None | INET, nullable | Client IP address (from X-Forwarded-For header) | None |
| **request_id** | str \| None | VARCHAR(255), nullable | Correlation ID for tracing distributed requests | None |
| **user_agent** | str \| None | VARCHAR(500), nullable | Client HTTP User-Agent header | None |
| **success** | bool | NOT NULL | Operation succeeded (true) or failed (false) | True |
| **failure_reason** | str \| None | VARCHAR(1000), nullable | Error message if success=false | None |
| **occurred_at** | datetime | TIMESTAMPTZ, NOT NULL | Server timestamp of operation (UTC) | now() |
| **created_at** | datetime | TIMESTAMPTZ, NOT NULL | When audit record was created (inherited from BaseModel) | now() |
| **updated_at** | datetime | TIMESTAMPTZ, NOT NULL | When audit record was last updated (inherited from BaseModel) | now() |

### 1.3 Field Type Mappings (SQLAlchemy Mapped[] Syntax)

```python
actor_id: Mapped[UUID | None]          # Foreign key to users.id, nullable
actor_role: Mapped[str]                # Role at time of action
action: Mapped[str]                    # Action type (CREATE, UPDATE, DELETE, etc.)
resource_type: Mapped[str]             # Entity type (DigitalAsset, Report, etc.)
resource_id: Mapped[UUID]              # ID of entity affected
before_state: Mapped[dict | None]      # JSONB snapshot before change
after_state: Mapped[dict | None]       # JSONB snapshot after change
ip_address: Mapped[str | None]         # Client IP (INET type in PostgreSQL)
request_id: Mapped[str | None]         # Request correlation ID
user_agent: Mapped[str | None]         # HTTP User-Agent
success: Mapped[bool]                  # Operation success flag
failure_reason: Mapped[str | None]     # Error message if failed
occurred_at: Mapped[datetime]          # Operation timestamp (UTC)
```

### 1.4 Indexes

| Index Name | Columns | Purpose | Rationale |
|---|---|---|---|
| PK | id | Primary key | Fast lookup by audit ID |
| UQ | (actor_id, resource_id, occurred_at) | Unique constraint | Prevent duplicate audit records for same resource by same actor at same time |
| IX | actor_id | Query by actor | Fast filtering by user ("who made changes?") |
| IX | (resource_type, resource_id) | Query by resource | Fast filtering by affected entity ("what changed?") |
| IX | occurred_at DESC | Query by timestamp | Efficient chronological queries (DESC for "latest first") |

### 1.5 Immutability Constraints

**ORM Layer:**
- AuditLog class does NOT expose update() or delete() methods
- Application code must never call session.update(audit_log)
- Application code must never call session.delete(audit_log)
- Documentation enforces semantic immutability

**Database Layer (Role-Based Access Control):**
- Application database role has GRANT SELECT, INSERT on audit_logs
- Application database role has NO GRANT for UPDATE, DELETE on audit_logs
- Admin role retains full privileges for forensics and debugging
- Attempt to UPDATE or DELETE raises PostgreSQL permission denied error

### 1.6 __repr__() Implementation

The __repr__() method must return a useful debugging string WITHOUT exposing sensitive fields (state blobs):

```
<AuditLog id=550e8400-e29b-41d4-a716-446655440000 action=CREATE_ASSET actor=jane resource=DigitalAsset:abc123...>
```

Does NOT include:
- before_state (could contain sensitive data)
- after_state (could contain sensitive data)
- ip_address, user_agent, request_id (could enable tracking)
- failure_reason (could leak security details)

---

## 2. Database Immutability Strategy

### 2.1 Role-Based Access Control (RBAC)

**Goal:** Prevent any modification to audit logs, even if application is compromised.

**Implementation:**

```sql
-- Application database role permissions
GRANT SELECT, INSERT ON audit_logs TO app_user;
GRANT USAGE ON SEQUENCE audit_logs_id_seq TO app_user;

-- Explicitly REVOKE UPDATE and DELETE
REVOKE UPDATE, DELETE ON audit_logs FROM app_user;

-- Admin role retains all privileges for forensics
GRANT ALL PRIVILEGES ON audit_logs TO app_admin;
```

**Enforcement:**
1. INSERT audit records: ✅ Allowed (GRANT INSERT)
2. SELECT audit records: ✅ Allowed (GRANT SELECT)
3. UPDATE audit_logs: ❌ Raises "permission denied" error
4. DELETE from audit_logs: ❌ Raises "permission denied" error
5. TRUNCATE audit_logs: ❌ Only admin role allowed (not application role)

### 2.2 Unique Constraint

**Constraint:** UNIQUE(actor_id, resource_id, occurred_at)

**Purpose:** Prevent duplicate audit records

**Scenario:** If the same actor performs the same action on the same resource at the exact same microsecond, the unique constraint prevents duplicate inserts.

**Error Handling:** Application layer should catch psycopg2.IntegrityError if duplicate is attempted.

### 2.3 Immutability by Design

**Core Principle:** Audit logs must be append-only (no modification or deletion allowed).

**Architectural Layers:**
1. **ORM Layer:** AuditLog class design forbids update/delete operations
2. **Database Layer:** GRANT statements prevent UPDATE/DELETE at SQL level
3. **Repository Layer:** AuditLogRepository exposes only create() and query() methods (no update/delete)
4. **Application Layer:** Semantic documentation enforces audit trail integrity principle

---

## 3. Alembic Migration Strategy

### 3.1 Migration File Structure

**Location:** `backend/migrations/versions/YYYYMMDD_HHMM_<rev>_add_audit_logs_table.py`

**Generated via:** `alembic revision --autogenerate -m "Add audit_logs table"`

### 3.2 Migration Operations (upgrade)

The migration performs:

1. **Create audit_logs table**
   - All columns with correct types
   - NOT NULL constraints
   - Default values (occurred_at=now(), success=true)
   - Foreign key to users.id (actor_id)

2. **Create Indexes**
   - Primary key on id
   - Unique index on (actor_id, resource_id, occurred_at)
   - Index on actor_id
   - Composite index on (resource_type, resource_id)
   - Index on occurred_at DESC

3. **Set Immutability**
   - Execute GRANT statements to restrict application role
   - GRANT SELECT, INSERT only
   - REVOKE UPDATE, DELETE

4. **Verify Schema**
   - All columns present
   - All constraints enforced
   - All indexes created

### 3.3 Migration Operations (downgrade)

The downgrade reverses all changes:
1. DROP INDEX statements
2. DROP TABLE audit_logs CASCADE
3. Implicit: Constraints and foreign keys dropped with table

### 3.4 Migration Testing

Before deployment, verify:

```bash
# Upgrade path
alembic upgrade head

# Downgrade path
alembic downgrade -1

# Re-upgrade to ensure idempotency
alembic upgrade head

# Verify table schema
\d audit_logs

# Verify indexes
\di audit_logs*

# Verify permissions
\dp audit_logs
```

---

## 4. ORM Model Implementation Details

### 4.1 Inheritance

```python
class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    # ... fields ...
```

**Inherited from BaseModel:**
- id: UUID PK (auto-generated)
- created_at: Timestamp (set on INSERT)
- updated_at: Timestamp (set on INSERT, updated on UPDATE)
- deleted_at: Soft-delete timestamp (nullable)

**Defined in AuditLog:**
- actor_id, actor_role, action, resource_type, resource_id
- before_state, after_state
- ip_address, request_id, user_agent
- success, failure_reason
- occurred_at

### 4.2 Foreign Key to users.id

```python
actor_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id"),
    nullable=True,
    index=True,
    comment="Actor who performed the action (FK to users, nullable for system actions)"
)
```

**Nullable:** True (system-initiated operations have no actor)

**Index:** Yes (common filter: "actions by this user")

**Cascading:** Soft delete (users can be soft-deleted without removing audit trail)

### 4.3 JSONB Columns

```python
before_state: Mapped[dict | None] = mapped_column(
    JSONB,
    nullable=True,
    comment="Entity state before operation (null for creates)"
)

after_state: Mapped[dict | None] = mapped_column(
    JSONB,
    nullable=True,
    comment="Entity state after operation (null for deletes)"
)
```

**Type:** JSONB (binary JSON, indexed, queryable)

**Nullable:** Yes (creates have no before_state, deletes have no after_state)

**Content:** Full entity snapshot (all fields, not just changes)

**Purpose:** Enable forensic analysis ("what was the old value?")

### 4.4 Timestamp Fields

```python
occurred_at: Mapped[datetime] = mapped_column(
    TIMESTAMP(timezone=True),
    nullable=False,
    server_default=func.now(),
    comment="Server timestamp of operation (UTC)"
)
```

**Type:** TIMESTAMP WITH TIMEZONE (UTC always)

**Server Default:** now() (database generates on INSERT)

**Purpose:** Record when operation occurred (separate from created_at audit record timestamp)

### 4.5 Table Arguments

```python
__table_args__ = (
    # Unique constraint to prevent duplicate audits
    UniqueConstraint(
        "actor_id",
        "resource_id",
        "occurred_at",
        name="uq_audit_logs_actor_resource_time"
    ),
    # Composite index for resource change queries
    Index(
        "ix_audit_logs_resource",
        "resource_type",
        "resource_id",
    ),
    # Index for chronological queries (DESC for latest first)
    Index(
        "ix_audit_logs_occurred_at",
        "occurred_at",
        postgresql_ops={"occurred_at": "DESC"},
    ),
)
```

---

## 5. Export and Discovery

### 5.1 Model Export

**File:** `backend/app/models/__init__.py`

Add to imports:
```python
from app.models.audit_log import AuditLog
```

Add to __all__:
```python
__all__ = [
    # ... existing exports ...
    "AuditLog",
]
```

**Purpose:** Enables Alembic to discover AuditLog during autogenerate.

---

## 6. ORM Model Tests

### 6.1 Unit Tests

**File:** `backend/tests/unit/test_audit_log_model.py`

**Test Coverage:**

| Test | Purpose | Validates |
|---|---|---|
| Instantiate with all fields | Model accepts all audit fields | Model instantiation works |
| Instantiate with required fields | Model works with minimal fields | Required vs. optional fields clear |
| Nullable actor_id | System actions can have no actor | Semantic completeness |
| Default success=true | Operation success defaults to true | Sensible defaults |
| Default before_state=None | Creates have no before state | Semantic correctness |
| Default after_state=None | Deletes have no after state (in practice) | Semantic correctness |
| __repr__() returns string | String representation exists | Debugging support |
| __repr__() excludes state blobs | State blobs not in repr | Security (no data leaks) |
| Model exports from app.models | AuditLog importable | Discovery by Alembic |
| Field types correct | String, UUID, bool, dict types | Type correctness |

### 6.2 Integration Tests

**Test Coverage:**

| Test | Purpose | Validates |
|---|---|---|
| Insert audit record via ORM | INSERT allowed by application role | GRANT INSERT working |
| SELECT audit record | SELECT allowed by application role | GRANT SELECT working |
| UPDATE audit_logs fails | UPDATE denied by database | Immutability enforced |
| DELETE audit_logs fails | DELETE denied by database | Immutability enforced |
| Unique constraint violation | Duplicate (actor_id, resource_id, occurred_at) fails | Constraint enforced |

### 6.3 Test Fixtures

Use `db_session` fixture from `backend/tests/conftest.py`:

```python
@pytest.mark.asyncio
async def test_insert_audit_log(db_session: AsyncSession) -> None:
    """Test: INSERT audit record succeeds."""
    audit_log = AuditLog(
        actor_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        actor_role="analyst",
        action="CREATE_ASSET",
        resource_type="DigitalAsset",
        resource_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
        after_state={"name": "test_asset"},
        occurred_at=datetime.now(UTC),
    )
    db_session.add(audit_log)
    await db_session.commit()
    
    # Verify insert succeeded
    assert audit_log.id is not None
    assert audit_log.created_at is not None
```

---

## 7. Error Handling

### 7.1 Repository Exception Types

Future repository layer (E4+) will define:

```python
class AuditLogImmutableError(Exception):
    """Attempt to modify immutable audit log."""
    pass

class AuditLogInsertError(Exception):
    """Failed to insert audit log record."""
    pass

class AuditLogQueryError(Exception):
    """Failed to query audit logs."""
    pass

class DuplicateAuditLogError(Exception):
    """Duplicate audit record for (actor_id, resource_id, occurred_at)."""
    pass
```

### 7.2 Permission Errors

Database permission errors are caught at application layer:

```python
from psycopg2 import errors as psycopg2_errors
from sqlalchemy.exc import OperationalError

try:
    session.execute(update(AuditLog).where(...))
except OperationalError as e:
    if isinstance(e.orig, psycopg2_errors.InsufficientPrivilege):
        # Application role lacks UPDATE privilege
        logger.error("Audit log tampering attempted: UPDATE denied by database")
        raise AuditLogImmutableError("Cannot modify audit logs") from e
```

---

## 8. Implementation Notes

### 8.1 Key Decisions

1. **Immutability Enforcement at Two Layers**
   - ORM layer: No update/delete methods exposed
   - Database layer: GRANT statements prevent SQL-level modifications
   - Rationale: Defense in depth — if ORM is bypassed, database still protects

2. **JSONB for State Snapshots**
   - Not individual fields (more flexible for schema changes)
   - Rationale: Schema can evolve without audit log schema changes
   - Rationale: Enable forensic analysis ("what was the old value?")

3. **Nullable actor_id**
   - System-initiated operations (cleanup jobs, retries) have no actor
   - Rationale: Audit trail must cover all operations, not just user-initiated
   - Rationale: Security monitoring needs complete picture

4. **Unique Constraint on (actor_id, resource_id, occurred_at)**
   - Prevents accidental duplicate audits
   - Rationale: Same actor, same resource, same microsecond = same operation
   - Rationale: Database-level enforcement prevents race conditions

5. **Server Default for occurred_at**
   - `occurred_at` defaults to database now() (not application now())
   - Rationale: Prevents timezone confusion and clock skew
   - Rationale: Audit timestamp should reflect server time, not client time

### 8.2 Security Considerations

1. **State Blob Sanitization**
   - Before and after state should NOT contain sensitive fields (passwords, tokens)
   - Application layer must sanitize before inserting
   - Future: Implement AuditLog.sanitize_state() helper

2. **IP Address Capture**
   - Extracted from X-Forwarded-For header in FastAPI middleware
   - Or direct request.client.host if no proxy
   - Used for geographic tracking and abuse detection

3. **Request ID for Correlation**
   - Links audit log to application logs
   - Enables "follow the request" troubleshooting
   - Generated by middleware or application

4. **Immutability as Defense**
   - Even if attacker gains database access, audit trail cannot be tampered with
   - Compliance requirement (SOC2, PCI-DSS, HIPAA)

### 8.3 Performance Considerations

1. **Indexes for Common Queries**
   - actor_id: "What did user X do?"
   - (resource_type, resource_id): "What happened to this asset?"
   - occurred_at DESC: "What's the latest activity?"

2. **JSONB Advantages**
   - Queryable: Can filter by nested fields without deserialization
   - Indexed: GIN indexes possible for complex queries
   - Flexible: Schema evolution without ALTER TABLE

3. **Partition Strategy (Future)**
   - Time-series data ideal for partitioning
   - Partition by occurred_at (monthly or daily)
   - Archive old partitions for cost savings

---

## 9. Traceability

| Requirement | Design Section | Implementation | Test |
|---|---|---|---|
| R1 AC #1: AuditLog ORM model defined | §1.2, §1.3, §4 | audit_log.py | test_audit_log_model.py |
| R1 AC #2: Inherits from BaseModel | §4.1 | class AuditLog(BaseModel) | test_model_inherits_from_basemodel |
| R1 AC #3: All required fields | §1.2, §1.3 | Mapped[] declarations | test_instantiate_with_all_fields |
| R1 AC #4: Field types correct | §1.3 | Type annotations | test_field_types_are_correct |
| R1 AC #5: __tablename__ = "audit_logs" | §1.1, §4.2 | __tablename__ | test_model_has_tablename |
| R1 AC #6: __repr__() excludes state | §1.6, §4.5 | __repr__() implementation | test_repr_excludes_state |
| R1 AC #7: Immutability documented | §2, §8.2 | Class docstring | Design document |
| R1 AC #8: AuditLog exported | §5.1 | __init__.py import | test_imports_audit_log |
| R1 AC #9: Syntax check | §4 | Python 3.12+ syntax | Ruff, MyPy checks |
| R1 AC #10: No circular imports | §4, §5 | No circular deps | test_import_audit_log |
| R2 AC #1: Immutable constraint documented | §2, §8.2 | Migration + docstring | Design document |
| R2 AC #2: Unique index on (actor_id, resource_id, occurred_at) | §1.4, §4.5 | UniqueConstraint | Generated migration |
| R2 AC #3: GRANT SELECT, INSERT | §2.1, §3.2 | Migration SQL | Integration tests |
| R2 AC #4: UPDATE fails with permission error | §2.1, §7 | REVOKE UPDATE | test_update_audit_logs_fails |
| R2 AC #5: DELETE fails with permission error | §2.1, §7 | REVOKE DELETE | test_delete_audit_logs_fails |
| R3 AC #1-10: Migration generated and validated | §3, §8 | alembic revision --autogenerate | Manual review + CI |
| R5 AC #1-11: Test coverage complete | §6 | test_audit_log_model.py | All tests pass |

---

## 10. Out of Scope (Future Tasks)

| Item | Owner | Reason |
|---|---|---|
| Audit event publishing logic | E4 Service layer | Business logic, not schema |
| Audit log query/retrieval API | E4 Route handlers | HTTP endpoints, not ORM |
| Retention policies | E4+ Compliance | Future: data lifecycle |
| Audit dashboards | UI/Analytics | UI layer, not backend |
| Real-time audit streaming | E5+ Observability | Messaging system needed |

---

## 11. Success Criteria

- [ ] design.md created and reviewed
- [ ] audit_log.py implemented (AuditLog model complete)
- [ ] models/__init__.py exports AuditLog
- [ ] Alembic migration generated and reviewed
- [ ] All unit tests pass (model instantiation, defaults, types, __repr__)
- [ ] All integration tests pass (INSERT allowed, UPDATE/DELETE denied)
- [ ] Ruff: 0 violations
- [ ] MyPy: 0 errors (strict mode)
- [ ] Pytest: All tests pass (including E3.T1-E3.T7)
- [ ] No regressions in prior tasks

---

## References

- 22-Engineering-Backlog: E3.T8 (Audit Logs ORM Model and Migration)
- 04-Database-Design §4: ERD (audit_logs table)
- 04-Database-Design §11: Audit Strategy
- 07-Backend-Development-Standards §8: ORM model conventions
- 08-Security-Architecture §6: Audit trail integrity
