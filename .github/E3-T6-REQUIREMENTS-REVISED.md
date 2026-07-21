# E3.T6 Requirements — Revised Per Engineering Feedback

**Status:** ✅ Requirements revised and ready for final review  
**Date:** 2025-01-17  
**Task ID:** E3.T6  

---

## Changes Made

Based on disciplined engineering feedback, the requirements have been revised to clearly separate **what the system must do** (Requirements) from **how to implement it** (Design).

### 1. Index Specification Moved to Design

**Before:** Requirements specified exactly 8 indexes with names and partial conditions.

**After:** Requirements state the business need:
> "The database shall efficiently support queries by... Query performance shall not degrade as the analyses table grows past 100,000 records."

**Why:** Index selection (count, types, composite vs. partial) is a **design decision**, not a business requirement. Design phase will justify specific index choices.

---

### 2. SQLAlchemy Details Removed

**Before:** Requirements mentioned:
- `Mapped[T]` type annotations
- `lazy="joined"`, `lazy="selectin"` loading strategies
- `mapped_column()`
- `relationship()`
- Constraint naming patterns

**After:** All SQLAlchemy-specific details removed.

**Why:** These are **implementation concerns**. Requirements define *what must be queryable*; Design defines *how to make it queryable*.

---

### 3. Module Exports Removed from Requirements

**Before:** Required `app/models/__init__.py` with specific export patterns.

**After:** Removed entirely.

**Why:** Model registration is an **implementation detail**. Requirements don't dictate where code lives or how it's exported.

---

### 4. Documentation Style Removed

**Before:** Required "comprehensive docstrings (100+ lines)", specific field documentation, `__repr__()` method behavior.

**After:** Removed all documentation requirements.

**Why:** Documentation is an **implementation concern**. Requirements define the data; Design/implementation defines how it's documented.

---

### 5. Critical Fix: Analyzer Key + Version

**Before:** Requirements incorrectly referenced `analyzer_slugs` for the idempotency constraint.

**After:** Split into two separate requirements:
- **R3 (AC6):** analyzer_slugs field exists (ordered list of analyzers applied)
- **R4 (New):** Separate analyzer_key and analyzer_version fields for idempotency

**Traceability to Backlog:**
```
22-Engineering-Backlog E3.T6:
"Create `app/models/analysis.py` per 04-Database-Design §6:
`id` (UUID PK), `digital_asset_id` (FK → digital_assets),
`analyzer_key`, `analyzer_version`, `status` (enum: ...),
...
Add partial unique index on (digital_asset_id, analyzer_key,
analyzer_version) for completed analyses per 02-Domain-Model invariant 6."
```

**Why:** The backlog clearly specifies `analyzer_key` and `analyzer_version` (not `analyzer_slugs`). The partial unique index enforces the domain invariant 6: re-running the same analyzer version on the same asset returns the existing Analysis.

---

### 6. Threat Score Immutability Clarified

**Before:** Mentioned score ranges but not immutability clearly.

**After:** R3 (AC11-12) explicitly states:
- "Analysis has a threat_score field **(nullable before completion, immutable after)**"
- "threat_score must be in range [0.0 to 1.0] or null"

**Why:** Immutability is a **business rule**, not an implementation detail. Verdicts are the source of security truth and must never be mutated retroactively.

---

### 7. New Requirement: Lifecycle Invariants

**Added:** **Requirement R10 — Analysis Lifecycle Invariants**

```
User Story: As a system architect, I need to enforce valid 
status transitions so that analyses progress through their 
lifecycle correctly and prevent invalid state changes.

Acceptance Criteria:
1. Status transitions follow a strict state machine:
   - pending → running
   - pending → cancelled
   - running → completed
   - running → failed
   - running → cancelled
   - completed is terminal
   - failed is terminal
   - cancelled is terminal
2. Backward transitions are impossible
3. Invalid transitions are rejected at application layer
```

