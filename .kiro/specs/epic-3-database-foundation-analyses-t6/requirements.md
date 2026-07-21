# E3.T6 — Analyses ORM Model and Migration — Requirements Specification

## Document Information

| Field | Value |
|---|---|
| **Feature Name** | epic-3-database-foundation-analyses-t6 |
| **Task ID** | E3.T6 |
| **Specification Version** | 1.0.0 |
| **Status** | Draft (Awaiting Review) |
| **Owner** | Engineering Team |
| **Audience** | Engineers, Code Reviewers |
| **Dependencies** | E3.T5 (DigitalAsset ORM complete), 04-Database-Design §5.6, 02-Domain-Model §Analysis |
| **Last Updated** | 2025-01-17 |

---

## 1. Introduction

### 1.1 Purpose

This specification defines requirements for implementing the **Analyses ORM model** and its corresponding **Alembic migration** for the Sentinel security analysis platform.

The `Analysis` entity represents a security analysis job — the complete lifecycle from request through completion. It is the central record linking:
- A `DigitalAsset` being analyzed
- One or more `Analyzers` applied to that asset
- The extracted security verdict (threat score, confidence, severity)
- The full AI reasoning payload (structured JSON)
- Lifecycle timestamps and status

This task creates the persistent storage layer for the async analysis pipeline defined in the Architecture and Domain Model.

### 1.2 Scope

**In Scope:**
- Analysis record structure with all required fields
- Analysis lifecycle states and state machine
- Field constraints (ranges, validity, immutability rules)
- Queryability by common access patterns (asset, status, requester, severity)
- Referential integrity to DigitalAsset
- Idempotency guarantee per Domain Model invariant 6
- Storage of reasoning and enrichment data as queryable structures
- Timestamps capturing analysis job lifecycle
- Relationship to DigitalAsset for result context

**Out of Scope:**
- Integration test implementation (covered in post-implementation testing phase)
- Repository interface or implementation (covered in E3.T10)
- Analyzer registry implementation (separate task)
- Analysis service/business logic (separate task)
- API endpoints for creating/retrieving analyses (separate task)

---

## 2. Glossary

| Term | Definition |
|---|---|
| **Analysis** | A security analysis job record. Represents one invocation of one or more analyzers against one digital asset. |
| **AnalysisStatus** | Enum with 5 possible values: pending, running, completed, failed, cancelled. Defines the lifecycle state of an analysis job. |
| **Verdict** | The extracted security assessment: threat score [0.0–1.0], confidence [0.0–1.0], severity (LOW/MEDIUM/HIGH/CRITICAL). |
| **Reasoning Payload** | Full AI model output as JSONB, including reasoning steps, IOCs, data gaps, model version, and token usage. |
| **Enrichment Data** | Extracted threat intelligence fields from third-party APIs (VirusTotal, URLScan, Shodan, etc.) stored as JSONB. |
| **Immutability** | Once an Analysis reaches a terminal state (completed, failed), its verdict fields and reasoning are never updated. Re-analysis creates a new Analysis row. |
| **Idempotency Index** | A partial unique index enforcing Domain Model invariant 6: re-running the same analyzer version on the same asset returns the existing Analysis, not a duplicate. |
| **Partial Index** | A B-tree index that indexes only rows matching a WHERE clause condition (e.g., status = 'completed'). Reduces index size for large tables. |
| **JSONB** | PostgreSQL's binary JSON type. Supports efficient containment queries and GIN indexing. Used for unstructured threat intelligence data. |
| **FK Constraint** | Foreign key constraint enforcing referential integrity and cascading deletion rules. |
| **ORM Model** | SQLAlchemy Mapped class defining database schema, relationships, and constraints in Python code. |

---

## 3. Requirements

### Requirement R1: Analysis Entity Persistence

**User Story:** As a system, I need to persist analysis job records to PostgreSQL so that security analysis results are durable and queryable.

#### Acceptance Criteria

1. An Analysis entity exists with stable identity (system-generated ID)
2. Analysis records can be inserted into persistent storage
3. Analysis records can be retrieved by ID
4. Analysis records can be queried by digital_asset_id
5. Analysis records can be queried by status
6. The entity is immutable after reaching a terminal state (completed, failed, or cancelled)

---

### Requirement R2: Analysis Status Values

**User Story:** As an operator, I need to track analysis job progress through well-defined lifecycle states so that I can monitor pipeline health and report job status accurately.

#### Acceptance Criteria

1. Analysis has a status field with exactly 5 valid values:
   - `pending` — Analysis is queued, awaiting worker pickup
   - `running` — Worker is actively processing this analysis
   - `completed` — Analysis finished successfully with a verdict
   - `failed` — Analysis failed with error details
   - `cancelled` — Analysis was cancelled before completion
2. Only these 5 values are allowed (enforced at database level)
3. Status can be queried and filtered efficiently

---

### Requirement R3: Analysis Core Fields

**User Story:** As an engineer, I need Analysis records to capture all essential information about a security analysis job so that the system can track job state, ownership, and completion status.

