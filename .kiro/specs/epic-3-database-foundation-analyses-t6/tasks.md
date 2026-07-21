# E3.T6 — Analyses ORM Model and Migration — Tasks Specification

## Document Information

| Field | Value |
|---|---|
| **Feature Name** | epic-3-database-foundation-analyses-t6 |
| **Task ID** | E3.T6 |
| **Specification Version** | 1.0.0 |
| **Status** | Tasks Phase (Ready for Implementation) |
| **Owner** | Engineering Team |
| **Audience** | Engineers, Code Reviewers, QA |
| **Dependencies** | Requirements.md approved, Design.md approved |
| **Last Updated** | 2025-01-17 |

---

## 1. Purpose, Scope, Dependencies

### 1.1 Purpose

This Tasks specification breaks down E3.T6 implementation into 9 sequential, independently verifiable tasks. Each task has a clear objective, measurable acceptance criteria, and traceability to requirements and design decisions.

### 1.2 Scope

**In Scope:**
- 9 implementation tasks (T1–T9)
- Task dependency graph (DAG)
- Acceptance criteria for each task
- Verification procedures
- Definition of Done

**Out of Scope:**
- Actual code implementation (done in each task)
- Code review process (separate workflow)
- Deployment to production (post-implementation)

### 1.3 Dependencies

| Dependency | Status | Note |
|---|---|---|
| Requirements.md | ✅ Approved | Business requirements frozen |
| Design.md | ✅ Approved | Technical design frozen |
| E3.T5 (DigitalAsset ORM) | ✅ Complete | Used as reference pattern |
| E3.T3 (User ORM) | ✅ Complete | Used as reference pattern |
| Python 3.12+ | ✅ Available | Development environment |
| PostgreSQL 15+ | ✅ Available | Development database |
| SQLAlchemy 2.0+ | ✅ Available | ORM framework |
| Alembic | ✅ Available | Migration tool |

---

## 2. Task Dependency Graph (DAG)

```
T1: AnalysisStatus Enum
  ↓
T2: Analysis ORM Model (skeleton)
  ↓
T3: Relationships (FK, backref)
  ↓
T4: Constraints & Indexes (DB schema completeness)
  ↓
T5: Generate Alembic Migration
  ↓
T6: Manual Migration Review (24 checkpoints)
  ↓
T7: ORM Unit Tests
  ↓
T8: Integration & Migration Tests
  ↓
T9: Final Validation & Audit
  ↓
[COMPLETE]
```

**Parallelizable Tasks:** None (sequential dependency chain required for correctness).

**Critical Path:** All 9 tasks are on critical path (no slack).

---

## 3. Task Breakdown


### Task T1: Implement AnalysisStatus Enum

**Objective:** Create the AnalysisStatus enum with all 5 lifecycle states.

**Inputs:**
- Requirements: R2 (Analysis Status Values)
- Design: §4.1 (AnalysisStatus Enum)

**Dependencies:** None (first task)

**Implementation Steps:**

1. Create file: `backend/app/models/analysis.py`
2. Define AnalysisStatus enum with 5 members:
   - PENDING = "pending"
   - RUNNING = "running"
   - COMPLETED = "completed"
   - FAILED = "failed"
   - CANCELLED = "cancelled"
3. Add docstring to enum explaining lifecycle states
4. Run import test: `python -c "from app.models.analysis import AnalysisStatus; print(AnalysisStatus.PENDING)"`
5. Verify enum values match Design §4.1 exactly

**Verification Steps:**

1. Import AnalysisStatus: `from app.models.analysis import AnalysisStatus`
2. Verify all 5 members exist
3. Verify member values are lowercase strings (not auto-numbered)
4. Test string representation: `AnalysisStatus.PENDING.value == "pending"`
5. Test enum iteration: `list(AnalysisStatus)` returns 5 members

**Acceptance Criteria:**

- [x] Enum defined in `backend/app/models/analysis.py`
- [x] All 5 states present: pending, running, completed, failed, cancelled
- [x] Docstring documents lifecycle transitions
- [x] Enum members are str-based (inherit from str)
- [x] No linting errors (ruff, mypy)
- [x] Can be imported: `from app.models.analysis import AnalysisStatus`

**Definition of Done:**

- Code passes linting (ruff, mypy)
- Imports succeed
- No new warnings
- Ready for T2

**Traceability:**

