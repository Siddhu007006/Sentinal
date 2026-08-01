# E3.T6 — Analyses ORM Model and Migration — Design Specification

## Document Information

| Field | Value |
|---|---|
| **Feature Name** | epic-3-database-foundation-analyses-t6 |
| **Task ID** | E3.T6 |
| **Specification Version** | 1.0.0 |
| **Status** | Design Phase |
| **Owner** | Engineering Team |
| **Audience** | Engineers, Code Reviewers, Architects |
| **Dependencies** | E3.T5 complete, Requirements.md approved |
| **Last Updated** | 2025-01-17 |

---

## 1. Purpose, Scope, Dependencies

### 1.1 Purpose

This Design specification explains **how** the approved E3.T6 requirements will be implemented. It does not redefine requirements — it provides the technical architecture, schema design, and implementation strategy that satisfies each requirement.

### 1.2 Scope

**In Scope:**
- SQLAlchemy ORM model structure with column definitions
- PostgreSQL types for each column
- Enum design (AnalysisStatus, Severity)
- Relationship design and lazy loading strategy
- Index strategy with justification for each index
- Constraint design (CHECK, UNIQUE, FK)
- JSONB document structure and query patterns
- Alembic migration design
- Performance considerations
- Testing strategy
- Failure scenario handling

**Out of Scope:**
- Implementation code (covered in Tasks)
- Test code (covered in Tasks)
- Repository implementation (E3.T10)
- API endpoints (separate task)
- Worker/Celery integration details (separate task)

### 1.3 Dependencies

| Dependency | Status | Note |
|---|---|---|
| E3.T5 (DigitalAsset ORM) | ✅ Complete | Analysis has FK to DigitalAsset |
| E3.T3 (User ORM) | ✅ Complete | Analysis has FK to User (requested_by) |
| 04-Database-Design §5.6 | ✅ Authoritative | Source of truth for schema |
| 02-Domain-Model §Analysis | ✅ Authoritative | Source of truth for invariants |
| 22-Engineering-Backlog E3.T6 | ✅ Approved | Engineering approval for scope |

### 1.4 Relationship to E3.T5

E3.T5 established the pattern for ORM model design and migration strategy. E3.T6 follows the same approach:
- **Model location:** `app/models/analysis.py` (same pattern as `digital_asset.py`)
- **Inheritance:** Extends BaseModel for id, created_at, updated_at
- **Migration naming:** `YYYYMMDD_HHMM_<revision>_add_analyses_table.py`
- **Lazy loading:** Uses asymmetric strategy per E3.T5 pattern (joined for FK, selectin for reverse)
- **Testing:** Unit tests + integration tests + migration reversibility tests
- **Audit documentation:** Comprehensive checkpoint review (E3.T5 pattern)

### 1.5 Traceability to Requirements

This Design section traces to Requirements as follows:

| Requirement | Design Section(s) |
|---|---|
| R1 – Entity Persistence | §3 (Database Schema), §4 (Enum), §5 (Relationships) |
| R2 – Status Values | §4 (Enum Design) |
| R3 – Core Fields | §3 (Database Schema - all columns) |
| R4 – Analyzer Identity | §3 (analyzer_key, analyzer_version columns) |
| R5 – Referential Integrity | §5 (FK Relationship Design) |
| R6 – Query Efficiency | §6 (Index Strategy) |
| R7 – Idempotency Guarantee | §6 (Partial Unique Index) |
| R8 – Reasoning Storage | §8 (JSONB Design) |
| R9 – Relationship | §5 (Relationship Design) |
| R10 – Lifecycle Invariants | §7 (Constraint Strategy) |

---

## 2. Architecture

### 2.1 Position in Persistence Layer

The Analysis ORM model is the central persistent record in the analysis pipeline:

