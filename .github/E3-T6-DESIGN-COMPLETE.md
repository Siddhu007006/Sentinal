Two Recommendations Before Implementation
Recommendation 1 — Reconsider joined as the default relationship strategy

The design currently specifies:

Analysis → DigitalAsset: lazy="joined"
Analysis → User: lazy="joined"

This is reasonable if almost every query needs those related objects.

However, Analysis is likely to become one of the largest tables in Sentinel. Many operations—worker polling, dashboards, status updates, metrics, and batch processing—may only need Analysis fields.

For that reason, I'd recommend documenting why joined is expected to outperform selectin for your anticipated workload. If that justification can't be made convincingly, I'd lean toward selectin as the default and use explicit eager loading (joinedload()) where appropriate.

I wouldn't block implementation over this, but I would explicitly record the rationale because this choice affects performance as the table grows.

Recommendation 2 — Migration examples vs. implementation

The migration section includes a near-complete Alembic migration.

For a Design document, I'd present it as illustrative pseudocode or representative structure, not production-ready code.

That keeps the Design focused on architecture rather than drifting into implementation details.

Again, not a blocker—just a refinement of document scope.

Minor Editorial Observation

The document refers to 18 columns, but the logical grouping includes inherited fields alongside explicit columns.

Before implementation, verify that every occurrence of:

"18 fields"
"18 columns"

uses the same counting convention (explicit columns vs. inherited BaseModel fields). This avoids confusion during code review.

Approval

With those observations noted, I would mark this as:

E3.T6 Design Specification — Approved

The document is sufficiently complete to move into execution.

Next Phase

Proceed with:

tasks.md
Break implementation into small, dependency-aware tasks.
Include verification steps and Definition of Done for each task.
Design Review
One final pass to ensure every task maps back to a design section and requirement.
Implementation
ORM model
Alembic migration
Tests
Audit
Completion review

At this point, E3.T6 has a solid specification foundation, and the project can transition from design into controlled implementation.# E3.T6 Design Specification — COMPLETE

**Status:** ✅ **Design specification complete and ready for review**  
**Date:** 2025-01-17  
**Task ID:** E3.T6  
**Version:** 1.0.0 (Final)

---

## Overview

The E3.T6 Design specification is now complete, providing the technical architecture and implementation strategy for the Analyses ORM model and migration.

**Files:**
- ✅ `.kiro/specs/epic-3-database-foundation-analyses-t6/design.md` (15 sections, 600+ lines)
- ✅ Follows the 14-section template you provided
- ✅ Establishes pattern for E3.T7+ consistency

---

## Design Structure (15 Sections)

### 1. Purpose, Scope, Dependencies ✅
- Clarifies design answers "how" (not "what")
- Explicitly traces to Requirements
- Maps dependencies (E3.T5, authoritative docs)
- Establishes relationship to E3.T5 pattern

### 2. Architecture ✅
- **Persistence layer position:** Analysis as central job record
- **Interactions:**
  - DigitalAsset (E3.T5): FK + lazy joined
  - User (E3.T3): FK + lazy joined
  - Repository Layer (E3.T10): Interface pattern
  - Future AnalysisService (E6): Service integration
  - Celery Workers (E5): Job correlation
- **Architecture diagram:** Shows data flow through persistence layer

### 3. Database Schema ✅
- **18 columns** across 6 logical groups with complete justification
- **For each column:**
  - PostgreSQL type (uuid, text, double precision, text[], jsonb, timestamptz)
  - SQLAlchemy type (UUID, str, float, list[str], dict, DateTime)
  - Nullable (YES/NO)
  - Default value (if any)
  - Server default (now(), gen_random_uuid())
  - Constraints (FK, CHECK, PK)
  - Mutable (YES/NO)
  - Rationale (why this design)
- **Design decisions explained:**
  - UUID vs integer PK (distributed, security)
  - Double precision vs decimal (algorithmic, not exact money)
  - TEXT for enums vs PostgreSQL ENUM (schema flexibility)
  - JSONB for reasoning (schema-flexible, consumed as unit)
  - TEXT[] for analyzer_slugs (small, immutable, no join needed)

