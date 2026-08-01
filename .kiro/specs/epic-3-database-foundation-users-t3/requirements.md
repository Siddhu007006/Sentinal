# E3.T3 — User ORM Model and Migration

## Specification Document

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-users-t3/requirements.md |
| **Feature** | users-orm-model-t3 |
| **Status** | In Review |
| **Owner** | Engineering Team |
| **Traces to** | 22-Engineering-Backlog E3.T3 |
| **Dependencies** | E3.T1 (Database Foundation), E3.T2 (Alembic Configuration) |

---

## Introduction

E3.T3 creates the first persistent domain entity: the **User** model. This is the identity anchor for the entire system—every digital asset, analysis, report, and audit log is owned by or attributed to a User.

This task focuses on:
1. Defining the User ORM model with all required fields and constraints
2. Generating the initial Alembic migration capturing the complete user schema
3. Validating the migration workflow end-to-end (generate, review, test, commit)
4. Establishing standards for migration quality and review

**Scope Boundary:**
- ✅ User ORM model definition (fields, constraints, indexes, enums)
- ✅ Initial Alembic migration (table creation, constraints, indexes, defaults)
- ✅ Migration generation and manual review workflow
- ✅ Migration testing (upgrade/downgrade, constraint validation)
- ✅ ORM model tests (field defaults, constraints, relationships)
- ❌ Authentication logic (E4: Authentication & Authorization)
- ❌ API endpoints (E4+: Route handlers)
- ❌ Repository pattern (E3.T10: Domain Repository Interfaces)
- ❌ Password hashing/validation (E4.T2: Password Hashing Service)
- ❌ User management services (E4: User domain layer)

---

## Requirements

### Requirement 1: User ORM Model Definition

**User Story:** As a developer, I want a User ORM model that represents the authoritative registry of all Sentinel platform users so that the system has a consistent identity anchor for all entities and operations.

**Description:**

The User model must:
- Inherit from BaseModel (providing UUID PK, timestamps, common patterns)
- Define all fields required by Database Design spec (04-Database-Design §5.1)
- Use appropriate SQLAlchemy type mappings (Mapped[...] syntax)
- Include docstrings explaining field purposes and constraints
- Provide a UserRole enum for role-based access control
- Be properly registered in the models package for Alembic discovery

**Rationale:**

User is the root identity entity. Every subsequent entity (Upload, DigitalAsset, Analysis, Report) will reference this model. Establishing the correct model structure now prevents schema corrections later.

**Acceptance Criteria:**

1. ✅ User model defined in `backend/app/models/user.py`
2. ✅ User inherits from BaseModel (not Base directly)
3. ✅ All required fields present with correct types:
   - `email` (Mapped[str], unique, indexed)
   - `password_hash` (Mapped[str], not null)
   - `full_name` (Mapped[str], not null)
   - `role` (Mapped[str], with CHECK constraint)
   - `is_active` (Mapped[bool], default true)
   - `is_verified` (Mapped[bool], default false)
   - `created_at`, `updated_at` (inherited from BaseModel)
   - `deleted_at` (Mapped[datetime | None], nullable, for soft delete)
4. ✅ UserRole enum defined with values: ADMIN, ANALYST, VIEWER
5. ✅ User class has `__tablename__ = "users"`
6. ✅ User class has `__repr__()` for debugging (does not expose password_hash)
7. ✅ Model file has comprehensive docstrings
8. ✅ User exported from `backend/app/models/__init__.py` for Alembic discovery
9. ✅ Model passes syntax check: `python -m py_compile app/models/user.py`
10. ✅ No circular imports: `python -c "from app.models import User; print(User)"`

**Architectural Notes:**
- Traces to: 04-Database-Design §5.1 (User table specification)
- Traces to: 02-Domain-Model (User as identity anchor)
- Traces to: 07-Backend-Development-Standards §8 (ORM model conventions)