```
┌─────────────────────────────────────────────────────────┐
│                      FastAPI App                         │
├─────────────────────────────────────────────────────────┤
│  API Routes (endpoints)  │  Celery Workers (job queue)   │
├─────────────────────────────────────────────────────────┤
│           Application Services Layer                     │
│    (AnalysisService, AnalysisQueryService, etc.)        │
├─────────────────────────────────────────────────────────┤
│  Domain Layer (Repository Interfaces, Entities)         │
├─────────────────────────────────────────────────────────┤
│         Infrastructure / Persistence Layer              │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  PostgreSQL Database                           │    │
│  │  ┌──────────────────────────────────────────┐  │    │
│  │  │  ANALYSES TABLE (this design)            │  │    │
│  │  │  - id (PK)                               │  │    │
│  │  │  - digital_asset_id (FK)                 │  │    │
│  │  │  - requested_by (FK)                     │  │    │
│  │  │  - status (enum)                         │  │    │
│  │  │  - threat_score, confidence, severity    │  │    │
│  │  │  - reasoning_payload, enrichment_data    │  │    │
│  │  │  - [indexes, constraints, timestamps]    │  │    │
│  │  └──────────────────────────────────────────┘  │    │
│  │  ┌──────────────────────────────────────────┐  │    │
│  │  │  DIGITAL_ASSETS TABLE (E3.T5)           │  │    │
│  │  │  USERS TABLE (E3.T3)                    │  │    │
│  │  └──────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  SQLAlchemy Session Pool (asyncpg driver)     │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Interactions

**1. DigitalAsset (E3.T5):**
- Analysis has FK to DigitalAsset (required, immutable)
- DigitalAsset has one-to-many relationship to Analyses
- Lazy loading: Analysis→DigitalAsset uses `lazy="joined"` (eager, single query)

**2. User (E3.T3):**
- Analysis has FK to User via `requested_by` (required, immutable)
- User has one-to-many relationship to Analyses
- Lazy loading: Analysis→User uses `lazy="joined"` (eager, single query)

**3. Repository Layer (E3.T10/E3.T11):**
- AnalysisRepository interface defines query methods
- PostgreSQL implementation uses SQLAlchemy session
- Soft-delete filtering (not applicable to analyses; they're never soft-deleted)

**4. Future AnalysisService (E6):**
- Service layer creates Analysis records (status=pending)
- Workers update Analysis (pending→running→completed/failed)
- Repository provides queryable access

**5. Celery Workers (E5):**
- Celery tasks hold celery_task_id for correlation
- Workers update Analysis status and verdict fields
- Immutability prevents post-completion updates

---

## 3. Database Schema

### 3.1 Column Design

Analysis table has **18 explicit columns** across 6 logical groups, plus 2 inherited fields (id, created_at from BaseModel). Each column is designed for both correctness and query performance.

**Column Summary:** 18 explicit + 2 inherited (from BaseModel) = 20 ORM fields total.

#### Group 1: Identity (3 explicit columns, includes inherited timestamp)

| Column | PostgreSQL Type | SQLAlchemy Type | Nullable | Default | Server Default | Constraints | Mutable | Rationale |
|---|---|---|---|---|---|---|---|---|
| `id` | `uuid` | `UUID` | NO | — | `gen_random_uuid()` | PK | NO | Stable, opaque identifier. Auto-generated at insert. Inherited from BaseModel. |
| `digital_asset_id` | `uuid` | `UUID` | NO | — | — | FK→digital_assets(id) ON DELETE RESTRICT | NO | Required, immutable. FK ensures no orphans. |
| `requested_by` | `uuid` | `UUID` | NO | — | — | FK→users(id) ON DELETE RESTRICT | NO | Immutable. Tracks who triggered analysis. |
| `created_at` (inherited) | `timestamptz` | `DateTime` | NO | — | `now()` | — | NO | Auto-set at insert. Immutable. Inherited from BaseModel. Tracks analysis request time. |

#### Group 2: Analyzer Identity (2 columns)

| Column | PostgreSQL Type | SQLAlchemy Type | Nullable | Default | Server Default | Constraints | Mutable | Rationale |
|---|---|---|---|---|---|---|---|---|
| `analyzer_key` | `text` | `str` | NO | — | — | Part of idempotency index | NO | Immutable. Identifies analyzer module (e.g., "virustotal_analyzer"). |
| `analyzer_version` | `text` | `str` | NO | — | — | Part of idempotency index | NO | Immutable. Specific version (e.g., "v2.1.0"). Pair with analyzer_key enforces idempotency. |

#### Group 3: Status & Job Tracking (6 columns)

| Column | PostgreSQL Type | SQLAlchemy Type | Nullable | Default | Server Default | Constraints | Mutable | Rationale |
|---|---|---|---|---|---|---|---|---|
| `status` | `text` | `str` (enum) | NO | `'pending'` | — | CHECK IN ('pending','running','completed','failed','cancelled') | YES | Mutable only during job lifecycle. Enforced at DB level. |
| `analyzer_slugs` | `text[]` | `list[str]` | NO | — | — | — | NO | Ordered array of analyzer identifiers applied. Immutable. |
| `retry_count` | `integer` | `int` | NO | `0` | — | CHECK >= 0 | YES | Tracks retries. Incremented by worker. |
| `celery_task_id` | `text` | `str` | YES | NULL | — | Part of partial index | NO | Celery job correlation ID. Immutable. |
| `error_message` | `text` | `str` | YES | NULL | — | — | YES | Human-readable error. Only on failed status. |
| `error_code` | `text` | `str` | YES | NULL | — | — | YES | Machine-readable error code (e.g., "ENRICHMENT_TIMEOUT"). |

#### Group 4: Verdict Fields — Written Once on Completion (3 columns)

| Column | PostgreSQL Type | SQLAlchemy Type | Nullable | Default | Server Default | Constraints | Mutable | Rationale |
|---|---|---|---|---|---|---|---|---|
| `threat_score` | `double precision` | `float` | YES | NULL | — | CHECK threat_score BETWEEN 0.0 AND 1.0 OR threat_score IS NULL | NO | Immutable once set. Range [0.0–1.0] or NULL. Source of truth for severity calculation. |
| `confidence` | `double precision` | `float` | YES | NULL | — | CHECK confidence BETWEEN 0.0 AND 1.0 OR confidence IS NULL | NO | Immutable once set. Range [0.0–1.0] or NULL. |
| `severity` | `text` | `str` (enum) | YES | NULL | — | CHECK severity IN ('LOW','MEDIUM','HIGH','CRITICAL') OR severity IS NULL | NO | Derived from threat_score thresholds. Immutable once set. |

#### Group 5: Reasoning & Enrichment — JSONB (2 columns)

| Column | PostgreSQL Type | SQLAlchemy Type | Nullable | Default | Server Default | Constraints | Mutable | Rationale |
|---|---|---|---|---|---|---|---|---|
| `reasoning_payload` | `jsonb` | `dict` | YES | NULL | — | — | NO | Full AI output. Schema-flexible. Immutable once set. GIN indexable for future full-text search. |
| `enrichment_data` | `jsonb` | `dict` | YES | NULL | — | — | NO | Extracted threat intelligence. Immutable once set. Structure varies by source. |

#### Group 6: Lifecycle Timestamps (2 columns)

| Column | PostgreSQL Type | SQLAlchemy Type | Nullable | Default | Server Default | Constraints | Mutable | Rationale |
|---|---|---|---|---|---|---|---|---|
| `started_at` | `timestamptz` | `DateTime` | YES | NULL | — | — | NO | When worker picked up job. Immutable once set. |
| `completed_at` | `timestamptz` | `DateTime` | YES | NULL | — | — | NO | When job reached terminal state. Immutable once set. |

### 3.2 Column Design Rationale

**UUID vs Integer PK:** UUID (not auto-increment) because:
- Distributed systems benefit from globally unique IDs without coordination
- Security: does not expose row count or creation order
- Aligns with E3.T5 pattern and domain model identity

**Double Precision for Threat Score:** Not numeric/decimal because:
- Threat scores are algorithmic approximations, not exact financial values
- Range is [0.0–1.0], well within float64 precision for comparisons
- Doubles are more storage-efficient than decimals
- **Critical:** Business comparisons must never rely on exact equality (documented in requirements)

**JSONB for Reasoning & Enrichment:** Because:
- Schema is flexible (varies by AI model, by enrichment source)
- Consumed as a unit (not queried field-by-field)
- Queryable via GIN index for future full-text search
- Stored alongside verdict for audit trail

**TEXT for Enums:** Not PostgreSQL ENUM type because:
- Text is more flexible for schema evolution
- Aligns with E3.T5 pattern
- Application layer validates enum values (CHECK constraint is safety net)
- Easier migration if enum values change

**Array for analyzer_slugs:** TEXT[] not separate junction table because:
- Slugs are small, immutable set (typically 1–5 analyzers)
- Easier to query (no join needed)
- Aligns with PostgreSQL best practices for small collections



---

## 4. Enum Design

### 4.1 AnalysisStatus Enum

**Definition:** 5-member enum representing analysis job lifecycle.

```python
class AnalysisStatus(str, Enum):
    """Analysis job lifecycle states."""

    PENDING = "pending"  # Queued, awaiting worker pickup
    RUNNING = "running"  # Worker actively processing
    COMPLETED = "completed"  # Successfully finished with verdict
    FAILED = "failed"  # Failed; error details in error_message/error_code
    CANCELLED = "cancelled"  # Cancelled before completion
```

**Implementation Decision: TEXT Column + CHECK Constraint**

**Why not PostgreSQL ENUM type?**
- Schema evolution: Adding new status values requires ALTER TYPE (harder migration)
- Downgrades: Removing status values requires ENUM recreation (complex migration)
- Extensibility: Future statuses (paused, retry_scheduled) easier with TEXT

**Why CHECK constraint?**
- Database enforces 5 valid values at insert/update time
- Prevents invalid status from being written
- Application layer validates before INSERT (defense in depth)

**State Machine Transitions:**
```
pending   ──→  running
  ↓
running   ──→  completed
  ↓            ↓
  └─→ failed ──┴─ (terminal)
  ↓
  └─→ cancelled (terminal)
