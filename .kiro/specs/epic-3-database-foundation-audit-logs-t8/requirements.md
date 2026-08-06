# E3.T8 — Audit Logs ORM Model and Migration

## Specification Document

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-audit-logs-t8/requirements.md |
| **Feature** | audit-logs-orm-model-t8 |
| **Status** | In Review |
| **Owner** | Engineering Team |
| **Traces to** | 22-Engineering-Backlog E3.T8 |
| **Dependencies** | E3.T1 (Database Foundation), E3.T2 (Alembic Configuration), E3.T3 (User ORM Model) |

---

## Introduction

E3.T8 creates the **AuditLog** ORM model, which records every state-changing operation in the system for compliance, debugging, and security analysis.

This task focuses on:
1. Defining the AuditLog ORM model with immutable audit fields
2. Generating the Alembic migration for the `audit_logs` table
3. Enforcing immutability at the application layer (no UPDATE/DELETE allowed)
4. Establishing the audit schema for enterprise observability

**Scope Boundary:**
- ✅ AuditLog ORM model definition (fields, constraints, immutability)
- ✅ Alembic migration for `audit_logs` table creation
- ✅ Database role permissions (no UPDATE/DELETE on audit_logs)
- ✅ ORM model tests (field defaults, immutability enforcement)
- ❌ Audit event publishing/trigger logic (E4+: Service layer)
- ❌ Audit log query/retrieval API (E4+: Route handlers)
- ❌ Retention policies (future: compliance automation)
- ❌ Audit log dashboards (future: analytics)

---

## Requirements

### Requirement 1: AuditLog ORM Model Definition

**User Story:** As a compliance officer, I want every state-changing operation to be immutably recorded so that I can trace all changes for compliance audits and security investigations.

**Description:**

The AuditLog model must:
- Inherit from BaseModel (providing UUID PK, immutable timestamps)
- Define all fields required by Database Design spec (04-Database-Design §4 ERD)
- Use appropriate SQLAlchemy type mappings (Mapped[...] syntax)
- Include comprehensive docstrings explaining field purposes
- Capture actor (who), action (what), resource (what was changed), and state (before/after)
- Store IP address and request context for security correlation
- Be immutable by design (no application layer UPDATEs or DELETEs)

**Rationale:**

Audit logs are the foundation of compliance, forensics, and incident response. Once written, they must never be modified or deleted—accidental or malicious. This is enforced both by ORM design (no update() methods) and database permissions (database role has no UPDATE/DELETE privileges).

**Acceptance Criteria:**

1. ✅ AuditLog model defined in `backend/app/models/audit_log.py`
2. ✅ AuditLog inherits from BaseModel (not Base directly)
3. ✅ All required fields present with correct types:
   - `id` (Mapped[UUID], PK, auto-generated)
   - `actor_id` (Mapped[UUID | None], FK → users, nullable for system actions)
   - `actor_role` (Mapped[str], captures role at time of action)
   - `action` (Mapped[str], e.g., "CREATE_ASSET", "DELETE_REPORT")
   - `resource_type` (Mapped[str], e.g., "DigitalAsset", "Report")
   - `resource_id` (Mapped[UUID], identifies what changed)
   - `before_state` (Mapped[dict | None], JSONB, state before change)
   - `after_state` (Mapped[dict | None], JSONB, state after change)
   - `ip_address` (Mapped[str | None], inet type, client IP)
   - `request_id` (Mapped[str | None], trace correlation ID)
   - `user_agent` (Mapped[str | None], client context)
   - `success` (Mapped[bool], operation success flag)
   - `failure_reason` (Mapped[str | None], error message if failed)
   - `occurred_at` (Mapped[datetime], server timestamp of operation)
4. ✅ AuditLog class has `__tablename__ = "audit_logs"`
5. ✅ AuditLog class has `__repr__()` that exposes only non-sensitive fields
6. ✅ Model enforces immutability constraint in docstring and comments
7. ✅ Model file has comprehensive docstrings
8. ✅ AuditLog exported from `backend/app/models/__init__.py` for Alembic discovery
9. ✅ Model passes syntax check: `python -m py_compile app/models/audit_log.py`
10. ✅ No circular imports: `python -c "from app.models import AuditLog; print(AuditLog)"`

**Architectural Notes:**
- Traces to: 04-Database-Design §4 ERD (audit_logs table specification)
- Traces to: 04-Database-Design §11 (Audit Strategy)
- Traces to: 02-Domain-Model (observability as a cross-cutting concern)
- Traces to: 07-Backend-Development-Standards §8 (ORM model conventions)

**Out of Scope:**
- ❌ Audit event publishing (belongs in E4: Service layer)
- ❌ Audit log querying API (belongs in E4: Route handlers)
- ❌ Retention policies or archival (future: compliance automation)