**Out of Scope:**
- ❌ Password validation or hashing logic (belongs in E4.T2)
- ❌ Email verification flow (belongs in E4)
- ❌ User authentication or login (belongs in E4)
- ❌ Repository implementation (belongs in E3.T10)

---

### Requirement 2: Database Constraints and Indexes

**User Story:** As an operator, I want database constraints and indexes to enforce data integrity and enable efficient queries so that the User table remains consistent and queryable even under concurrent access.

**Description:**

The User table must enforce:
- **Unique constraint** on email (case-insensitive login lookups)
- **Check constraint** on role (only admin/analyst/viewer allowed)
- **Not null constraints** on required fields
- **Indexes** for efficient queries:
  - Primary key index (id)
  - Unique index (email)
  - Composite index (is_active, created_at DESC) for user list queries

**Rationale:**

Email uniqueness prevents duplicate accounts. Role validation ensures only valid RBAC values are stored. Indexes enable fast lookups by email (login) and listing active users by creation date (admin dashboard).

**Acceptance Criteria:**

1. ✅ Unique constraint on email enforced at database level (cannot insert duplicate)
2. ✅ Check constraint on role enforced (only 'admin'/'analyst'/'viewer' allowed)
3. ✅ Not null constraints on email, password_hash, full_name, role, is_active, is_verified
4. ✅ Primary key index on id (automatic)
5. ✅ Unique index on email (automatic from unique=True)
6. ✅ Composite index on (is_active, created_at DESC) for admin queries
7. ✅ Constraints named following convention (ck_, uq_, pk_, ix_) for clarity in migrations
8. ✅ Integration test: attempt duplicate email insert → unique violation
9. ✅ Integration test: attempt invalid role → check constraint violation
10. ✅ Integration test: attempt null value on required field → not null violation

**Architectural Notes:**
- Traces to: 04-Database-Design §5.1 (constraints and indexes specification)
- Traces to: 08-Security-Architecture §4 (user identity uniqueness)

---

### Requirement 3: Initial Alembic Migration

**User Story:** As a developer, I want the initial Alembic migration to be generated automatically from the User model so that schema changes are version-controlled and can be reviewed before deployment.

**Description:**

The migration must:
- Be generated via `alembic revision --autogenerate` (Alembic compares ORM model to database state)
- Create the `users` table with all columns, constraints, and indexes
- Include appropriate default values and server-side defaults
- Be syntactically valid Python (importable without errors)
- Include comprehensive docstrings and metadata headers
- Include both upgrade() and downgrade() functions

**Rationale:**

Alembic autogenerate detects schema changes from the ORM model and generates migration scripts. This automation reduces manual SQL writing and ensures migrations stay synchronized with the ORM.

**Acceptance Criteria:**

1. ✅ Migration file created in `backend/migrations/versions/`
2. ✅ Migration file named with timestamp pattern: YYYYMMDD_HHMM_<rev>_<slug>.py
3. ✅ Migration file is syntactically valid Python: `python -m py_compile migrations/versions/<file>.py`
4. ✅ Migration includes docstring with revision ID and description
5. ✅ Migration includes revision metadata (revision, down_revision, branch_labels, depends_on)
6. ✅ upgrade() function creates users table with all columns
7. ✅ upgrade() function creates UNIQUE constraint on email
8. ✅ upgrade() function creates CHECK constraint on role
9. ✅ upgrade() function creates indexes (primary key, unique email, composite is_active/created_at)
10. ✅ downgrade() function drops users table
11. ✅ Migration can be imported: `python -c "import migrations.versions.<file>"`
12. ✅ **CRITICAL: Migration has been manually reviewed** before being committed (see Requirement 4)

**Architectural Notes:**
- Traces to: 22-Engineering-Backlog E3.T2 (migration workflow)
- Traces to: 07-Backend-Development-Standards §8 (migration standards)
- Traces to: 12-CI-CD-Architecture §3 (migration validation in CI)

---

### Requirement 4: Migration Validation