```

### 4.2 Severity Enum (Derived)

**Definition:** Severity is derived from threat_score thresholds, not stored separately in most systems. However, Sentinel stores it for performance.

**Calculation:**
- `threat_score < 0.25` → `LOW`
- `0.25 ≤ threat_score < 0.50` → `MEDIUM`
- `0.50 ≤ threat_score < 0.75` → `HIGH`
- `threat_score ≥ 0.75` → `CRITICAL`

**Stored in severity column because:**
- Analyst dashboards filter by severity frequently
- Avoids recalculation in every query
- Denormalization is justified (score is source of truth; severity is derived cache)

**CHECK Constraint:**
```sql
CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') OR severity IS NULL)
```

---

## 5. Relationship Design

### 5.1 Analysis → DigitalAsset

**Foreign Key Definition:**

```python
digital_asset_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("digital_assets.id", ondelete="RESTRICT", onupdate="RESTRICT"),
    nullable=False,
)
```

**Design Decisions:**

| Decision | Choice | Rationale |
|---|---|---|
| **Cardinality** | Many-to-One | Multiple Analyses per Asset; one Asset per Analysis |
| **Nullable** | NO (NOT NULL) | Every Analysis must have a parent Asset |
| **Mutable** | NO (immutable after creation) | Analysis belongs to specific asset forever |
| **ON DELETE** | RESTRICT | Prevent accidental deletion of assets with pending/running analyses |
| **ON UPDATE** | RESTRICT | UUIDs never change; prevents accidents |
| **Lazy Loading** | `lazy="selectin"` | Separate SELECT IN query. At scale (10M rows), avoids JOIN cost for queries that don't need asset context. |
| **Cascade Delete** | None | ON DELETE RESTRICT prevents cascade; safer for data integrity |
| **Back-populates** | `back_populates="analyses"` | DigitalAsset.analyses returns collection of all Analyses for that Asset |

**Lazy Loading Strategy Decision: `selectin` as Default**

**Conservative Default for Scale:** Analyses will become one of Sentinel's largest tables (10M+ rows projected in Phase 3). The lazy loading strategy reflects this scale requirement.

**Query Pattern Analysis:**

Many common analysis operations need only Analysis fields, not related objects:
- Worker queue monitoring: `SELECT id, status FROM analyses WHERE status = 'pending' ORDER BY created_at` (no asset/user join needed)
- Dashboard metrics: `SELECT COUNT(*) FROM analyses WHERE status = 'completed' AND severity = 'CRITICAL'` (no join needed)
- Status updates: `UPDATE analyses SET status = 'running' WHERE id = ?` (no join needed)
- Batch processing: `SELECT id, status FROM analyses WHERE created_at < ?` (no join needed)

**Lazy Loading Performance Trade-offs:**

- **`lazy="joined"` (eager JOIN):** Single query, but at 10M rows:
  - JOINs become expensive for queries that don't need related objects
  - If DigitalAsset→Analyses is accessed (reverse direction), Cartesian product multiplies result size
  - Forces loading DigitalAsset/User even when only Analysis fields are needed

- **`lazy="selectin"` (separate SELECT IN):** Two queries, but:
  - Analysis query executes first; costs 1x for all analysis operations
  - DigitalAsset/User loaded only if actually accessed in code
  - At 10M rows with 10K concurrent analyses, `SELECT IN` is more efficient than large JOINs

**Chosen Strategy: `lazy="selectin"` (default, with explicit optimization)**

- **Analysis→DigitalAsset:** `lazy="selectin"`
  - Load pattern: Query 1 fetches Analyses; Query 2 (if accessed) fetches related DigitalAssets via `SELECT * FROM digital_assets WHERE id IN (...)`
  - Benefit: Zero join cost for analysis-only queries (majority); asset loaded separately only when accessed
  - Trade-off: Two queries instead of one JOIN (acceptable trade-off at 10M rows)

- **Analysis→User:** `lazy="selectin"`
  - Same pattern and rationale as DigitalAsset

- **Explicit eager loading for performance-critical paths:**
  - Query handlers that need `analysis.digital_asset` context can use `joinedload()` to optimize:
    ```python
    session.query(Analysis).options(joinedload(Analysis.digital_asset)).filter(...).all()
    ```
  - Explicit optimization only where profiling confirms >80% of calls need the join
  - Default remains conservative; specific paths optimize with metrics

**Deviation from E3.T5:**
- E3.T5 (Uploads, DigitalAssets) used `lazy="joined"` for smaller tables (100K rows projected)
- E3.T6 (Analyses) is designed for 10M+ rows → conservative `selectin` is safer default
- As Analyses table grows and query patterns stabilize, profiling may justify switching specific queries to `joinedload()`
- Both approaches allow selective optimization at query time

### 5.2 Analysis → User (requested_by)

**Foreign Key Definition:**

```python
requested_by: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False
)
```

**Design Decisions:**

| Decision | Choice | Rationale |
|---|---|---|
| **Cardinality** | Many-to-One | Multiple Analyses per User; one User per Analysis |
| **Nullable** | NO (NOT NULL) | Every Analysis must be requested by a User |
| **Mutable** | NO | User cannot change after creation (audit trail) |
| **ON DELETE** | RESTRICT | Prevent deletion of user if they have analyses |
| **Lazy Loading** | `lazy="selectin"` | Separate SELECT IN query. Provides user context for audit trails without JOIN cost. |
| **Back-populates** | `back_populates="analyses_requested"` | User.analyses_requested returns all analyses they requested |

---

## 6. Index Strategy

### 6.1 Index Justification

Analyses table is write-intensive and query-intensive. Indexes must balance:
- Query performance (R6: queries under 100k rows)
- Insert/update cost (indexes slow writes slightly)
- Storage cost (each index uses disk space)
- Maintenance cost (VACUUM updates index metadata)

### 6.2 Index Specification

#### Index 1: Primary Key (Implicit)

| Aspect | Value |
|---|---|
| **Type** | B-tree |
| **Columns** | `id` |
| **Query Pattern** | `SELECT * FROM analyses WHERE id = ?` |
| **Selectivity** | Unique (0.0001% of rows) |
| **Reason** | PK lookup; essential for single-record retrieval |
| **Trade-off** | Minimal (implicit PK index) |

#### Index 2: Asset + Status (Composite)

| Aspect | Value |
|---|---|
| **Type** | B-tree |
| **Columns** | `(digital_asset_id, status)` |
| **Query Pattern** | `SELECT * FROM analyses WHERE digital_asset_id = ? AND status = ?` |
| **Selectivity** | Medium (~2–5% of rows per asset) |
| **Reason** | Most common dashboard query: all analyses for asset, filtered by status (pending, completed, failed, etc.) |
| **Trade-off** | Modest index size. Write cost acceptable. |
| **Name** | `ix_analyses_asset_status` |

#### Index 3: Asset + Created_at DESC (Latest)

| Aspect | Value |
|---|---|
| **Type** | B-tree |
| **Columns** | `(digital_asset_id, created_at DESC)` |
| **Query Pattern** | `SELECT * FROM analyses WHERE digital_asset_id = ? ORDER BY created_at DESC LIMIT 1` |
| **Selectivity** | Medium (asset-scoped) |
| **Reason** | Frequent query: "most recent analysis for this asset" (used by detail view) |
| **Trade-off** | Covers both WHERE and ORDER BY; eliminates sort |
| **Name** | `ix_analyses_asset_latest` |

#### Index 4: Pending Job Queue (Partial)

| Aspect | Value |
|---|---|
| **Type** | B-tree (Partial) |
| **Columns** | `(created_at ASC)` |
| **Condition** | `WHERE status = 'pending'` |
| **Query Pattern** | `SELECT * FROM analyses WHERE status = 'pending' ORDER BY created_at ASC` |
| **Selectivity** | Low (~1–2% of rows) |
| **Reason** | Worker queue monitoring: fetch pending jobs in FIFO order. Partial index excludes completed/failed/cancelled (majority). |
| **Trade-off** | Partial index much smaller than full-table index. Write cost only for pending inserts. |
| **Name** | `ix_analyses_pending` |
| **Maintenance** | Workers frequently transition pending→running→completed, so this index is under churn. Partial index reduces churn cost. |

#### Index 5: User History (Composite)

| Aspect | Value |
|---|---|
| **Type** | B-tree |
| **Columns** | `(requested_by, created_at DESC)` |
| **Query Pattern** | `SELECT * FROM analyses WHERE requested_by = ? ORDER BY created_at DESC` |
| **Selectivity** | Medium (user-scoped) |
| **Reason** | User's analysis history view (audit trail): all analyses they requested, newest first |
| **Trade-off** | Covers both WHERE and ORDER BY |
| **Name** | `ix_analyses_user_history` |

#### Index 6: Celery Task Correlation (Partial)

| Aspect | Value |
|---|---|
| **Type** | B-tree (Partial) |
| **Columns** | `(celery_task_id)` |
| **Condition** | `WHERE celery_task_id IS NOT NULL` |
| **Query Pattern** | `SELECT * FROM analyses WHERE celery_task_id = ?` |
| **Selectivity** | Very High (~0.1–0.5% of rows have non-NULL celery_task_id) |
| **Reason** | Celery callback correlation: worker reports task completion, API looks up Analysis by task ID |
| **Trade-off** | Partial index excludes NULL values (majority). Only impacts running analyses. |
| **Name** | `ix_analyses_celery_task` |

#### Index 7: Severity Dashboard (Partial)

| Aspect | Value |
|---|---|
| **Type** | B-tree (Partial) |
| **Columns** | `(severity, created_at DESC)` |
| **Condition** | `WHERE status = 'completed'` |
| **Query Pattern** | `SELECT * FROM analyses WHERE status = 'completed' AND severity = 'CRITICAL' ORDER BY created_at DESC` |
| **Selectivity** | Low (~5–10% of rows are completed) |
| **Reason** | Analyst dashboard: filter completed analyses by threat level (CRITICAL, HIGH, MEDIUM, LOW) |
| **Trade-off** | Partial index excludes pending/running/failed. Severe churn on completed status change, but completed is terminal (no further changes). |
| **Name** | `ix_analyses_severity_completed` |

#### Index 8: Idempotency (Partial Unique)

| Aspect | Value |
|---|---|
| **Type** | B-tree Unique (Partial) |
| **Columns** | `(digital_asset_id, analyzer_key, analyzer_version)` |
| **Condition** | `WHERE status = 'completed'` |
| **Query Pattern** | Insertion: Check uniqueness before INSERT. Application query: `SELECT * FROM analyses WHERE digital_asset_id = ? AND analyzer_key = ? AND analyzer_version = ? AND status = 'completed'` |
| **Selectivity** | Medium (enforces uniqueness on completed analyses per asset+analyzer pair) |
| **Reason** | **Domain Model Invariant 6:** Only one completed analysis per (asset, analyzer_key, analyzer_version). Partial index allows multiple pending/failed/cancelled (retries). |
| **Trade-off** | Unique index prevents duplicates. Partial condition excludes non-completed (allows retries). |
| **Name** | `uq_analyses_asset_analyzer_completed` |
| **Enforcement** | DB-level (UNIQUE constraint) + application-layer validation (defense in depth) |

### 6.3 Index Summary

| Name | Type | Columns | Partial | Size (Estimate) | Rationale |
|---|---|---|---|---|---|
| `analyses_pkey` | PK | id | NO | Small | PK lookup |
| `ix_analyses_asset_status` | B-tree | (asset_id, status) | NO | Medium | Dashboard: asset + status filter |
| `ix_analyses_asset_latest` | B-tree | (asset_id, created_at DESC) | NO | Medium | Recent analysis query |
| `ix_analyses_pending` | B-tree | (created_at ASC) | YES | Small | Worker queue (partial) |
| `ix_analyses_user_history` | B-tree | (requested_by, created_at DESC) | NO | Medium | User history view |
| `ix_analyses_celery_task` | B-tree | (celery_task_id) | YES | Tiny | Celery callback (partial) |
| `ix_analyses_severity_completed` | B-tree | (severity, created_at DESC) | YES | Small | Threat dashboard (partial) |
| `uq_analyses_asset_analyzer_completed` | UNIQUE | (asset_id, analyzer_key, analyzer_version) | YES | Small | Idempotency (partial unique) |

**Total: 8 indexes, 3 partial, 1 unique**



---

## 7. Constraint Strategy

### 7.1 CHECK Constraints

CHECK constraints enforce business rules at the database level.

#### Constraint 1: Status Validation

```sql
CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
```

**Enforcement:** Prevents invalid status values at INSERT/UPDATE time.  
**Rationale:** Status is enum-like; only 5 valid values.  
**Catch-all:** Application layer validates; DB is safety net.  
**Name:** `ck_analyses_status`

#### Constraint 2: Threat Score Range

```sql
CHECK (threat_score BETWEEN 0.0 AND 1.0 OR threat_score IS NULL)
```

**Enforcement:** Threat score must be in [0.0–1.0] or NULL (before completion).  
**Rationale:** Threat scores represent probabilities; domain is [0, 1].  
**Name:** `ck_analyses_threat_score`

#### Constraint 3: Confidence Range

```sql
CHECK (confidence BETWEEN 0.0 AND 1.0 OR confidence IS NULL)
```

**Enforcement:** Confidence must be in [0.0–1.0] or NULL.  
**Name:** `ck_analyses_confidence`

#### Constraint 4: Severity Validation

```sql
CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') OR severity IS NULL)
```

**Enforcement:** Severity is one of 4 labels or NULL (before completion).  
**Name:** `ck_analyses_severity`

#### Constraint 5: Retry Count Non-Negative

```sql
CHECK (retry_count >= 0)
```

**Enforcement:** Retry count cannot be negative.  
**Name:** `ck_analyses_retry_count`

### 7.2 UNIQUE Constraints

#### Constraint 1: Idempotency (Partial Unique Index)

```sql
UNIQUE (digital_asset_id, analyzer_key, analyzer_version) WHERE status = 'completed'
```

**Enforcement:** Only one completed analysis per (asset, analyzer, version) triple.  
**Rationale:** Domain Model Invariant 6: re-running same analyzer returns existing Analysis.  
**Partial condition:** Allows multiple pending/running/failed/cancelled (permits retries).  
**Implementation:** Created as partial unique index (not traditional UNIQUE constraint) for flexibility.  
**Name:** `uq_analyses_asset_analyzer_completed`

### 7.3 Foreign Key Constraints

#### FK 1: digital_asset_id → digital_assets(id)

```sql
FOREIGN KEY (digital_asset_id) REFERENCES digital_assets(id) 
  ON DELETE RESTRICT 
  ON UPDATE RESTRICT