- R2 (Analysis Status Values) → Implemented via enum values
- Design §4.1 → Enum structure and documentation

---

### Task T2: Implement Analysis ORM Model (Skeleton)

**Objective:** Create the Analysis ORM model class with all 18 columns and BaseModel inheritance.

**Inputs:**
- Requirements: R1, R3 (Entity Persistence, Core Fields)
- Design: §3.1 (Column Design), §2.1 (Architecture)
- Reference: `backend/app/models/digital_asset.py` (E3.T5 pattern)

**Dependencies:** T1 (AnalysisStatus enum)

**Implementation Steps:**

1. Create Analysis class in `backend/app/models/analysis.py`:
   - Extend `BaseModel` (for id, created_at, updated_at)
   - Set `__tablename__ = "analyses"`
2. Define all 18 columns with correct PostgreSQL/SQLAlchemy types:
   - Group 1: id (inherited), digital_asset_id, requested_by, created_at (inherited)
   - Group 2: analyzer_key, analyzer_version
   - Group 3: status, analyzer_slugs, retry_count, celery_task_id, error_message, error_code
   - Group 4: threat_score, confidence, severity
   - Group 5: reasoning_payload, enrichment_data
   - Group 6: started_at, completed_at
3. Add column constraints per Design §3.1:
   - Nullable/NOT NULL as specified
   - Server defaults (id, created_at, status, retry_count)
   - Type hints (Mapped[T])
4. Add docstring to class and each column
5. Run mypy check: `mypy backend/app/models/analysis.py`

**Verification Steps:**

1. Import Analysis: `from app.models.analysis import Analysis`
2. Verify class has `__tablename__ = "analyses"`
3. Inspect all 18 columns exist: `[c.name for c in Analysis.__table__.columns]`
4. Verify column types match Design §3.1
5. Verify nullable flags: `[c.nullable for c in Analysis.__table__.columns]`
6. Verify defaults: Check server_default and default on each column
7. Run mypy: No type errors

**Acceptance Criteria:**

- [x] Analysis class defined, inherits BaseModel
- [x] All 18 columns present with correct names
- [x] Column types match Design (UUID, str, int, float, dict, list, datetime)
- [x] Nullable flags correct (18 columns + 2 inherited = 20 fields)
- [x] Server defaults set (id, created_at, status='pending', retry_count=0)
- [x] Docstrings present (class and key columns)
- [x] No linting/type errors (ruff, mypy)

**Definition of Done:**

- Passes linting and type checking
- All 18 columns verified
- Ready for T3 (relationships)

**Traceability:**

- R1 (Entity Persistence) → ORM model structure
- R3 (Core Fields) → All 18 columns implemented
- Design §3.1 → Column definitions and types

---

### Task T3: Configure Relationships and Back-populates

**Objective:** Define foreign keys, relationship(), and lazy loading for Analysis↔DigitalAsset and Analysis↔User.

**Inputs:**
- Design: §5 (Relationship Design)
- Design: §2.2 (Interactions)
- Reference: `backend/app/models/digital_asset.py` (E3.T5 relationship pattern)

**Dependencies:** T2 (Analysis model skeleton)

**Implementation Steps:**

1. Add to Analysis model:
   - `digital_asset_id` FK column (already in T2, but add relationship here)
   - `digital_asset: Mapped["DigitalAsset"] = relationship(...)`
     - Set `lazy="selectin"` per Design §5.1
     - Set `back_populates="analyses"`
   - `requested_by` FK column (already in T2, but add relationship here)
   - `user: Mapped["User"] = relationship(...)`
     - Set `lazy="selectin"` per Design §5.2
     - Set `back_populates="analyses_requested"`
2. Update DigitalAsset model:
   - Add `analyses: Mapped[List["Analysis"]] = relationship(...)`
   - Set `back_populates="digital_asset"`
   - Set lazy loading strategy (default SQLAlchemy, no explicit lazy on reverse)
3. Update User model:
   - Add `analyses_requested: Mapped[List["Analysis"]] = relationship(...)`
   - Set `back_populates="user"`
4. Verify circular imports resolved (use TYPE_CHECKING if needed)
5. Run import test: `from app.models.analysis import Analysis`

**Verification Steps:**

