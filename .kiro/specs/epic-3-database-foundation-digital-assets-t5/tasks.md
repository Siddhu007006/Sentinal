# Implementation Plan

## Overview

**Feature:** E3.T5 DigitalAsset ORM Model

E3.T5 implements the DigitalAsset ORM model with immutability enforcement, composite deduplication constraint, and comprehensive index strategy. This is the central entity of Sentinel — every analysis, report, and threat verdict revolves around DigitalAsset.

This task list follows the exact pattern established in E3.T3 (User model) and E3.T4 (Upload model), with 5 sequential tasks totaling ~3.5-4 hours of effort.

---

## Task Dependency Graph

### Waves and Dependencies

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": [1],
      "description": "Validate DigitalAsset ORM model structure"
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
Criticality: **P0 (central platform entity, core identity, immutability)**

## Tasks

### - [ ] 1. Validate DigitalAsset ORM Model Structure

**Priority:** P0  
**Requirement:** R1–R3 (DigitalAsset ORM Model, AssetType, Immutability)  
**Design Decision:** D1–D6  
**Complexity:** Low  
**Estimated Effort:** 25 min  
**Files Affected:** `backend/app/models/digital_asset.py` (NEW), `backend/app/models/__init__.py` (UPDATE)  

**Description:**
Create the DigitalAsset ORM model from the design specification. Define all 12 fields with correct types and constraints, implement AssetType enum with five types, enforce immutability through structural design, create required indexes, and export for use.

**Acceptance Criteria:**
1. ✅ DigitalAsset model file created: `backend/app/models/digital_asset.py`
2. ✅ Model syntax valid: `python -m py_compile app/models/digital_asset.py` succeeds
3. ✅ All 12 fields present with correct types:
   - id (UUID PK, auto-generated)
   - user_id (UUID FK → users, NOT NULL)
   - upload_id (UUID FK → uploads, nullable, only for file type)
   - asset_type (String, NOT NULL, CHECK constraint: url/domain/ip_address/file_hash/file)
   - raw_value (String ≤2048, NOT NULL)
   - normalized_value (String ≤2048, NOT NULL, composite UNIQUE with asset_type)
   - display_label (String ≤512, nullable)
   - metadata (JSONB, nullable, default {})
   - is_active (Boolean, NOT NULL, default True)
   - created_at (inherited, immutable)
   - updated_at (inherited, audit-only)
   - deleted_at (inherited, soft delete)
4. ✅ AssetType enum defined as StrEnum with five values: URL, DOMAIN, IP_ADDRESS, FILE_HASH, FILE
5. ✅ Each asset type has documentation comment explaining use case and example values
6. ✅ BaseModel inheritance: `class DigitalAsset(BaseModel):`
7. ✅ UNIQUE constraint on (normalized_value, asset_type) composite key defined via __table_args__
8. ✅ Indexes created via __table_args__ (4x minimum):
   - (user_id, created_at DESC)
   - (user_id, asset_type, created_at DESC)
   - (normalized_value, asset_type)
   - metadata (GIN)
9. ✅ CHECK constraints defined:
   - asset_type IN ('url', 'domain', 'ip_address', 'file_hash', 'file')
   - (asset_type = 'file') = (upload_id IS NOT NULL) — structural invariant
10. ✅ DigitalAsset and AssetType exported from `backend/app/models/__init__.py`
11. ✅ Comprehensive docstrings: module (50+ lines describing immutability, deduplication), class, enum, fields
12. ✅ __repr__() method returns useful debugging string without exposing metadata
13. ✅ No syntax errors, circular imports, or regressions in E3.T3/E3.T4/E2 tests (≥275 tests passing)
14. ✅ Type annotations complete and correct (mypy friendly)

---

### - [ ] 2. Generate Initial Alembic Migration

**Priority:** P0  
**Requirement:** R5 (Initial Alembic Migration)  
**Design Decision:** D9 (Migration Generation Workflow)  
**Complexity:** Low  
**Estimated Effort:** 10 min  
**Files Affected:** `backend/migrations/versions/<YYYYMMDD_HHMM>_*.py` (NEW)  
**Depends On:** Task 1 complete

