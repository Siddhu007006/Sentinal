# Sentinel --- Domain Model

**Status:** Final v1.0.0 · Sprint 0 **Owner:** Siddhu **Last updated:**
2026-07-11 **Depends on:** `01-Product-Requirements.md`

## Purpose

The PRD said *what* and *why*. This document says *what things exist*
--- the entities, their identities, their relationships, and the rules
that must always hold true about them, independent of any database or
API. Get this right and the Architecture, API Design, and Database
Design docs mostly write themselves; get it wrong and every later doc
inherits the mistake.

## Modeling principles

Two questions worth asking of every entity, since getting them right up
front prevents a lot of schema churn later.

**1. What is its identity --- how do you know two records are "the same
thing"?**

Most entities here get identity from an assigned key, generated at
creation: `User`, `Upload`, `Analysis`, `Report`. `Digital Asset` is the
deliberate exception --- its identity *is* its content hash. Two uploads
of byte-identical files aren't two assets that happen to be equal;
they're the same asset, because identity is derived from content rather
than assigned. This is what makes deduplication free: it's not a "have I
seen this before?" search against a separate index, it's just a
primary-key lookup.

**2. At what granularity is it immutable --- the record, or the
collection?**

"Digital assets are immutable, analyses are mutable" (the original
framing from the PRD) is directionally right but easy to over-read. In
this model: - A `Digital Asset` row never changes after creation ---
enforced structurally, not by convention, since its key is derived from
its content. You can't edit it without it becoming a different row with
a different key. - An `Analysis` row also never changes after creation.
What's mutable is the *collection*: the set of Analyses attached to an
asset grows over time as new analyzer runs happen. Re-analyzing appends
a new row; it doesn't update an old one. That preserves history --- what
analyzer v1.0.0 said, even after v2.0.0 exists --- which is what the
PRD's observability goal actually requires. - Same pattern for `Report`:
immutable once generated; new Reports get generated as Analyses
accumulate, old ones aren't rewritten. - `User` is the one entity here
that's genuinely mutable in place --- profile fields update on the same
row.

Rule of thumb: if you catch yourself wanting to `UPDATE` a
`Digital Asset`, `Analysis`, or `Report` row after creation, that's
usually a sign something is modeled wrong --- the fix is almost always a
new row, not an edit.

## Entity relationship diagram

``` mermaid
erDiagram
    USER {
        uuid id PK
        string email UK
        string display_name
        timestamp created_at
    }
    UPLOAD {
        uuid id PK
        uuid user_id FK
        string status
        uuid digital_asset_id FK "nullable until resolved"
        bigint bytes_received
        timestamp started_at
        timestamp completed_at
    }
    DIGITAL_ASSET {
        uuid id PK
        string sha256_hash UK
        string mime_type
        bigint size_bytes
        string storage_object_reference
        timestamp first_seen_at
    }
    ANALYSIS {
        uuid id PK
        uuid digital_asset_id FK
        string analyzer_key
        string analyzer_version
        string status
        jsonb result
        timestamp created_at
    }
    REPORT {
        uuid id PK
        uuid digital_asset_id FK
        timestamp generated_at
    }

    USER ||--o{ UPLOAD : initiates
    DIGITAL_ASSET ||--|{ UPLOAD : "matched by"
    DIGITAL_ASSET ||--o{ ANALYSIS : "analyzed via"
    DIGITAL_ASSET ||--o{ REPORT : "summarized in"
    ANALYSIS }o--o{ REPORT : "included in"
```

Exact column types, indexes, and constraints belong to
`05-Database-Design.md` --- this diagram is the conceptual shape, not
the schema.

## Entities

### User

-   **Identity:** system-generated ID.
-   **Key attributes:** email (unique --- also the auth identifier),
    display name, created_at.
-   **Mutability:** mutable in place. The one entity here where an
    `UPDATE` is the normal, expected operation.
-   **Invariants:** email is unique; a `User` must exist before any
    `Upload` can be initiated (auth is a precondition, not an
    afterthought).

### Upload

**`Upload` is a persisted domain entity**, not a transient process. It represents every upload attempt, including successful, failed, duplicate, and resumable uploads.

Two of the PRD's own engineering goals force this: - **Idempotency**
needs somewhere to check "have I already seen this exact attempt?" ---
which requires a durable record to check against, not an in-memory
request that vanishes on completion. - **Observability** needs failed
and duplicate uploads to be visible. If nothing is recorded until a
`Digital Asset` exists, the exact case someone would want to debug --- a
failed upload --- leaves no trace.

`Upload` and `Digital Asset` answer different questions: `Upload`
answers *"who tried to send what, when, and did it work"* --- one row
per attempt, even for duplicates. `Digital Asset` answers *"what content
exists"* --- one row per distinct hash, regardless of how many attempts
produced it.

``` mermaid
stateDiagram-v2
    [*] --> pending: client initiates upload
    pending --> in_progress: bytes start streaming
    in_progress --> in_progress: chunk received, hash updates
    in_progress --> completed: stream finishes, hash finalized
    in_progress --> failed: stream interrupted or rejected
    completed --> [*]
    failed --> [*]
```