### 4. Enum Design ✅
- **AnalysisStatus:** 5 members (pending, running, completed, failed, cancelled)
- **Implementation:** TEXT + CHECK constraint (not PostgreSQL ENUM)
- **Justification:** Schema evolution flexibility (adding/removing values easier with TEXT)
- **State machine:** Documented transitions (pending→running→completed|failed, running→cancelled)
- **Severity enum:** Derived from threat_score thresholds (LOW/MEDIUM/HIGH/CRITICAL)

### 5. Relationship Design ✅
- **Analysis → DigitalAsset:**
  - Many-to-One, NOT NULL, immutable
  - ON DELETE RESTRICT, ON UPDATE RESTRICT
  - lazy="joined" (eager, single query)
  - Justification: Analyses frequently accessed with asset context
  
- **Analysis → User (requested_by):**
  - Many-to-One, NOT NULL, immutable
  - ON DELETE RESTRICT
  - lazy="joined" (eager, audit trail)
  - Justification: User context essential for tracking
  
- **Reverse relationships:**
  - DigitalAsset.analyses: back_populates, lazy="selectin" (separate SELECT IN)
  - User.analyses_requested: back_populates, lazy="selectin"
  - Asymmetric strategy justification: Avoids Cartesian product on reverse access

### 6. Index Strategy ✅
- **8 indexes** with complete justification for each
- **For each index:**
  - Type (B-tree, Unique, Partial)
  - Columns (with DESC ordering noted)
  - Query pattern (what query it speeds up)
  - Selectivity estimate (% rows selected)
  - Reason (business use case)
  - Trade-off (storage vs. write cost)
  - Name (following convention)

| Index | Type | Purpose | Partial |
|---|---|---|---|
| analyses_pkey | PK | Single-row lookup | NO |
| ix_analyses_asset_status | B-tree | Asset + status filter | NO |
| ix_analyses_asset_latest | B-tree | Most recent per asset | NO |
| ix_analyses_pending | B-tree | Worker queue | YES |
| ix_analyses_user_history | B-tree | User's analysis history | NO |
| ix_analyses_celery_task | B-tree | Celery job correlation | YES |
| ix_analyses_severity_completed | B-tree | Analyst dashboard (completed) | YES |
| uq_analyses_asset_analyzer_completed | Unique | Idempotency enforcement | YES |

**Justification for partial indexes:**
- Pending queue: Only ~1–2% of rows (old analyses filtered out) → 50x smaller
- Celery task: Only ~0.1% have non-NULL celery_task_id → 100x smaller
- Severity dashboard: Only ~5–10% are completed → 10x smaller
- Idempotency: Only completed analyses participate (pending/running/failed allow retries)

### 7. Constraint Strategy ✅
- **CHECK constraints (5):**
  - status IN ('pending', 'running', 'completed', 'failed', 'cancelled')
  - threat_score BETWEEN 0.0 AND 1.0 OR NULL
  - confidence BETWEEN 0.0 AND 1.0 OR NULL
  - severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') OR NULL
  - retry_count >= 0

- **UNIQUE constraints:**
  - Partial unique (asset_id, analyzer_key, analyzer_version) WHERE status='completed'
  - Enforces idempotency: only one completed per analyzer pair
  - Allows multiple pending/running/failed (retries)

- **FK constraints:**
  - digital_asset_id → digital_assets(id) ON DELETE RESTRICT
  - requested_by → users(id) ON DELETE RESTRICT

- **NOT NULL constraints:** Documented for all 10 required columns

- **Immutability enforcement:**
  - Application layer forbids UPDATE of immutable columns
  - Database design supports (immutable columns documented)
  - Future: Role-based permissions (Phase 2)

### 8. JSONB Design ✅
- **Why JSONB:**
  - Schema-flexible (AI model outputs vary)
  - Consumed as unit (full payload retrieved atomically)
  - GIN indexable (future full-text search)
  - External API responses (VirusTotal, Shodan stored as-is)

- **reasoning_payload structure:**
  - threat_score, confidence, severity (derived AI verdict)
  - summary (narrative)
  - reasoning_steps (chain of logic)
  - iocs (indicators of compromise with confidence)
  - data_gaps (missing information affecting analysis)
  - model_version, prompt_version (reproducibility)
  - tokens_used (billing, performance tracking)
  - Query patterns: Filter by score, check IOC types, full-text search