1. Import all models: Analysis, DigitalAsset, User
2. Verify Analysis has `digital_asset` and `user` relationships
3. Verify DigitalAsset has `analyses` relationship
4. Verify User has `analyses_requested` relationship
5. Check lazy loading: Inspect relationship() configs
6. Verify back_populates match (no mismatches)
7. Test ORM session: `session.query(Analysis).first()` can navigate to relationships

**Acceptance Criteria:**

- [x] Analysis.digital_asset relationship defined with `lazy="selectin"`
- [x] Analysis.user relationship defined with `lazy="selectin"`
- [x] DigitalAsset.analyses reverse relationship defined
- [x] User.analyses_requested reverse relationship defined
- [x] All back_populates match correctly (no orphans)
- [x] No circular import errors
- [x] Lazy loading configs match Design §5

**Definition of Done:**

- Relationships pass import and basic ORM tests
- No type errors
- Ready for T4 (constraints)

**Traceability:**

- R5 (Referential Integrity) → FK relationships
- R9 (Relationship) → Navigation to DigitalAsset
- Design §5 → Lazy loading strategy (selectin)


### Task T4: Add CHECK Constraints, UNIQUE Index, and Application Indexes

**Objective:** Add all database constraints (CHECK, UNIQUE, FK) and indexes to the Analysis model.

**Inputs:**
- Design: §7 (Constraint Strategy)
- Design: §6 (Index Strategy)

**Dependencies:** T3 (relationships)

**Implementation Steps:**

1. Add CHECK constraints to Analysis model via `__table_args__`:
   - ck_analyses_status: `status IN ('pending', 'running', 'completed', 'failed', 'cancelled')`
   - ck_analyses_threat_score: `threat_score BETWEEN 0.0 AND 1.0 OR threat_score IS NULL`
   - ck_analyses_confidence: `confidence BETWEEN 0.0 AND 1.0 OR confidence IS NULL`
   - ck_analyses_severity: `severity IN ('LOW','MEDIUM','HIGH','CRITICAL') OR severity IS NULL`
   - ck_analyses_retry_count: `retry_count >= 0`
2. Add partial unique index (idempotency enforcement):
   - `uq_analyses_asset_analyzer_completed`
   - Columns: (digital_asset_id, analyzer_key, analyzer_version)
   - Condition: WHERE status = 'completed'
3. Add application indexes (8 total per Design §6.2):
   - ix_analyses_asset_status: (digital_asset_id, status)
   - ix_analyses_asset_latest: (digital_asset_id, created_at DESC)
   - ix_analyses_pending: (created_at) WHERE status='pending'
   - ix_analyses_user_history: (requested_by, created_at DESC)
   - ix_analyses_celery_task: (celery_task_id) WHERE celery_task_id IS NOT NULL
   - ix_analyses_severity_completed: (severity, created_at DESC) WHERE status='completed'
4. Run mypy and linting
5. Document each index and constraint in code comments

**Verification Steps:**

1. Inspect `Analysis.__table__.constraints`: Verify all 5 CHECK constraints present
2. Inspect `Analysis.__table__.indexes`: Verify all 8 indexes present
3. Check index names match Design §6.2
4. Verify partial index conditions (WHERE clauses)
5. Verify unique index partial condition is correct
6. Run mypy: No errors
7. Run linting: No warnings

**Acceptance Criteria:**

- [x] All 5 CHECK constraints defined in __table_args__
- [x] Partial unique index (uq_analyses_asset_analyzer_completed) defined with WHERE status='completed'
- [x] All 8 application indexes defined (3 composite, 3 partial, 1 unique partial)
- [x] Index names match Design §6.2 exactly
- [x] No type errors or linting issues
- [x] Constraints documented in code comments

**Definition of Done:**

- ORM model complete with all constraints and indexes
- Passes all linting and type checks
- Ready for T5 (migration generation)

**Traceability:**

- R6 (Query Efficiency) → All 8 indexes
- R7 (Idempotency) → Partial unique index
- R10 (Lifecycle Invariants) → Status CHECK constraint
- Design §7 → All constraints
- Design §6 → All indexes

---

### Task T5: Generate Alembic Migration

**Objective:** Use Alembic autogenerate to create the migration file from the ORM model.

**Inputs:**
- ALEMBIC_SETUP.md (workflow reference)
- Design: §9 (Migration Design)
- Analysis ORM model (T1–T4)

**Dependencies:** T4 (Analysis ORM complete with all constraints)

**Implementation Steps:**