**Description:**
Generate the initial migration from the DigitalAsset ORM model using Alembic autogenerate. Verify naming convention, syntax, and that down_revision correctly references E3.T4 migration.

**Acceptance Criteria:**
1. ✅ Migration file created in `backend/migrations/versions/` with naming: YYYYMMDD_HHMM_<rev>_add_digital_assets_table.py
2. ✅ Migration syntax valid: `python -m py_compile migrations/versions/<file>.py` succeeds
3. ✅ File can be imported without errors
4. ✅ Migration includes docstring, revision, down_revision, branch_labels, depends_on metadata
5. ✅ down_revision = '<E3.T4_migration_revision>' (E3.T4 Upload migration)
6. ✅ upgrade() and downgrade() functions present and non-empty
7. ✅ upgrade() creates digital_assets table with all 12 columns
8. ✅ downgrade() drops digital_assets table
9. ✅ No uncommitted migration yet (will commit after Task 3 review)
10. ✅ Migration follows E3.T3/E3.T4 patterns: clear structure, idempotent, reversible

---

### - [ ] 3. Manual Review of Generated Migration

**Priority:** P0  
**Requirement:** R5 (Migration Validation)  
**Design Decision:** D9 (Migration Generation Workflow)  
**Complexity:** Medium  
**Estimated Effort:** 50 min  
**Files Affected:** `backend/migrations/versions/<file>.py` (may edit)  
**Depends On:** Task 2 complete

**Description:**
Conduct comprehensive manual review of generated migration following E3.T3/E3.T4 pattern (13+ critical checkpoints). Verify table definition, all 12 column types and constraints, composite UNIQUE, indexes, CHECK constraints, and downgrade correctness. Document findings in review audit document.

**Acceptance Criteria (13+ Critical Checkpoints):**
1. ✅ Table name: "digital_assets" (matches __tablename__)
2. ✅ All 12 columns present with correct types and nullability
3. ✅ id: uuid NOT NULL PRIMARY KEY DEFAULT gen_random_uuid()
4. ✅ user_id: uuid NOT NULL with FK to users(id) ON DELETE RESTRICT
5. ✅ upload_id: uuid nullable with FK to uploads(id) ON DELETE SET NULL
6. ✅ asset_type: text NOT NULL with CHECK constraint
7. ✅ raw_value: text NOT NULL (length constraint enforced at app layer)
8. ✅ normalized_value: text NOT NULL
9. ✅ display_label: text nullable
10. ✅ metadata: jsonb nullable DEFAULT '{}'::jsonb
11. ✅ is_active: boolean NOT NULL DEFAULT true
12. ✅ created_at: timestamptz NOT NULL DEFAULT now()
13. ✅ updated_at: timestamptz NOT NULL DEFAULT now()
14. ✅ deleted_at: timestamptz nullable
15. ✅ UNIQUE constraint: (normalized_value, asset_type) with correct naming (uq_digital_assets_...)
16. ✅ FK constraints: user_id → users.id (RESTRICT), upload_id → uploads.id (SET NULL)
17. ✅ CHECK constraint 1: asset_type IN ('url', 'domain', 'ip_address', 'file_hash', 'file')
18. ✅ CHECK constraint 2: (asset_type = 'file') = (upload_id IS NOT NULL)
19. ✅ Indexes present:
    - (user_id, created_at DESC)
    - (user_id, asset_type, created_at DESC)
    - (normalized_value, asset_type)
    - metadata GIN
20. ✅ downgrade() drops digital_assets table completely
21. ✅ Migration metadata correct (revision, down_revision, branch_labels=None)
22. ✅ Code quality: docstrings, idempotency, naming conventions (ck_, uq_, pk_, ix_, fk_)
23. ✅ Review documented comprehensively; signed off and approved
24. ✅ Reversibility verified: upgrade + downgrade leaves database in clean state

---

### - [ ] 4. ORM and Migration Tests