**Why:** Domain Model invariants are **business requirements**, not implementation details. They define what transitions are valid.

---

### 8. JSONB Requirement Clarified

**Before:** Required JSONB schema examples and field documentation.

**After:** Requirements state:
- "reasoning_payload shall be stored as structured JSON"
- "enrichment_data shall be stored as structured JSON"

**Schema examples moved to Design** where implementation details belong.

**Why:** Requirements specify *what data exists*; Design specifies *how it's structured*.

---

## Requirements Summary (Revised)

### 10 Requirements, 55 Acceptance Criteria

| R# | Requirement | Focus |
|---|---|---|
| **R1** | Analysis Entity Persistence | Durability, queryability, immutability |
| **R2** | Status Values | 5 lifecycle states, database enforcement |
| **R3** | Core Fields | 22 ACs covering all 18 fields and their constraints |
| **R4** | Analyzer Identity Fields | analyzer_key + analyzer_version for idempotency |
| **R5** | Referential Integrity | FK to DigitalAsset, immutable relationship |
| **R6** | Query Efficiency | Performance requirements (not specific indexes) |
| **R7** | Idempotency Guarantee | Domain Model invariant 6: no duplicate analyses |
| **R8** | Reasoning Storage | Structured JSON for reasoning and enrichment data |
| **R9** | Relationship to Digital Asset | Navigation capability |
| **R10** | Lifecycle Invariants | **NEW:** Status state machine + terminal states |

---

## Design Decisions Deferred to Design Phase

1. **Index Strategy** — Which specific indexes to implement (B-tree, partial, covering, etc.)
2. **Lazy Loading Strategy** — How to efficiently load relationships
3. **Relationship Backref** — Whether DigitalAsset includes reverse collection
4. **Celery Task Indexing** — Indexing approach for job correlation
5. **Retry Count Mutability** — Whether field is updated or immutable

---

## Key Business Rules Extracted

These are NOT implementation details — they are domain invariants documented for Design/implementation reference:

1. **Immutability After Completion** — Verdicts are source of truth, never mutated
2. **Idempotency** — Same analyzer_key + analyzer_version on same asset returns existing Analysis
3. **Terminal States** — completed, failed, cancelled are final; no further transitions
4. **Single Asset** — Analysis belongs to exactly one DigitalAsset, immutable
5. **Immutable Ownership** — requested_by cannot change after creation
6. **Strict State Machine** — Only valid transitions permitted

---

## Alignment with E3.T5 Pattern

The revised requirements follow the same discipline established in E3.T5:

✅ **Requirements focus on:** Business rules, data model, invariants, external contracts  
✅ **Design will focus on:** Implementation strategy, indexing, relationships, SQLAlchemy patterns  
✅ **Tasks will focus on:** Code implementation, testing, validation  
✅ **Audit will focus on:** Quality gates, traceability, production readiness

---

## Critical Fields Confirmed

All 18 fields accounted for:

**Inherited (3):** id, created_at, updated_at  
**Identity (2):** digital_asset_id, requested_by  
**Status & Tracking (5):** status, analyzer_slugs, retry_count, error_message, error_code, celery_task_id  
**Verdict (4):** threat_score, confidence, severity, (implicit error_code)  
**Reasoning (2):** reasoning_payload, enrichment_data  
**Lifecycle (2):** started_at, completed_at  
**Analyzer Identity (2):** analyzer_key, analyzer_version ← **KEY ADDITION**

---

## Ready for Approval

✅ All 10 requirements (R1–R10) specify **business requirements**, not implementation  
✅ All 55 acceptance criteria are measurable and testable  
✅ Analyzer_key + analyzer_version fields confirmed per backlog  
✅ Status lifecycle state machine clearly defined  
✅ Immutability and idempotency rules formalized as domain invariants  
✅ Design decisions properly deferred to Design phase  
✅ Implementation details (Mapped[], lazy loading, docstrings, exports) removed  

**Status:** ✅ **Ready for user approval before Design phase**