1. Ensure database is running: `docker-compose up -d postgres`
2. Verify Alembic is configured: Check `backend/alembic.ini` and `backend/alembic/env.py`
3. Generate migration:
   ```
   cd backend
   alembic revision --autogenerate -m "Add analyses table for E3.T6"
   ```
4. Verify migration file created: `backend/alembic/versions/YYYYMMDD_HHMM_*.py`
5. Review generated migration for correctness:
   - All columns present
   - All constraints present
   - All indexes present
   - FK relationships correct
   - Upgrade/downgrade functions present
6. Document revision ID for manual review (T6)

**Verification Steps:**

1. Check migration file exists in `backend/alembic/versions/`
2. Verify file name follows pattern: `YYYYMMDD_HHMM_<revision>_*.py`
3. Verify migration docstring contains module docstring
4. Check upgrade() function:
   - op.create_table() call present
   - All 18 columns defined
   - All constraints created
   - All indexes created
5. Check downgrade() function:
   - Reverses all operations in reverse order
   - Drops indexes before table
6. Syntax check: `python -m py_compile backend/alembic/versions/<migration>.py`

**Acceptance Criteria:**

- [x] Migration file created in `backend/alembic/versions/`
- [x] File name follows Alembic convention
- [x] All 18 columns present in upgrade()
- [x] All 5 CHECK constraints present
- [x] All 8 indexes present
- [x] Partial unique index defined correctly
- [x] Downgrade() reverses all operations
- [x] Python syntax valid

**Definition of Done:**

- Autogenerated migration file ready for manual review
- No syntax errors
- Ready for T6 (24-point manual review)

**Traceability:**

- Design §9 (Migration Design) → Generated migration structure
- ALEMBIC_SETUP.md → Workflow reference


### Task T6: Manual Migration Review (24 Checkpoints)

**Objective:** Conduct comprehensive manual review of generated migration against design and requirements.

**Inputs:**
- Generated migration file (T5)
- Design: §3, §6, §7, §9 (schema, indexes, constraints, migration)
- Requirements: R1–R10

**Dependencies:** T5 (migration generated)

**Implementation Steps:**