**Priority:** P0  
**Requirement:** R6 (ORM Model and Migration Test Coverage)  
**Design Decision:** D10 (Testing Strategy)  
**Complexity:** Medium  
**Estimated Effort:** 1.5h  
**Files Affected:** `backend/tests/unit/test_digital_asset_model.py` (NEW), `backend/tests/integration/test_digital_asset_migration.py` (NEW)  
**Depends On:** Task 3 complete

**Description:**
Create comprehensive unit and integration tests for DigitalAsset model and migration. Validate constraint enforcement (FK, UNIQUE composite, NOT NULL, CHECK), immutability, soft delete, enum correctness, migration lifecycle (upgrade/downgrade/idempotency), and no regressions in E3.T3/E3.T4/E2 tests.

**Acceptance Criteria:**
1. ✅ Unit tests created (16+ tests):
   - Instantiation with all fields
   - Instantiation with minimal required fields (nullable fields omitted)
   - Field types correct after instantiation
   - AssetType enum: all five values present
   - AssetType values are strings (StrEnum)
   - Defaults: is_active=True, metadata={}
   - Immutability: core fields cannot be mutated
   - __repr__() returns useful string
   - No circular imports
2. ✅ Integration tests created (10+ tests):
   - FK constraint: valid/invalid user_id
   - FK constraint: valid/invalid upload_id for file type
   - FK constraint: upload_id required only for file asset type
   - UNIQUE composite (normalized_value, asset_type): duplicates rejected
   - UNIQUE: same normalized_value allowed for different asset_type
   - UNIQUE: same normalized_value + type rejected
   - CHECK constraint: asset_type must be one of five values
   - CHECK constraint: invalid asset_type rejected
   - CHECK constraint: (asset_type = 'file') = (upload_id IS NOT NULL) symmetry
   - NOT NULL constraints: each required field tested
   - Soft delete: deleted_at can be set; is_active remains changeable
   - Migration upgrade: `alembic upgrade head` creates table with all columns
   - Migration downgrade: `alembic downgrade <E3.T4_revision>` drops table
   - Migration idempotency: upgrade + downgrade + upgrade succeeds
   - Deduplication simulation: same asset submitted twice returns same row
3. ✅ All unit tests pass: `pytest backend/tests/unit/test_digital_asset_model.py -v`
4. ✅ All integration tests pass: `pytest backend/tests/integration/test_digital_asset_migration.py -v`
5. ✅ Full test suite passes: `pytest backend/tests/ -v` (≥300+ total: 275+ existing + 25+ new)
6. ✅ No regressions: E3.T3 tests ≥250 passing, E3.T4 tests passing, E2 tests passing
7. ✅ Migration file migrates correctly in development/test environment
8. ✅ Test counts reported and documented

---

### - [ ] 5. Validation and Final Audit

**Priority:** P0  
**Requirement:** All R1–R6  
**Design Decision:** All D1–D10  
**Complexity:** Medium  
**Estimated Effort:** 30 min  
**Files Affected:** `.github/E3-T5-ALEMBIC-VERIFICATION.md` (NEW), `.github/E3-T5-ORM-AND-MIGRATION-TESTS-COMPLETION.md` (NEW), `.github/E3-T5-FINAL-AUDIT.md` (NEW), `.github/E3-T5-COMPLETION-SUMMARY.md` (NEW)  
**Depends On:** Task 4 complete

**Description:**
Run all quality gates (Ruff, MyPy, PyTest, Compileall), verify no regressions, and create comprehensive audit documents following E3.T3/E3.T4 pattern. This is the sign-off milestone for E3.T5.