---

### Requirement 2: Database Immutability Enforcement

**User Story:** As a security engineer, I want the database to prevent any UPDATE or DELETE operations on audit logs so that malicious actors cannot tamper with the audit trail.

**Description:**

The audit_logs table must:
- Have a unique index on `(actor_id, resource_id, occurred_at)` to prevent duplicate records
- Enforce immutability at the database level via role-based access control
- Deny UPDATE and DELETE privileges to the application database role
- Allow only INSERT and SELECT privileges to the application role
- Support TRUNCATE only via admin role (not application)

**Rationale:**

Database-level enforcement is the strongest defense against audit tampering. Even if the application is compromised, the audit trail cannot be modified. This is standard in compliance frameworks (SOC2, PCI-DSS, HIPAA).

**Acceptance Criteria:**

1. ✅ Immutable constraint documented in migration
2. ✅ Unique index on (actor_id, resource_id, occurred_at) prevents duplicate audits
3. ✅ Database role has GRANT SELECT, INSERT on audit_logs (not UPDATE or DELETE)
4. ✅ Attempt to UPDATE audit_logs raises permission error
5. ✅ Attempt to DELETE audit_logs raises permission error
6. ✅ Application can INSERT new audit records without error
7. ✅ Application can SELECT/query audit records without error
8. ✅ Admin role retains full privileges (for forensics, debugging)
9. ✅ Integration test: `UPDATE audit_logs SET action = 'X'` fails with permission denied
10. ✅ Integration test: `DELETE FROM audit_logs` fails with permission denied

**Architectural Notes:**
- Traces to: 04-Database-Design §11 (Audit Strategy, immutability by role)
- Traces to: 08-Security-Architecture §6 (audit trail integrity)

---

### Requirement 3: Alembic Migration for AuditLog

**User Story:** As a developer, I want the audit_logs table migration to be automatically generated and validated so that the schema is version-controlled and reversible.

**Description:**

The migration must:
- Be generated via `alembic revision --autogenerate`
- Create the `audit_logs` table with all columns, constraints, and indexes
- Include immutability enforcement (role-based access control)
- Be syntactically valid Python
- Include comprehensive docstrings and metadata

**Rationale:**

Alembic autogenerate ensures the migration stays synchronized with the ORM model. The migration serves as the single source of truth for schema evolution.

**Acceptance Criteria:**

1. ✅ Migration file created in `backend/migrations/versions/`
2. ✅ Migration file named with timestamp pattern: YYYYMMDD_HHMM_<rev>_<slug>.py
3. ✅ Migration file is syntactically valid Python
4. ✅ upgrade() function creates audit_logs table with all columns
5. ✅ upgrade() function creates unique index on (actor_id, resource_id, occurred_at)
6. ✅ upgrade() function creates indexes for efficient querying:
   - Index on actor_id (who performed actions)
   - Index on resource_type, resource_id (what was changed)
   - Index on occurred_at DESC (chronological queries)
7. ✅ upgrade() function sets immutability via GRANT statements (if using custom SQL)
8. ✅ downgrade() function drops audit_logs table
9. ✅ Migration can be imported without errors
10. ✅ **CRITICAL: Migration has been manually reviewed** before commit
11. ✅ No regressions in E3.T1-E3.T7 tests after migration

**Architectural Notes:**
- Traces to: 22-Engineering-Backlog E3.T2 (migration workflow)
- Traces to: 07-Backend-Development-Standards §8 (migration standards)

---

### Requirement 4: Migration Validation

**User Story:** As a DBA, I want the migration to be manually reviewed and validated to ensure the schema correctly enforces immutability before deployment.

**Description:**

The migration must:
- Have all generated SQL manually reviewed for accuracy
- Verify table names and column types match the ORM model
- Verify indexes match the requirements
- Verify immutability constraints are enforced
- Pass upgrade/downgrade cycle testing
- Pass CI validation stages

**Rationale:**

Manual review is essential for audit trail migrations. A flaw in the immutability enforcement could compromise compliance.

**Acceptance Criteria:**

1. ✅ Migration code reviewed for accuracy and completeness
2. ✅ Table name is "audit_logs" (matches __tablename__)
3. ✅ All columns present with correct types and defaults
4. ✅ Unique index on (actor_id, resource_id, occurred_at) present
5. ✅ All query-optimization indexes present
6. ✅ Nullable fields correct (actor_id, before_state, after_state, ip_address, request_id, user_agent, failure_reason are nullable)
7. ✅ occurred_at has server default (now())
8. ✅ downgrade() reverses all changes
9. ✅ Migration passes upgrade/downgrade cycle: `alembic upgrade head && alembic downgrade base` succeeds
10. ✅ Migration passes CI pipeline validation
11. ✅ No regressions in prior test suites (E3.T3-E3.T7)