```

**Enforcement:** Every Analysis must reference an existing DigitalAsset.  
**ON DELETE RESTRICT:** Prevent deletion of assets with analyses.  
**ON UPDATE RESTRICT:** Prevent UUID changes (never happens, but safe).  
**Rationale:** Analyses are useless without their asset; no orphans allowed.  
**Name:** `fk_analyses_digital_asset`

#### FK 2: requested_by → users(id)

```sql
FOREIGN KEY (requested_by) REFERENCES users(id)
  ON DELETE RESTRICT
  ON UPDATE RESTRICT
```

**Enforcement:** Analysis must reference an existing User.  
**ON DELETE RESTRICT:** Prevent deletion of user who requested analyses.  
**Rationale:** Audit trail: every analysis has an owner.  
**Name:** `fk_analyses_requested_by`

### 7.4 NOT NULL Constraints

| Column | NOT NULL | Rationale |
|---|---|---|
| `id` | YES | PK; every row must have identity |
| `digital_asset_id` | YES | FK; every analysis belongs to an asset |
| `requested_by` | YES | FK; every analysis is requested by someone |
| `analyzer_key` | YES | Required for idempotency identification |
| `analyzer_version` | YES | Required for idempotency identification |
| `analyzer_slugs` | YES | At least one analyzer must be applied |
| `status` | YES | Every analysis must have a state |
| `retry_count` | YES | Default 0; never NULL |
| `created_at` | YES | Every row timestamped at creation |
| `threat_score` | NO | NULL before completion |
| `confidence` | NO | NULL before completion |
| `severity` | NO | NULL before completion |
| `reasoning_payload` | NO | NULL before completion |
| `enrichment_data` | NO | NULL before completion |
| `error_message` | NO | NULL except on failed status |
| `error_code` | NO | NULL except on failed status |
| `celery_task_id` | NO | NULL if not queued to Celery |
| `started_at` | NO | NULL until worker picks up job |
| `completed_at` | NO | NULL until terminal state |

### 7.5 Immutability Enforcement

Immutability is enforced by:

1. **Application Logic:** Repository implementation forbids UPDATE of immutable columns
2. **Database Design:** Columns designed as immutable in schema review
3. **Future: Database Role Permissions:** (Phase 2) Grant INSERT-only, no UPDATE, to API server role

Immutable columns:
- `id`, `digital_asset_id`, `requested_by`, `created_at` (always)
- `analyzer_key`, `analyzer_version`, `analyzer_slugs` (always)
- `threat_score`, `confidence`, `severity` (after completion)
- `reasoning_payload`, `enrichment_data` (after completion)
- `started_at`, `completed_at` (after creation)

Mutable columns (state machine):
- `status` (pending → running → terminal)
- `retry_count` (incremented by worker)
- `error_message`, `error_code` (set on failure)
- `celery_task_id` (set when queued)

---

## 8. JSONB Design

### 8.1 Why JSONB

JSONB is appropriate for Analyses because:

1. **Schema-Flexible:** AI model outputs vary by model version and prompt iteration. Storing in typed columns would require migrations every deployment.
2. **Consumed as a Unit:** Full reasoning payload retrieved and returned atomically — not queried field-by-field.
3. **GIN Indexable:** Future full-text search on reasoning summaries via `to_tsvector`.
4. **External Integration:** Threat intelligence APIs (VirusTotal, Shodan) return large nested JSON; storing as-is avoids denormalization.

### 8.2 reasoning_payload Structure

**Purpose:** Store full AI model output, including reasoning steps, IOCs discovered, data gaps, model metadata.

**Expected Structure:**

```json
{
  "threat_score": 0.91,
  "confidence": 0.87,
  "severity": "CRITICAL",
  "summary": "URL exhibits phishing indicators including credential harvesting form, throwaway domain, and high detection rate.",
  "reasoning_steps": [
    "VirusTotal flagged URL with 47/92 engine detections",
    "Domain registered 3 days ago — consistent with throwaway infrastructure",
    "URLScan detected login form harvesting credentials",
    "WHOIS shows registrar change 1 day ago — another phishing signal"
  ],
  "iocs": [
    {"type": "domain", "value": "evil-banking.tk", "confidence": 0.99},
    {"type": "ip_address", "value": "198.51.100.42", "confidence": 0.80},
    {"type": "email", "value": "attacker@evil-banking.tk", "confidence": 0.75}
  ],
  "data_gaps": [
    "Shodan API unavailable for this IP range",
    "No passive DNS records found (privacy-protected)"
  ],
  "model_version": "gpt-4o-2024-11-20",
  "prompt_version": "v1.2.0",
  "tokens_used": {
    "prompt": 1842,
    "completion": 412,
    "total": 2254
  }
}
```

**Query Patterns:**

- Filter by threat_score range: `WHERE (reasoning_payload->>'threat_score')::float > 0.75`
- Check for specific IOC type: `WHERE reasoning_payload @> '[{"type": "domain"}]'`
- Full-text search on summary: `WHERE to_tsvector('english', reasoning_payload->>'summary') @@ websearch_to_tsquery('phishing')`
- Extract all IOCs: `SELECT jsonb_array_elements(reasoning_payload->'iocs') AS ioc`

**GIN Index (Future):**

```sql
CREATE INDEX ix_analyses_reasoning_fts 
  ON analyses USING GIN (to_tsvector('english', reasoning_payload->>'summary'))