- **enrichment_data structure:**
  - Extracted (not raw) fields from each threat intelligence source
  - VirusTotal: detection_rate, categories, last_analysis_date
  - URLScan: threats, suspicious_features
  - Shodan: (if available)
  - WHOIS: registrar, registration dates
  - Query patterns: Filter by source availability, extract threat categories

- **Update strategy:**
  - Both fields immutable after completion
  - Never updated
  - Re-analysis creates new Analysis row

### 9. Migration Design ✅
- **File location:** `backend/migrations/versions/YYYYMMDD_HHMM_<revision>_add_analyses_table.py`
- **Structure:** Complete migration code with:
  - Docstring with revision ID, dependencies, traceability
  - `upgrade()` function: CREATE TABLE, constraints, indexes
  - `downgrade()` function: DROP INDEX (reverse order), DROP TABLE

- **Upgrade strategy:**
  - Create table with all columns, defaults, server defaults
  - Create constraints (PK, FK, CHECK, UNIQUE)
  - Create indexes (concurrent, non-blocking)

- **Downgrade strategy:**
  - Drop indexes in reverse order (safe FK handling)
  - Drop table
  - Fully reversible

- **Locking implications:**
  - CREATE TABLE: Brief exclusive lock (acceptable, new table)
  - Index creation: Concurrent (non-blocking, PostgreSQL default)
  - No impact on running API traffic

### 10. Performance Considerations ✅
- **Expected table growth:**
  - Phase 1 (v1.0–1.3): 100K–500K rows/year
  - Phase 2 (v1.4–2.0): 1M–5M rows/year
  - Phase 3 (2.0+): 10M+ rows

- **Insert cost:** ~4x (4 full indexes + 2 partial index checks)
- **Update cost:** ~1.1x (mostly balanced by removal from partial pending index)
- **JSONB storage:** 5–8 KB/row → 5–8 GB at 1M rows
- **VACUUM implications:** Autovacuum handles; partial indexes reduce cost
- **Future partitioning:** If >10M rows, partition by created_at ranges

### 11. Failure Scenarios ✅
- **Duplicate request:** Idempotency check → first INSERT succeeds, second conflicts → return existing
- **FK violation:** Non-existent asset → FK constraint rejects
- **Enum mismatch:** Invalid status → CHECK constraint rejects
- **Rollback failure:** Test downgrade locally before deploying
- **Concurrent inserts:** No locking; partial unique index enforces on completed only
- **Race condition (idempotency):** Retry logic catches uniqueness violation, fetches winner

### 12. Testing Strategy ✅
- **Unit tests:** Instantiation, field types, defaults, enum validation, relationships, immutability
- **Integration tests:** FK constraints, unique idempotency, CHECK constraints, indexes (EXPLAIN), partial index behavior
- **Migration tests:** Upgrade/downgrade idempotency, schema consistency, constraints present, indexes present
- **Constraint tests:** Detailed violation tests for each constraint
- **Performance validation:** Index usage verification, query latency, batch performance
- Each test section traces back to requirements

### 13. Alternatives Considered ✅
- **JSONB vs normalized tables:** REJECTED normalized (join complexity, storage overhead)
- **PostgreSQL ENUM vs TEXT:** REJECTED ENUM (schema evolution inflexibility)
- **Application-only deduplication vs partial unique index:** REJECTED application-only (race conditions)
- **Lazy loading strategies:** CHOSEN asymmetric (joined for FK, selectin for reverse)
- **UUID vs integer PK:** REJECTED integer (security, distribution concerns)

**Each alternative documents:**
- Why it was considered
- Pros and cons
- Why it was rejected
- What was chosen instead
- Rationale for the choice

### 14. Traceability Matrix ✅
Maps all 10 requirements to design sections:
- R1 (Persistence) → §3, §5
- R2 (Status) → §4.1, §7.1
- R3 (Fields) → §3.1
- R4 (Analyzer Identity) → §3.1 (group 2)
- R5 (Referential Integrity) → §5.1, §7.3
- R6 (Query Efficiency) → §6
- R7 (Idempotency) → §6.2 (Index 8), §7.2
- R8 (Reasoning Storage) → §8
- R9 (Relationship) → §5.1, §5.2
- R10 (Lifecycle Invariants) → §7.1, §7.5

