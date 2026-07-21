# E3.T6 — Analyses ORM Model and Migration — Requirements Specification Created

**Status:** ✅ Requirements specification complete and ready for review  
**Date:** 2025-01-17  
**Task ID:** E3.T6  
**Specification Type:** Feature (Requirements-First workflow)

---

## Overview

The E3.T6 requirements specification has been created following the disciplined engineering workflow established in E3.T5. This spec defines all requirements for implementing the **Analyses ORM model** — the central record for security analysis jobs in the Sentinel platform.

---

## Key Specification Artifacts

**Location:** `.kiro/specs/epic-3-database-foundation-analyses-t6/`

### Files Created

1. **requirements.md** (420+ lines)
   - Introduction and scope
   - Glossary of 11 key terms
   - 10 detailed requirements with acceptance criteria (R1–R10)
   - Definition of Done with 14 checklist items
   - Design decisions deferred to design phase
   - Requirements traceability matrix

2. **.config.kiro** (metadata)
   - Spec configuration (type: feature, workflow: requirements-first)
   - Status tracking
   - Prerequisite validation (all ✅ complete)
   - Dependent tasks reference

---

## Requirements Summary

### 10 Requirements Covering 52 Acceptance Criteria

| ID | Requirement | Focus Area |
|---|---|---|
| **R1** | Analysis ORM Model Definition | Class structure, inheritance, docstrings, exports |
| **R2** | AnalysisStatus Enum | 5-member enum: pending, running, completed, failed, cancelled |
| **R3** | Analysis Fields and Types | 18 fields: inherited (3) + identity (2) + tracking (5) + verdict (4) + reasoning (2) + lifecycle (2) |
| **R4** | Foreign Key to DigitalAsset | FK constraint with ON DELETE RESTRICT |
| **R5** | CHECK Constraints | Status validation + score ranges [0.0–1.0] + severity validation |
| **R6** | Indexes (8 total) | Query optimization for asset status, asset latest, pending jobs, user history, celery correlation, severity dashboard |
| **R7** | Idempotency Constraint | Partial unique index on (digital_asset_id, analyzer_slugs) WHERE status='completed' per Domain Model invariant 6 |
| **R8** | JSONB Schemas | reasoning_payload and enrichment_data documentation with examples |
| **R9** | Relationship to DigitalAsset | SQLAlchemy relationship with lazy loading strategy (TBD in design phase) |
| **R10** | Module Exports | Analysis and AnalysisStatus exported from app/models/__init__.py |

---

## Analysis Entity Overview

### 18 Total Fields

**Inherited from BaseModel (3):**
- `id: UUID` (PK, auto-generated)
- `created_at: DateTime` (auto-set)
- `updated_at: DateTime` (from BaseModel)

**Core Identity (2):**
- `digital_asset_id: UUID` (FK to DigitalAsset, NOT NULL)
- `requested_by: UUID` (FK to User who triggered analysis, NOT NULL)

**Status & Tracking (5):**
- `status: str` (enum: pending/running/completed/failed/cancelled, default pending)
- `analyzer_slugs: list[str]` (array of analyzer IDs applied, NOT NULL)
- `celery_task_id: Optional[str]` (Celery correlation ID)
- `retry_count: int` (NOT NULL, default 0)
- `error_message: Optional[str]` (only on failed status)

**Verdict Fields — Written Once (4):**
- `threat_score: Optional[float]` (CHECK 0.0–1.0, null until completion)
- `confidence: Optional[float]` (CHECK 0.0–1.0, null until completion)
- `severity: Optional[str]` (enum: LOW/MEDIUM/HIGH/CRITICAL, null until completion)
- `error_code: Optional[str]` (machine-readable error, only on failed)

**Reasoning & Enrichment — JSONB (2):**
- `reasoning_payload: Optional[dict]` (AI output with reasoning steps, IOCs, data gaps, model version)
- `enrichment_data: Optional[dict]` (extracted threat intelligence from API sources)

**Lifecycle (2):**
- `started_at: Optional[DateTime]` (when worker picked up job)
- `completed_at: Optional[DateTime]` (when job reached terminal state)

### Key Constraints

- **CHECK constraint on status:** Only valid values allowed
- **CHECK constraints on scores:** threat_score and confidence must be in [0.0–1.0] or NULL
- **CHECK constraint on severity:** Only LOW/MEDIUM/HIGH/CRITICAL or NULL
- **Foreign Key:** digital_asset_id → digital_assets.id (ON DELETE RESTRICT)
- **Unique Partial Index:** (digital_asset_id, analyzer_slugs) WHERE status='completed' — enforces idempotency per Domain Model invariant 6