**Architectural Notes:**
- Traces to: 12-CI-CD-Architecture §3 (migration validation in CI)
- Traces to: 04-Database-Design §11 (audit immutability validation)

---

### Requirement 5: ORM Model Test Coverage

**User Story:** As a developer, I want comprehensive tests for the AuditLog model to ensure it correctly captures and enforces immutability constraints.

**Description:**

Tests must cover:
- Model instantiation with valid data
- Default values and server-side defaults
- Field type validation
- Immutability semantics (no update() or delete() operations)
- Timestamp auto-population (occurred_at)
- Nullable fields behavior
- Database immutability enforcement (INSERT allowed, UPDATE/DELETE denied)

**Rationale:**

Unit tests validate that the ORM model and database schema work together to prevent audit tampering.

**Acceptance Criteria:**

1. ✅ Test file created: `backend/tests/unit/test_audit_log_model.py`
2. ✅ Test: instantiate AuditLog with valid data (actor_id, action, resource_type, resource_id, after_state, occurred_at) succeeds
3. ✅ Test: default values are correct (success=true, before_state=None, after_state=None for creates)
4. ✅ Test: occurred_at is set on creation
5. ✅ Test: actor_id can be None (system actions)
6. ✅ Test: model __repr__() returns useful string without exposing state blobs
7. ✅ Integration test: insert valid audit record via ORM succeeds
8. ✅ Integration test: attempt UPDATE on audit_logs raises permission error
9. ✅ Integration test: attempt DELETE from audit_logs raises permission error
10. ✅ Integration test: insert duplicate (actor_id, resource_id, occurred_at) raises unique constraint error
11. ✅ All tests pass: `pytest tests/unit/test_audit_log_model.py -v`

**Architectural Notes:**
- Traces to: 07-Backend-Development-Standards §7 (ORM testing patterns)
- Traces to: 04-Database-Design §11 (audit immutability validation)

---

## Acceptance Criteria Summary

| # | Criterion | Status |
|---|-----------|--------|
| **R1** | AuditLog ORM model defined and exported | ⏳ Pending |
| **R2** | Database immutability enforcement configured | ⏳ Pending |
| **R3** | Alembic migration generated and validated | ⏳ Pending |
| **R4** | Migration manually reviewed | ⏳ Pending |
| **R5** | ORM model test coverage complete | ⏳ Pending |

---

## Definition of Ready

Before implementation begins:
- ✅ E3.T1 complete (Database Foundation, fixtures, engine disposal)
- ✅ E3.T2 complete (Alembic Configuration, migration workflow)
- ✅ E3.T3 complete (User ORM Model, first migration pattern established)
- ✅ PostgreSQL 16 container operational
- ✅ Alembic ready to generate migrations
- ✅ CI pipeline ready to validate migrations

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| **Immutability not enforced at DB** | Audit tampering possible | Low | Manual review of GRANT statements (R4 AC #1) |
| **Generated migration has errors** | Schema corruption | Low | Manual review and testing (R4) |
| **Indexes insufficient for queries** | Poor audit log performance | Low | Review indexes match requirements |
| **Unique constraint conflicts** | Duplicate audit records possible | Very Low | Constraint enforced at DB, tested in CI |

---

## Dependencies & Sequencing

```
E3.T1 (Database Foundation)
E3.T2 (Alembic Configuration)
E3.T3 (User ORM Model) ✓
  ├─ Provides User entity and FK reference
  └─ Enables: E3.T8 ✓

E3.T8 (Audit Logs ORM Model & Migration) ← YOU ARE HERE
  ├─ Defines immutable audit table
  ├─ Establishes immutability pattern
  └─ Enables: E3.T9+ (other models)
```

---

## Glossary

| Term | Definition |
|---|---|
| **Audit Log** | Immutable record of a state-changing operation (create, update, delete) for compliance and forensics |
| **Immutable** | Cannot be modified after creation (enforced at DB and application layers) |
| **Before/After State** | JSONB snapshots of entity state before and after the operation |
| **Actor** | User who initiated the operation (nullable for system-initiated operations) |
| **Resource** | Entity that was changed (identified by resource_type and resource_id) |
| **Role-Based Access Control (RBAC)** | Database permissions tied to roles to enforce immutability |

---

## References

- 22-Engineering-Backlog: E3.T8 (Audit Logs ORM Model and Migration)
- 04-Database-Design §4: ERD (audit_logs table)
- 04-Database-Design §11: Audit Strategy
- 02-Domain-Model: Observability as cross-cutting concern
- 06-Repository-Structure §6: models/ directory organization
- 07-Backend-Development-Standards §8: ORM model conventions
- 08-Security-Architecture §6: Audit trail integrity
- E3.T3 Completion: User ORM Model (FK reference)
