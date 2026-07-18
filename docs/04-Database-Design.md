# 04 --- Database Design

------------------------------------------------------------------------

## Document Information

  -----------------------------------------------------------------------
  Field                               Value
  ----------------------------------- -----------------------------------
  **Version**                         1.0.2

  **Status**                          Authoritative

  **Owner**                           Sentinel Core Team

  **Dependencies**                    `01-PRD.md`, `02-Domain-Model.md`,
                                      `03-Architecture.md`

  **Last Updated**                    2025

  **Audience**                        Senior Engineers, Database
                                      Reviewers, Technical Hiring
                                      Evaluators
  -----------------------------------------------------------------------

### Revision History

  Version   Date   Author               Summary
  --------- ------ -------------------- -------------------------------
  1.0.0     2025   Sentinel Core Team   Initial authoritative release

------------------------------------------------------------------------

## Table of Contents

1.  [Purpose](#1-purpose)
2.  [Database Philosophy](#2-database-philosophy)
3.  [Database Overview](#3-database-overview)
4.  [Entity Relationship Diagram](#4-entity-relationship-diagram)
5.  [Table Specifications](#5-table-specifications)
6.  [Keys](#6-keys)
7.  [Constraints](#7-constraints)
8.  [Indexing Strategy](#8-indexing-strategy)
9.  [Data Lifecycle](#9-data-lifecycle)
10. [Soft Delete Strategy](#10-soft-delete-strategy)
11. [Audit Strategy](#11-audit-strategy)
12. [Transactions](#12-transactions)
13. [Concurrency](#13-concurrency)
14. [Performance Strategy](#14-performance-strategy)
15. [Storage Strategy](#15-storage-strategy)
16. [Migration Strategy](#16-migration-strategy)
17. [Backup & Recovery](#17-backup--recovery)
18. [Security](#18-security)
19. [Future Evolution](#19-future-evolution)
20. [Architecture Traceability](#20-architecture-traceability)
21. [Appendix](#21-appendix)

------------------------------------------------------------------------

## 1. Purpose

This document is the **canonical database design specification** for the
Sentinel platform. It defines every table, column, constraint, index,
relationship, and lifecycle rule in the PostgreSQL database, and ---
critically --- justifies every decision against alternatives.

This is not a schema dump with column names. It is a design document
that answers the question *why this schema exists in this form*,
traceable at every point back to the PRD, Domain Model, and
Architecture.

### Relationship to Upstream Documents

**PRD (`01-PRD.md`)** defines the product requirements that drive data
requirements. Every table in this schema exists because the PRD requires
a capability that demands persistent state. If a table cannot be traced
to a PRD requirement, it does not belong in this schema.

**Domain Model (`02-Domain-Model.md`)** defines the business entities
--- `User`, `Upload`, `DigitalAsset`, `Analysis`, `Analyzer`, `Report`
--- and the invariants that govern them. The database schema is the
persistence projection of the Domain Model. Schema decisions that would
violate a domain invariant are rejected regardless of engineering
convenience.

**Architecture (`03-Architecture.md`)** defines the system structure:
Modular Monolith with five layers, PostgreSQL as the authoritative
source of truth, object storage for binary artifacts, and Redis as the
message broker. The database schema operates within these constraints.
It never stores binary files. It never duplicates data that belongs in
object storage. It never attempts to replace the message queue.

------------------------------------------------------------------------

## 2. Database Philosophy

### 2.1 Why PostgreSQL

PostgreSQL is not a default --- it is the deliberate choice for Sentinel
because the data model demands it.

Sentinel's core entities are **inherently relational**: a `User` owns
many `DigitalAssets`, each `DigitalAsset` is associated with one or more
`Analyses`, each `Analysis` produces one `Verdict`, and a `Report`
aggregates multiple `Verdicts`. These relationships have referential
integrity requirements that cannot be enforced at the application layer
with acceptable reliability. PostgreSQL's foreign key constraints, CHECK
constraints, and transactional DDL mean the database itself enforces
correctness --- not just the application.

  -------------------------------------------------------------------------------------
  Requirement             PostgreSQL Capability                 Why This Matters for
                                                                Sentinel
  ----------------------- ------------------------------------- -----------------------
  ACID transactions       Serializable isolation, WAL-backed    Verdict persistence
                          durability                            must be atomic ---
                                                                partial writes produce
                                                                corrupt intelligence

  Relational integrity    Foreign keys with declarative cascade An `Analysis` without a
                          rules                                 parent `DigitalAsset`
                                                                is an orphan that
                                                                breaks the domain model

  Semi-structured AI      Native `JSONB` with GIN indexing      AI reasoning payloads
  output                                                        are schema-flexible but
                                                                still queryable

  Full-text search        `tsvector` + GIN +                    Verdicts and reports
                          `websearch_to_tsquery`                must be searchable
                                                                without an external
                                                                search engine

  Array columns           Native `text[]`, `uuid[]`             IOC lists, tag arrays,
                                                                analyzer sets ---
                                                                cleaner than join
                                                                tables for small sets

  Async Python driver     SQLAlchemy Async + asyncpg --- fastest async           Critical for
                          PostgreSQL driver available           non-blocking I/O in
                                                                FastAPI and Celery
                                                                async workers

  Row-level locking       `SELECT ... FOR UPDATE SKIP LOCKED`   Queue-style task
                                                                claiming without a
                                                                separate broker for
                                                                scheduled tasks

  Partial indexes         Index only rows matching a condition  Index only `PENDING`
                                                                analysis jobs, not the
                                                                full table

  Generated columns       Computed columns stored alongside     `severity` derived from
                          data                                  `threat_score`
                                                                thresholds without
                                                                application logic
  -------------------------------------------------------------------------------------

### 2.2 Why ACID

Analysis of digital assets is **consequential**. If a verdict is written
partially --- threat score committed but IOCs not --- a user receives
dangerously incorrect security intelligence. ACID guarantees prevent
this class of error entirely:

-   **Atomicity:** The verdict, its IOCs, and the analysis job status
    update commit as one unit or not at all
-   **Consistency:** Foreign key and CHECK constraints are enforced
    before any commit is acknowledged
-   **Isolation:** Concurrent analyses of different assets do not
    observe each other's partial state
-   **Durability:** Once PostgreSQL acknowledges a commit, the verdict
    survives process crash, power loss, and filesystem failure (via WAL)

No eventual-consistency model is acceptable for security verdicts. The
cost of a false negative (malicious asset rated safe due to a partial
write) exceeds the cost of any read latency that ACID might impose.

### 2.3 Why a Relational Database

The domain model has clear, stable relationships with well-defined
cardinalities. This is exactly the use case relational databases were
designed for. The join paths are predictable: a frontend displaying a
report needs
`reports → report_assets → digital_assets → analyses → verdicts`. This
is 4 joins --- performant with correct indexing, and trivially expressed
in SQL.

A document store would require denormalizing this graph into each
document, forcing the application to maintain consistency across
redundant copies. The complexity is not removed --- it is moved from the
database (where the DBMS enforces it) to the application (where
developers must enforce it manually across every write path).

### 2.4 Why NOT MongoDB

MongoDB is the correct choice when: - Documents are deeply nested and
schema-free by nature - Access patterns are exclusively document-centric
(no cross-document joins needed) - The team needs sub-millisecond writes
at massive horizontal scale with flexible schemas

None of these conditions apply to Sentinel:

1.  **The data is relational.** A `Report` that aggregates `Verdicts`
    from multiple `DigitalAssets` cannot be expressed as a single
    document without massive denormalization
2.  **ACID is non-negotiable.** MongoDB's multi-document transactions
    are available but slow and poorly supported in async Python drivers
3.  **Referential integrity matters.** MongoDB has no foreign keys.
    Orphaned `Analysis` records pointing to deleted `DigitalAssets`
    would require application-layer cleanup --- a reliability hazard
4.  **The schema is stable.** Sentinel's entities are well-defined in
    the Domain Model. The flexibility MongoDB provides comes at the cost
    of discipline MongoDB cannot enforce

### 2.5 Why NOT DynamoDB

DynamoDB is optimal for key-value or single-table access patterns at
global scale, with predictable single-digit millisecond latency under
any load. Sentinel's query patterns do not fit this model:

-   **Variable access patterns:** Assets are queried by user, by type,
    by submission date, by analysis status, and by threat score.
    DynamoDB requires designing a table and its GSIs around a fixed set
    of access patterns at creation time
-   **No joins:** The report aggregation use case requires joining
    across 4--5 entities. DynamoDB has no join capability --- this
    becomes application-side data assembly with multiple round-trips
-   **Local development:** DynamoDB requires either DynamoDB Local (a
    separate service) or AWS credentials during development --- a
    friction DynamoDB adds that PostgreSQL does not
-   **Lock-in:** DynamoDB is AWS-specific. The architecture requires
    provider-agnostic infrastructure

### 2.6 Normalization Strategy

Sentinel uses **third normal form (3NF)** as the baseline, with
deliberate, justified exceptions.

**Why 3NF:** Every non-key attribute depends on the whole key and
nothing but the key. This eliminates update anomalies. If the email
address of a user changes, it changes in exactly one row in one table
--- not across denormalized copies scattered through the database.

**Deliberate exceptions:**

  -----------------------------------------------------------------------
  Denormalization         Table                   Justification
  ----------------------- ----------------------- -----------------------
  `severity` stored       `analyses`              Severity is a computed
  alongside                                       label derived from the
  `threat_score`                                  score threshold.
                                                  Storing it avoids
                                                  recalculation in every
                                                  read query and makes
                                                  SQL filtering on
                                                  severity direct. The
                                                  score remains the
                                                  source of truth;
                                                  severity is a derived
                                                  cache

  `asset_count` cached on `reports`               Reports aggregate many
  `reports`                                       assets; counting at
                                                  read time would require
                                                  a subquery on every
                                                  list endpoint. A cached
                                                  counter updated
                                                  transactionally is a
                                                  justified
                                                  denormalization

  `display_name` on       `analyzers`             A human-readable label
  `analyzers`                                     is not derivable from
                                                  the `slug` alone --- it
                                                  is a separate
                                                  attribute, not
                                                  denormalization
  -----------------------------------------------------------------------

### 2.7 When JSONB Is Appropriate

JSONB is the correct storage type when the data is:

1.  **Schema-flexible by nature:** AI model outputs vary by model
    version, capability, and prompt iteration. Locking them into rigid
    columns would require a migration every time a new model is deployed
2.  **Consumed as a unit:** The full reasoning payload is fetched and
    returned atomically --- it is not queried column-by-column in SQL
3.  **Indexed via GIN for key existence or containment:**
    `WHERE reasoning @> '{"severity": "CRITICAL"}'` is a legitimate
    query pattern
4.  **External API responses:** VirusTotal, Shodan, and URLScan return
    large, nested JSON structures that would require dozens of columns
    or separate tables to normalize --- without query benefit

**Where JSONB is used:** - `analyses.reasoning_payload` --- full AI
model output including reasoning steps, data gaps, model metadata -
`analyses.enrichment_data` --- raw threat intelligence API responses per
source - `digital_assets.metadata` --- asset-type-specific metadata
(e.g., HTTP headers for URLs, EXIF for files, WHOIS for domains) -
`audit_logs.before_state` / `audit_logs.after_state` --- point-in-time
snapshots for audit records

### 2.8 When JSONB Is NOT Appropriate

JSONB is the wrong choice when the data is:

1.  **Queried column-by-column:** If the application consistently
    filters by `WHERE payload->>'email' = ?`, that field belongs in a
    typed column with an index, not inside JSONB
2.  **Subject to referential integrity:** Foreign keys cannot be
    declared inside JSONB. A `user_id` that should reference the `users`
    table must be a typed `uuid` column, not `metadata->>'user_id'`
3.  **Subject to NOT NULL or CHECK constraints:** PostgreSQL cannot
    enforce `CHECK (payload->>'threat_score' BETWEEN 0 AND 1)` as
    reliably or performantly as
    `CHECK (threat_score BETWEEN 0.0 AND 1.0)` on a typed column
4.  **Aggregated in SQL:** `AVG(threat_score)` is far more efficient
    than `AVG((reasoning_payload->>'threat_score')::numeric)` --- type
    casting at query time degrades performance and loses optimizer
    statistics

### 2.9 Immutability Strategy

Verdicts are **immutable by design**. A verdict, once written,
represents the security assessment at a specific point in time, using a
specific set of enrichment data and a specific AI model. Mutating a
verdict retroactively would corrupt the historical record.

Immutability is enforced by: 1. No `UPDATE` privilege granted to the API
server database role on the `analyses` table's verdict columns after
initial write 2. A new `Analysis` record is created for each re-analysis
request --- the old record is preserved 3. `created_at` timestamps are
set once at insert time via `DEFAULT now()` and never updated

### 2.10 Data Ownership & Source of Truth

  ---------------------------------------------------------------------------------------
  Data Domain             Source of Truth                         Rationale
  ----------------------- --------------------------------------- -----------------------
  All structured entity   PostgreSQL                              ACID, relational
  data                                                            integrity, query
                                                                  capability

  Binary file content     Object Storage (S3/MinIO/R2)            PostgreSQL is not a
                                                                  blob store; object
                                                                  storage is built for
                                                                  this

  Raw AI prompt/response  Object Storage                          Large blobs that are
  pairs                   (`audit/{job_id}/ai_exchange.json`)     retrieved as-a-unit,
                                                                  not queried

  Raw enrichment API      Object Storage                          Full responses are
  responses               (`enrichment/{job_id}/{source}.json`)   large; only extracted
                                                                  fields come into
                                                                  PostgreSQL

  Pending task queue      Redis                                   Ephemeral job delivery;
                                                                  PostgreSQL is not a
                                                                  queue

  JWT access tokens       Nowhere (stateless)                     Self-validating; no
                                                                  server-side storage
                                                                  needed

  Refresh tokens          PostgreSQL (`user_refresh_tokens`)      Requires revocation
                                                                  capability; must
                                                                  persist across restarts
  ---------------------------------------------------------------------------------------

------------------------------------------------------------------------

## 3. Database Overview

### 3.1 What PostgreSQL Is Responsible For

-   **User identity and authentication state:** Users, their hashed
    credentials, their roles, and their refresh tokens
-   **Asset registry:** Every digital asset submitted by every user ---
    its type, its value, its storage key, and its metadata
-   **Upload tracking:** The upload record that links a user file
    submission to its object storage location and processing status
-   **Analysis job lifecycle:** The full lifecycle of every analysis job
    --- pending, running, completed, failed --- including timing, error
    context, and the extracted verdict data
-   **Analyzer registry:** The catalog of analyzers (threat intelligence
    enrichers) available in the system and their configuration
-   **Verdict data:** The normalized, queryable verdict fields (threat
    score, confidence, severity) and the JSONB reasoning payload
-   **Report definitions:** The metadata of composite reports --- which
    assets they cover, their summary, their storage key for the rendered
    PDF
-   **Audit trail:** Every state-changing operation, who performed it,
    when, and what changed

### 3.2 What PostgreSQL Is NOT Responsible For

  ---------------------------------------------------------------------------------
  Responsibility          Correct Location        Reason
  ----------------------- ----------------------- ---------------------------------
  Binary file storage     Object Storage          PostgreSQL's WAL was not designed
  (uploaded files, PDFs)                          for large binary objects; object
                                                  storage is cheaper, faster, and
                                                  purpose-built

  Full AI prompt/response Object Storage          A single AI exchange can exceed
  text                                            32KB; storing thousands of these
                                                  in PostgreSQL wastes
                                                  shared_buffers and bloats WAL

  Raw enrichment API      Object Storage          Full VirusTotal/Shodan responses
  responses                                       are large JSON blobs that are
                                                  retrieved as-a-unit, not
                                                  SQL-queried

  Task queue state        Redis                   PostgreSQL is not a message
                                                  broker;
                                                  `SELECT FOR UPDATE SKIP LOCKED`
                                                  approximates queue behavior but
                                                  lacks routing, dead-letter, and
                                                  TTL semantics

  Session state           Nowhere (stateless JWT) Access tokens are validated
                                                  cryptographically; no server-side
                                                  session store needed

  Application cache       Redis                   Read-heavy responses (e.g.,
                                                  analyzer catalog) are cached in
                                                  Redis; PostgreSQL serves the
                                                  source of truth
  ---------------------------------------------------------------------------------

### 3.3 PostgreSQL Instance Architecture

    Application Processes
      API Server (asyncpg)
      Workers    (asyncpg)
            │
            ▼
      PgBouncer (transaction pooling). Applications connect to PgBouncer; PgBouncer connects to PostgreSQL.
      pool_size=20 (API), pool_size=10 (workers)
            │
            ▼
      PostgreSQL 16 (primary)
      max_connections=100
      shared_buffers=256MB
      effective_cache_size=768MB
      work_mem=4MB
      wal_level=replica
            │
            ▼ (streaming replication — v1.1+)
      PostgreSQL 16 (read replica)

The single primary PostgreSQL instance is sufficient for Sentinel v1. A
read replica is documented as the next scaling step when read query load
(primarily report listing and verdict retrieval) causes observable
latency on the primary.

------------------------------------------------------------------------

## 4. Entity Relationship Diagram

``` mermaid
erDiagram
    users {
        uuid id PK
        text email UK
        text password_hash
        text role
        boolean is_active
        boolean is_verified
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at
    }

    user_refresh_tokens {
        uuid id PK
        uuid user_id FK
        text token_hash UK
        timestamptz expires_at
        boolean is_revoked
        text user_agent
        inet ip_address
        timestamptz created_at
        timestamptz revoked_at
    }

    uploads {
        uuid id PK
        uuid user_id FK
        text original_filename
        text storage_key UK
        text content_type
        bigint file_size_bytes
        text checksum_sha256
        text upload_status
        timestamptz created_at
        timestamptz completed_at
    }

    digital_assets {
        uuid id PK
        uuid user_id FK
        uuid upload_id FK
        text asset_type
        text raw_value
        text normalized_value
        text display_label
        jsonb metadata
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at
    }

    analyzers {
        uuid id PK
        text slug UK
        text display_name
        text description
        text asset_types
        text version
        boolean is_active
        boolean is_builtin
        jsonb default_config
        timestamptz created_at
        timestamptz updated_at
    }

    analyses {
        uuid id PK
        uuid digital_asset_id FK
        uuid requested_by FK
        text status
        text[] analyzer_slugs
        float threat_score
        float confidence
        text severity
        jsonb reasoning_payload
        jsonb enrichment_data
        text error_message
        text error_code
        integer retry_count
        text celery_task_id
        timestamptz requested_at
        timestamptz started_at
        timestamptz completed_at
    }

    report_assets {
        uuid report_id FK
        uuid digital_asset_id FK
        integer position
    }

    reports {
        uuid id PK
        uuid user_id FK
        text title
        text summary
        text storage_key
        text render_status
        integer asset_count
        float aggregate_threat_score
        text highest_severity
        jsonb metadata
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at
    }

    audit_logs {
        uuid id PK
        uuid actor_id FK
        text actor_role
        text action
        text resource_type
        uuid resource_id
        jsonb before_state
        jsonb after_state
        inet ip_address
        text request_id
        text user_agent
        boolean success
        text failure_reason
        timestamptz occurred_at
    }

    users ||--o{ user_refresh_tokens : "holds"
    users ||--o{ uploads : "creates"
    users ||--o{ digital_assets : "owns"
    users ||--o{ analyses : "requests"
    users ||--o{ reports : "authors"
    users ||--o{ audit_logs : "generates"
    uploads ||--o| digital_assets : "materializes"
    digital_assets ||--o{ analyses : "analyzed_by"
    digital_assets ||--o{ report_assets : "included_in"
    reports ||--o{ report_assets : "contains"
```

------------------------------------------------------------------------

## 5. Table Specifications

### 5.1 `users`

**Purpose:** The authoritative registry of all Sentinel platform users.
Provides the identity anchor for every other entity in the system.

**Business Responsibility:** Every digital asset, analysis, report, and
audit log is owned by or attributed to a row in this table. User
deactivation (`is_active = false`) must propagate to access control
without destroying historical records.

  ------------------------------------------------------------------------------------------------------
  Column            Type            Nullable    Default               Constraints    Description
  ----------------- --------------- ----------- --------------------- -------------- -------------------
  `id`              `uuid`          NO          `gen_random_uuid()`   PK             Stable, opaque user
                                                                                     identifier

  `email`           `text`          NO          ---                   UNIQUE, NOT    Primary login
                                                                      NULL           credential and
                                                                                     contact address

  `password_hash`   `text`          NO          ---                   NOT NULL       bcrypt hash
                                                                                     (cost=12). Never
                                                                                     plaintext

  `role`            `text`          NO          `'user'`              NOT NULL,      RBAC role as
                                                                      CHECK IN       defined in
                                                                      (`'user'`,     Architecture §11.3
                                                                      `'analyst'`,   
                                                                      `'admin'`)     

  `is_active`       `boolean`       NO          `true`                NOT NULL       `false` =
                                                                                     soft-deactivated,
                                                                                     all auth attempts
                                                                                     rejected

  `is_verified`     `boolean`       NO          `false`               NOT NULL       Email verification
                                                                                     status

  `created_at`      `timestamptz`   NO          `now()`               NOT NULL       Account creation
                                                                                     timestamp,
                                                                                     immutable after
                                                                                     insert

  `updated_at`      `timestamptz`   NO          `now()`               NOT NULL       Updated by trigger
                                                                                     on any column
                                                                                     change

  `deleted_at`      `timestamptz`   YES         `NULL`                ---            Soft delete
                                                                                     timestamp; NULL =
                                                                                     active
  ------------------------------------------------------------------------------------------------------

**Indexes:**

  -------------------------------------------------------------------------------------------
  Index Name               Columns                        Type              Rationale
  ------------------------ ------------------------------ ----------------- -----------------
  `users_pkey`             `id`                           Primary           PK lookup

  `users_email_uk`         `email`                        Unique            Login lookup,
                                                                            uniqueness
                                                                            enforcement

  `users_active_created`   `is_active, created_at DESC`   B-tree            Admin user list
                                                                            filtered to
                                                                            active users,
                                                                            sorted by recency
  -------------------------------------------------------------------------------------------

**Business Rules:** - Email must be stored in lowercased, normalized
form (enforced at application layer, verified by CHECK) -
`password_hash` must never be returned in any API response --- enforced
by the repository layer's response projection - Deactivating a user
(`is_active = false`) does NOT delete their assets, analyses, or
reports - Hard deletion of a user is not supported in v1 ---
`deleted_at` is set and the row is excluded from all queries via a
default WHERE clause in the repository

**Future Extensibility:** When organizations are introduced (§19), an
`organization_id` foreign key is added to this table. The `role` column
evolves to a join table `user_roles` when workspace-scoped roles are
needed.

------------------------------------------------------------------------

### 5.2 `user_refresh_tokens`

**Purpose:** Server-side store for opaque refresh tokens, enabling
revocation of specific sessions without invalidating all user sessions.

**Business Responsibility:** The JWT access token is stateless
(15-minute lifetime). The refresh token is the server-side lever for
session control --- logout, password change, and admin revocation all
operate here.

  ----------------------------------------------------------------------------------------------------
  Column         Type            Nullable    Default               Constraints   Description
  -------------- --------------- ----------- --------------------- ------------- ---------------------
  `id`           `uuid`          NO          `gen_random_uuid()`   PK            Token record
                                                                                 identifier

  `user_id`      `uuid`          NO          ---                   FK →          Token owner
                                                                   `users.id` ON 
                                                                   DELETE        
                                                                   CASCADE       

  `token_hash`   `text`          NO          ---                   UNIQUE, NOT   SHA-256 hash of the
                                                                   NULL          opaque token value.
                                                                                 Never the raw token

  `expires_at`   `timestamptz`   NO          ---                   NOT NULL      Absolute expiry;
                                                                                 tokens past this are
                                                                                 rejected regardless
                                                                                 of `is_revoked`

  `is_revoked`   `boolean`       NO          `false`               NOT NULL      Explicit revocation
                                                                                 (logout, password
                                                                                 change)

  `user_agent`   `text`          YES         `NULL`                ---           Browser/client
                                                                                 identifier for
                                                                                 session display

  `ip_address`   `inet`          YES         `NULL`                ---           Issuing IP for
                                                                                 security review

  `created_at`   `timestamptz`   NO          `now()`               NOT NULL      Token issuance
                                                                                 timestamp

  `revoked_at`   `timestamptz`   YES         `NULL`                ---           NULL if not revoked;
                                                                                 set when
                                                                                 `is_revoked = true`
  ----------------------------------------------------------------------------------------------------

**Indexes:**

  -----------------------------------------------------------------------------------
  Index Name              Columns           Type                    Rationale
  ----------------------- ----------------- ----------------------- -----------------
  `urt_pkey`              `id`              Primary                 PK lookup

  `urt_token_hash_uk`     `token_hash`      Unique                  O(1) token
                                                                    validation lookup

  `urt_user_id`           `user_id`         B-tree                  Revoke all
                                                                    sessions for a
                                                                    user

  `urt_expires_cleanup`   `expires_at`      B-tree (partial:        Efficient cleanup
                                            `is_revoked = false`)   of expired active
                                                                    tokens
  -----------------------------------------------------------------------------------

**Business Rules:** - Tokens are rotated on every use --- each refresh
operation invalidates the presented token and issues a new one - Raw
token values are never stored --- only their SHA-256 hash. A database
breach does not expose usable tokens - Expired tokens are purged by a
scheduled cleanup task (Celery beat, daily at 02:00 UTC) using
`DELETE WHERE expires_at < now()` - ON DELETE CASCADE from `users`
ensures tokens are hard-deleted when a user is hard-deleted (admin
operation only)

------------------------------------------------------------------------

### 5.3 `uploads`

**Purpose:** Tracks the lifecycle of user-initiated file uploads ---
from the moment a multipart upload is received to the moment the file is
confirmed stored in object storage and associated with a `DigitalAsset`.

**Business Responsibility:** Decouples the upload event from asset
creation. A file upload may fail partway through (network error, size
limit exceeded, invalid content type). The `upload` record exists before
the asset, capturing the attempt even when it does not produce a valid
asset. This is the write-ahead record for file ingestion.

  ---------------------------------------------------------------------------------------------------------
  Column                Type            Nullable    Default               Constraints       Description
  --------------------- --------------- ----------- --------------------- ----------------- ---------------
  `id`                  `uuid`          NO          `gen_random_uuid()`   PK                Upload record
                                                                                            identifier

  `user_id`             `uuid`          NO          ---                   FK → `users.id`   Uploading user
                                                                          ON DELETE         
                                                                          RESTRICT          

  `original_filename`   `text`          NO          ---                   NOT NULL          User-provided
                                                                                            filename,
                                                                                            sanitized at
                                                                                            application
                                                                                            layer. For
                                                                                            display only
                                                                                            --- never used
                                                                                            as a storage
                                                                                            key

  `storage_key`         `text`          YES         `NULL`                UNIQUE            Object storage
                                                                                            key after
                                                                                            successful
                                                                                            upload. NULL
                                                                                            until upload
                                                                                            completes

  `content_type`        `text`          NO          ---                   NOT NULL          Detected MIME
                                                                                            type (from
                                                                                            magic bytes,
                                                                                            not file
                                                                                            extension)

  `file_size_bytes`     `bigint`        NO          ---                   NOT NULL, CHECK   File size in
                                                                          \> 0              bytes,
                                                                                            validated
                                                                                            against 100MB
                                                                                            limit at
                                                                                            application
                                                                                            layer

  `checksum_sha256`     `text`          YES         `NULL`                ---               SHA-256 of file
                                                                                            content,
                                                                                            computed during
                                                                                            upload. Used
                                                                                            for
                                                                                            deduplication

  `upload_status`       `text`          NO          `'pending'`           NOT NULL, CHECK   Upload
                                                                          IN (`'pending'`,  lifecycle state
                                                                          `'processing'`,   
                                                                          `'completed'`,    
                                                                          `'failed'`)       

  `created_at`          `timestamptz`   NO          `now()`               NOT NULL          Upload
                                                                                            initiation
                                                                                            timestamp

  `completed_at`        `timestamptz`   YES         `NULL`                ---               Timestamp when
                                                                                            upload reached
                                                                                            `completed` or
                                                                                            `failed`
  ---------------------------------------------------------------------------------------------------------

**Indexes:**

  -----------------------------------------------------------------------------------------------------------
  Index Name                 Columns                       Type                             Rationale
  -------------------------- ----------------------------- -------------------------------- -----------------
  `uploads_pkey`             `id`                          Primary                          PK lookup

  `uploads_storage_key_uk`   `storage_key`                 Unique (partial:                 Prevents two
                                                           `storage_key IS NOT NULL`)       upload records
                                                                                            claiming the same
                                                                                            object storage
                                                                                            key

  `uploads_user_id`          `user_id`                     B-tree                           List user's
                                                                                            uploads

  `uploads_checksum`         `checksum_sha256`             B-tree (partial:                 Deduplication
                                                           `checksum_sha256 IS NOT NULL`)   check before
                                                                                            accepting a new
                                                                                            upload

  `uploads_status_pending`   `upload_status, created_at`   B-tree (partial:                 Cleanup job to
                                                           `upload_status = 'pending'`)     purge stale
                                                                                            pending uploads
                                                                                            older than 24
                                                                                            hours
  -----------------------------------------------------------------------------------------------------------

**Business Rules:** - `storage_key` is constructed programmatically:
`uploads/{user_id}/{upload_id}/{safe_filename}` --- never from the raw
`original_filename` - Duplicate detection: if `checksum_sha256` matches
an existing completed upload for the same user, the API returns the
existing `upload_id` without re-uploading (idempotent upload) - Pending
uploads older than 24 hours are cleaned up by the scheduled task and the
associated object storage key is deleted if it was written

**Future Extensibility:** The `upload_status` enum grows to include
`'scanning'` when ClamAV integration is added as a pre-processing stage.

------------------------------------------------------------------------

### 5.4 `digital_assets`

**Purpose:** The central entity of the Sentinel platform. Represents a
single digital artifact submitted for security evaluation --- a URL,
domain, IP address, file hash, or uploaded file.

**Business Responsibility:** `DigitalAsset` is the entity around which
the entire analysis lifecycle revolves. Every `Analysis` belongs to a
`DigitalAsset`. Every `Report` references one or more `DigitalAssets`.
This table is the starting point for all analysis queries.

  ----------------------------------------------------------------------------------------------------------------------------
  Column               Type            Nullable    Default               Constraints       Description
  -------------------- --------------- ----------- --------------------- ----------------- -----------------------------------
  `id`                 `uuid`          NO          `gen_random_uuid()`   PK                Stable asset identifier

  `user_id`            `uuid`          NO          ---                   FK → `users.id`   Asset owner
                                                                         ON DELETE         
                                                                         RESTRICT          

  `upload_id`          `uuid`          YES         `NULL`                FK → `uploads.id` Populated only for `file` asset
                                                                         ON DELETE SET     type
                                                                         NULL              

  `asset_type`         `text`          NO          ---                   NOT NULL, CHECK   Asset classification. Drives which
                                                                         IN (`'url'`,      analyzers are eligible
                                                                         `'domain'`,       
                                                                         `'ip_address'`,   
                                                                         `'file_hash'`,    
                                                                         `'file'`)         

  `raw_value`          `text`          NO          ---                   NOT NULL          The raw submitted value (e.g.,
                                                                                           `https://evil.example.com/login`,
                                                                                           `198.51.100.4`)

  `normalized_value`   `text`          NO          ---                   NOT NULL          Canonicalized form used for
                                                                                           deduplication (e.g., lowercased
                                                                                           domain, defanged URL)

  `display_label`      `text`          YES         `NULL`                ---               Optional user-provided label for
                                                                                           the asset in reports

  `metadata`           `jsonb`         NO          `'{}'`                NOT NULL          Asset-type-specific metadata. See
                                                                                           §5.4.1

  `is_active`          `boolean`       NO          `true`                NOT NULL          `false` = user has archived this
                                                                                           asset

  `created_at`         `timestamptz`   NO          `now()`               NOT NULL          Submission timestamp, immutable

  `updated_at`         `timestamptz`   NO          `now()`               NOT NULL          Updated by trigger

  `deleted_at`         `timestamptz`   YES         `NULL`                ---               Soft delete timestamp
  ----------------------------------------------------------------------------------------------------------------------------

**Indexes:**

  ------------------------------------------------------------------------------------------------------------------------
  Index Name              Columns                          Type                                         Rationale
  ----------------------- -------------------------------- -------------------------------------------- ------------------
  `da_pkey`               `id`                             Primary                                      PK lookup

  `da_user_created`       `user_id, created_at DESC`       B-tree                                       User's asset list,
                                                                                                        paginated by
                                                                                                        recency --- the
                                                                                                        primary list query

  `da_user_type`          `user_id, asset_type`            B-tree                                       Filter user's
                                                                                                        assets by type

  `da_normalized_value`   `normalized_value, asset_type`   B-tree                                       Deduplication
                                                                                                        check: does this
                                                                                                        user already have
                                                                                                        this asset?

  `da_metadata_gin`       `metadata`                       GIN                                          JSONB containment
                                                                                                        queries on
                                                                                                        metadata fields

  `da_active_only`        `user_id, created_at DESC`       B-tree (partial:                             The default
                                                           `deleted_at IS NULL AND is_active = true`)   listing query ---
                                                                                                        excludes
                                                                                                        deleted/archived
                                                                                                        assets
  ------------------------------------------------------------------------------------------------------------------------

**§5.4.1 --- `metadata` JSONB Schema by Asset Type**

The `metadata` column is JSONB because asset-type-specific attributes
vary significantly and new asset types may be introduced without schema
migrations. The following schemas are normalized and enforced at the
application layer via Pydantic:

``` json
// asset_type = 'url'
{
  "scheme": "https",
  "hostname": "evil.example.com",
  "path": "/login",
  "query_params": {"redirect": "http://attacker.com"},
  "port": null,
  "fragment": null
}

// asset_type = 'domain'
{
  "tld": "com",
  "registered_domain": "example.com",
  "subdomain": "evil",
  "is_ip_address": false
}

// asset_type = 'ip_address'
{
  "version": 4,
  "is_private": false,
  "is_loopback": false,
  "asn": null
}

// asset_type = 'file_hash'
{
  "algorithm": "sha256",
  "hash_value": "a3f5..."
}

// asset_type = 'file'
{
  "original_filename": "invoice.pdf",
  "detected_mime_type": "application/pdf",
  "file_size_bytes": 204800,
  "checksum_sha256": "a3f5...",
  "storage_key": "uploads/usr_01J.../ast_01J.../invoice.pdf"
}
```

**Business Rules:** - `raw_value` is stored as-submitted;
`normalized_value` is the canonical form used for deduplication. For
domains, this means lowercasing; for URLs, it means stripping trailing
slashes and normalizing percent-encoding - A user submitting the same
`normalized_value` + `asset_type` twice receives the existing `asset_id`
--- idempotent submission - `upload_id` is only non-NULL when
`asset_type = 'file'`; enforced by CHECK:
`(asset_type = 'file') = (upload_id IS NOT NULL)`

------------------------------------------------------------------------

### 5.5 `analyzers`

**Purpose:** The catalog of available analyzers --- the named enrichment
engines that can be applied to a digital asset. An analyzer represents a
specific threat intelligence source or analysis capability (e.g.,
VirusTotal, Shodan, URLScan, or an AI reasoning step).

**Business Responsibility:** Analyzers are configuration entities, not
runtime entities. They define *what* can be applied --- not *what was
applied* (that is `analyses.analyzer_slugs`). This table is read-heavy
and changes infrequently.

  --------------------------------------------------------------------------------------------------------------
  Column             Type            Nullable    Default               Constraints   Description
  ------------------ --------------- ----------- --------------------- ------------- ---------------------------
  `id`               `uuid`          NO          `gen_random_uuid()`   PK            Analyzer identifier

  `slug`             `text`          NO          ---                   UNIQUE, NOT   URL-safe, kebab-case
                                                                       NULL          identifier (e.g.,
                                                                                     `virustotal-url`,
                                                                                     `shodan-ip`). Used as the
                                                                                     reference key in
                                                                                     `analyses.analyzer_slugs`

  `display_name`     `text`          NO          ---                   NOT NULL      Human-readable name for UI
                                                                                     display

  `description`      `text`          YES         `NULL`                ---           What this analyzer does and
                                                                                     what data it produces

  `asset_types`      `text[]`        NO          ---                   NOT NULL      Array of asset types this
                                                                                     analyzer supports (e.g.,
                                                                                     `{'url', 'domain'}`)

  `version`          `text`          NO          `'1.0.0'`             NOT NULL      Semantic version of this
                                                                                     analyzer's implementation

  `is_active`        `boolean`       NO          `true`                NOT NULL      `false` = disabled; will
                                                                                     not be included in new
                                                                                     analyses

  `is_builtin`       `boolean`       NO          `true`                NOT NULL      Distinguishes
                                                                                     platform-provided analyzers
                                                                                     from future marketplace
                                                                                     entries

  `default_config`   `jsonb`         NO          `'{}'`                NOT NULL      Default configuration for
                                                                                     this analyzer (e.g.,
                                                                                     timeout, retries, API
                                                                                     endpoint)

  `created_at`       `timestamptz`   NO          `now()`               NOT NULL      When this analyzer was
                                                                                     registered

  `updated_at`       `timestamptz`   NO          `now()`               NOT NULL      Last configuration change
  --------------------------------------------------------------------------------------------------------------

**Indexes:**

  ------------------------------------------------------------------------------------
  Index Name            Columns                    Type              Rationale
  --------------------- -------------------------- ----------------- -----------------
  `analyzers_pkey`      `id`                       Primary           PK lookup

  `analyzers_slug_uk`   `slug`                     Unique            Slug lookup
                                                                     (primary access
                                                                     pattern for
                                                                     workers)

  `analyzers_active`    `is_active, asset_types`   GIN               Filter active
                                                   (asset_types) +   analyzers for a
                                                   B-tree            given asset type
                                                   (is_active)       
  ------------------------------------------------------------------------------------

**Business Rules:** - Slugs are immutable after creation --- they are
referenced in `analyses.analyzer_slugs` and in worker task routing. A
slug change would break historical records - `asset_types` uses a GIN
index on the array column to support `WHERE 'url' = ANY(asset_types)`
efficiently - The `default_config` JSONB is appropriate here because
configuration schemas vary by analyzer and are fetched as-a-unit

**Future Extensibility:** When the Analyzer Marketplace is introduced
(§19), `is_builtin = false` entries are submitted by third-party
providers and stored here with additional columns (`publisher_id`,
`pricing_tier`, `review_status`).

------------------------------------------------------------------------

### 5.6 `analyses`

**Purpose:** The central job record for every security analysis
performed on a digital asset. Captures the full lifecycle from request
to completion, including the extracted verdict fields and the JSONB
reasoning payload.

**Business Responsibility:** This is the most write-intensive and
query-intensive table in the system. Workers write to it continuously
(status updates, result writes). The API reads from it for job status
polling and verdict retrieval. Every design decision in this table is
made with both write throughput and read latency in mind.

  ---------------------------------------------------------------------------------------------------------------------
  Column                Type            Nullable    Default               Constraints           Description
  --------------------- --------------- ----------- --------------------- --------------------- -----------------------
  `id`                  `uuid`          NO          `gen_random_uuid()`   PK                    Analysis job
                                                                                                identifier, returned to
                                                                                                client as `job_id`

  `digital_asset_id`    `uuid`          NO          ---                   FK →                  The asset being
                                                                          `digital_assets.id`   analyzed
                                                                          ON DELETE RESTRICT    

  `requested_by`        `uuid`          NO          ---                   FK → `users.id` ON    User who triggered this
                                                                          DELETE RESTRICT       analysis

  `status`              `text`          NO          `'pending'`           NOT NULL, CHECK IN    Job lifecycle state
                                                                          (`'pending'`,         
                                                                          `'running'`,          
                                                                          `'completed'`,        
                                                                          `'failed'`,           
                                                                          `'cancelled'`)        

  `analyzer_slugs`      `text[]`        NO          ---                   NOT NULL              Ordered list of
                                                                                                analyzer slugs applied
                                                                                                in this analysis

  `threat_score`        `double precision`         YES         `NULL`                CHECK (threat_score   Final threat score. **DOUBLE PRECISION is used for transport efficiency; business comparisons must never rely on exact equality.**
                                                                          BETWEEN 0.0 AND 1.0)  \[0.0--1.0\]; NULL
                                                                                                until analysis
                                                                                                completes

  `confidence`          `double precision`         YES         `NULL`                CHECK (confidence     AI confidence in the
                                                                          BETWEEN 0.0 AND 1.0)  verdict \[0.0--1.0\];
                                                                                                NULL until analysis
                                                                                                completes

  `severity`            `text`          YES         `NULL`                CHECK IN (`'LOW'`,    Derived severity label;
                                                                          `'MEDIUM'`, `'HIGH'`, NULL until analysis
                                                                          `'CRITICAL'`)         completes

  `reasoning_payload`   `jsonb`         YES         `NULL`                ---                   Full AI output:
                                                                                                reasoning steps, IOCs,
                                                                                                data gaps, model
                                                                                                metadata

  `enrichment_data`     `jsonb`         YES         `NULL`                ---                   Extracted (not raw)
                                                                                                fields from each
                                                                                                enrichment source

  `error_message`       `text`          YES         `NULL`                ---                   Human-readable error
                                                                                                description when
                                                                                                `status = 'failed'`

  `error_code`          `text`          YES         `NULL`                ---                   Machine-readable error
                                                                                                code (e.g.,
                                                                                                `ENRICHMENT_TIMEOUT`,
                                                                                                `AI_PARSE_FAILURE`)

  `retry_count`         `integer`       NO          `0`                   NOT NULL, CHECK \>= 0 Number of Celery retry
                                                                                                attempts consumed

  `celery_task_id`      `text`          YES         `NULL`                ---                   Celery task UUID for
                                                                                                status correlation and
                                                                                                cancellation

  `requested_at`        `timestamptz`   NO          `now()`               NOT NULL              When the analysis was
                                                                                                submitted to the queue

  `started_at`          `timestamptz`   YES         `NULL`                ---                   When the worker picked
                                                                                                up this job

  `completed_at`        `timestamptz`   YES         `NULL`                ---                   When the job reached a
                                                                                                terminal state
                                                                                                (`completed` or
                                                                                                `failed`)
  ---------------------------------------------------------------------------------------------------------------------

**Indexes:**

  --------------------------------------------------------------------------------------------------------------------------------------
  Index Name                 Columns                                                   Type                            Rationale
  -------------------------- --------------------------------------------------------- ------------------------------- -----------------
  `analyses_pkey`            `id`                                                      Primary                         PK lookup

  `analyses_asset_status`    `digital_asset_id, status`                                B-tree                          "All analyses for
                                                                                                                       this asset" ---
                                                                                                                       the primary join
                                                                                                                       path from the
                                                                                                                       asset detail view

  `analyses_asset_latest`    `digital_asset_id, requested_at DESC`                     B-tree                          "Most recent
                                                                                                                       analysis for this
                                                                                                                       asset" --- the
                                                                                                                       most common read
                                                                                                                       pattern

  `analyses_pending`         `requested_at ASC`                                        B-tree (partial:                Worker queue
                                                                                       `status = 'pending'`)           monitoring; admin
                                                                                                                       view of backlog

  `analyses_user_history`    `requested_by, requested_at DESC`                         B-tree                          User's analysis
                                                                                                                       history across
                                                                                                                       all their assets

  `analyses_celery_task`     `celery_task_id`                                          B-tree (partial:                Status
                                                                                       `celery_task_id IS NOT NULL`)   correlation from
                                                                                                                       Celery callbacks

  `analyses_severity`        `severity, requested_at DESC`                             B-tree (partial:                Filter completed
                                                                                       `status = 'completed'`)         analyses by
                                                                                                                       severity ---
                                                                                                                       analyst dashboard

  `analyses_reasoning_fts`   `to_tsvector('english', reasoning_payload->>'summary')`   GIN                             Full-text search
                                                                                                                       on AI-generated
                                                                                                                       summaries
  --------------------------------------------------------------------------------------------------------------------------------------

**Business Rules:** - Status transitions are strictly ordered:
`pending → running → completed | failed`; `pending → cancelled`;
`running → cancelled`. Backwards transitions are rejected at the
application layer - `threat_score`, `confidence`, `severity`,
`reasoning_payload`, and `enrichment_data` are only written once, when
the job completes. They are never updated after that point (immutability
of verdicts) - `severity` is derived from `threat_score` thresholds (LOW
\< 0.25, MEDIUM \< 0.50, HIGH \< 0.75, CRITICAL ≥ 0.75) --- storing it
alongside the score is a justified denormalization to avoid threshold
recalculation in SQL - Re-analysis creates a new `analyses` row; it does
not update the existing one - `enrichment_data` stores extracted fields
(threat categories, detection counts, scores) --- not the full raw API
response. Full raw responses are in object storage

**§5.6.1 --- `reasoning_payload` JSONB Schema**

``` json
{
  "threat_score": 0.91,
  "confidence": 0.87,
  "severity": "CRITICAL",
  "summary": "The URL exhibits multiple indicators of a credential phishing campaign...",
  "reasoning_steps": [
    "1. VirusTotal flagged this URL with 47/92 engine detections",
    "2. The domain was registered 3 days ago — consistent with throwaway phishing infrastructure",
    "3. URLScan detected a login form harvesting credentials to an offsite endpoint"
  ],
  "iocs": [
    { "type": "domain", "value": "evil.example.com", "confidence": 0.95 },
    { "type": "ip_address", "value": "198.51.100.4", "confidence": 0.80 }
  ],
  "data_gaps": ["Shodan data unavailable for this IP range"],
  "model_version": "gpt-4o-2024-11-20",
  "prompt_version": "v1.2.0",
  "tokens_used": { "prompt": 1842, "completion": 412, "total": 2254 }
}
```

------------------------------------------------------------------------

### 5.7 `reports`

**Purpose:** Composite intelligence reports that aggregate verdicts from
multiple digital assets into a single narrative document. A report is a
user-authored artifact, not an automatically generated one.

**Business Responsibility:** Reports are the primary deliverable of the
Sentinel platform --- the thing users share with stakeholders. They
reference `digital_assets` through a join table (`report_assets`) and
carry a rendered artifact key pointing to the PDF in object storage.

  ----------------------------------------------------------------------------------------------------------------------
  Column                     Type            Nullable    Default               Constraints               Description
  -------------------------- --------------- ----------- --------------------- ------------------------- ---------------
  `id`                       `uuid`          NO          `gen_random_uuid()`   PK                        Report
                                                                                                         identifier

  `user_id`                  `uuid`          NO          ---                   FK → `users.id` ON DELETE Report author
                                                                               RESTRICT                  

  `title`                    `text`          NO          ---                   NOT NULL, CHECK (length   Report title
                                                                               \> 0 AND length \<= 500)  

  `summary`                  `text`          YES         `NULL`                ---                       User-authored
                                                                                                         executive
                                                                                                         summary

  `storage_key`              `text`          YES         `NULL`                ---                       Object storage
                                                                                                         key for
                                                                                                         rendered PDF.
                                                                                                         NULL until
                                                                                                         rendered

  `render_status`            `text`          NO          `'draft'`             NOT NULL, CHECK IN        PDF generation
                                                                               (`'draft'`,               lifecycle state
                                                                               `'rendering'`,            
                                                                               `'rendered'`, `'failed'`) 

  `asset_count`              `integer`       NO          `0`                   NOT NULL, CHECK \>= 0     Cached count of
                                                                                                         assets in this
                                                                                                         report
                                                                                                         (denormalized
                                                                                                         counter)

  `aggregate_threat_score`   `double precision`         YES         `NULL`                CHECK                     Average threat
                                                                               (aggregate_threat_score   score across
                                                                               BETWEEN 0.0 AND 1.0)      all analyzed
                                                                                                         assets;
                                                                                                         recalculated
                                                                                                         when assets
                                                                                                         change

  `highest_severity`         `text`          YES         `NULL`                CHECK IN (`'LOW'`,        Maximum
                                                                               `'MEDIUM'`, `'HIGH'`,     severity across
                                                                               `'CRITICAL'`)             all verdicts;
                                                                                                         recalculated
                                                                                                         when assets
                                                                                                         change

  `metadata`                 `jsonb`         NO          `'{}'`                NOT NULL                  Report
                                                                                                         settings:
                                                                                                         template,
                                                                                                         branding,
                                                                                                         included
                                                                                                         sections

  `created_at`               `timestamptz`   NO          `now()`               NOT NULL                  Report creation
                                                                                                         timestamp

  `updated_at`               `timestamptz`   NO          `now()`               NOT NULL                  Last
                                                                                                         modification
                                                                                                         timestamp

  `deleted_at`               `timestamptz`   YES         `NULL`                ---                       Soft delete
                                                                                                         timestamp
  ----------------------------------------------------------------------------------------------------------------------

**Indexes:**

  ---------------------------------------------------------------------------------------------------------------------
  Index Name                Columns                      Type                                         Rationale
  ------------------------- ---------------------------- -------------------------------------------- -----------------
  `reports_pkey`            `id`                         Primary                                      PK lookup

  `reports_user_created`    `user_id, created_at DESC`   B-tree                                       User's report
                                                                                                      list, paginated
                                                                                                      by recency

  `reports_render_status`   `render_status`              B-tree (partial:                             Worker queue for
                                                         `render_status IN ('draft', 'rendering')`)   pending render
                                                                                                      jobs

  `reports_active`          `user_id, created_at DESC`   B-tree (partial: `deleted_at IS NULL`)       Default listing
                                                                                                      query
  ---------------------------------------------------------------------------------------------------------------------

**Business Rules:** - `asset_count`, `aggregate_threat_score`, and
`highest_severity` are recalculated in the same transaction whenever an
asset is added to or removed from the report --- transactional counter
update, not eventual consistency - A report can be created as a `draft`
before all assets have completed analysis --- the aggregate scores
reflect only assets with completed verdicts - `storage_key` is only set
after a successful PDF render. If `render_status = 'failed'`, the
previous `storage_key` (if any) is preserved for debugging

------------------------------------------------------------------------

### 5.8 `report_assets`

**Purpose:** The join table between `reports` and `digital_assets`. A
many-to-many relationship with an ordering attribute.

**Business Responsibility:** A single report contains multiple digital
assets. A single digital asset can appear in multiple reports. The
`position` column enables user-defined ordering of assets within a
report --- critical for narrative flow in the rendered document.

  --------------------------------------------------------------------------------------------
  Column               Type        Nullable    Default     Constraints           Description
  -------------------- ----------- ----------- ----------- --------------------- -------------
  `report_id`          `uuid`      NO          ---         FK → `reports.id` ON  Parent report
                                                           DELETE CASCADE        

  `digital_asset_id`   `uuid`      NO          ---         FK →                  Referenced
                                                           `digital_assets.id`   asset
                                                           ON DELETE RESTRICT    

  `position`           `integer`   NO          ---         NOT NULL, CHECK \>= 0 Display order
                                                                                 within the
                                                                                 report
                                                                                 (0-indexed)
  --------------------------------------------------------------------------------------------

**Primary Key:** Composite `(report_id, digital_asset_id)` --- an asset
can appear at most once in a report.

**Indexes:**

  --------------------------------------------------------------------------------------------
  Index Name             Columns                           Type              Rationale
  ---------------------- --------------------------------- ----------------- -----------------
  `ra_pkey`              `(report_id, digital_asset_id)`   Primary           Uniqueness
                                                           (composite)       enforcement and
                                                                             PK lookup

  `ra_report_position`   `report_id, position`             B-tree            Ordered retrieval
                                                                             of assets in a
                                                                             report

  `ra_asset_reports`     `digital_asset_id`                B-tree            "Which reports
                                                                             include this
                                                                             asset?" ---
                                                                             reverse lookup
  --------------------------------------------------------------------------------------------

**Business Rules:** - ON DELETE CASCADE from `reports`: removing a
report removes all its `report_assets` rows atomically - ON DELETE
RESTRICT from `digital_assets`: an asset cannot be deleted while it is
referenced in any report - `position` values must be contiguous and
0-indexed within a report --- enforced at the application layer during
add/remove/reorder operations

------------------------------------------------------------------------

### 5.9 `audit_logs`

**Purpose:** Immutable record of every state-changing operation
performed by any actor on any resource. The basis for security
investigation, compliance, and non-repudiation.

**Business Responsibility:** Audit logs answer the question "who did
what, when, and what changed?" for every write operation in the system.
They are append-only --- no UPDATE or DELETE is ever issued against this
table in production.

  ------------------------------------------------------------------------------------------------------
  Column             Type            Nullable    Default               Constraints   Description
  ------------------ --------------- ----------- --------------------- ------------- -------------------
  `id`               `uuid`          NO          `gen_random_uuid()`   PK            Audit record
                                                                                     identifier

  `actor_id`         `uuid`          YES         `NULL`                FK →          User who performed
                                                                       `users.id` ON the action; NULL
                                                                       DELETE SET    for
                                                                       NULL          system-initiated
                                                                                     operations

  `actor_role`       `text`          YES         `NULL`                ---           Role at time of
                                                                                     action
                                                                                     (denormalized ---
                                                                                     role may change)

  `action`           `text`          NO          ---                   NOT NULL      Verb-noun action
                                                                                     identifier (e.g.,
                                                                                     `user.login`,
                                                                                     `asset.delete`,
                                                                                     `report.render`)

  `resource_type`    `text`          NO          ---                   NOT NULL      Entity type
                                                                                     affected (e.g.,
                                                                                     `user`,
                                                                                     `digital_asset`,
                                                                                     `analysis`)

  `resource_id`      `uuid`          YES         `NULL`                ---           UUID of the
                                                                                     affected record;
                                                                                     NULL for
                                                                                     non-resource
                                                                                     actions (e.g.,
                                                                                     `system.startup`)

  `before_state`     `jsonb`         YES         `NULL`                ---           Snapshot of
                                                                                     relevant fields
                                                                                     before the
                                                                                     operation. NULL for
                                                                                     CREATE actions

  `after_state`      `jsonb`         YES         `NULL`                ---           Snapshot of
                                                                                     relevant fields
                                                                                     after the
                                                                                     operation. NULL for
                                                                                     DELETE actions

  `ip_address`       `inet`          YES         `NULL`                ---           Client IP at time
                                                                                     of action

  `request_id`       `text`          YES         `NULL`                ---           Trace request ID
                                                                                     for correlation
                                                                                     with application
                                                                                     logs

  `user_agent`       `text`          YES         `NULL`                ---           HTTP User-Agent
                                                                                     header

  `success`          `boolean`       NO          `true`                NOT NULL      Whether the action
                                                                                     completed
                                                                                     successfully

  `failure_reason`   `text`          YES         `NULL`                ---           Populated when
                                                                                     `success = false`

  `occurred_at`      `timestamptz`   NO          `now()`               NOT NULL      Wall clock
                                                                                     timestamp of the
                                                                                     event
  ------------------------------------------------------------------------------------------------------

**Indexes:**

  ----------------------------------------------------------------------------------------------------------
  Index Name            Columns                                          Type              Rationale
  --------------------- ------------------------------------------------ ----------------- -----------------
  `audit_pkey`          `id`                                             Primary           PK lookup

  `audit_actor_time`    `actor_id, occurred_at DESC`                     B-tree            "What did this
                                                                                           user do?" ---
                                                                                           security
                                                                                           investigation

  `audit_resource`      `resource_type, resource_id, occurred_at DESC`   B-tree            "What happened to
                                                                                           this asset?" ---
                                                                                           resource history

  `audit_action_time`   `action, occurred_at DESC`                       B-tree            "All login events
                                                                                           in the last 24
                                                                                           hours" ---
                                                                                           operational
                                                                                           monitoring

  `audit_occurred_at`   `occurred_at DESC`                               B-tree            Admin audit log
                                                                                           viewer ---
                                                                                           reverse
                                                                                           chronological
  ----------------------------------------------------------------------------------------------------------

**Business Rules:** - This table is **append-only** in production. The
database role used by the API server has INSERT privilege only on this
table --- no UPDATE, no DELETE - `before_state` and `after_state` are
field-selective snapshots, not full row dumps. They include only fields
relevant to the action (e.g., for a role change: `{"role": "user"}`
before and `{"role": "analyst"}` after) - Sensitive fields
(`password_hash`, raw tokens) are **never** written to audit logs -
Retention: 2 years. Rows older than 2 years are archived to object
storage (`audit/archive/YYYY-MM/`) and hard-deleted from PostgreSQL - ON
DELETE SET NULL for `actor_id`: if a user is deleted, the audit record
is preserved with `actor_id = NULL` and `actor_role` serving as the
historical role reference

------------------------------------------------------------------------

## 6. Keys

### 6.1 Primary Keys --- UUID v4

Every table uses `uuid` as its primary key, generated by PostgreSQL's
`gen_random_uuid()` function.

**Why UUID over serial/bigserial:**

  -----------------------------------------------------------------------
  Criterion         UUID              BIGSERIAL         Decision
  ----------------- ----------------- ----------------- -----------------
  Global uniqueness Guaranteed across Unique only       ✅ UUID ---
                    all nodes         within one        required when IDs
                                      sequence          appear in URLs,
                                                        logs, and
                                                        messages

  Predictability    Non-sequential    Sequential ---    ✅ UUID ---
                    --- cannot be     exposes volume,   security by
                    enumerated        enables IDOR      design
                                      attacks           

  Performance       16 bytes; index   8 bytes; smaller  ❌ UUID ---
                    size larger than  index             acceptable
                    int                                 trade-off

  Merge-ability     Records from      Sequences collide ✅ UUID ---
                    multiple sources  on merge          required for
                    can be merged                       future
                    without collision                   multi-tenant data
                                                        isolation

  Readability in    `ast_01J...` with `12345` ---       ✅ UUID ---
  logs              prefix ---        meaningless       observability
                    identifiable      without context   benefit
  -----------------------------------------------------------------------

**Why NOT UUIDv7 (time-ordered):** UUIDv7 provides monotonically
increasing IDs that cluster better in B-tree indexes. It is a meaningful
improvement for tables with extremely high insert rates. For Sentinel
v1's insert volume, the operational complexity of ensuring UUIDv7
generation across all insertion paths is not justified. UUIDv7 is
documented as the migration path when index bloat on high-volume tables
becomes measurable.

**Why NOT ULID:** ULID is not a PostgreSQL-native type. It requires a
custom extension or application-side generation with text storage,
losing the 16-byte efficiency of the native `uuid` type.

### 6.2 Foreign Keys

All foreign keys are declared at the database level --- not only at the
application layer. This is a deliberate choice: application bugs, direct
database access, and data migrations should never be able to produce
orphaned records.

Cascade strategy is decided per-relationship based on business
semantics:

  ----------------------------------------------------------------------------------
  Relationship                       ON DELETE               Rationale
  ---------------------------------- ----------------------- -----------------------
  `user_refresh_tokens.user_id`      CASCADE                 A deleted user's
                                                             sessions should be
                                                             destroyed

  `uploads.user_id`                  RESTRICT                Prevent deleting a user
                                                             who has uploads ---
                                                             must be resolved first

  `digital_assets.user_id`           RESTRICT                A user's assets are
                                                             historical records;
                                                             deletion requires
                                                             explicit resolution

  `digital_assets.upload_id`         SET NULL                If an upload record is
                                                             cleaned up, the asset
                                                             is unaffected

  `analyses.digital_asset_id`        RESTRICT                Analysis history is
                                                             tied to the asset;
                                                             asset deletion requires
                                                             prior cleanup

  `analyses.requested_by`            RESTRICT                Analysis attribution
                                                             must be preserved

  `reports.user_id`                  RESTRICT                Reports are user-owned
                                                             historical artifacts

  `report_assets.report_id`          CASCADE                 Deleting a report
                                                             removes its asset
                                                             associations

  `report_assets.digital_asset_id`   RESTRICT                An asset in use by a
                                                             report cannot be
                                                             deleted

  `audit_logs.actor_id`              SET NULL                Audit history is
                                                             preserved even when the
                                                             actor is deleted
  ----------------------------------------------------------------------------------

### 6.3 Natural Keys and Business Identity

Natural keys exist alongside UUID primary keys where they serve a
distinct purpose:

  ---------------------------------------------------------------------------------------------
  Column                            Table                   Type              Business Purpose
  --------------------------------- ----------------------- ----------------- -----------------
  `email`                           `users`                 UNIQUE NOT NULL   User login
                                                                              identifier; must
                                                                              be unique in the
                                                                              system

  `slug`                            `analyzers`             UNIQUE NOT NULL   Stable,
                                                                              human-readable
                                                                              reference used in
                                                                              worker routing
                                                                              and API responses

  `normalized_value + asset_type`   `digital_assets`        ---               Deduplication
                                    (composite)                               key; enforced at
                                                                              application layer
                                                                              (not a DB unique
                                                                              constraint
                                                                              because it is
                                                                              per-user)

  `checksum_sha256`                 `uploads`               ---               Content
                                                                              deduplication;
                                                                              not a unique
                                                                              constraint
                                                                              because different
                                                                              users may upload
                                                                              the same file

  `token_hash`                      `user_refresh_tokens`   UNIQUE NOT NULL   Token lookup and
                                                                              collision
                                                                              prevention
  ---------------------------------------------------------------------------------------------

### 6.4 Hash Identity

`user_refresh_tokens.token_hash` stores the SHA-256 hash of the raw
opaque token. This is a form of hash identity: the token's identity in
the database is its hash, not its value. This ensures that even with
full read access to the database, an attacker cannot reconstruct valid
refresh tokens.

The same pattern applies to `uploads.checksum_sha256` --- a content
fingerprint used for deduplication, not a primary identifier.

------------------------------------------------------------------------

## 7. Constraints

### 7.1 Unique Constraints

  ------------------------------------------------------------------------------------------------------
  Table                   Columns                           Constraint Name            Justification
  ----------------------- --------------------------------- -------------------------- -----------------
  `users`                 `email`                           `users_email_uk`           One account per
                                                                                       email address

  `user_refresh_tokens`   `token_hash`                      `urt_token_hash_uk`        Token hashes must
                                                                                       be unique;
                                                                                       collision would
                                                                                       allow token
                                                                                       confusion

  `uploads`               `storage_key`                     `uploads_storage_key_uk`   Each object
                                                            (partial)                  storage key must
                                                                                       be claimed by
                                                                                       exactly one
                                                                                       upload record

  `analyzers`             `slug`                            `analyzers_slug_uk`        Slugs are stable
                                                                                       identifiers used
                                                                                       in worker routing
                                                                                       --- must be
                                                                                       unique

  `report_assets`         `(report_id, digital_asset_id)`   PK composite               An asset appears
                                                                                       at most once in a
                                                                                       report
  ------------------------------------------------------------------------------------------------------

### 7.2 Check Constraints

Check constraints encode domain invariants at the database layer ---
they remain enforced regardless of application bugs:

  -----------------------------------------------------------------------------------------------------------------------------------
  Table              Column                     Constraint                                                        Rationale
  ------------------ -------------------------- ----------------------------------------------------------------- -------------------
  `users`            `role`                     `IN ('user', 'analyst', 'admin')`                                 Prevents invalid
                                                                                                                  roles from being
                                                                                                                  persisted

  `uploads`          `file_size_bytes`          `> 0`                                                             Zero-byte uploads
                                                                                                                  are invalid

  `uploads`          `upload_status`            `IN ('pending', 'processing', 'completed', 'failed')`             Closed enumeration
                                                                                                                  of valid states

  `digital_assets`   `asset_type`               `IN ('url', 'domain', 'ip_address', 'file_hash', 'file')`         Closed enumeration
                                                                                                                  of asset types

  `digital_assets`   `upload_id` presence       `(asset_type = 'file') = (upload_id IS NOT NULL)`                 Structural
                                                                                                                  invariant: only
                                                                                                                  file assets have an
                                                                                                                  upload

  `analyses`         `status`                   `IN ('pending', 'running', 'completed', 'failed', 'cancelled')`   Closed enumeration

  `analyses`         `threat_score`             `BETWEEN 0.0 AND 1.0`                                             Domain invariant
                                                                                                                  from `ThreatScore`
                                                                                                                  value object

  `analyses`         `confidence`               `BETWEEN 0.0 AND 1.0`                                             Domain invariant
                                                                                                                  from
                                                                                                                  `ConfidenceLevel`
                                                                                                                  value object

  `analyses`         `severity`                 `IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')`                        Closed severity
                                                                                                                  enumeration

  `analyses`         `retry_count`              `>= 0`                                                            Retries cannot be
                                                                                                                  negative

  `reports`          `title` length             `length(title) BETWEEN 1 AND 500`                                 Prevents empty or
                                                                                                                  excessively long
                                                                                                                  titles

  `reports`          `render_status`            `IN ('draft', 'rendering', 'rendered', 'failed')`                 Closed enumeration

  `reports`          `asset_count`              `>= 0`                                                            Counter cannot be
                                                                                                                  negative

  `reports`          `aggregate_threat_score`   `BETWEEN 0.0 AND 1.0`                                             Same domain
                                                                                                                  invariant

  `report_assets`    `position`                 `>= 0`                                                            Positions are
                                                                                                                  non-negative
                                                                                                                  integers
  -----------------------------------------------------------------------------------------------------------------------------------

### 7.3 NOT NULL Strategy

The default for every column is NOT NULL unless there is an explicit
business reason for a column to be absent. Nullable columns require a
reason:

  ---------------------------------------------------------------------------
  Nullable Column             Table                   Reason for Nullability
  --------------------------- ----------------------- -----------------------
  `storage_key`               `uploads`               NULL until upload
                                                      completes --- the
                                                      two-phase upload
                                                      lifecycle

  `checksum_sha256`           `uploads`               Computed after
                                                      streaming completes;
                                                      unavailable at record
                                                      creation

  `completed_at`              `uploads`               Terminal state not yet
                                                      reached

  `upload_id`                 `digital_assets`        Only populated for
                                                      `file` asset type

  `display_label`             `digital_assets`        Optional user-provided
                                                      annotation

  `description`               `analyzers`             Optional documentation
                                                      field

  `threat_score`,             `analyses`              Only populated after
  `confidence`, `severity`                            analysis completes

  `reasoning_payload`,        `analyses`              Only populated after
  `enrichment_data`                                   analysis completes

  `error_message`,            `analyses`              Only populated when
  `error_code`                                        status = 'failed'

  `celery_task_id`            `analyses`              NULL until worker picks
                                                      up the job

  `started_at`,               `analyses`              Lifecycle timestamps;
  `completed_at`                                      NULL until event occurs

  `summary`, `storage_key`    `reports`               Optional/deferred
                                                      fields

  `aggregate_threat_score`,   `reports`               Null until at least one
  `highest_severity`                                  analyzed asset is
                                                      included

  `deleted_at`                `users`,                Soft delete marker;
                              `digital_assets`,       NULL = active record
                              `reports`               

  `actor_id`                  `audit_logs`            NULL for
                                                      system-initiated
                                                      operations
  ---------------------------------------------------------------------------

### 7.4 Referential Integrity

All foreign keys are declared at the database level with explicit ON
DELETE actions (see §6.2). There are no "soft" foreign keys maintained
only at the application layer. The principle is: if the relationship
matters for correctness, the database enforces it.

------------------------------------------------------------------------

## 8. Indexing Strategy

### 8.1 Primary Indexes

Every table has a primary key index on its `id` column. These are UUID
B-tree indexes and are the default lookup path for all REST resource
fetches (`GET /api/v1/assets/{id}`).

### 8.2 The Indexing Decision Framework

An index is created only when all three conditions are met: 1. The query
it supports is in the expected hot path (appears in §14.4) 2. The table
has more than \~1,000 rows where a sequential scan would be measurably
slower 3. The write overhead (index maintenance on INSERT/UPDATE) does
not exceed the read benefit

Every index below is justified against this framework.

### 8.3 Complete Index Registry

``` sql
-- ============================================================
-- users
-- ============================================================

-- Login: SELECT WHERE email = ?
-- Cardinality: 1 row per unique email — extremely high selectivity
CREATE UNIQUE INDEX users_email_uk ON users (email);

-- Admin user management: list active users by creation date
-- Partial: only active users are in the default view
CREATE INDEX users_active_created
    ON users (is_active, created_at DESC)
    WHERE deleted_at IS NULL;

-- ============================================================
-- user_refresh_tokens
-- ============================================================

-- Token validation: SELECT WHERE token_hash = ?
-- Called on every refresh request — must be O(1)
CREATE UNIQUE INDEX urt_token_hash_uk ON user_refresh_tokens (token_hash);

-- Session revocation: DELETE WHERE user_id = ?
-- Called on password change and admin revocation
CREATE INDEX urt_user_id ON user_refresh_tokens (user_id);

-- Scheduled cleanup: DELETE WHERE expires_at < now() AND is_revoked = false
-- Partial index — only targets active tokens; revoked tokens are already dead
CREATE INDEX urt_expires_cleanup
    ON user_refresh_tokens (expires_at)
    WHERE is_revoked = false;

-- ============================================================
-- uploads
-- ============================================================

-- Upload deduplication: SELECT WHERE checksum_sha256 = ? AND user_id = ?
-- Partial: only completed uploads are deduplication candidates
CREATE INDEX uploads_checksum
    ON uploads (checksum_sha256, user_id)
    WHERE checksum_sha256 IS NOT NULL AND upload_status = 'completed';

-- User upload history
CREATE INDEX uploads_user_id ON uploads (user_id, created_at DESC);

-- Stale upload cleanup: find pending uploads older than 24 hours
CREATE INDEX uploads_status_pending
    ON uploads (created_at)
    WHERE upload_status = 'pending';

-- ============================================================
-- digital_assets
-- ============================================================

-- Primary list query: user's assets, paginated by recency
-- This is the most-executed query in the system
CREATE INDEX da_user_created
    ON digital_assets (user_id, created_at DESC)
    WHERE deleted_at IS NULL;

-- Type-filtered listing: user's assets of a specific type
CREATE INDEX da_user_type
    ON digital_assets (user_id, asset_type, created_at DESC)
    WHERE deleted_at IS NULL;

-- Deduplication: has this user already submitted this asset?
-- normalized_value is typically 20–200 chars — B-tree is appropriate
CREATE INDEX da_normalized_value
    ON digital_assets (user_id, asset_type, normalized_value)
    WHERE deleted_at IS NULL;

-- JSONB metadata containment queries (e.g., WHERE metadata @> '{"tld": "ru"}')
CREATE INDEX da_metadata_gin ON digital_assets USING GIN (metadata);

-- ============================================================
-- analyzers
-- ============================================================

-- Primary lookup by workers: SELECT WHERE slug = ?
CREATE UNIQUE INDEX analyzers_slug_uk ON analyzers (slug);

-- Catalog query: active analyzers for a given asset type
-- Uses GIN on the array column to support = ANY(asset_types)
CREATE INDEX analyzers_asset_types_gin ON analyzers USING GIN (asset_types);

-- ============================================================
-- analyses
-- ============================================================

-- Status polling: SELECT WHERE id = ? (covered by PK)
-- Result retrieval: JOIN analyses ON digital_asset_id WHERE status = 'completed'
CREATE INDEX analyses_asset_status
    ON analyses (digital_asset_id, status, requested_at DESC);

-- Most recent analysis for an asset (primary join in asset detail view)
CREATE INDEX analyses_asset_latest
    ON analyses (digital_asset_id, requested_at DESC);

-- Worker queue monitoring: how many jobs are pending?
CREATE INDEX analyses_pending
    ON analyses (requested_at ASC)
    WHERE status = 'pending';

-- User's analysis history across all assets
CREATE INDEX analyses_user_history
    ON analyses (requested_by, requested_at DESC);

-- Celery task correlation (worker callback → DB update)
CREATE INDEX analyses_celery_task
    ON analyses (celery_task_id)
    WHERE celery_task_id IS NOT NULL;

-- Analyst dashboard: filter completed analyses by severity
CREATE INDEX analyses_severity_completed
    ON analyses (severity, requested_at DESC)
    WHERE status = 'completed';

-- Full-text search on AI-generated verdict summaries
-- Expression index on extracted JSONB text field
CREATE INDEX analyses_reasoning_fts
    ON analyses USING GIN (
        to_tsvector('english', COALESCE(reasoning_payload->>'summary', ''))
    )
    WHERE status = 'completed';

-- ============================================================
-- reports
-- ============================================================

-- User's report list, paginated by recency (default view)
CREATE INDEX reports_user_created
    ON reports (user_id, created_at DESC)
    WHERE deleted_at IS NULL;

-- Worker queue: find reports pending render
CREATE INDEX reports_render_pending
    ON reports (created_at ASC)
    WHERE render_status IN ('draft', 'rendering');

-- ============================================================
-- report_assets
-- ============================================================

-- Ordered asset list within a report
CREATE INDEX ra_report_position ON report_assets (report_id, position);

-- Reverse lookup: which reports include this asset?
CREATE INDEX ra_asset_reports ON report_assets (digital_asset_id);

-- ============================================================
-- audit_logs
-- ============================================================

-- Security investigation: what did this user do?
CREATE INDEX audit_actor_time ON audit_logs (actor_id, occurred_at DESC)
    WHERE actor_id IS NOT NULL;

-- Resource history: what happened to this digital asset?
CREATE INDEX audit_resource
    ON audit_logs (resource_type, resource_id, occurred_at DESC)
    WHERE resource_id IS NOT NULL;

-- Operational monitoring: all login failures in the last hour
CREATE INDEX audit_action_time ON audit_logs (action, occurred_at DESC);

-- Default admin view: reverse chronological all events
CREATE INDEX audit_occurred_at ON audit_logs (occurred_at DESC);
```

------------------------------------------------------------------------

## 9. Data Lifecycle

### 9.1 Upload Lifecycle

``` mermaid
stateDiagram-v2
    [*] --> pending : POST /assets (file upload received)
    pending --> processing : File validated, streaming to object storage
    processing --> completed : Object storage write confirmed, checksum stored
    processing --> failed : Storage error, size limit, invalid content type
    pending --> failed : Validation failure (magic bytes, size)
    completed --> [*] : upload_id referenced by digital_asset
    failed --> [*] : Record retained 7 days for debugging, then purged
```

Uploads in `pending` state older than 24 hours are considered abandoned.
The cleanup task runs daily, sets their status to `failed`, and deletes
any partial object storage writes using the `storage_key` if it was set.

### 9.2 Digital Asset Lifecycle

``` mermaid
stateDiagram-v2
    [*] --> active : Asset created (submitted by user)
    active --> active : New analysis requested
    active --> archived : User archives asset (is_active = false)
    archived --> active : User reactivates asset
    active --> soft_deleted : User deletes asset (deleted_at set)
    archived --> soft_deleted : User deletes asset
    soft_deleted --> [*] : Hard delete after 90-day retention period
```

A soft-deleted asset is excluded from all user-facing queries
(`WHERE deleted_at IS NULL`). Analyses referencing a soft-deleted asset
are preserved --- historical analysis data is never destroyed by
user-initiated deletion. Hard deletion of the asset row only occurs
after the 90-day retention window, during which the data can be
recovered by an admin.

### 9.3 Analysis Lifecycle

``` mermaid
stateDiagram-v2
    [*] --> pending : Analysis job created in DB, task published to queue
    pending --> running : Celery worker picks up task (started_at set)
    running --> completed : All stages succeed, verdict written
    running --> failed : Stage error after max retries (error_message set)
    pending --> cancelled : User or admin cancels before worker picks up
    running --> cancelled : User or admin cancels running job
    failed --> [*] : Record retained permanently (historical audit)
    completed --> [*] : Record retained permanently (immutable verdict)
    cancelled --> [*] : Record retained for audit trail
```

Analyses are **never hard-deleted**. They form the permanent historical
record of every security evaluation performed by the platform.

### 9.4 Report Lifecycle

``` mermaid
stateDiagram-v2
    [*] --> draft : Report created with initial asset list
    draft --> draft : Assets added, removed, or reordered
    draft --> rendering : User requests PDF generation
    rendering --> rendered : PDF written to object storage
    rendering --> failed : PDF generation error
    failed --> rendering : User retries render
    rendered --> rendering : User requests re-render (after new assets added)
    draft --> soft_deleted : User deletes report
    rendered --> soft_deleted : User deletes report
    soft_deleted --> [*] : Hard delete after 90-day retention
```

### 9.5 Retention Policy

  -----------------------------------------------------------------------
  Entity                  Soft Delete Retention   Hard Delete Policy
  ----------------------- ----------------------- -----------------------
  `users`                 90 days                 Admin-only; requires
                                                  explicit action

  `uploads`               7 days                  Automatic cleanup task
  (failed/abandoned)                              

  `digital_assets`        90 days                 Automatic after
                                                  retention window

  `analyses`              Never soft-deleted      Permanent retention;
                                                  archive to cold storage
                                                  after 2 years

  `reports`               90 days                 Automatic after
                                                  retention window

  `audit_logs`            Not soft-deleted        Archive to object
                                                  storage after 2 years;
                                                  hard-delete from
                                                  PostgreSQL

  `user_refresh_tokens`   None                    Purged on next daily
  (expired)                                       cleanup run
  -----------------------------------------------------------------------

### 9.6 Archival Strategy

Rows older than 2 years in `analyses` and `audit_logs` are exported to
Parquet format and uploaded to object storage
(`archive/analyses/YYYY/MM/` and `archive/audit_logs/YYYY/MM/`) before
being hard-deleted from PostgreSQL. This controls table bloat while
preserving compliance-required history indefinitely in cheaper storage.

------------------------------------------------------------------------

## 10. Soft Delete Strategy

### 10.1 Which Tables Use Soft Delete

  ---------------------------------------------------------------------------------------
  Table                   Soft Delete       Mechanism                  Rationale
  ----------------------- ----------------- -------------------------- ------------------
  `users`                 ✅ Yes            `deleted_at TIMESTAMPTZ`   User accounts
                                                                       contain historical
                                                                       attribution; hard
                                                                       delete is
                                                                       destructive to
                                                                       audit integrity

  `digital_assets`        ✅ Yes            `deleted_at TIMESTAMPTZ`   Assets referenced
                                                                       by analyses cannot
                                                                       be hard-deleted
                                                                       without breaking
                                                                       historical records

  `reports`               ✅ Yes            `deleted_at TIMESTAMPTZ`   Reports may be
                                                                       referenced by
                                                                       external
                                                                       stakeholders;
                                                                       90-day grace
                                                                       period allows
                                                                       recovery

  `uploads`               ❌ No             Status-based (`failed`)    Uploads are either
                                                                       in-progress,
                                                                       complete, or
                                                                       failed. Failed
                                                                       uploads are purged
                                                                       by cleanup, not
                                                                       soft-deleted

  `analyses`              ❌ No             Permanent retention        Analyses are
                                                                       immutable
                                                                       historical records
                                                                       --- deletion is
                                                                       never appropriate

  `analyzers`             ❌ No             `is_active = false`        Analyzers are
                                                                       deactivated, not
                                                                       deleted; the slug
                                                                       must remain for
                                                                       historical
                                                                       `analyzer_slugs`
                                                                       references in
                                                                       `analyses`

  `user_refresh_tokens`   ❌ No             `is_revoked = true`        Revoked tokens are
                                                                       effectively dead;
                                                                       `is_revoked` is
                                                                       the equivalent of
                                                                       a status flag

  `audit_logs`            ❌ No             Append-only                Audit records must
                                                                       never be deleted
                                                                       or hidden

  `report_assets`         ❌ No             Direct DELETE              The join table has
                                                                       no independent
                                                                       identity; its rows
                                                                       are created and
                                                                       deleted as part of
                                                                       report editing
                                                                       transactions
  ---------------------------------------------------------------------------------------

### 10.2 Soft Delete Implementation

All soft-deleted tables have: 1. A `deleted_at TIMESTAMPTZ DEFAULT NULL`
column 2. All repository query methods include
`WHERE deleted_at IS NULL` in the default scope 3. Partial indexes
exclude soft-deleted rows (see §8.3) 4. A separate `get_deleted(id)`
repository method for admin recovery operations 5. No UPDATE or SELECT
access to soft-deleted rows by the standard API surface

### 10.3 Why NOT a Separate `deleted_*` Archive Table

Some teams move soft-deleted rows into a separate `deleted_users` table.
This keeps the primary table smaller but introduces: - Two-step queries
when recovering a record - Schema drift when the main table is migrated
but the archive table is forgotten - Complexity in foreign key
relationships (which table is the canonical reference?)

The simpler, correct solution is partial indexes on `deleted_at IS NULL`
--- the query cost of soft-deleted rows is eliminated at the index
level, not by moving data.

------------------------------------------------------------------------

## 11. Audit Strategy

### 11.1 What Is Audited

Every state-changing operation on the following resources writes an
`audit_logs` record:

  -----------------------------------------------------------------------
  Resource                            Audited Actions
  ----------------------------------- -----------------------------------
  `users`                             `user.register`, `user.login`,
                                      `user.login_failed`, `user.logout`,
                                      `user.role_change`,
                                      `user.deactivate`,
                                      `user.reactivate`, `user.delete`

  `uploads`                           `upload.create`, `upload.complete`,
                                      `upload.fail`

  `digital_assets`                    `asset.create`, `asset.archive`,
                                      `asset.restore`, `asset.delete`

  `analyses`                          `analysis.request`,
                                      `analysis.start`,
                                      `analysis.complete`,
                                      `analysis.fail`, `analysis.cancel`

  `reports`                           `report.create`, `report.update`,
                                      `report.asset_add`,
                                      `report.asset_remove`,
                                      `report.render_request`,
                                      `report.render_complete`,
                                      `report.delete`

  `analyzers`                         `analyzer.create`,
                                      `analyzer.update`,
                                      `analyzer.deactivate`
  -----------------------------------------------------------------------

Read operations are **not** audited at the database level.
High-frequency reads (listing assets, viewing verdicts) are captured in
structured application logs with sufficient context for investigation
without creating write amplification on the `audit_logs` table.

### 11.2 Audit Record Construction

Audit records are written by the Application Service layer --- not by
database triggers. This is a deliberate choice:

**Why application-layer auditing, not database triggers:** - Triggers
run with database credentials and cannot capture HTTP-level context
(request ID, user agent, IP address) - Triggers execute in the same
transaction as the modified row --- an application crash after the
trigger fires but before the outer transaction commits results in a
trigger that ran on uncommitted data - Application-layer auditing
captures intent (the action name) rather than just the mutation (which
columns changed) - Application-layer auditing can include before/after
state with business-relevant field selection, not just raw column deltas

**Audit write pattern:**

``` sql
-- The audit insert is part of the same transaction as the main operation
BEGIN;
  UPDATE digital_assets SET deleted_at = now() WHERE id = $1;
  INSERT INTO audit_logs (actor_id, actor_role, action, resource_type, resource_id,
      before_state, after_state, ip_address, request_id, success, occurred_at)
  VALUES ($actor_id, $actor_role, 'asset.delete', 'digital_asset', $asset_id,
      $before_snapshot, $after_snapshot, $ip, $request_id, true, now());
COMMIT;
```

Writing the audit record in the same transaction as the operation
guarantees that there is never an audit record for an operation that did
not commit, and never a committed operation without an audit record.

### 11.3 Before/After State Snapshots

Snapshots capture the minimum set of fields needed to reconstruct what
changed:

``` json
// audit_logs record for a role change
{
  "action": "user.role_change",
  "before_state": { "role": "user" },
  "after_state": { "role": "analyst" },
  "resource_type": "user",
  "resource_id": "550e8400-e29b-41d4-a716-446655440000"
}

// audit_logs record for an analysis completion
{
  "action": "analysis.complete",
  "before_state": { "status": "running" },
  "after_state": {
    "status": "completed",
    "threat_score": 0.91,
    "severity": "CRITICAL",
    "completed_at": "2025-01-15T14:23:01.452Z"
  }
}
```

Fields excluded from all snapshots: `password_hash`, raw tokens,
`ip_address` (already in top-level audit column), `user_agent`.

------------------------------------------------------------------------

## 12. Transactions

### 12.1 Where Transactions Are Required

Every write operation that touches more than one table --- or that
requires atomicity between a state mutation and a side effect --- uses
an explicit database transaction:

  -----------------------------------------------------------------------
  Operation               Tables in Transaction   Why Atomic
  ----------------------- ----------------------- -----------------------
  User registration       `users` INSERT +        Audit must not exist
                          `audit_logs` INSERT     without the user

  Asset submission (file) `uploads` INSERT +      Three records form one
                          `digital_assets`        business event
                          INSERT + `audit_logs`   
                          INSERT                  

  Analysis request        `analyses` INSERT +     Job record and audit
                          `audit_logs` INSERT     log are one unit

  Analysis completion     `analyses` UPDATE       Partial verdict writes
                          (status, verdict) +     produce corrupt
                          `audit_logs` INSERT     intelligence

  Report asset addition   `report_assets`         Counter and membership
                          INSERT + `reports`      must be consistent
                          UPDATE (asset_count,    
                          scores) + `audit_logs`  
                          INSERT                  

  Token rotation          `user_refresh_tokens`   No window where both
                          UPDATE (revoke old) +   tokens are valid or
                          INSERT (new)            neither is valid

  User deactivation       `users` UPDATE +        User cannot be
                          `user_refresh_tokens`   deactivated while their
                          UPDATE (revoke all) +   sessions remain active
                          `audit_logs` INSERT     
  -----------------------------------------------------------------------

### 12.2 Where Transactions Are Intentionally Avoided

  -----------------------------------------------------------------------
  Operation                           Why No Transaction
  ----------------------------------- -----------------------------------
  Audit log reads                     Read-only; transactions add
                                      overhead without isolation benefit

  Asset listing                       Paginated SELECTs; acceptable to
                                      see committed data at query start

  Analyzer catalog fetch              Read-only; result is cached in
                                      Redis

  Health check probe                  `SELECT 1` --- no transaction
                                      overhead needed
  -----------------------------------------------------------------------

### 12.3 Isolation Level

The default isolation level is **Read Committed** --- PostgreSQL's
default. This is appropriate for Sentinel because: - Analysis jobs are
uniquely owned by one worker at a time (claimed via `celery_task_id`) -
Verdict writes are append-only --- no concurrent updates to the same
analysis row - User registration and token rotation use explicit
row-level locks (`SELECT FOR UPDATE`) where repeatable-read semantics
are required

**Serializable isolation** is used for: - The refresh token rotation
operation (read-then-write on the same token row) to prevent a race
condition where two simultaneous refresh requests both succeed

### 12.4 Idempotency

Write operations that may be retried must be idempotent at the database
level:

  -------------------------------------------------------------------------------------------------------------------------
  Operation                           Idempotency Mechanism
  ----------------------------------- -------------------------------------------------------------------------------------
  Asset submission (duplicate)        `normalized_value + asset_type + user_id` existence check in a single atomic query
                                      with `INSERT ... ON CONFLICT DO NOTHING RETURNING id`

  Analysis completion (worker retry)  `UPDATE analyses SET status = 'completed' ... WHERE id = $1 AND status = 'running'`
                                      --- the WHERE clause makes double-completion a no-op

  Upload deduplication                `checksum_sha256` lookup returns existing upload_id without re-creating

  Audit log                           Idempotency is explicitly NOT required --- duplicate audit events are acceptable
                                      (over-auditing is safer than under-auditing)
  -------------------------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

## 13. Concurrency

### 13.1 Optimistic Locking

`digital_assets` and `reports` use an `updated_at` timestamp for
optimistic concurrency control in user-facing update operations. When a
user updates a report title, the application includes the last-known
`updated_at` in the UPDATE WHERE clause:

``` sql
UPDATE reports
SET title = $new_title, updated_at = now()
WHERE id = $id AND updated_at = $client_known_updated_at AND deleted_at IS NULL;
```

If `updated_at` has changed (another request modified the row), the
UPDATE affects 0 rows. The application detects this and returns HTTP 409
Conflict with the current state of the resource.

**Why not a version counter (`version_number INTEGER`):** A timestamp is
equally effective for Sentinel's concurrency patterns and requires no
additional column on tables where `updated_at` already exists for audit
purposes. A separate version column is justified only when sub-second
concurrent writes to the same row are expected --- not the case for
report edits.

### 13.2 Duplicate Upload Prevention

Race condition scenario: two requests from the same user submit the same
file simultaneously.

Prevention: 1. The `checksum_sha256` index supports an existence check
before INSERT 2. The INSERT uses
`ON CONFLICT (checksum_sha256) WHERE upload_status = 'completed' DO NOTHING RETURNING id`
--- whichever request wins the race creates the record; the other
receives the existing `id` 3. The storage write uses the `upload_id` as
part of the key --- even if two writes race to the same key, object
storage's put operation is idempotent (last write wins, but both write
the same bytes)

### 13.3 Analysis Job Race Conditions

Race condition scenario: two workers attempt to claim the same `pending`
analysis job.

Prevention: The worker claims a job using a conditional UPDATE:

``` sql
UPDATE analyses
SET status = 'running', started_at = now(), celery_task_id = $celery_task_id
WHERE id = $job_id AND status = 'pending'
RETURNING id;
```

If two workers race on the same job, only one UPDATE will find
`status = 'pending'` and return a row. The other gets zero rows and
knows the job is already claimed. This is a lightweight optimistic claim
--- no advisory lock or SELECT FOR UPDATE needed.

### 13.4 Report Counter Consistency

`reports.asset_count`, `aggregate_threat_score`, and `highest_severity`
are denormalized counters. They must be updated in the same transaction
as the `report_assets` INSERT/DELETE to remain consistent:

``` sql
BEGIN;
  INSERT INTO report_assets (report_id, digital_asset_id, position)
  VALUES ($report_id, $asset_id, $position);

  UPDATE reports
  SET asset_count = asset_count + 1,
      aggregate_threat_score = (
          SELECT AVG(a.threat_score)
          FROM analyses a
          JOIN report_assets ra ON ra.digital_asset_id = a.digital_asset_id
          WHERE ra.report_id = $report_id AND a.status = 'completed'
      ),
      highest_severity = (
          SELECT a.severity
          FROM analyses a
          JOIN report_assets ra ON ra.digital_asset_id = a.digital_asset_id
          WHERE ra.report_id = $report_id AND a.status = 'completed'
          ORDER BY CASE a.severity
              WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3
              WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 1 ELSE 0 END DESC
          LIMIT 1
      ),
      updated_at = now()
  WHERE id = $report_id;
COMMIT;
```

------------------------------------------------------------------------

## 14. Performance Strategy

### 14.1 Pagination

All list endpoints use **keyset (cursor) pagination**, not offset
pagination.

**Why keyset over offset:**

Offset pagination (`LIMIT 25 OFFSET 500`) requires PostgreSQL to scan
and discard 500 rows before returning 25 --- O(offset) cost that grows
with page depth. More critically, concurrent inserts cause "page drift"
where items shift positions between pages, causing rows to appear on two
pages or be skipped entirely.

Keyset pagination encodes the last-seen row's values into the cursor and
uses them as WHERE clause predicates:

``` sql
-- Page 1
SELECT id, created_at, ...
FROM digital_assets
WHERE user_id = $user_id AND deleted_at IS NULL
ORDER BY created_at DESC, id DESC
LIMIT 25;

-- Page 2 (cursor = last row's created_at + id from page 1)
SELECT id, created_at, ...
FROM digital_assets
WHERE user_id = $user_id AND deleted_at IS NULL
  AND (created_at, id) < ($last_created_at, $last_id)
ORDER BY created_at DESC, id DESC
LIMIT 25;
```

The composite `(created_at DESC, id DESC)` ordering ensures stable,
unique ordering even when multiple assets share the same timestamp. The
`da_user_created` index makes this query an index scan --- O(1)
regardless of page depth.

### 14.2 Avoiding N+1 Queries

The primary N+1 risk in Sentinel is loading a list of assets and then
issuing separate queries to find the latest verdict for each asset. This
is avoided by:

1.  **JOIN with lateral subquery:** Load assets with their most recent
    completed analysis in a single query

``` sql
SELECT
    da.*,
    latest_analysis.threat_score,
    latest_analysis.severity,
    latest_analysis.status AS analysis_status
FROM digital_assets da
LEFT JOIN LATERAL (
    SELECT threat_score, severity, status
    FROM analyses
    WHERE digital_asset_id = da.id
    ORDER BY requested_at DESC
    LIMIT 1
) latest_analysis ON true
WHERE da.user_id = $user_id AND da.deleted_at IS NULL
ORDER BY da.created_at DESC, da.id DESC
LIMIT 25;
```

2.  **Batch loading in application:** When the ORM is used, the
    repository layer performs explicit batch fetching using
    `WHERE id = ANY($ids::uuid[])` --- never one query per parent entity

### 14.3 Expected Hot Query Patterns

  --------------------------------------------------------------------------
  Query                   Frequency               Optimized By
  ----------------------- ----------------------- --------------------------
  User's asset list       Very High               `da_user_created` partial
  (paginated)                                     index, keyset pagination

  Asset detail + latest   High                    `analyses_asset_latest`
  analysis                                        index, LATERAL join

  Analysis job status     High                    PK lookup on `analyses.id`
  poll                                            

  User's report list      Medium                  `reports_user_created`
  (paginated)                                     partial index

  Analyzer catalog (all   Medium                  `analyzers_slug_uk` +
  active)                                         Redis cache (TTL 5 min)

  Verdict full-text       Low                     `analyses_reasoning_fts`
  search                                          GIN index

  Admin audit log review  Very Low                `audit_occurred_at` index

  Pending job count       Low                     `analyses_pending` partial
  (monitoring)                                    index
  --------------------------------------------------------------------------

### 14.4 Large Report Queries

When generating a report PDF, the worker must fetch all assets, their
latest analyses, and their verdicts in one pass. This uses a CTE to
avoid re-scanning `report_assets`:

``` sql
WITH report_data AS (
    SELECT ra.position, da.id AS asset_id, da.raw_value, da.asset_type,
           a.threat_score, a.severity, a.reasoning_payload
    FROM report_assets ra
    JOIN digital_assets da ON da.id = ra.digital_asset_id
    LEFT JOIN LATERAL (
        SELECT threat_score, severity, reasoning_payload
        FROM analyses
        WHERE digital_asset_id = da.id AND status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1
    ) a ON true
    WHERE ra.report_id = $report_id
    ORDER BY ra.position
)
SELECT * FROM report_data;
```

### 14.5 Analyzer Catalog Caching

The `analyzers` table changes rarely (new analyzers are added by
platform engineers, not users). The full active analyzer catalog is
cached in Redis with a 5-minute TTL. Workers read from Redis on every
analysis; the cache is invalidated on any `analyzers` write.

------------------------------------------------------------------------

## 15. Storage Strategy

### 15.1 What Stays in PostgreSQL

  -----------------------------------------------------------------------------
  Data              Table                   Column Type       Rationale
  ----------------- ----------------------- ----------------- -----------------
  User identity     `users`                 Typed columns     Relational,
                                                              queried,
                                                              constrained

  Asset metadata    `digital_assets`        Typed + JSONB     Relational
                                                              structure +
                                                              type-specific
                                                              flexible fields

  Analysis verdicts `analyses`              Typed + JSONB     Threat
                                                              score/severity
                                                              are typed for SQL
                                                              queries;
                                                              reasoning is
                                                              JSONB

  Report            `reports`               Typed + JSONB     Report metadata
  definitions                                                 is relational;
                                                              settings are
                                                              JSONB

  Audit records     `audit_logs`            Typed + JSONB     Queryable audit
                                                              trail;
                                                              before/after
                                                              state is JSONB

  Refresh tokens    `user_refresh_tokens`   Typed             Small, frequently
                                                              read, requires
                                                              precise
                                                              constraint
                                                              enforcement
  -----------------------------------------------------------------------------

### 15.2 What Goes Into Object Storage

  -------------------------------------------------------------------------------------------------
  Artifact                Storage Key Pattern                               Rationale
  ----------------------- ------------------------------------------------- -----------------------
  Uploaded files (raw     `uploads/{user_id}/{upload_id}/{safe_filename}`   Binary content;
  binary)                                                                   PostgreSQL is not a
                                                                            blob store

  Full AI prompt+response `audit/{job_id}/ai_exchange.json`                 Can exceed 32KB;
  pairs                                                                     retrieved as-a-unit,
                                                                            not SQL-queried

  Raw enrichment API      `enrichment/{job_id}/{source}.json`               Large nested JSON; only
  responses                                                                 extracted fields enter
                                                                            PostgreSQL

  Rendered report PDFs    `reports/{report_id}/report.pdf`                  Binary; 1MB--50MB per
                                                                            report

  Analysis archive (\>2   `archive/analyses/{YYYY}/{MM}/{date}.parquet`     Cold storage after
  years)                                                                    PostgreSQL retention
                                                                            window

  Audit log archive (\>2  `archive/audit_logs/{YYYY}/{MM}/{date}.parquet`   Compliance retention at
  years)                                                                    low cost
  -------------------------------------------------------------------------------------------------

**The hard rule:** Binary data is never stored in PostgreSQL. A `bytea`
column for file content would bloat shared_buffers, explode WAL size,
and make backups unmanageable. Object storage handles binary artifacts;
PostgreSQL stores the key that points to them.

### 15.3 The Storage Key Contract

Object storage keys stored in PostgreSQL (`uploads.storage_key`,
`reports.storage_key`) follow a deterministic pattern built from UUIDs
--- never from user-supplied filenames. The key stored in PostgreSQL is
the single source of truth for locating the artifact. If the key is lost
from PostgreSQL, the artifact is effectively unreachable (object storage
has no structured index).

------------------------------------------------------------------------

## 16. Migration Strategy

### 16.1 Alembic as the Migration Engine

All schema changes are managed by **Alembic**, the SQLAlchemy-native
migration tool. No schema change --- including index additions and
column alterations --- is applied without an Alembic migration file.

**Why Alembic:** - Native integration with SQLAlchemy models ---
`alembic revision --autogenerate` detects drift between ORM models and
the live schema - Migration files are Python scripts, enabling arbitrary
SQL and data migrations in the same migration - Version history is
stored in the `alembic_version` table in PostgreSQL --- the database
itself knows which migration version it is at - `alembic downgrade -1`
provides one-step rollback

### 16.2 Migration File Naming Convention

    {YYYY}{MM}{DD}{HHMM}_{sequential}_{short_description}.py

    Examples:
    20250115_0001_create_users_table.py
    20250115_0002_create_uploads_table.py
    20250116_0001_add_is_verified_to_users.py
    20250120_0001_add_analyses_reasoning_fts_index.py

The timestamp prefix ensures chronological ordering. The sequential
counter handles multiple migrations on the same day. The description is
a human-readable summary of the change.

### 16.3 Zero-Downtime Migration Rules

Sentinel must be deployable without taking the application offline. The
following rules apply to all migrations:

  ------------------------------------------------------------------------------------------------------------------
  Operation               Zero-Downtime Safe?     Technique
  ----------------------- ----------------------- ------------------------------------------------------------------
  ADD COLUMN with DEFAULT ✅ Yes (PostgreSQL 11+) PostgreSQL 11+ stores the default in catalog, not in each row

  ADD COLUMN NOT NULL     ❌ No                   Add nullable first, backfill, then add NOT NULL constraint
  without DEFAULT                                 

  DROP COLUMN             ⚠️ Code must be         Remove column references from code, then run migration
                          deployed first          

  ADD INDEX CONCURRENTLY  ✅ Yes                  Use `CREATE INDEX CONCURRENTLY` --- does not hold table lock

  DROP INDEX CONCURRENTLY ✅ Yes                  Use `DROP INDEX CONCURRENTLY`

  ADD FOREIGN KEY         ⚠️ Use NOT VALID first  `ALTER TABLE ADD CONSTRAINT ... NOT VALID; VALIDATE CONSTRAINT;`
                                                  --- splits lock into two short operations

  ALTER COLUMN TYPE       ❌ Often No             Add new column, backfill, migrate application, drop old column

  ADD UNIQUE CONSTRAINT   ⚠️ Create unique index  `CREATE UNIQUE INDEX CONCURRENTLY`; then
                          concurrently first      `ADD CONSTRAINT USING INDEX`

  RENAME TABLE/COLUMN     ❌ No                   Use views or add new column; never rename in place
  ------------------------------------------------------------------------------------------------------------------

### 16.4 Migration Execution Protocol

``` bash
# 1. Review the generated migration
alembic revision --autogenerate -m "add_analyzer_marketplace_fields"

# 2. Review and edit the generated file — autogenerate is not always correct
vim alembic/versions/20250115_0003_add_analyzer_marketplace_fields.py

# 3. Run against staging environment
alembic upgrade head

# 4. Verify schema matches ORM models
alembic check

# 5. Run integration tests against migrated schema
pytest tests/integration/

# 6. Apply to production
alembic upgrade head
```

### 16.5 Schema Evolution Philosophy

The schema evolves by addition, not mutation: - New columns are added;
old columns are deprecated then removed after a safe period - New tables
are added; old tables are dropped only when all references are gone -
Enum values are added; never removed (existing data references them) -
Indexes are added `CONCURRENTLY`; old indexes are dropped only when the
new one is confirmed healthy

------------------------------------------------------------------------

## 17. Backup & Recovery

### 17.1 Backup Strategy

  ---------------------------------------------------------------------------------------
  Backup Type    Tool                        Frequency      Retention      Storage
  -------------- --------------------------- -------------- -------------- --------------
  Continuous WAL `pg_basebackup` + WAL-G     Every 5        7 days         Object storage
  archiving                                  minutes (WAL)                 (encrypted)

  Daily logical  `pg_dump --format=custom`   Daily at 01:00 30 days        Object storage
  backup                                     UTC                           (separate
                                                                           bucket)

  Weekly full    `pg_basebackup`             Weekly (Sunday 90 days        Object storage
  backup                                     02:00 UTC)                    (separate
                                                                           region)
  ---------------------------------------------------------------------------------------

**Why both physical and logical backups:** - Physical (WAL-G): enables
point-in-time recovery to any second within the retention window.
Required for RPO \< 1 minute - Logical (pg_dump): enables selective
table restoration, cross-version migration, and schema-only restoration
without a full cluster restore

### 17.2 Recovery Objectives

  -----------------------------------------------------------------------
  Objective               Target                  Mechanism
  ----------------------- ----------------------- -----------------------
  **RPO** (Recovery Point ≤ 5 minutes             Continuous WAL
  Objective)                                      archiving with 5-minute
                                                  WAL segment rotation

  **RTO** (Recovery Time  ≤ 30 minutes            Pre-tested restore
  Objective)                                      runbook; replica
                                                  promotion in ≤ 5
                                                  minutes
  -----------------------------------------------------------------------

**Assumption:** These targets assume the production environment has
access to the object storage bucket containing WAL archives. In a
full-region failure scenario, RTO extends to the time required to
restore from the cross-region weekly backup --- estimated 2--4 hours for
a database of Sentinel's expected size.

### 17.3 Restore Runbook (Summary)

``` bash
# Point-in-time recovery using WAL-G
wal-g backup-fetch $PGDATA LATEST
wal-g wal-fetch $WAL_SEGMENT $PGDATA/pg_wal/

# Logical restore of a single table (e.g., to recover accidentally deleted data)
pg_restore --table=digital_assets --data-only -d sentinel_db backup.dump

# Verify restore integrity
psql sentinel_db -c "SELECT COUNT(*), MAX(created_at) FROM analyses;"
psql sentinel_db -c "SELECT pg_size_pretty(pg_database_size('sentinel_db'));"
```

### 17.4 Backup Verification

Backups are verified weekly by restoring the latest daily logical backup
to an isolated PostgreSQL instance and running: 1.
`pg_restore --schema-only` --- confirms schema integrity 2. Row count
assertions against known-good counts 3. A sample query from each major
table

An unverified backup is not a backup.

------------------------------------------------------------------------

## 18. Security

### 18.1 Encryption at Rest

The PostgreSQL data directory is encrypted using the host's disk
encryption (LUKS on Linux, or provider-managed encryption for
cloud-hosted instances). PostgreSQL itself does not perform column-level
encryption for v1 --- the assumption is that disk encryption + network
encryption + role-based access control provides sufficient protection at
this scale.

**Exception:** If regulatory requirements demand column-level encryption
for PII (email addresses), the `pgcrypto` extension provides
`pgp_sym_encrypt`/`pgp_sym_decrypt` with key rotation support. This is
documented as a compliance-driven upgrade path.

### 18.2 Password Storage

User passwords are **never stored in plaintext**. The
`users.password_hash` column stores the output of bcrypt with a cost
factor of 12. bcrypt is chosen over Argon2id because: - It is
universally supported by Python's `passlib` library - Its cost factor
provides \~300ms hash time on commodity hardware --- sufficient to make
brute force economically impractical

**Assumption:** When regulatory compliance requires Argon2id (the
current OWASP recommendation), the migration path is: add a
`password_algorithm` column, re-hash passwords on next login, and
deprecate bcrypt after a migration window.

### 18.3 PII Handling

The only PII stored in PostgreSQL is `users.email`. Mitigations: - Email
is stored lowercased and normalized, reducing the information density -
The `api_server` database role has SELECT access to `users.email` only
through views that exclude `password_hash` - Audit logs never capture
email in before/after state --- the `resource_id` (UUID) is the
reference - Future: if GDPR right-to-erasure is required, `users.email`
is the only field that cannot be anonymized without breaking login ---
the process is deactivation + email overwrite with a pseudonymous value

### 18.4 Least Privilege --- Database Roles

Three database roles are defined:

  -----------------------------------------------------------------------
  Role                    Privileges              Used By
  ----------------------- ----------------------- -----------------------
  `sentinel_api`          SELECT, INSERT, UPDATE  API server
                          on most tables;         
                          INSERT-only on          
                          `audit_logs`            

  `sentinel_worker`       SELECT, INSERT, UPDATE  Background workers
                          on `analyses`,          
                          `uploads`; INSERT-only  
                          on `audit_logs`         

  `sentinel_admin`        Full privileges on all  Admin tools, migrations
                          tables                  (run manually)
  -----------------------------------------------------------------------

No application process connects with superuser credentials. Connection
strings are injected via environment variables per process.

### 18.5 SQL Injection Protection

All database access goes through SQLAlchemy's parameterized query
interface. No raw SQL strings with f-string interpolation exist in the
codebase --- this is enforced by the code review checklist and a custom
Ruff linter rule that flags `text()` calls with string concatenation.

The single exception is the Alembic migration runner, which constructs
DDL statements programmatically --- reviewed manually on every
migration.

------------------------------------------------------------------------

## 19. Future Evolution

The schema is designed to support the following capabilities without
breaking backward compatibility. All additions are additive --- no
existing column is renamed or removed.

### 19.1 Organizations

``` sql
-- Add organization support
CREATE TABLE organizations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    slug text UNIQUE NOT NULL,
    plan text NOT NULL DEFAULT 'free'
        CHECK (plan IN ('free', 'pro', 'enterprise')),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Users belong to organizations
ALTER TABLE users ADD COLUMN organization_id uuid
    REFERENCES organizations(id) ON DELETE RESTRICT;

-- Assets are scoped to organizations (not just users)
ALTER TABLE digital_assets ADD COLUMN organization_id uuid
    REFERENCES organizations(id) ON DELETE RESTRICT;
```

The `organization_id` columns are nullable in their initial migration
--- existing single-tenant users are unaffected. All new multi-tenant
users have a non-NULL `organization_id`. Repository queries are updated
to filter by `organization_id` when present.

### 19.2 Workspaces

``` sql
CREATE TABLE workspaces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE digital_assets ADD COLUMN workspace_id uuid
    REFERENCES workspaces(id) ON DELETE RESTRICT;
ALTER TABLE reports ADD COLUMN workspace_id uuid
    REFERENCES workspaces(id) ON DELETE RESTRICT;
```

### 19.3 API Keys

``` sql
CREATE TABLE api_keys (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash text UNIQUE NOT NULL,  -- SHA-256 of the raw key; never the key itself
    display_prefix text NOT NULL,   -- First 8 chars for UI display (e.g., "sntnl_ab")
    name text NOT NULL,
    scopes text[] NOT NULL DEFAULT '{}',
    is_active boolean NOT NULL DEFAULT true,
    expires_at timestamptz,
    last_used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
```

API keys follow the same hash-only storage pattern as refresh tokens.
The raw key is shown once at creation time and never again.

### 19.4 Notifications

``` sql
CREATE TABLE notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type text NOT NULL,  -- 'analysis.completed', 'report.rendered', 'threat.critical'
    payload jsonb NOT NULL DEFAULT '{}',
    is_read boolean NOT NULL DEFAULT false,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX notifications_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE is_read = false;
```

### 19.5 Analyzer Marketplace

``` sql
-- Existing analyzers table gains marketplace columns
ALTER TABLE analyzers ADD COLUMN publisher_id uuid
    REFERENCES users(id) ON DELETE RESTRICT;
ALTER TABLE analyzers ADD COLUMN pricing_tier text
    CHECK (pricing_tier IN ('free', 'paid', 'enterprise'));
ALTER TABLE analyzers ADD COLUMN review_status text NOT NULL DEFAULT 'pending'
    CHECK (review_status IN ('pending', 'approved', 'rejected'));
ALTER TABLE analyzers ADD COLUMN marketplace_listed_at timestamptz;

-- Track which organizations have subscribed to which paid analyzers
CREATE TABLE analyzer_subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id),
    analyzer_id uuid NOT NULL REFERENCES analyzers(id),
    subscribed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, analyzer_id)
);
```

### 19.6 Webhooks

``` sql
CREATE TABLE webhooks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    url text NOT NULL,
    secret_hash text NOT NULL,  -- HMAC signing key hash
    events text[] NOT NULL,     -- e.g., {'analysis.completed', 'report.rendered'}
    is_active boolean NOT NULL DEFAULT true,
    failure_count integer NOT NULL DEFAULT 0,
    last_triggered_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE webhook_deliveries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id uuid NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    response_status integer,
    response_body text,
    success boolean NOT NULL DEFAULT false,
    attempted_at timestamptz NOT NULL DEFAULT now()
);
```

### 19.7 Team Collaboration

``` sql
CREATE TABLE workspace_members (
    workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role text NOT NULL DEFAULT 'member'
        CHECK (role IN ('owner', 'admin', 'analyst', 'member', 'viewer')),
    invited_by uuid REFERENCES users(id) ON DELETE SET NULL,
    joined_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);
```

### 19.8 Backward Compatibility Guarantee

All future schema changes follow these rules: 1. New columns are always
nullable or have a DEFAULT --- existing rows are never broken by an
addition 2. Existing column types are never changed in-place --- new
columns are added and old ones deprecated 3. Existing CHECK constraints
are never tightened --- only relaxed or extended 4. Existing indexes are
never renamed --- new indexes are created with the new naming convention
before old ones are dropped

------------------------------------------------------------------------

## 20. Architecture Traceability

Every table in this schema is traceable to a specific entity or
requirement from the upstream documents.

  ---------------------------------------------------------------------------------------------
  Table                   Domain Model      PRD Requirement   Architecture Reference
                          Entity                              
  ----------------------- ----------------- ----------------- ---------------------------------
  `users`                 `User`            User              Auth module
                                            registration,     (`sentinel.modules.auth`), §11
                                            authentication,   
                                            RBAC              

  `user_refresh_tokens`   ---               Stateful session  Auth module, §11.2
                                            revocation for    
                                            refresh tokens    

  `uploads`               `Upload`          File upload for   Assets module
                                            file-type assets; (`sentinel.modules.assets`),
                                            deduplication     §13.3

  `digital_assets`        `DigitalAsset`    Core entity: URL, Assets module, §8.2
                                            domain, IP, file  
                                            hash, file        
                                            submission        

  `analyzers`             `Analyzer`        Pluggable threat  Enrichment module
                                            intelligence      (`sentinel.modules.enrichment`)
                                            enrichers         

  `analyses`              `Analysis` (Job + Analysis job      Analysis module
                          Verdict)          lifecycle; AI     (`sentinel.modules.analysis`),
                                            verdict           §9.2
                                            persistence       

  `reports`               `Report`          Composite report  Reports module
                                            generation and    (`sentinel.modules.reports`)
                                            PDF export        

  `report_assets`         --- (join entity) Many-to-many:     Reports module
                                            reports reference 
                                            multiple assets   

  `audit_logs`            `AuditLog`        Security audit    Shared infrastructure; §14
                                            trail; admin      (Observability)
                                            compliance view   
  ---------------------------------------------------------------------------------------------

**Note on `analyses` duality:** The architecture document uses the term
`AnalysisJob` for the job lifecycle record and `Verdict` for the verdict
output. In the database schema, these are unified in the single
`analyses` table. This is a deliberate denormalization: a 1:1
relationship between job and verdict (every completed job produces
exactly one verdict) does not warrant a separate table. Separating them
would introduce a mandatory JOIN on every verdict retrieval with no
compensating benefit.

------------------------------------------------------------------------

## 21. Appendix

### 21.1 Naming Conventions

All names follow **snake_case** exclusively. No camelCase, no
PascalCase, no abbreviations unless universally understood (`id`, `url`,
`ip`).

### 21.2 Table Naming

-   Tables are **plural nouns**: `users`, `digital_assets`, `analyses`,
    `audit_logs`
-   Join tables combine both table names in alphabetical order:
    `report_assets` (not `asset_reports`)
-   No table prefixes (no `tbl_`, no `sentinel_`) --- the database name
    provides the namespace

### 21.3 Column Naming

  ----------------------------------------------------------------------------------
  Pattern                 Convention                         Example
  ----------------------- ---------------------------------- -----------------------
  Primary key             `id`                               `id uuid`

  Foreign key             `{referenced_table_singular}_id`   `user_id`,
                                                             `digital_asset_id`

  Boolean flags           `is_{adjective}`                   `is_active`,
                                                             `is_verified`,
                                                             `is_revoked`

  Timestamps              `{event}_at`                       `created_at`,
                                                             `deleted_at`,
                                                             `completed_at`

  Status enums            `{noun}_status`                    `upload_status`,
                                                             `render_status`

  Counts (cached)         `{noun}_count`                     `asset_count`

  Storage keys            `storage_key`                      `storage_key`
                                                             (consistent across all
                                                             tables)

  JSONB payloads          `{noun}_payload` or `{noun}_data`  `reasoning_payload`,
                                                             `enrichment_data`
  ----------------------------------------------------------------------------------

### 21.4 Timestamp Conventions

-   All timestamps are `TIMESTAMPTZ` (timestamp with time zone) ---
    never `TIMESTAMP` without zone
-   All timestamps are stored in **UTC** --- the application layer
    handles timezone conversion for display
-   Immutable timestamps (`created_at`) default to `now()` and are never
    updated
-   Mutable timestamps (`updated_at`) are updated by an `ON UPDATE`
    trigger on every table that uses them
-   Lifecycle timestamps (`started_at`, `completed_at`, `deleted_at`)
    are nullable and set exactly once

**The `updated_at` trigger (applied to all mutable tables):**

``` sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
-- (Repeated for digital_assets, reports, analyzers)
```

### 21.5 UUID Conventions

-   All UUIDs are generated by PostgreSQL's `gen_random_uuid()` (UUID
    v4) --- not the application
-   UUIDs are stored as the native `uuid` type (16 bytes) --- never as
    `text` (36 bytes)
-   UUIDs are exposed in API responses as lowercase hyphenated strings:
    `"550e8400-e29b-41d4-a716-446655440000"`
-   Application-layer ID prefixes (e.g., `ast_`, `job_`, `rpt_`) are a
    display convention applied at serialization time --- not stored in
    the database

### 21.6 Foreign Key Naming

    fk_{child_table}_{parent_table}_{column}

    Examples:
    fk_digital_assets_users_user_id
    fk_analyses_digital_assets_digital_asset_id
    fk_report_assets_reports_report_id

### 21.7 Index Naming

    {table_abbreviation}_{columns}[_{qualifier}]

    Qualifiers: uk (unique), gin, fts, partial descriptors

    Examples:
    da_user_created          -- digital_assets (user_id, created_at)
    analyses_pending         -- analyses WHERE status = 'pending'
    urt_token_hash_uk        -- user_refresh_tokens (token_hash) UNIQUE
    da_metadata_gin          -- digital_assets (metadata) GIN
    analyses_reasoning_fts   -- analyses full-text search GIN

### 21.8 Migration Naming

    {YYYYMMDD}_{sequence}_{imperative_description}.py

    Rules:
    - Use imperative verb: create_, add_, drop_, alter_, rename_
    - Be specific: not "update_users" but "add_is_verified_to_users"
    - One logical change per migration file

    Examples:
    20250115_0001_create_users_table.py
    20250115_0002_create_uploads_table.py
    20250115_0003_create_digital_assets_table.py
    20250116_0001_add_is_verified_to_users.py
    20250120_0001_add_analyses_reasoning_fts_index.py
    20250125_0001_add_organization_id_to_users.py

------------------------------------------------------------------------

*This document is the canonical database design specification for
Sentinel v1. No schema change may be applied to any environment without
a corresponding Alembic migration file reviewed against the rules in
§16. All design decisions not addressed here should be resolved by
applying the philosophy in §2, cross-referencing the Domain Model and
Architecture documents, and treating the most conservative correct
option as the default.*

------------------------------------------------------------------------

## Design Review Notes (v1.0.1)

This revision incorporates only consistency improvements and does not
change the database design.

### Consistency

-   The Database Design remains consistent with the finalized PRD,
    Domain Model, and Architecture.
-   PostgreSQL remains the authoritative source for structured data
    while object storage remains the authoritative source for binary
    objects.

### Recommendation: Password Hash Algorithm

If the implementation has not yet been finalized, prefer **Argon2id**
over bcrypt for new deployments because it provides memory-hard password
hashing while remaining supported by modern Python libraries. Existing
bcrypt deployments do not require migration solely because of this
recommendation.

### Recommendation: Enumerations

Where practical, centralize repeated enumerated values (status,
severity, role) into PostgreSQL ENUM types or application-level value
objects to reduce divergence between schema and code. This is an
implementation recommendation rather than a schema requirement.

### Recommendation: Naming Consistency

Use a single timestamp naming convention (`created_at`, `updated_at`,
`deleted_at`, `completed_at`) consistently across future tables
introduced after v1.