-   **Identity:** system-generated ID.
-   **Key attributes:** user_id, status, bytes_received (supports
    resumability), digital_asset_id (null until resolved), started_at,
    completed_at.
-   **Mutability:** mutable while `in_progress`; frozen once it reaches
    a terminal state (`completed` or `failed`) --- at that point it
    behaves like an audit log entry.
-   **Invariants:** `digital_asset_id` is null until status is
    `completed`; always belongs to exactly one `User`.

### Digital Asset

-   **Identity:** Domain identity is the SHA-256 content hash. A UUID may be used as a persistence surrogate key for foreign-key convenience, but it is not the business identity of the asset.
-   **Key attributes:** sha256_hash (unique), mime_type, size_bytes,
    storage_object_reference (pointer into object storage),
    first_seen_at.
-   **Mutability:** immutable, full stop.
-   **Invariants:**
    -   Hash is unique.
    -   Hash is **always computed server-side from the actual received
        bytes** --- never trusted from the client. A client-asserted
        hash would make both deduplication and integrity checking
        meaningless: anyone could claim any hash for any content. This
        is the one invariant in this document that's non-negotiable
        regardless of how the rest of the system evolves.

### Analysis

-   **Identity:** system-generated ID.
-   **Key attributes:** digital_asset_id, analyzer_key,
    analyzer_version, status (`pending` / `running` / `completed` /
    `failed` --- analysis is queued and asynchronous per the PRD),
    result (analyzer-specific structured data), created_at.
-   **Mutability:** mutable only while transitioning through the execution lifecycle (`pending` → `running`). Once it reaches a terminal state (`completed` or `failed`), the record becomes immutable. Re-analysis always creates a new Analysis record.
-   **Invariants:**
    -   Always references exactly one `Digital Asset`.
    -   The triple (digital_asset_id, analyzer_key, analyzer_version) is
        effectively idempotent: requesting analysis again with an
        *identical* analyzer version returns the existing `Analysis`
        rather than creating a duplicate row. A new row only gets
        created when the analyzer version differs --- which is what
        "re-analyze with a newer version" (PRD use case 4) actually
        means in practice.

### Report

-   **Identity:** system-generated ID.
-   **Key attributes:** digital_asset_id, generated_at, the set of
    Analyses it draws from, rendered content.
-   **Mutability:** immutable once generated --- a snapshot, not a live
    view. New Analyses prompt a *new* Report; they don't retroactively
    change an old one.
-   **Invariants:**
    -   References at least one `Analysis`.
    -   Every `Analysis` it references must belong to the *same*
        `Digital Asset` as the Report itself --- mixing Analyses from
        different assets into one Report would conflate two unrelated
        pieces of content.
    -   Phase 1: generated on request, not automatically after every
        Analysis completes. Automatic generation is a reasonable Phase 2
        addition once more than one analyzer feeds into it.

## A note on `Analyzer`

Phase 1 scope in the PRD talks about "the Analyzer interface" as core
platform work, which raises a fair question: is `Analyzer` a sixth
domain entity?

Not in v1. An analyzer is *code* --- a registered function that inspects
a `Digital Asset` and produces a result --- not a row in a database. All
the domain model needs from it is enough metadata to make an `Analysis`
traceable: which analyzer, which version. That's two fields on
`Analysis` (`analyzer_key`, `analyzer_version`), not a separate table.

This is a placeholder, not a permanent call. If Phase 2 introduces a
real analyzer registry --- third-party analyzers, independent
versioning, enable/disable toggles --- `Analyzer` graduates into a
first-class entity at that point. Modeling one now, for a single
hardcoded analyzer, would be solving a problem that doesn't exist yet.

## Invariants --- consolidated

For quick reference, and later, for writing tests against:

1.  A `Digital Asset`'s hash is unique and always server-computed from
    actual bytes, never client-supplied.
2.  A `Digital Asset` row, once created, never changes.
3.  An `Upload`'s `digital_asset_id` is null until its status is
    `completed`.
4.  An `Upload` always belongs to exactly one `User`.
5.  An `Analysis` always references exactly one `Digital Asset`.
6.  Re-running the same analyzer version against the same asset returns
    the existing `Analysis`, not a duplicate.
7.  A `Report` only references Analyses belonging to the same
    `Digital Asset` it summarizes.
8.  `Digital Asset`, `Analysis`, and `Report` rows are never updated
    after creation --- new information means a new row.

## Explicitly excluded from this model

-   **`Database`, `Backend`** --- implementation details of *how* these
    entities are persisted and served, not business entities.
-   **`Organization`** --- deferred per the PRD's Non-Goals. `User` has
    no organization relationship in v1.
-   **`Analyzer`** --- not yet a first-class entity; see above.

## Related documents

-   `01-Product-Requirements.md` --- what and why *(this doc depends on
    it)*
-   `03-Architecture.md` --- system architecture, tech stack rationale
    *(next)*
-   `04-API-Design.md`
-   `05-Database-Design.md` --- where these conceptual entities become
    actual tables
-   `06-Repository-Structure.md`
-   `adr/` --- Architecture Decision Records