#### Acceptance Criteria

**Identity and Ownership (Required):**
1. Analysis has a unique system-generated identifier (id)
2. Analysis has a digital_asset_id field referencing the asset being analyzed (immutable)
3. Analysis has a requested_by field referencing the user who triggered the analysis (immutable)
4. Analysis has a created_at timestamp (immutable after creation)

**Status and Job Tracking (Required):**
5. Analysis has a status field with 5 valid values (pending, running, completed, failed, cancelled)
6. Analysis has an analyzer_slugs field containing the ordered list of analyzers applied (immutable)
7. Analysis has a retry_count field tracking the number of retry attempts consumed (integer, ≥ 0)
8. Analysis has an error_message field (nullable, only populated on failed status)
9. Analysis has an error_code field (nullable, only populated on failed status)
10. Analysis has a celery_task_id field for Celery job correlation (nullable)

**Verdict Fields — Written Once on Completion (Required):**
11. Analysis has a threat_score field (nullable before completion, immutable after)
12. threat_score must be in range [0.0 to 1.0] or null
13. Analysis has a confidence field (nullable before completion, immutable after)
14. confidence must be in range [0.0 to 1.0] or null
15. Analysis has a severity field (nullable before completion, immutable after)
16. severity must be one of: LOW, MEDIUM, HIGH, CRITICAL, or null

**Reasoning and Enrichment (Required):**
17. Analysis has a reasoning_payload field storing structured analysis reasoning (nullable before completion)
18. reasoning_payload shall be stored as structured JSON
19. Analysis has an enrichment_data field storing extracted threat intelligence (nullable before completion)
20. enrichment_data shall be stored as structured JSON

**Lifecycle Timestamps (Required):**
21. Analysis has a started_at field (nullable until status = running)
22. Analysis has a completed_at field (nullable until status reaches terminal state)

---

### Requirement R4: Analyzer Identity Fields

**User Story:** As an analyst tracking analysis history, I need to identify which analyzer version produced a verdict so that I can understand which threat intelligence sources were used and can re-run the same analysis if needed.

#### Acceptance Criteria

1. Analysis has an analyzer_key field (immutable, identifies the analyzer module)
2. Analysis has an analyzer_version field (immutable, identifies the specific analyzer code version)
3. Both fields are required (not nullable)
4. The pair (digital_asset_id, analyzer_key, analyzer_version) must have a queryable relationship to completed analyses (see R8 for idempotency)

---

### Requirement R5: Referential Integrity to Digital Asset

**User Story:** As a data integrity engineer, I need the database to prevent orphaned analysis records so that every analysis is linked to an existing digital asset.

#### Acceptance Criteria

1. digital_asset_id is a required field (not nullable)
2. digital_asset_id references a DigitalAsset record
3. Deleting a DigitalAsset is prevented if analyses reference it (referential integrity)
4. The relationship is immutable (digital_asset_id cannot change after creation)

---

### Requirement R6: Query Efficiency

**User Story:** As an operator, I need analysis records to be queryable with predictable performance so that UI dashboards and status monitoring don't degrade under load.

#### Acceptance Criteria

