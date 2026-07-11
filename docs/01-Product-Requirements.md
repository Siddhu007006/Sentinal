# Sentinel — Product Requirements Document

**Status:** Draft v0.1 · Sprint 0
**Owner:** Siddhu
**Last updated:** 2026-07-11

## Why this document exists

A PRD is the contract between "what we're building" and "why," written before any code exists, so every later document — Domain Model, Architecture, API Design — has one source of truth to point back to. If a design decision in a later doc can't be traced to something here, that's usually a sign this PRD is incomplete, not that the decision is wrong. Treat this as a living reference, not a stone tablet — it'll get revised as scope firms up.

## 1. Vision

Sentinel is a platform for uploading any digital asset and running it through a pipeline of pluggable analyzers — security, media, and document intelligence — producing a durable, auditable report for each asset.

Most tools force a choice of lane: a malware sandbox, a media metadata extractor, a document parser. Sentinel treats "upload → analyze → report" as one reusable pipeline and makes the analyzer the variable, not the pipeline.

## 2. Problem Statement

Digital asset analysis tooling tends to be siloed by domain. Security teams run files through sandboxes; media teams run assets through separate metadata pipelines; document-heavy workflows use yet another set of tools — and each silo re-solves the same underlying problems: ingesting a file safely, deduplicating it, storing it durably, tracking what's been done to it, and reporting results.

Sentinel's bet is that the substrate underneath all of that — upload, dedup, storage, orchestration, reporting — is the same regardless of what the analyzer does with the bytes, and is worth building once, well, instead of once per domain.

(For this build specifically, the problem being solved is as much about the builder's understanding of how a production-grade ingestion and analysis platform is actually architected as it is about the product itself — both are legitimate goals of this PRD.)

## 3. Goals

**Product**
- Accept an uploaded file of arbitrary type and size through a streamed upload path.
- Deduplicate identical content via hashing and preserve integrity guarantees for every stored asset.
- Run one or more analyzers against an asset and persist results as a versioned Analysis, independent of the underlying asset.
- Produce a human-readable Report from one or more Analyses.
- Support adding new analyzer types without changing the core platform.

**Engineering**
- Model a clean domain (entities, not database tables) with an explicit boundary between platform and analyzer.
- Cover production concerns tutorials tend to skip: auth, background processing, idempotency, content-addressable storage, observability.
- Produce documentation — this PRD plus Domain Model, Architecture, API Design, DB Design, ADRs — thorough enough to onboard a new engineer with no verbal handoff.

## 4. Non-Goals (v1)

- **Not** a competitor to production security vendors on detection accuracy or threat intelligence breadth.
- **Not** multi-tenant. There's no `Organization` entity in v1 — every `User` operates in their own space. Multi-tenancy is a reasonable next step once the core pipeline is proven out, but designing auth and the domain model around it now, with no immediate use case, adds cost without adding proof.
- **Not** real-time — analysis is asynchronous, queued, and eventually consistent.
- **Not** best-in-class analyzers across every domain on day one — see Scope.

## 5. Target Users

Worth naming even without a real user base, since it shapes what "done" means:

- **A security-minded developer** who wants to know whether a file is safe to open, without standing up a sandbox themselves.
- **Someone triaging a batch of files** — an old drive, a scraped dataset, an inbox export — who wants structure imposed on unstructured content: types, hashes, duplicates, extracted metadata.
- **The engineer building Sentinel** — arguably the primary consumer of the documentation, if not the product.

## 6. Core Use Cases

1. A user uploads a file. Sentinel streams it to storage, hashes it, and either creates a new Digital Asset or recognizes a duplicate of an existing one.
2. A user requests analysis of a Digital Asset. Sentinel queues the work, runs the appropriate analyzer(s), and stores the result as an Analysis linked to that asset.
3. A user views a Report summarizing one or more Analyses for an asset, without needing to know what ran underneath.
4. A user re-analyzes an existing asset with a newer analyzer version without re-uploading — because the asset (immutable) and the analysis (mutable, versioned) are separate concerns.

## 7. Scope

### Phase 1 (this build)
- Platform substrate: auth, streamed upload, hashing/dedup, object storage integration, Postgres metadata, background queue.
- The `Analyzer` interface itself — the plumbing that lets an analyzer be registered and invoked — built to be genuinely pluggable, not hardcoded for one domain.
- **One** concrete analyzer, implemented end-to-end, as proof the framework works: a hash / file-type / static-property analyzer. Deliberately the cheapest analyzer to build correctly, and it exercises the full pipeline without requiring heavy domain-specific logic (codecs, NLP models) before the platform itself is proven.
- One Report format rendering that analyzer's output.

### Phase 2+ (explicitly deferred)
- Additional analyzers: media (image/video/audio metadata and content signals), document/text (parsing, extraction, NLP-driven insight), deeper security signals (behavioral/sandbox-style analysis).
- Multi-tenancy (`Organization` entity).
- Analyzer marketplace / third-party analyzer registration.

This phasing exists because "all analyzer domains" is the right *architectural* target — the framework genuinely shouldn't care what an analyzer does — but building convincing analyzers in three different domains at once would either take forever or produce three shallow implementations instead of one solid platform plus one solid analyzer. Depth on the platform first; breadth deferred on purpose.

## 8. Domain Model (summary)

Full detail lives in `02-Domain-Model.md`; summary for this document's purposes:

| Entity | Mutability | Description |
|---|---|---|
| `User` | mutable | An account that owns uploads and requests analyses. |
| `Upload` | transient / process | The act of receiving bytes — an event/process that produces or matches a Digital Asset, not necessarily a durable business entity in its own right. |
| `Digital Asset` | **immutable** | The content itself, identified by its hash. Never changes once stored. |
| `Analysis` | mutable, versioned | The result of running one analyzer against one Digital Asset. Many Analyses can point at one Asset. |
| `Report` | mutable | A human-facing summary composed from one or more Analyses. |

`Database` and `Backend` are deliberately excluded — they're implementation details of *how* these entities are persisted and served, not business entities.

## 9. Success Metrics

No real user base, so "success" means:
- A file can be uploaded, deduplicated, analyzed, and reported on end-to-end with no manual steps.
- Adding a second analyzer later touches the analyzer package only — not the upload path, auth, or storage layer.
- Every decision in later docs (Architecture, DB Design) traces back to a goal or use case in this PRD.

## 10. Open Questions

1. Should `Upload` be its own persisted entity (to track failed/partial uploads), or stay a transient process with nothing recorded until a Digital Asset exists? Leaning toward "track it, but it's not a core domain entity" — to be settled in the Domain Model doc.
2. Is deferring `Organization` (Non-Goals, above) acceptable, or should `User` be designed with a future `Organization` relationship in mind even if unbuilt?
3. Confirm the Phase 1 analyzer choice (hash / file-type / static-property) — open to a different first analyzer if there's a stronger reason to pick one.

## 11. Related Documents

- `02-Domain-Model.md` — entities, relationships, invariants *(next)*
- `03-Architecture.md` — system architecture, tech stack rationale
- `04-API-Design.md`
- `05-Database-Design.md`
- `06-Repository-Structure.md`
- `adr/` — Architecture Decision Records