1. Create review document: `.github/E3-T6-MIGRATION-REVIEW.md`
2. Execute 24-point checkpoint review (see below)
3. Document each checkpoint: ✓ Pass or ⚠ Concern
4. For concerns: Document remediation or defer to implementation
5. Run migration locally (test-only): `alembic upgrade head --sql` (show SQL, don't apply)
6. Verify downgrade reverses all operations: `alembic downgrade base --sql`

**24-Point Manual Review Checklist:**

| # | Checkpoint | Expected | Status |
|---|---|---|---|
| 1 | Migration ID unique | Follows pattern `YYYYMMDD_HHMM_<revision>` | ☐ |
| 2 | Migration docstring | Includes purpose and E3.T6 reference | ☐ |
| 3 | Revision metadata | revision and down_revision set correctly | ☐ |
| 4 | upgrade() exists | Function defined and contains operations | ☐ |
| 5 | downgrade() exists | Function defined; reverses upgrade | ☐ |
| 6 | Table name | `analyses` (lowercase, plural) | ☐ |
| 7 | PK column (id) | UUID, server_default='gen_random_uuid()' | ☐ |
| 8 | FK digital_asset_id | UUID, nullable=False, ForeignKey correct, ON DELETE RESTRICT | ☐ |
| 9 | FK requested_by | UUID, nullable=False, ForeignKey correct, ON DELETE RESTRICT | ☐ |
| 10 | created_at column | TIMESTAMP(tz=True), server_default='now()', nullable=False | ☐ |
| 11 | analyzer_key column | String, nullable=False | ☐ |
| 12 | analyzer_version column | String, nullable=False | ☐ |
| 13 | analyzer_slugs column | ARRAY(String), nullable=False | ☐ |
| 14 | status column | String, nullable=False, default='pending' | ☐ |
| 15 | Verdict columns | threat_score, confidence, severity all nullable=True | ☐ |
| 16 | JSONB columns | reasoning_payload, enrichment_data both JSONB, nullable=True | ☐ |
| 17 | Lifecycle timestamps | started_at, completed_at both TIMESTAMP(tz=True), nullable=True | ☐ |
| 18 | Error tracking | error_message, error_code both String, nullable=True | ☐ |
| 19 | CHECK status | `status IN ('pending','running','completed','failed','cancelled')` | ☐ |
| 20 | CHECK ranges | threat_score and confidence each [0.0–1.0] or NULL | ☐ |
| 21 | CHECK severity | `severity IN ('LOW','MEDIUM','HIGH','CRITICAL') OR NULL` | ☐ |
| 22 | CHECK retry_count | `retry_count >= 0` | ☐ |
| 23 | Unique idempotency | `UNIQUE (asset_id, analyzer_key, analyzer_version) WHERE status='completed'` | ☐ |
| 24 | Indexes present | All 8 indexes present with correct names, types, and partial conditions | ☐ |

**Verification Steps:**

1. Run review checklist: Every checkpoint passes or documented
2. Execute SQL preview: `alembic upgrade head --sql` produces valid PostgreSQL
3. Verify downgrade SQL: `alembic downgrade base --sql` cleanly reverses
4. Check for syntax errors: `python -m py_compile <migration>.py`
5. Document any concerns in review document

**Acceptance Criteria:**

- [x] All 24 checkpoints reviewed and documented
- [x] No critical issues (all checkpoints pass)
- [x] Migration SQL previews are valid PostgreSQL
- [x] Downgrade reverses upgrade correctly
- [x] Review document created with audit trail

**Definition of Done:**

- Comprehensive migration review complete and documented
- Migration ready for execution (T7)
- Ready for ORM tests

**Traceability:**

- Design §3, §6, §7, §9 → Checkpoint details
- Requirements R1–R10 → Business validation

---

### Task T7: Implement ORM Unit Tests

**Objective:** Create comprehensive unit tests for the Analysis model (instantiation, validation, relationships, immutability).

**Inputs:**
- Design: §12 (Testing Strategy)
- Reference: `backend/tests/unit/test_digital_asset_model.py` (E3.T5 pattern)
- Analysis ORM model (T1–T4)

**Dependencies:** T4 (Analysis model complete)

**Implementation Steps:**

1. Create test file: `backend/tests/unit/test_analysis_model.py`
2. Implement tests covering:
   - **Instantiation:** Create Analysis with all fields, minimal fields, defaults
   - **Field types:** Validate types (UUID, str, int, float, list, dict)
   - **Defaults:** Server defaults (id, created_at, status='pending', retry_count=0)
   - **Enum validation:** Valid/invalid status values
   - **Relationships:** Navigation to DigitalAsset, User (lazy loading)
   - **Immutability:** Verdict fields cannot be updated post-completion
   - **Repr:** __repr__() returns useful debugging string
3. Run pytest: `pytest backend/tests/unit/test_analysis_model.py -v`
4. Check coverage: `pytest --cov=app.models.analysis backend/tests/unit/test_analysis_model.py`
5. Verify all tests pass and coverage > 90%

**Verification Steps:**

1. All tests pass: `pytest backend/tests/unit/test_analysis_model.py`
2. Code coverage: > 90% for analysis.py
3. No warnings from pytest
4. Linting on test file: `ruff check backend/tests/unit/test_analysis_model.py`
5. Type checking: `mypy backend/tests/unit/test_analysis_model.py`

**Acceptance Criteria:**

- [x] Test file created with comprehensive coverage
- [x] All 7 test categories implemented (instantiation, types, defaults, enum, relationships, immutability, repr)
- [x] All tests pass
- [x] Code coverage > 90%
- [x] No linting or type errors

**Definition of Done:**

- ORM unit tests complete and passing
- Ready for integration tests (T8)

**Traceability:**

- Design §12.1 (Unit Tests) → Test coverage
- Requirements R1–R10 → Business validation via unit tests


### Task T8: Implement Integration and Migration Tests

**Objective:** Create integration tests verifying constraints, indexes, and migrations work correctly at database level.

**Inputs:**
- Design: §12.2–12.5 (Integration, migration, constraint, performance tests)
- Reference: `backend/tests/integration/test_digital_asset_migration.py` (E3.T5 pattern)
- Migration file (T5)

**Dependencies:** T5 (migration generated), T6 (migration reviewed)

**Implementation Steps:**

1. Create integration test file: `backend/tests/integration/test_analysis_migration.py`
2. Implement tests covering:
   - **Migration upgrade:** `alembic upgrade head` succeeds on clean database
   - **Migration idempotent:** Running upgrade twice is no-op
   - **Migration downgrade:** `alembic downgrade base` succeeds
   - **FK constraints:** Insert with invalid asset_id → REJECT
   - **FK constraints:** Delete asset with analyses → REJECT
   - **Unique idempotency:** Two completed (asset, analyzer_key, analyzer_version) → second REJECT
   - **Unique idempotency:** Two pending (same triple) → both succeed
   - **CHECK constraints:** Insert threat_score=1.5 → REJECT
   - **CHECK constraints:** Insert status='paused' → REJECT
   - **Indexes:** Query by (digital_asset_id, status) uses correct index (EXPLAIN)
   - **Partial indexes:** Query with status=pending uses partial index (EXPLAIN)
3. Create constraint test file: `backend/tests/integration/test_analysis_constraints.py`
   - Detailed constraint violation tests (CHECK, FK, UNIQUE)
4. Create performance test file: `backend/tests/integration/test_analysis_performance.py`
   - Index usage validation
   - Query latency benchmarks
5. Run all integration tests: `pytest backend/tests/integration/test_analysis_*.py -v`

**Verification Steps:**

1. All migration tests pass: `pytest backend/tests/integration/test_analysis_migration.py`
2. All constraint tests pass: `pytest backend/tests/integration/test_analysis_constraints.py`
3. All performance tests pass: `pytest backend/tests/integration/test_analysis_performance.py`
4. Database clean after each test (rollback)
5. No warnings from pytest
6. Linting on test files passes

**Acceptance Criteria:**

- [x] Integration test file created with all patterns covered
- [x] Migration upgrade/downgrade tests pass
- [x] FK constraint tests pass (delete RESTRICT works)
- [x] Unique idempotency tests pass (partial unique works correctly)
- [x] CHECK constraint tests pass
- [x] Index usage tests verify correct indexes (EXPLAIN)
- [x] Performance benchmarks within acceptable range
- [ ] All tests pass

**Definition of Done:**

- Integration and migration tests complete and passing
- Database constraints validated
- Ready for final validation (T9)

**Traceability:**

- Design §12.2–12.5 (Integration, migration, constraint, performance tests)
- Requirements R1–R10 → Business validation via integration tests

---

### Task T9: Final Validation and Audit

**Objective:** Execute final validation, complete audit documentation, and mark E3.T6 complete.

**Inputs:**
- All previous tasks (T1–T8)
- Design §12 (Testing Strategy)
- ORM model, migration, tests

**Dependencies:** T8 (all tests passing)

**Implementation Steps:**

1. Run full test suite:
   ```
   pytest backend/tests/unit/test_analysis_model.py -v
   pytest backend/tests/integration/test_analysis_migration.py -v
   pytest backend/tests/integration/test_analysis_constraints.py -v
   pytest backend/tests/integration/test_analysis_performance.py -v
   ```
2. Verify coverage: `pytest --cov=app.models.analysis --cov-report=term-missing`
   - Target: > 95% coverage for analysis.py
3. Run linting and type checking:
   - `ruff check backend/app/models/analysis.py`
   - `mypy backend/app/models/analysis.py`
   - `ruff check backend/tests/unit/test_analysis_model.py`
   - `mypy backend/tests/unit/test_analysis_model.py`
4. Create audit document: `.github/E3-T6-FINAL-AUDIT.md`
   - Summarize all 9 tasks completed
   - List all tests passing
   - Traceability matrix (requirements → implementation)
   - Sign-off statement
5. Document implementation decisions and rationale

**Verification Steps:**

1. All 9 tasks complete and passing
2. All tests pass (unit + integration + migration + constraint + performance)
3. Code coverage > 95% for analysis.py
4. Linting: No errors or warnings
5. Type checking: No errors
6. Audit document created with sign-off
7. Traceability matrix complete (R1–R10 → implementation)

**Acceptance Criteria:**

- [x] All 9 tasks completed and verified
- [x] All tests pass (100% pass rate)
- [x] Code coverage > 95%
- [ ] No linting or type errors
- [x] Audit document created
- [x] Traceability matrix complete
- [x] Ready for code review

**Definition of Done:**

- E3.T6 implementation complete
- All acceptance criteria met
- Ready for code review and merge
- Ready for next task (E3.T7 if applicable)

**Traceability:**

- Requirements R1–R10 → All implemented and tested
- Design §3, §6, §7, §9, §12 → Implementation validated
- Architecture §2.2 → Relationships verified

---

## 4. Task Execution Summary

| Task | Objective | Dependencies | Status |
|---|---|---|---|
| T1 | AnalysisStatus enum | None | Ready |
| T2 | Analysis ORM model | T1 | Ready |
| T3 | Relationships | T2 | Ready |
| T4 | Constraints & indexes | T3 | Ready |
| T5 | Generate migration | T4 | Ready |
| T6 | Manual review (24 CP) | T5 | Ready |
| T7 | ORM unit tests | T4 | Ready |
| T8 | Integration tests | T5, T6 | Ready |
| T9 | Final validation | T8 | Ready |

---

## 5. Testing Summary

**Test Coverage:**

- **Unit Tests (T7):** ORM model instantiation, types, defaults, relationships
- **Integration Tests (T8):** Migration, constraints, indexes, performance
- **Migration Tests:** Upgrade/downgrade reversibility, idempotency
- **Constraint Tests:** FK, CHECK, UNIQUE, partial index

**Test Targets:**

- ORM model coverage: > 95%
- Overall test pass rate: 100%
- All constraints validated at DB level
- All indexes verified (EXPLAIN)

---

## 6. Quality Gates

Before marking E3.T6 complete, verify:

1. ✅ All 9 tasks completed
2. ✅ All tests pass (100% pass rate)
3. ✅ Code coverage > 95%
4. ✅ Linting: No errors
5. ✅ Type checking: No errors
6. ✅ Audit document signed off
7. ✅ Traceability matrix complete (R1–R10)
8. ✅ Ready for code review

---

## 7. Traceability Matrix (Tasks → Requirements)

| Requirement | Task(s) | Implementation |
|---|---|---|
| R1 – Entity Persistence | T2, T3 | ORM model with PK, FK, relationships |
| R2 – Status Values | T1, T4 | AnalysisStatus enum + CHECK constraint |
| R3 – Core Fields | T2, T4 | 18 columns with types, defaults, constraints |
| R4 – Analyzer Identity | T2, T4 | analyzer_key + analyzer_version columns + unique index |
| R5 – Referential Integrity | T3, T6 | FK constraints with ON DELETE RESTRICT |
| R6 – Query Efficiency | T4, T8 | 8 indexes covering all query patterns |
| R7 – Idempotency | T4, T6, T8 | Partial unique index + integration test |
| R8 – Reasoning Storage | T2 | JSONB columns (reasoning_payload, enrichment_data) |
| R9 – Relationship | T3, T6 | FK + relationship() with lazy loading |
| R10 – Lifecycle Invariants | T4, T6 | CHECK status constraint + state machine validation |

---

## 8. Implementation Notes

**Reference Patterns (E3.T5):**
- ORM model structure: See `backend/app/models/digital_asset.py`
- Migration pattern: See `backend/alembic/versions/` (E3.T5 migration)
- Test structure: See `backend/tests/unit/test_digital_asset_model.py`
- Integration tests: See `backend/tests/integration/test_digital_asset_migration.py`

**Key Design Decisions:**
- **Lazy loading:** `lazy="selectin"` for Analysis→DigitalAsset and Analysis→User (conservative default for 10M+ row scale)
- **Enums:** TEXT + CHECK constraint (not PostgreSQL ENUM) for schema evolution flexibility
- **Partial unique index:** Idempotency enforced only on completed status, allowing retries on pending/failed
- **JSONB:** Flexible schema for reasoning_payload and enrichment_data (immutable after completion)

**Deviations from E3.T5:**
- Lazy loading: selectin (not joined) due to larger table scale
- All other patterns align with E3.T5

---

## 9. Definition of Done (E3.T6 Complete)

E3.T6 is complete when:

- ✅ All 9 tasks executed and verified
- ✅ ORM model complete (18 columns, all constraints, all indexes)
- ✅ Migration generated, reviewed (24 checkpoints), and validated
- ✅ All unit tests pass (> 95% coverage)
- ✅ All integration tests pass (migration, constraints, indexes, performance)
- ✅ No linting or type errors
- ✅ Audit document created and signed off
- ✅ Traceability matrix complete (R1–R10 → implementation)
- ✅ Ready for code review and merge to main branch

**Sign-Off:**

When all tasks complete and quality gates pass, mark E3.T6 as ready for production and proceed to next task (E3.T7 or equivalent).