### 8 Indexes for Query Performance

1. **analyses_pkey** — PK lookup on id
2. **analyses_asset_status** — (digital_asset_id, status) for "all analyses for this asset"
3. **analyses_asset_latest** — (digital_asset_id, requested_at DESC) for "most recent"
4. **analyses_pending** — Partial on (requested_at) WHERE status='pending' for worker queue
5. **analyses_user_history** — (requested_by, requested_at DESC) for user analysis history
6. **analyses_celery_task** — Partial on celery_task_id WHERE celery_task_id IS NOT NULL
7. **analyses_severity** — Partial on (severity, requested_at DESC) WHERE status='completed'
8. **uq_analyses_asset_analyzers_completed** — Unique partial for idempotency

---

## Design Decisions Deferred to Design Phase

Five architectural decisions are documented for the Design specification phase:

1. **Lazy Loading Strategy** — Following E3.T5's asymmetric pattern, should Analysis.digital_asset use joined/selectin/select_in?
2. **Relationship Backref** — Should DigitalAsset include reverse_populates for the one-to-many collection?
3. **Celery Task Indexing** — B-tree alone or partial unique index?
4. **Index Cost-Benefit Analysis** — Storage vs. query improvement tradeoffs
5. **Retry Count Mutability** — Immutable after insert or mutable during retry attempts?

---

## Traceability

All requirements trace back to authoritative documents:

- **04-Database-Design.md §5.6** — Table specification, field types, constraints, indexes, JSONB schema
- **02-Domain-Model.md §Analysis** — Entity invariants, immutability, idempotency constraint
- **06-Repository-Structure.md §7** — Model location and registration pattern
- **07-Backend-Development-Standards.md §7** — ORM modeling standards

---

## Prerequisite Status

✅ **All prerequisites complete:**
- E3.T5 (DigitalAsset ORM) — Complete, DigitalAsset model is ready as FK target
- Database Design — 04-Database-Design.md §5.6 finalized
- Domain Model — 02-Domain-Model.md §Analysis defined

✅ **Ready to proceed:** Design phase can begin immediately after user review and approval

---

## Next Steps

### Immediate (User Action)
1. **Review requirements.md** — Verify all 10 requirements are complete and correct
2. **Confirm field list** — Check that all 18 fields match your expectations
3. **Approve specification** — Mark as reviewed before proceeding to design

### Upon Approval (Orchestration)
1. Generate **design.md** — Finalize lazy loading, index justifications, relationship definitions
2. Generate **tasks.md** — Define 5–6 implementation tasks with DAG dependencies
3. **Conduct design review** — Approve design before implementation begins
4. **Begin implementation** — Task 1: Validate ORM structure, Task 2: Generate migration, etc.

---

## File References

| File | Purpose |
|---|---|
| `.kiro/specs/epic-3-database-foundation-analyses-t6/requirements.md` | Main specification document |
| `.kiro/specs/epic-3-database-foundation-analyses-t6/.config.kiro` | Spec metadata and status |
| `docs/04-Database-Design.md` §5.6 | Source of truth for table schema |
| `docs/02-Domain-Model.md` §Analysis | Source of truth for entity invariants |
| `docs/07-Backend-Development-Standards.md` §7 | ORM modeling standards reference |

---

## Disciplined Engineering Workflow

This specification follows the same high-standard engineering discipline established in E3.T5:

✅ **Phase 1: Requirements** (this document)
- Complete requirements with 52 acceptance criteria
- Traceability to authoritative documents
- Clear definition of done
- Design decisions deferred to Design phase

⏭️ **Phase 2: Design** (pending user approval)
- Design decisions for lazy loading, indexing, relationships
- Architecture trade-off analysis
- Design review checkpoint

⏭️ **Phase 3: Tasks** (pending design approval)
- 5–6 sequential implementation tasks with DAG dependencies
- Task-level acceptance criteria
- Task review checkpoint

⏭️ **Phase 4: Implementation** (pending task approval)
- Subagent delegation for code implementation
- Quality gates (Ruff, MyPy, pytest)
- Test coverage requirements

⏭️ **Phase 5: Audit** (post-implementation)
- Comprehensive audit documents
- Requirements traceability verification
- Production readiness sign-off

---

**Status:** Ready for user review. The specification is disciplined, complete, and ready to proceed to design phase upon approval.