### 15. Design Review Checklist ✅
All checkpoints verified:
- ✅ Schema complete (18 columns)
- ✅ Constraints defined
- ✅ Indexes justified
- ✅ Enums explained
- ✅ Relationships designed
- ✅ JSONB schemas documented
- ✅ Migration design complete
- ✅ Performance analyzed
- ✅ Failure scenarios handled
- ✅ Testing strategy defined
- ✅ Alternatives considered
- ✅ Traceability complete
- ✅ Aligned with E3.T5 pattern
- ✅ Ready for implementation

---

## Template Established for E3.T7+

This Design specification establishes a reusable template for all future E3.T* tasks:

**Standard Sections for E3.T7, E3.T8, etc.:**
1. Purpose, Scope, Dependencies
2. Architecture
3. Database Schema (or equivalent)
4. Enum Design
5. Relationship Design
6. Index Strategy
7. Constraint Strategy
8. JSONB Design (or alternative data format)
9. Migration Design
10. Performance Considerations
11. Failure Scenarios
12. Testing Strategy
13. Alternatives Considered
14. Traceability Matrix
15. Design Review Checklist

**Consistency Benefits:**
- Engineers know what to expect in each document
- Reviews focus on substance, not format
- Easier to spot gaps or inconsistencies
- Audits can follow the same checklist
- Future readers understand decision context (alternatives + rationale)

---

## Key Design Decisions (Highlighted)

### 1. Asymmetric Lazy Loading (E3.T5 Pattern)
- Analysis→DigitalAsset: `lazy="joined"` (eager, common access)
- DigitalAsset→Analyses: `lazy="selectin"` (separate, less common)

### 2. Partial Unique Index for Idempotency
- Enforces: Only one completed analysis per (asset, analyzer_key, analyzer_version)
- Allows: Multiple pending/running/failed (retries)
- Database-level enforcement (not application-only)

### 3. TEXT for Enums + CHECK Constraint
- Schema-flexible (adding/removing values easier)
- CHECK constraint prevents invalid inserts
- Application validates (defense in depth)

### 4. Immutability by Design
- Verdict fields never updated after completion
- Re-analysis creates new row
- Enforced by application logic + design

### 5. 8 Optimized Indexes
- 5 full-table indexes (4 composite, 1 PK)
- 3 partial indexes (1 unique, 2 selective)
- Covers all query patterns from R6 (dashboard, queue, history, etc.)
- Balances performance vs. write/storage cost

---

## Alignment with Architecture

This Design follows and extends the E3.T5 pattern:

| Aspect | E3.T5 | E3.T6 |
|---|---|---|
| **Model location** | app/models/digital_asset.py | app/models/analysis.py |
| **Inheritance** | BaseModel (id, created_at, updated_at) | BaseModel (same) |
| **FK relationships** | User, Upload | DigitalAsset, User |
| **Lazy loading** | Asymmetric (joined/selectin) | Asymmetric (joined/selectin) |
| **Immutability** | Hash is identity | Verdict fields immutable |
| **Index strategy** | Multiple indexes for query patterns | 8 indexes (3 partial) |
| **Testing** | Unit + integration + migration | Unit + integration + migration |
| **Audit** | Comprehensive checkpoint review | Will follow same pattern |

---

## Next Steps

### For User Review
1. Review the 15-section Design specification
2. Validate design decisions (especially the 8 indexes and partial unique index)
3. Approve or request changes
4. Mark as "APPROVED" when ready

### For Implementation (Tasks Phase)
Once Design is approved, proceed to **tasks.md** with:
- Task 1: Validate ORM structure (syntax, imports, relationships)
- Task 2: Generate Alembic migration
- Task 3: Manual migration review (24+ checkpoints, E3.T5 pattern)
- Task 4: Unit + integration tests
- Task 5: Final audit (quality gates, traceability)

---

## Sign-Off

**Design Specification:**
- Version: 1.0.0 (Final)
- Status: **READY FOR REVIEW**
- Location: `.kiro/specs/epic-3-database-foundation-analyses-t6/design.md`
- Template: Established for E3.T7+

**Deliverable:** 15-section design with complete justification for every column, index, constraint, and design decision.