```

### 8.3 enrichment_data Structure

**Purpose:** Store extracted threat intelligence from external sources (not raw API responses).

**Expected Structure:**

```json
{
  "virustotal": {
    "detections": 47,
    "engines_total": 92,
    "detection_rate": "47/92",
    "categories": ["phishing", "malware"],
    "last_analysis_date": "2025-01-17T10:30:00Z"
  },
  "urlscan": {
    "threats": ["phishing"],
    "suspicious_features": ["login_form", "external_submission"]
  },
  "shodan": null,
  "whois": {
    "registrar": "NameCheap",
    "registered": "2025-01-14",
    "updated": "2025-01-16"
  }
}
```

**Query Patterns:**

- Find analyses where VirusTotal detection rate high: `WHERE (enrichment_data->'virustotal'->>'detection_rate')::int > 70`
- Find analyses with Shodan data available: `WHERE enrichment_data->'shodan' IS NOT NULL`
- Extract all threat categories: `SELECT jsonb_object_keys(enrichment_data) AS source`

**Design Decision: Extracted, Not Raw**

- **Not stored:** Full raw VirusTotal/Shodan API responses (too large, stored in object storage)
- **Instead stored:** Key threat indicators (detection count, categories, dates)
- **Rationale:** Raw data in object storage (audit trail); extracted fields in DB (queryable)

### 8.4 Update Strategy

Both JSONB fields are immutable after creation:
- Set once when analysis completes
- Never updated thereafter
- Re-analysis creates new Analysis row (not UPDATE of old row)

---

## 9. Migration Design

### 9.1 Migration File Structure and Illustrative Pattern

**File Location:** `backend/migrations/versions/YYYYMMDD_HHMM_<revision>_add_analyses_table.py`

**Example:** `20250117_1600_001a_add_analyses_table.py`

**Illustrative Pattern (Not Production Code):**

The pseudocode below illustrates the structure and operations needed. **This is not production-ready code**; Alembic's autogenerate will produce the actual implementation from the ORM model.

For the step-by-step Alembic workflow, see `backend/ALEMBIC_SETUP.md`.

**Migration Structure (Annotated Pseudocode):**

The migration follows Alembic's standard pattern:

```python
"""Add analyses table for security analysis job tracking.

Revision ID: 001a
Revises: <E3.T5 migration ID>
Create Date: 2025-01-17 16:00:00.000000

Traces to: E3.T6 Requirements, 04-Database-Design §5.6
"""

# Migration metadata
revision = "001a"
down_revision = "<E3.T5 migration ID>"