1. The database shall efficiently support queries by:
   - Analysis id (unique lookup)
   - digital_asset_id + status (list analyses for an asset by status)
   - digital_asset_id + created_at (find most recent analysis for an asset)
   - status = pending + created_at (worker job queue monitoring)
   - requested_by + created_at (user's analysis history across all assets)
   - severity + status (analyst dashboard filtering completed analyses by threat level)
   - celery_task_id (Celery callback status correlation)
2. Query performance shall not degrade as the analyses table grows past 100,000 records

---

### Requirement R7: Idempotency Guarantee

**User Story:** As a system designer, I need re-running the same analyzer version against the same asset to return the existing Analysis record, not create a duplicate, so that the system enforces Domain Model invariant 6.

#### Acceptance Criteria

1. When an Analysis is completed with a specific (digital_asset_id, analyzer_key, analyzer_version) triple, only one such completed Analysis may exist
2. If a request arrives to analyze the same asset with the same analyzer at the same version, the system returns the existing Analysis record
3. This idempotency applies only to **completed** analyses; pending, running, failed, and cancelled analyses do not participate in the uniqueness check (allowing retries)
4. The idempotency constraint is enforced at the database level, not just in application logic

---

### Requirement R8: Reasoning and Enrichment Data Storage

**User Story:** As a security analyst, I need analysis reasoning and threat intelligence to be queryable so that I can investigate verdicts and understand what data was available during the analysis.

#### Acceptance Criteria

1. reasoning_payload stores the full AI model output including reasoning steps, IOCs found, data gaps, and model metadata
2. reasoning_payload shall be stored as structured JSON (queryable by field)
3. enrichment_data stores extracted threat intelligence from external sources (e.g., VirusTotal, Shodan, URLScan)
4. enrichment_data shall be stored as structured JSON
5. Both fields are nullable before analysis completion
6. Both fields are immutable after analysis completion

---

### Requirement R9: Relationship to Digital Asset

**User Story:** As a backend engineer, I need to navigate from an Analysis to its associated Digital Asset so that I can retrieve asset context when displaying analysis results.

#### Acceptance Criteria

1. Analysis belongs to exactly one DigitalAsset
2. The relationship is immutable (cannot be changed after Analysis creation)
3. The system shall allow navigation from an Analysis to its associated DigitalAsset

---

### Requirement R10: Analysis Lifecycle Invariants

**User Story:** As a system architect, I need to enforce valid status transitions so that analyses progress through their lifecycle correctly and prevent invalid state changes.

#### Acceptance Criteria

1. Status transitions follow a strict state machine:
   - pending → running (worker claims the job)
   - pending → cancelled (job cancelled before pickup)
   - running → completed (analysis succeeded)
   - running → failed (analysis failed)
   - running → cancelled (job cancelled mid-execution)
   - completed is terminal (no further transitions possible)
   - failed is terminal (no further transitions possible)
   - cancelled is terminal (no further transitions possible)
2. Backward transitions are impossible (e.g., completed → running is rejected)
3. Invalid transitions are rejected at the application layer

---

## 4. Definition of Done

**Requirements Approval Checklist:**
- [ ] All 10 requirements (R1–R10) reviewed and understood
- [ ] All 55 acceptance criteria are clear and measurable
- [ ] Analyzer_key and analyzer_version fields are confirmed (not analyzer_slugs)
- [ ] Status lifecycle state machine is confirmed
- [ ] Immutability rules are confirmed
- [ ] Query patterns are confirmed sufficient for UI dashboard and monitoring needs
- [ ] Specification approved by user before proceeding to Design phase

---

## 5. Design Decisions Deferred to Design Phase

The following design decisions will be finalized during the Design specification phase:

1. **Index Strategy** — Which specific indexes (count, types, partial conditions) to implement for R6 query efficiency
2. **Lazy Loading Strategy** — How to efficiently load DigitalAsset relationship from Analysis
3. **Relationship Backref** — Whether DigitalAsset includes reverse relationship to Analysis collection
4. **Celery Task ID Indexing** — Whether celery_task_id requires special indexing
5. **Retry Count Mutability** — Whether retry_count is updated during job execution or immutable

---

## 6. Requirements Traceability

| Requirement | Traces To |
|---|---|
| R1 — Entity Persistence | 02-Domain-Model §Analysis, 04-Database-Design §3 |
| R2 — Status Values | 02-Domain-Model §Analysis, 04-Database-Design §5.6 Status Column |
| R3 — Core Fields | 04-Database-Design §5.6 Column Specification Table |
| R4 — Analyzer Identity | 02-Domain-Model §Analysis invariant 6, 22-Engineering-Backlog E3.T6 |
| R5 — Referential Integrity | 04-Database-Design §5.6 FK Constraints, 02-Domain-Model §Analysis |
| R6 — Query Efficiency | 04-Database-Design §5.6 Index Rationale |
| R7 — Idempotency | 02-Domain-Model §Analysis invariant 6, 04-Database-Design §5.6 Business Rules |
| R8 — Reasoning Storage | 04-Database-Design §5.6.1 reasoning_payload, 04-Database-Design §2.7 When JSONB Is Appropriate |
| R9 — Relationship | 04-Database-Design §4 ERD, 02-Domain-Model §Analysis relationships |
| R10 — Lifecycle Invariants | 02-Domain-Model §Analysis, 04-Database-Design §5.6 Business Rules |

---

## 7. Acceptance Criteria Summary

| AC Count | Requirement | Domain |
|---|---|---|
| 4 | R1 (Entity Persistence) | Persistence & Queryability |
| 3 | R2 (Status Values) | Lifecycle States |
| 22 | R3 (Core Fields) | Field Definitions |
| 4 | R4 (Analyzer Identity) | Analysis Identification |
| 4 | R5 (Referential Integrity) | Data Integrity |
| 2 | R6 (Query Efficiency) | Performance |
| 4 | R7 (Idempotency) | Domain Invariants |
| 6 | R8 (Reasoning Storage) | Data Storage |
| 3 | R9 (Relationship) | Navigation |
| 3 | R10 (Lifecycle Invariants) | State Machine |
| **TOTAL** | **10 Requirements** | **55 Acceptance Criteria** |

---

## 8. Key Business Rules (Not Implementation Details)

1. **Immutability After Completion** — Once an Analysis reaches completed, failed, or cancelled status, verdict fields (threat_score, confidence, severity) are never modified
2. **Idempotency** — Re-running the same analyzer_key + analyzer_version on the same asset returns the existing completed Analysis, not a duplicate
3. **Status is Terminal** — completed, failed, and cancelled are terminal states; no further transitions possible
4. **Single Asset** — Analysis always belongs to exactly one DigitalAsset and cannot be reassigned
5. **Immutable Ownership** — requested_by (the user who triggered the analysis) cannot change after creation