**User Story:** As a DBA, I want the migration to be manually reviewed and validated to ensure it correctly represents the intended schema before it is deployed to production.

**Description:**

The migration must:
- Have **all generated SQL manually reviewed** before acceptance
- Verify table names match ORM model (`__tablename__`)
- Verify constraint names follow naming conventions
- Verify indexes match database design specification
- Verify default values and server-side defaults are correct
- Verify nullable/not-null flags match ORM definitions
- Verify upgrade() creates correct schema
- Verify downgrade() correctly removes schema (reversibility test)
- Pass all CI validation stages (upgrade → tests → downgrade)

**Rationale:**

Alembic autogenerate is powerful but not infallible. Manual review of the first migration establishes a quality standard for all future migrations. This prevents schema mistakes from reaching production.

**Acceptance Criteria:**

1. ✅ Migration code reviewed for accuracy and completeness
2. ✅ Table name is "users" (matches __tablename__)
3. ✅ All columns present with correct types (uuid, text, boolean, timestamptz)
4. ✅ All column defaults correct (gen_random_uuid() for id, now() for timestamps, true for is_active, false for is_verified, 'viewer' for role)
5. ✅ Nullable/not-null flags match ORM model (deleted_at nullable, others not-null)
6. ✅ Unique constraint on email present and named correctly (uq_users_email)
7. ✅ Check constraint on role present and enforces allowed values
8. ✅ All indexes present (primary key, unique email, composite is_active/created_at)
9. ✅ downgrade() function reverses all changes (can revert schema)
10. ✅ Migration passes upgrade/downgrade cycle: `alembic upgrade head && alembic downgrade base` succeeds
11. ✅ Migration passes CI pipeline: PostgreSQL container → upgrade → tests → downgrade → success
12. ✅ No regressions in E3.T1 tests after migration

**Architectural Notes:**
- Traces to: 12-CI-CD-Architecture §3 (migration validation stages)
- Traces to: 22-Engineering-Backlog E3.T2 (Alembic CI integration)

**Testing Strategy:**

Testing is done by CI pipeline automatically on every PR/push:
1. Fresh PostgreSQL container starts
2. `alembic upgrade head` — applies all pending migrations (creates users table)
3. `pytest` — runs application tests against migrated schema
4. `alembic downgrade base` — reverts all migrations (drops users table)
5. CI passes if all stages succeed

---

### Requirement 5: ORM Model Test Coverage

**User Story:** As a developer, I want comprehensive tests for the User model to ensure it enforces all constraints and behaves correctly in the application.

**Description:**

Tests must cover:
- Model instantiation with valid data
- Default values (role defaults to 'viewer', is_active to true, etc.)
- Field type validation
- Email uniqueness (cannot insert duplicate)
- Role validation (only valid roles accepted)
- Soft-delete semantics (deleted_at field behavior)
- Timestamp auto-population
- Model repr() output

**Rationale:**

Unit tests validate that the ORM model behaves as expected before it's used in application logic. They serve as executable specifications for model behavior.

**Acceptance Criteria:**

1. ✅ Test file created: `backend/tests/unit/test_user_model.py`
2. ✅ Test: instantiate User with valid data (all fields) succeeds
3. ✅ Test: instantiate User with minimal data (email, password_hash, full_name) succeeds
4. ✅ Test: default values are correct (role='viewer', is_active=true, is_verified=false)
5. ✅ Test: created_at and updated_at are set on creation
6. ✅ Test: deleted_at is None for active user
7. ✅ Test: model __repr__() returns useful string without exposing password_hash
8. ✅ Integration test: insert valid user via ORM succeeds
9. ✅ Integration test: insert user with duplicate email raises unique constraint error
10. ✅ Integration test: insert user with invalid role raises check constraint error
11. ✅ Integration test: insert user with null email raises not-null constraint error
12. ✅ All tests pass: `pytest tests/unit/test_user_model.py -v`