def upgrade() -> None:
    # 1. Create analyses table with all columns
    op.create_table(
        "analyses",
        # Identity columns (id, digital_asset_id, requested_by, created_at)
        Column("id", UUID, server_default="gen_random_uuid()", primary_key=True),
        Column(
            "digital_asset_id",
            UUID,
            ForeignKey("digital_assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column(
            "requested_by",
            UUID,
            ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        Column(
            "created_at", TIMESTAMP(tz=True), server_default="now()", nullable=False
        ),
        # Analyzer identity (analyzer_key, analyzer_version, analyzer_slugs)
        Column("analyzer_key", String, nullable=False),
        Column("analyzer_version", String, nullable=False),
        Column("analyzer_slugs", ARRAY(String), nullable=False),
        # Status & tracking (status, retry_count, celery_task_id, error_message, error_code)
        Column("status", String, server_default="pending", nullable=False),
        Column("retry_count", Integer, server_default="0", nullable=False),
        Column("celery_task_id", String, nullable=True),
        Column("error_message", String, nullable=True),
        Column("error_code", String, nullable=True),
        # Verdict fields (threat_score, confidence, severity)
        Column("threat_score", Double, nullable=True),
        Column("confidence", Double, nullable=True),
        Column("severity", String, nullable=True),
        # JSONB fields (reasoning_payload, enrichment_data)
        Column("reasoning_payload", JSONB, nullable=True),
        Column("enrichment_data", JSONB, nullable=True),
        # Lifecycle timestamps (started_at, completed_at)
        Column("started_at", TIMESTAMP(tz=True), nullable=True),
        Column("completed_at", TIMESTAMP(tz=True), nullable=True),
        # Constraints: PK, FKs, CHECKs, UNIQUE
    )

    # 2. Create CHECK constraints (status, score ranges, retry count, severity)
    op.create_check_constraint(
        "ck_analyses_status",
        "analyses",
        "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_analyses_threat_score",
        "analyses",
        "threat_score BETWEEN 0.0 AND 1.0 OR threat_score IS NULL",
    )
    op.create_check_constraint(
        "ck_analyses_confidence",
        "analyses",
        "confidence BETWEEN 0.0 AND 1.0 OR confidence IS NULL",
    )
    op.create_check_constraint(
        "ck_analyses_severity",
        "analyses",
        "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') OR severity IS NULL",
    )
    op.create_check_constraint(
        "ck_analyses_retry_count", "analyses", "retry_count >= 0"
    )

    # 3. Create indexes (in dependency order: PK first, then application indexes)
    op.create_index(
        "ix_analyses_asset_status", "analyses", ["digital_asset_id", "status"]
    )
    op.create_index(
        "ix_analyses_asset_latest", "analyses", ["digital_asset_id", "created_at DESC"]
    )
    op.create_index(
        "ix_analyses_user_history", "analyses", ["requested_by", "created_at DESC"]
    )
    op.create_index(
        "ix_analyses_pending",
        "analyses",
        ["created_at"],
        postgresql_where="status = 'pending'",
    )
    op.create_index(
        "ix_analyses_celery_task",
        "analyses",
        ["celery_task_id"],
        postgresql_where="celery_task_id IS NOT NULL",
    )
    op.create_index(
        "ix_analyses_severity_completed",
        "analyses",
        ["severity", "created_at DESC"],
        postgresql_where="status = 'completed'",
    )
    op.create_unique_index(
        "uq_analyses_asset_analyzer_completed",
        "analyses",
        ["digital_asset_id", "analyzer_key", "analyzer_version"],
        postgresql_where="status = 'completed'",
    )


def downgrade() -> None:
    # 1. Drop indexes in reverse order (FIFO)
    op.drop_index("uq_analyses_asset_analyzer_completed", table_name="analyses")
    op.drop_index("ix_analyses_severity_completed", table_name="analyses")
    op.drop_index("ix_analyses_celery_task", table_name="analyses")
    op.drop_index("ix_analyses_pending", table_name="analyses")
    op.drop_index("ix_analyses_user_history", table_name="analyses")
    op.drop_index("ix_analyses_asset_latest", table_name="analyses")
    op.drop_index("ix_analyses_asset_status", table_name="analyses")

    # 2. Drop table (automatically drops PK, FKs, CHECKs)
    op.drop_table("analyses")
```

**Implementation Guide:**

This pseudocode illustrates the logical operations needed for the migration. The actual implementation will use Alembic's `op.*` functions:

- `op.create_table()` — Create the analyses table with columns and constraints
- `op.create_index()` — Create each of the 8 indexes in dependency order
- `op.create_check_constraint()` — Create CHECK constraints for status, ranges, retry_count
- `op.drop_*` functions in downgrade (reverse order for FK safety)

**Do Not Use Pseudocode Directly:** This is illustrative architecture, not production-ready Python. The actual migration code will be:
1. Generated by Alembic autogenerate from the ORM model (primary method)
2. Manually reviewed using the patterns in `backend/ALEMBIC_SETUP.md`
3. Tested via `alembic upgrade head` and `alembic downgrade base` before deployment

See `backend/ALEMBIC_SETUP.md` for the complete workflow and tool usage.

### 9.2 Upgrade/Downgrade Strategy

**Upgrade (Forward):**
1. Create table with all columns, constraints, defaults
2. Create indexes in dependency order (PK first, then foreign keys, then application indexes)
3. Commit transaction

**Downgrade (Backward):**
1. Drop indexes in reverse order (to avoid FK constraint violations)
2. Drop table
3. Commit transaction

**Rollback Safety:**
- No data loss: Table is empty at creation (no migration issues)
- No blocking: Table creation doesn't lock existing tables
- Reversible: Downgrade fully reverses upgrade

### 9.3 Locking Implications

**Upgrade Locking:**
- `CREATE TABLE` acquires table lock briefly (acceptable, new table)
- `ALTER TABLE` for constraints (minimal lock)
- Index creation uses concurrent index build (non-blocking, PostgreSQL default)

**Downgrade Locking:**
- `DROP TABLE` briefly acquires exclusive lock (acceptable, new table)
- Index drops are instant (no data movement)

**Migration can run without blocking API traffic** (indexes built concurrently).



---

## 10. Performance Considerations

### 10.1 Expected Table Growth and Lazy Loading Implications

**Growth Rate Estimation:**

- **Phase 1 (v1.0–v1.3):** 100K–500K analyses per year (low user count, single analyzer)
- **Phase 2 (v1.4–v2.0):** 1M–5M analyses per year (scaling, multiple analyzers)
- **Phase 3 (v2.0+):** 10M+ analyses (enterprise scale)

**Lazy Loading Strategy Impact:**

The `lazy="selectin"` strategy (§5) is chosen precisely because of this growth trajectory:

- **At 100K rows:** Joined loading and selectin both perform well; selectin is conservative default
- **At 1M rows:** Selectin avoids costly JOINs for analysis-only queries; partial indexes reduce index size
- **At 10M rows:** Selectin becomes critical optimization; joined loading JOINs would be prohibitively expensive for majority of queries that only need Analysis fields

**Performance Profiles:**

| Scale | Joined Strategy | SelectIn Strategy | Recommendation |
|---|---|---|---|
| 100K rows | 1 query (fast join) | 2 queries (negligible overhead) | Either acceptable |
| 1M rows | 1 query (costly join) | 2 queries (faster than join) | SelectIn preferred |
| 10M rows | 1 query (very costly join) | 2 queries (necessary) | SelectIn required |

**Index Impact:**

- **At 100K rows:** All indexes fit in memory; query plans optimal
- **At 1M rows:** Partial indexes significantly smaller than full-table alternatives (10–100x smaller)
- **At 10M rows:** Partial unique index for idempotency remains small (~50MB vs 500MB if non-partial)

### 10.2 Insert Cost

**Typical Insert:** 18 columns, 8 indexes

| Operation | Cost | Notes |
|---|---|---|
| **Table INSERT** | 1x | Single tuple write |
| **PK index update** | 1x | B-tree leaf insertion |
| **ix_analyses_asset_status** | 1x | Composite B-tree |
| **ix_analyses_asset_latest** | 1x | Composite with DESC |
| **ix_analyses_user_history** | 1x | Composite with DESC |
| **ix_analyses_pending** | 0.1x | Only if status='pending' (partial) |
| **ix_analyses_celery_task** | 0.1x | Only if celery_task_id IS NOT NULL (partial) |
| **ix_analyses_severity_completed** | 0x | Only if status='completed' (partial, but never on first insert) |
| **uq_analyses_asset_analyzer_completed** | 0x | Only if status='completed' (partial) |
| **TOTAL** | ~4x | 4 full indexes + 2 partial checks |

**Optimization:** Indexes are write-optimized B-trees with minimal branching at low row counts. No significant performance penalty.

### 10.3 Update Cost

**Typical Status Transition:** pending → running

| Operation | Cost | Notes |
|---|---|---|
| **Update status column** | 1x | Single field change |
| **ix_analyses_asset_status** | 1x | Composite includes status; must rebalance |
| **ix_analyses_pending** | -0.1x | Removed from partial index (partial condition now false) |
| **TOTAL** | ~1.1x | Mostly balanced by removal from partial pending index |

**Immutability Benefit:** Verdict fields never updated post-completion, avoiding expensive index rebuilds.

### 10.4 JSONB Storage

**Average Payload Size:**

- **reasoning_payload:** 2–5 KB (reasoning steps, IOCs, model metadata)
- **enrichment_data:** 1–3 KB (extracted threat intel from APIs)
- **Total:** ~5–8 KB per row

**At 1M rows:** 5–8 GB total JSONB storage (acceptable, not prohibitive)

**GIN Index (Future):** If full-text search added on reasoning_payload summary:

```sql
CREATE INDEX ix_analyses_reasoning_fts ON analyses USING GIN 
  (to_tsvector('english', reasoning_payload->>'summary'))
```

Index size ~10–20% of JSONB data (~500MB–1.6GB at 1M rows). Worthwhile if search queries are common.

### 10.5 VACUUM Implications

**Autovacuum Strategy:**

- **Frequency:** Default PostgreSQL autovacuum (triggered by 20% tuple updates)
- **Analyses table churn:** Status transitions create dead tuples; autovacuum reclaims
- **Partial indexes:** Reduce VACUUM cost (fewer index entries to scan)
- **No explicit tuning needed** (v1.0); revisit if latency becomes issue

**Bloat Prevention:**

- Immutable verdict fields prevent post-completion updates (no dead tuples for those rows)
- Only status/error_message/retry_count updates (small tuples, little bloat)

### 10.6 Future Partitioning (If Required)

**When:** If table exceeds 10M rows and query latency degrades

**Strategy:** Partition by **status** and **created_at**:

```sql
CREATE TABLE analyses (...)
PARTITION BY RANGE (created_at) (
  PARTITION analyses_y2025_q1 VALUES FROM ('2025-01-01') TO ('2025-04-01'),
  PARTITION analyses_y2025_q2 VALUES FROM ('2025-04-01') TO ('2025-07-01'),
  ...
);
```

**Benefit:** Queries on recent analyses (common case) scan smaller partition.  
**Cost:** Slightly more complex query planning.

---

## 11. Failure Scenarios

### 11.1 Duplicate Analysis Request

**Scenario:** Two concurrent requests to analyze the same asset with the same analyzer version.

**Handling:**

1. **Application:** Check uniqueness before INSERT
   ```python
   existing = repo.get_completed_analysis(asset_id, analyzer_key, analyzer_version)
   if existing:
       return existing  # Return cached result
   ```

2. **Database:** Partial unique index enforces at DB level
   ```
   ON CONFLICT (digital_asset_id, analyzer_key, analyzer_version) 
   WHERE status = 'completed'
   ```

3. **Result:** First INSERT succeeds; second INSERT fails uniqueness constraint → application catches and returns existing record.

### 11.2 Foreign Key Violation

**Scenario:** Request to analyze non-existent asset.

**Handling:**

1. **Application:** Validate asset exists before creating Analysis
2. **Database:** FK constraint rejects INSERT if asset_id missing
3. **Result:** 404 error returned to client (application or DB catches)

### 11.3 Enum Mismatch

**Scenario:** Celery worker sets status to invalid value (e.g., "paused" before defined).

**Handling:**

1. **Application:** Enum validation before UPDATE
   ```python
   if status not in AnalysisStatus:
       raise ValueError(f"Invalid status: {status}")
   ```

2. **Database:** CHECK constraint rejects UPDATE
3. **Result:** ERROR raised; transaction rolled back

### 11.4 Rollback Failure

**Scenario:** Migration upgrade succeeds, but downgrade fails.

**Causes:** (Rare if migration designed correctly)
- Index DROP fails (table already dropped)
- Foreign key constraints prevent table drop

**Prevention:**

- Test downgrade locally: `alembic downgrade base`
- Ensure indexes dropped before table
- Ensure no dependent tables reference this table at v1.0

**Recovery:** Manual intervention via `psql` to drop orphaned objects.

### 11.5 Concurrent Inserts

**Scenario:** Multiple workers insert analyses for same asset simultaneously.

**Handling:**

1. **No locking issue:** Analyses table has no exclusive locks (separate rows)
2. **Partial unique index:** Only enforces on completed status (not pending/running)
3. **Result:** Multiple pending/running analyses allowed (expected: retries). Only one completed enforced.

### 11.6 Race Condition: Idempotency Check

**Scenario:** Between idempotency check and INSERT, another request completes the same analysis.

**Sequence:**
1. Request A: Check for completed analysis (not found)
2. Request B: Check for completed analysis (not found)
3. Request B: INSERT new analysis
4. Request A: INSERT new analysis (UNIQUE constraint violation!)

**Handling:**

1. **Application:** Retry logic on uniqueness violation
   ```python
   try:
       analysis = repo.create_analysis(...)
   except IntegrityError as e:
       if "uq_analyses_asset_analyzer_completed" in str(e):
           analysis = repo.get_completed_analysis(asset_id, analyzer_key, analyzer_version)
   ```

2. **Database:** Partial unique index prevents duplicate completion
3. **Result:** Second request detects conflict, fetches winner's result

---

## 12. Testing Strategy

### 12.1 Unit Tests

**Location:** `backend/tests/unit/test_analysis_model.py`

**Coverage:**

1. **Instantiation:** Create Analysis with all fields, minimal fields
2. **Field Types:** Validate types (UUID, str, int, float, list, dict)
3. **Defaults:** Verify server_default values (id, created_at, status, retry_count)
4. **Enum Validation:** Valid/invalid status values
5. **Relationships:** Analysis→DigitalAsset, Analysis→User (lazy loading)
6. **Repr:** Verify `__repr__()` returns useful debugging string
7. **Immutability:** Verify verdict fields cannot be updated after creation

**Example Test:**

```python
def test_analysis_threat_score_range():
    """Threat score must be in [0.0–1.0] or None."""
    analysis = Analysis(id=uuid4(), threat_score=0.5)
    assert 0.0 <= analysis.threat_score <= 1.0
    
    with pytest.raises(ValueError):
        Analysis(id=uuid4(), threat_score=1.5)
```

### 12.2 Integration Tests

**Location:** `backend/tests/integration/test_analysis_migration.py`

**Coverage:**

1. **FK Constraints:** Insert analysis with invalid asset_id → REJECT
2. **FK Constraints:** Delete asset with analyses → REJECT
3. **Unique Idempotency:** Insert two completed analyses (asset, analyzer_key, analyzer_version) → second REJECT
4. **Unique Idempotency:** Insert two pending analyses (same triple) → both succeed (partial constraint)
5. **CHECK Constraints:** Insert threat_score=1.5 → REJECT
6. **CHECK Constraints:** Insert status='paused' → REJECT
7. **Indexes:** Query by (digital_asset_id, status) uses correct index (EXPLAIN)
8. **Indexes:** Query with status=pending uses partial index (EXPLAIN)
9. **Partial Unique:** Query returns only one completed (asset, analyzer) pair

**Example Test:**

```python
def test_idempotency_partial_unique_completed():
    """Only one completed analysis per (asset, analyzer_key, analyzer_version)."""
    asset_id = uuid4()
    analyzer_key = "virustotal"
    analyzer_version = "v2.1.0"

    # Insert first completed analysis
    analysis1 = (
        analyses_table.insert()
        .values(
            id=uuid4(),
            digital_asset_id=asset_id,
            requested_by=user_id,
            analyzer_key=analyzer_key,
            analyzer_version=analyzer_version,
            status="completed",
            threat_score=0.9,
            confidence=0.85,
            severity="CRITICAL",
        )
        .execute()
    )

    # Try to insert second completed analysis (same triple) → should fail
    with pytest.raises(IntegrityError):
        analyses_table.insert().values(
            id=uuid4(),
            digital_asset_id=asset_id,
            requested_by=user_id,
            analyzer_key=analyzer_key,
            analyzer_version=analyzer_version,
            status="completed",
            threat_score=0.8,  # Different score
            confidence=0.9,
            severity="HIGH",
        ).execute()
```

### 12.3 Migration Tests

**Location:** `backend/tests/integration/test_migrations.py`

**Coverage:**

1. **Upgrade:** `alembic upgrade head` succeeds on clean database
2. **Upgrade Idempotent:** Running upgrade twice is no-op (2nd is no-op)
3. **Downgrade:** `alembic downgrade base` succeeds (removes analyses table)
4. **Downgrade Idempotent:** Running downgrade twice is no-op
5. **Schema Consistency:** After upgrade, table schema matches ORM model
6. **Constraints Present:** All CHECK, FK, UNIQUE constraints exist
7. **Indexes Present:** All 8 indexes exist and are named correctly

**Example Test:**

```python
def test_migration_upgrade_idempotent():
    """Running upgrade twice is idempotent."""
    # First upgrade
    runner.upgrade(revision="head")

    # Verify table exists
    assert "analyses" in inspector.get_table_names()

    # Second upgrade (should be no-op)
    runner.upgrade(revision="head")

    # Verify table still exists (unchanged)
    assert "analyses" in inspector.get_table_names()
```

### 12.4 Constraint Tests

**Location:** `backend/tests/integration/test_analysis_constraints.py`

**Coverage:** (Detailed constraint violation tests)

1. **status CHECK:** Invalid values rejected
2. **threat_score CHECK:** Out-of-range values rejected
3. **confidence CHECK:** Out-of-range values rejected
4. **severity CHECK:** Invalid values rejected
5. **retry_count CHECK:** Negative values rejected
6. **digital_asset_id FK:** Non-existent asset rejected
7. **requested_by FK:** Non-existent user rejected
8. **Partial unique:** Duplicate completed (asset, analyzer) rejected

### 12.5 Performance Validation

**Location:** `backend/tests/integration/test_analysis_performance.py`

**Coverage:**

1. **Index Usage:** Query by (digital_asset_id, status) uses `ix_analyses_asset_status`
2. **Index Usage:** Query by (requested_by, created_at DESC) uses `ix_analyses_user_history`
3. **Partial Index:** Query with status='pending' uses partial index (EXPLAIN ANALYZE)
4. **Query Latency:** Single-row lookup < 1ms
5. **Batch Query:** 1000-row result set < 100ms
6. **Large Table Simulation:** Query performance consistent at 1M rows (mock via seed data)

---

## 13. Alternatives Considered

### 13.1 JSONB vs Normalized Tables

**Alternative:** Store reasoning_payload and enrichment_data in separate tables

```sql
CREATE TABLE analysis_reasoning (
  id UUID PRIMARY KEY,
  analysis_id UUID REFERENCES analyses(id),
  threat_score FLOAT,
  confidence FLOAT,
  reasoning_steps TEXT[],
  iocs JSONB,
  ...
);
```

**Why REJECTED:**
- Adds join complexity (analysis + reasoning + enrichment requires multiple joins)
- Increases storage (separate index per table)
- Violates "consumed as a unit" principle (reasoning always retrieved with analysis)
- Extra index and constraint overhead
- **Chosen:** JSONB; reasoning/enrichment retrieved as single blob

### 13.2 Enum vs VARCHAR

**Alternative:** Use PostgreSQL ENUM type

```sql
CREATE TYPE analysis_status AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');
ALTER TABLE analyses ADD COLUMN status analysis_status;
```

**Why REJECTED:**
- Schema evolution: Adding new status requires TYPE recreation (disruptive migration)
- Downgrade difficulty: Removing enum values requires CASCADE (risky)
- **Chosen:** TEXT + CHECK constraint; more flexible for evolution

### 13.3 Partial Unique Index vs Application-Only Deduplication

**Alternative:** No database constraint; application checks uniqueness in code

```python
# Application only
def create_analysis(asset_id, analyzer_key, analyzer_version):
    existing = repo.get_completed_analysis(asset_id, analyzer_key, analyzer_version)
    if existing:
        return existing
    return repo.create_new(...)
```

**Why REJECTED:**
- Race conditions: Concurrent requests both pass check, both INSERT
- Silent failures: Constraint violated silently (no error)
- Maintenance burden: Every code path must replicate check
- **Chosen:** Partial unique index; database enforces at all times

### 13.4 Joined vs SelectIn Lazy Loading

**Alternative A:** `lazy="joined"` for all relationships (eager JOIN)
- Pro: Single query, predictable
- Con: Cartesian product if loading collection (Analysis→Analyses)

**Alternative B:** `lazy="selectin"` for all relationships
- Pro: No Cartesian product; separate SELECT IN query
- Con: Two queries instead of one

**Alternative C:** `lazy="select"` for all relationships (N+1)
- Pro: Individual queries
- Con: N+1 query problem if iterating collection

**Chosen:** Asymmetric strategy (like E3.T5)
- Analysis→DigitalAsset: `lazy="joined"` (often needed together)
- Analysis→User: `lazy="joined"` (often needed together)
- DigitalAsset→Analyses (reverse): `lazy="selectin"` (if accessed, load separate)

**Rationale:** Analysis typically fetched with asset/user context; reverse access less common but should not N+1.

### 13.5 UUID vs Integer PK

**Alternative:** Auto-incrementing integer primary key

```sql
id BIGSERIAL PRIMARY KEY
```

**Why REJECTED:**
- Exposes row count (security concern; client can infer growth rate)
- Non-distributed: requires coordination in multi-region (future)
- Not aligned with domain model (UUIDs are semantic identity)
- **Chosen:** UUID; aligns with E3.T5 pattern

---

## 14. Traceability Matrix

This matrix ensures every requirement is addressed by design.

| # | Requirement | Design Section | Implementation Mechanism |
|---|---|---|---|
| R1 | Entity Persistence | §3, §5 | ORM model with PK, FK, relationships |
| R2 | Status Values | §4.1, §7.1 | AnalysisStatus enum + CHECK constraint |
| R3 | Core Fields | §3.1 | 18 columns with types, defaults, constraints |
| R4 | Analyzer Identity | §3.1 (group 2) | analyzer_key + analyzer_version columns |
| R5 | Referential Integrity | §5.1, §7.3 | FK constraint ON DELETE RESTRICT |
| R6 | Query Efficiency | §6 | 8 indexes covering all query patterns |
| R7 | Idempotency | §6.2 (Index 8), §7.2 | Partial unique index on (asset_id, analyzer_key, analyzer_version) |
| R8 | Reasoning Storage | §8 | JSONB columns (reasoning_payload, enrichment_data) |
| R9 | Relationship | §5.1, §5.2 | FK + relationship() with lazy loading |
| R10 | Lifecycle Invariants | §7.1, §7.5 | CHECK status constraint + application state machine |

---

## 15. Design Review Checklist

- [x] Database schema complete (18 explicit columns, 6 logical groups)
- [x] All constraints defined (CHECK, FK, UNIQUE)
- [x] All indexes justified (8 indexes with rationale)
- [x] Enum design explained (AnalysisStatus, Severity)
- [x] Relationships designed (FK, lazy loading, cascade)
- [x] JSONB schemas documented (reasoning_payload, enrichment_data)
- [x] Migration design complete (upgrade/downgrade)
- [x] Performance considerations analyzed
- [x] Failure scenarios handled
- [x] Testing strategy defined
- [x] Alternatives considered and justified
- [x] Traceability matrix complete
- [x] Aligned with E3.T5 pattern
- [x] Ready for implementation

---

## Sign-Off

**Design Specification:**
- Version: 1.0.0 (Final)
- Status: **READY FOR IMPLEMENTATION**
- Location: `.kiro/specs/epic-3-database-foundation-analyses-t6/design.md`

**Next Steps:** Proceed to Task Specification (tasks.md) with implementation breakdown and DAG dependencies.