**Acceptance Criteria:**
1. ✅ Ruff: `ruff check app --fix; ruff check app` → 0 violations
2. ✅ MyPy: `mypy app --strict` → 0 errors
3. ✅ PyTest: `pytest backend/tests/ -v` → All passing (≥300+ tests)
4. ✅ Compileall: `python -m compileall backend/app/ -q` → Success
5. ✅ Migration file: exists, named correctly (YYYYMMDD_HHMM_*.py), down_revision correct
6. ✅ Migration syntax: `python -m py_compile migrations/versions/<file>.py` → Success
7. ✅ No regressions: E3.T3 ≥250, E3.T4 baseline all passing, E2 baseline all passing
8. ✅ DigitalAsset and AssetType correctly exported from models/__init__.py
9. ✅ All 12 fields present and correctly typed in ORM model
10. ✅ All 5 AssetType values defined with documentation
11. ✅ UNIQUE constraint on (normalized_value, asset_type) enforced at database level
12. ✅ CHECK constraints (asset_type validation + upload_id presence) enforced
13. ✅ All 4 indexes present and named correctly
14. ✅ Immutability enforced structurally: no UPDATE privilege on core fields
15. ✅ Audit documents created following E3.T3/E3.T4 pattern:
    - `.github/E3-T5-ALEMBIC-VERIFICATION.md`: Migration review with 13+ checkpoints
    - `.github/E3-T5-ORM-AND-MIGRATION-TESTS-COMPLETION.md`: Test results and coverage
    - `.github/E3-T5-FINAL-AUDIT.md`: Comprehensive quality gates + traceability
    - `.github/E3-T5-COMPLETION-SUMMARY.md`: Executive summary
16. ✅ Commit message prepared with full traceability (R1–R6, D1–D10, all tasks)
17. ✅ Ready for commit and E3.T6 (DigitalAsset relationships) or downstream epics

---

## Notes

- **Sequential Execution Required:** Each task depends on the previous one. Do not skip or reorder.
- **Manual Review Gate (Task 3):** Critical quality control. Document 13+ checkpoints comprehensively. This is the second time the manual review pattern is being applied (E3.T3, E3.T4); quality bar is now established.
- **Composite UNIQUE Constraint:** Most complex design decision. Verify that (normalized_value, asset_type) UNIQUE is enforced correctly at the database level. This is the deduplication key.
- **Immutability is Structural:** Design enforces immutability through structural decisions (no UPDATE privilege on core fields). Verify this is reflected in the ORM model design and documented clearly.
- **Central Entity Status:** DigitalAsset is the core of Sentinel. This task establishes the foundation for all downstream analysis and reporting. Quality is non-negotiable.
- **Migration Traceability:** down_revision must reference E3.T4 (Upload migration) to establish correct linear history: E3.T1 (BaseModel) → E3.T2 (User) → E3.T3 (User enhancements) → E3.T4 (Upload) → E3.T5 (DigitalAsset).
- **E3.T3/E3.T4 Pattern Reference:** Follow E3.T3 and E3.T4 tasks, manual review, and audit documents as exact model. Consistency across E3 entities is critical for maintainability.
- **Quality Gates Non-Negotiable:** All gates must pass before proceeding to downstream tasks (E3.T6+).

---

## Quality Gates Summary

| Gate | Expected | Verified By |
|---|---|---|
| Ruff | 0 violations | Task 5 |
| MyPy | 0 errors (--strict) | Task 5 |
| PyTest | ≥300+ passing | Task 5 |
| Compileall | Success | Task 5 |
| Migration File | Valid + named correctly | Task 5 |
| down_revision | E3.T4 migration | Task 2/3 |
| Regressions | None (E3.T3, E3.T4, E2) | Task 4/5 |
| UNIQUE Composite | (normalized_value, asset_type) working | Task 4 |
| Immutability | Structural enforcement verified | Task 4 |
| AssetType | All five types present + documented | Task 1 |

---

## Readiness Summary

**Prerequisites Verified:**
- ✅ E3.T3 complete (User model, migration, tests, audit)
- ✅ E3.T4 complete (Upload model, migration, tests, audit)
- ✅ Requirements.md complete (6 requirements, 35 AC)
- ✅ Design.md complete (10 design decisions)
- ✅ Database design reviewed (04-Database-Design §4, §5.4)
- ✅ Engineering backlog reviewed (22-Engineering-Backlog E3.T5)

**Ready to Begin:** ✅ YES

Start with Task 1: Validate DigitalAsset ORM Model Structure

