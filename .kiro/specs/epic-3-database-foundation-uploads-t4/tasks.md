# Implementation Plan

## Overview

**Feature:** E3.T4 Upload ORM Model

E3.T4 implements the Upload ORM model with bidirectional relationship to the User model, establishes the first cross-table foreign key constraint, and validates the migration workflow with comprehensive testing.

This task list follows the exact pattern established in E3.T3 (User model), with 5 sequential tasks totaling ~3.5-4 hours of effort.

---

## Task Dependency Graph

### Waves and Dependencies

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": [1],
      "description": "Validate Upload ORM model structure"
    },
    {
      "wave": 2,
      "tasks": [2],
      "description": "Generate initial migration",
      "dependsOn": [1]
    },
    {
      "wave": 3,
      "tasks": [3],
      "description": "Manual migration review (critical gate)",
      "dependsOn": [2]
    },
    {
      "wave": 4,
      "tasks": [4],
      "description": "ORM and migration tests",
      "dependsOn": [3]
    },
    {
      "wave": 5,
      "tasks": [5],
      "description": "Validation and final audit",
      "dependsOn": [4]
    }
  ]
}
```

Execution Strategy: **Sequential (strict linear dependencies)**
Total Effort: **~3.5-4 hours**
Complexity: **Medium**
Criticality: **P0 (foundational entity, first FK relationship)**

## Tasks

### Task Details

### - [ ] 1. Validate Upload ORM Model Structure

**Priority:** P0  
**Requirement:** R1 (Upload ORM Model Definition)  
**Design Decision:** D1–D2, D6  
**Complexity:** Low  
**Estimated Effort:** 25 min  
**Files Affected:** `backend/app/models/upload.py`, `backend/app/models/__init__.py`  

**Description:**
Create the Upload ORM model from the design specification. Define all 10 fields with correct types and constraints, implement UploadStatus enum with four states, configure bidirectional User relationship, and export for use.

**Acceptance Criteria:**
1. ✅ Upload model file created: `backend/app/models/upload.py`
2. ✅ Model syntax valid: `python -m py_compile app/models/upload.py` succeeds
3. ✅ All 10 fields present with correct types: id, user_id (FK), original_filename, storage_key (UNIQUE), content_type, file_size_bytes, checksum_sha256 (nullable), upload_status (default 'pending'), created_at (inherited), completed_at (nullable)
4. ✅ UploadStatus enum defined as StrEnum with PENDING, PROCESSING, COMPLETED, FAILED
5. ✅ BaseModel inheritance: `class Upload(BaseModel):`
6. ✅ User relationship configured with back_populates and lazy="joined" (many-to-one; optimizes common case of fetching upload + user)
7. ✅ User model updated with back_populates relationship using lazy="selectin" (one-to-many; avoids Cartesian product on collections)
8. ✅ Upload and UploadStatus exported from `backend/app/models/__init__.py`
9. ✅ Comprehensive docstrings: module (50+ lines), class, enum, fields
10. ✅ No syntax errors, circular imports, or regressions in E3.T1/E2 tests (≥250 tests passing)

---

### - [ ] 2. Generate Initial Alembic Migration

**Priority:** P0  
**Requirement:** R5 (Initial Alembic Migration)  
**Design Decision:** D7 (Migration Generation Workflow)  
**Complexity:** Low  
**Estimated Effort:** 10 min  
**Files Affected:** `backend/migrations/versions/<YYYYMMDD_HHMM>_*.py` (NEW)  
**Depends On:** Task 1 complete

**Description:**
Generate the initial migration from the Upload ORM model using Alembic autogenerate. Verify naming convention, syntax, and that down_revision correctly references E3.T3 migration (de771966819d).

**Acceptance Criteria:**
1. ✅ Migration file created in `backend/migrations/versions/` with naming: YYYYMMDD_HHMM_<rev>_add_uploads_table.py
2. ✅ Migration syntax valid: `python -m py_compile migrations/versions/<file>.py` succeeds
3. ✅ File can be imported without errors
4. ✅ Migration includes docstring, revision, down_revision, branch_labels, depends_on metadata
5. ✅ down_revision = 'de771966819d' (E3.T3 migration)
6. ✅ upgrade() and downgrade() functions present and non-empty
7. ✅ upgrade() creates uploads table; downgrade() drops table
8. ✅ No uncommitted migration yet (will commit after Task 3 review)

---

### - [ ] 3. Manual Review of Generated Migration

**Priority:** P0  
**Requirement:** R5 (Migration Validation)  
**Design Decision:** D7 (Migration Generation Workflow)  
**Complexity:** Medium  
**Estimated Effort:** 50 min  
**Files Affected:** `backend/migrations/versions/<file>.py` (may edit)  
**Depends On:** Task 2 complete

**Description:**
Conduct comprehensive manual review of generated migration following E3.T3 pattern (13+ critical checkpoints). Verify table definition, column types, constraints, indexes, and downgrade correctness. Document findings in review audit document.

**Acceptance Criteria (13+ Critical Checkpoints):**
1. ✅ Table name: "uploads" (matches __tablename__)
2. ✅ All 10 columns present with correct types and defaults
3. ✅ id: uuid NOT NULL PRIMARY KEY DEFAULT gen_random_uuid()
4. ✅ user_id: uuid NOT NULL with FK to users(id)
5. ✅ storage_key: text NOT NULL UNIQUE
6. ✅ content_type: text NOT NULL
7. ✅ file_size_bytes: bigint NOT NULL
8. ✅ upload_status: text NOT NULL DEFAULT 'pending' with CHECK constraint
9. ✅ created_at: timestamptz NOT NULL DEFAULT now()
10. ✅ completed_at: timestamptz (nullable)
11. ✅ Unique constraints: storage_key UNIQUE (and UNIQUE null-handling for idempotency_key if present)
12. ✅ FK constraint: fk_uploads_user_id to users(id)
13. ✅ CHECK constraint: upload_status IN ('pending', 'processing', 'completed', 'failed')
14. ✅ Indexes: (user_id, created_at DESC) composite, UNIQUE storage_key, PK automatic
15. ✅ downgrade() drops uploads table completely
16. ✅ Migration metadata correct (revision, down_revision=de771966819d, branch_labels=None, depends_on=None)
17. ✅ Code quality: docstrings, idempotency, naming conventions (ck_, uq_, pk_, ix_, fk_)
18. ✅ Review documented comprehensively; signed off and approved

---

### - [ ] 4. ORM and Migration Tests

**Priority:** P0  
**Requirement:** R6 (ORM Model and Migration Test Coverage)  
**Design Decision:** D8 (Testing Strategy)  
**Complexity:** Medium  
**Estimated Effort:** 1.5h  
**Files Affected:** `backend/tests/unit/test_upload_model.py` (NEW), `backend/tests/integration/test_upload_migration.py` (NEW)  
**Depends On:** Task 3 complete

**Description:**
Create comprehensive unit and integration tests for Upload model and migration. Validate constraint enforcement (FK, UNIQUE, NOT NULL, CHECK), relationship bidirectionality, migration lifecycle (upgrade/downgrade/idempotency), and no regressions in E3.T1/E2 tests.

**Acceptance Criteria:**
1. ✅ Unit tests created (10+ tests): instantiation, defaults, types, UploadStatus enum, relationships
2. ✅ Integration tests created (15+ tests): FK constraint, UNIQUE constraints, NOT NULL, CHECK constraint, migration upgrade/downgrade/idempotency
3. ✅ Migration upgrade succeeds: `alembic upgrade head` creates uploads table
4. ✅ Migration downgrade succeeds: `alembic downgrade de771966819d` drops uploads table
5. ✅ Relationship tests pass: Upload.user works (lazy load), User.uploads works (list)
6. ✅ All unit tests pass: `pytest backend/tests/unit/test_upload_model.py -v`
7. ✅ All integration tests pass: `pytest backend/tests/integration/test_upload_migration.py -v`
8. ✅ Full test suite passes: `pytest backend/tests/ -v` (≥275 total: 250+ existing + 25 new)
9. ✅ No regressions: E3.T1 tests ≥250 passing, E2 tests passing
10. ✅ Test counts reported and documented

---

### - [ ] 5. Validation and Final Audit

**Priority:** P0  
**Requirement:** All R1–R6  
**Design Decision:** All D1–D8  
**Complexity:** Medium  
**Estimated Effort:** 30 min  
**Files Affected:** `.github/E3-T4-ALEMBIC-VERIFICATION.md` (NEW), `.github/E3-T4-ORM-AND-MIGRATION-TESTS-COMPLETION.md` (NEW)  
**Depends On:** Task 4 complete

**Description:**
Run all quality gates (Ruff, MyPy, PyTest, Compileall), verify no regressions, and create comprehensive audit documents following E3.T3 pattern.

**Acceptance Criteria:**
1. ✅ Ruff: `ruff check app --fix; ruff check app` → 0 violations
2. ✅ MyPy: `mypy app --strict` → 0 errors
3. ✅ PyTest: `pytest backend/tests/ -v` → All passing (≥275 tests)
4. ✅ Compileall: `python -m compileall backend/app/ -q` → Success
5. ✅ Migration file: exists, named correctly (YYYYMMDD_HHMM_*.py), down_revision=de771966819d
6. ✅ Migration syntax: `python -m py_compile migrations/versions/<file>.py` → Success
7. ✅ No regressions: E3.T1 ≥250, E2 baseline all passing
8. ✅ Audit documents created with sections: summary, test results, quality gates, readiness
9. ✅ `.github/E3-T4-ALEMBIC-VERIFICATION.md` complete with migration review details
10. ✅ `.github/E3-T4-ORM-AND-MIGRATION-TESTS-COMPLETION.md` complete with test results
11. ✅ Commit message prepared with traceability (R1–R6, D1–D8, all tasks)
12. ✅ Ready for commit and E3.T5 start

---

## Notes

- **Sequential Execution Required:** Each task depends on the previous one. Do not skip or reorder.
- **Manual Review Gate (Task 3):** Critical quality control. Document 13+ checkpoints comprehensively.
- **First Cross-Table Relationship:** Verify bidirectional relationship works (Upload.user, User.uploads).
- **Migration Traceability:** down_revision must reference E3.T3 (de771966819d) to establish linear history.
- **E3.T3 Pattern Reference:** Follow E3.T3 tasks, manual review, and audit documents as exact model.
- **Quality Gates Non-Negotiable:** All gates must pass before proceeding to E3.T5.

---

## Quality Gates Summary

| Gate | Expected | Verified By |
|---|---|---|
| Ruff | 0 violations | Task 5 |
| MyPy | 0 errors (--strict) | Task 5 |
| PyTest | ≥275 passing | Task 5 |
| Compileall | Success | Task 5 |
| Migration File | Valid + named correctly | Task 5 |
| down_revision | de771966819d | Task 2/3 |
| Regressions | None (E3.T1, E2) | Task 4/5 |
| Relationships | Bidirectional working | Task 4 |

---

## Readiness Summary

**Prerequisites Verified:**
- ✅ E3.T3 complete (User model, migration, tests, audit)
- ✅ Requirements.md complete (6 requirements, 37 AC)
- ✅ Design.md complete (8 design decisions)
- ✅ Database design reviewed (04-Database-Design §5.2)
- ✅ Domain model reviewed (02-Domain-Model §4)
- ✅ Backlog reviewed (22-Engineering-Backlog E3.T4)

**Ready to Begin:** ✅ YES

Start with Task 1: Validate Upload ORM Model Structure