**Architectural Notes:**
- Traces to: 07-Backend-Development-Standards §7 (ORM testing patterns)
- Traces to: 10-Observability-Architecture (test observability and failure modes)

---

## Acceptance Criteria Summary

| # | Criterion | Status |
|---|-----------|--------|
| **R1** | User ORM model defined and exported | ⏳ Pending |
| **R2** | Database constraints and indexes configured | ⏳ Pending |
| **R3** | Initial migration generated | ⏳ Pending |
| **R4** | Migration manually reviewed and validated | ⏳ Pending |
| **R5** | ORM model test coverage complete | ⏳ Pending |

---

## Definition of Ready

Before implementation begins:
- ✅ E3.T1 complete (Database Foundation, fixtures, engine disposal)
- ✅ E3.T2 complete (Alembic Configuration, migration workflow)
- ✅ User model frozen (audit complete, last_login_at removed for traceability)
- ✅ PostgreSQL 16 container operational (`docker compose up`)
- ✅ Alembic ready to generate migrations
- ✅ CI pipeline ready to validate migrations

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| **Generated migration has errors** | Schema corruption, deployment failure | Low | Manual review required (R4 AC #1) before commit |
| **Constraint naming inconsistent** | Future migration confusion | Low | Review constraint names match conventions |
| **Defaults not captured** | Lost data in downgrade, schema inconsistency | Low | Verify all defaults in generated SQL |
| **Index missing or wrong** | Performance issues, query timeouts | Low | Verify indexes match Database Design spec |
| **Circular imports** | Model load failure, Alembic discovery fails | Low | Test: `from app.models import User` succeeds |
| **Soft-delete semantics unclear** | Query bugs, data visibility issues | Low | Tests verify deleted_at behavior |

---

## Dependencies & Sequencing

```
E3.T1 (Database Foundation)
  ├─ Exports get_db_session()
  ├─ Implements engine disposal
  ├─ Creates test fixtures
  └─ Enables: E3.T2 ✓

E3.T2 (Alembic Configuration)
  ├─ Establishes migration workflow
  ├─ Configures env.py for autogenerate
  ├─ Integrates migrations into CI
  └─ Enables: E3.T3 ✓

E3.T3 (User ORM Model & Migration) ← YOU ARE HERE
  ├─ Defines first persistent entity (User)
  ├─ Generates first schema migration
  ├─ Establishes migration review standard
  └─ Enables: E3.T4+ (other models, relationships)

E3.T4 (Upload Model & Migration)
  ├─ Defines Upload model with FK → User
  ├─ Generates second migration
  └─ Enables: E3.T5+ (asset, analysis, report models)
```

---

## Glossary

| Term | Definition |
|---|---|
| **ORM Model** | Python class that maps to a database table via SQLAlchemy |
| **Migration** | Versioned SQL script that defines schema changes (create, alter, drop) |
| **Autogenerate** | Alembic feature that compares ORM models to current schema and generates migration scripts |
| **Constraint** | Database-enforced rule (UNIQUE, CHECK, NOT NULL, FK) ensuring data integrity |
| **Index** | Database structure enabling efficient queries on one or more columns |
| **Soft Delete** | Marking a row as deleted (deleted_at timestamp) without removing it from the database |
| **Nullable** | A column that allows NULL values (empty/unknown state) |
| **Server Default** | A value provided by the database on INSERT if the application doesn't specify one |
| **BaseModel** | Abstract SQLAlchemy model providing UUID PK, timestamps, and common patterns |

---

## References

- 22-Engineering-Backlog: E3.T3 (User ORM Model and Migration)
- 04-Database-Design §5.1: `users` table specification
- 02-Domain-Model: User as identity anchor
- 06-Repository-Structure §6: models/ directory organization
- 07-Backend-Development-Standards §8: ORM model conventions
- 08-Security-Architecture §4: User identity and authentication
- E3.T1 Completion: Database Foundation (fixtures, engine disposal, Base.metadata)
- E3.T2 Completion: Alembic Configuration (autogenerate, CI integration)
