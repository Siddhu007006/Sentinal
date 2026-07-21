Document Information Document: docs/00-Project-Context.md Version: 1.0.0
Status: Final Owner: Founding Engineering Team Audience: All engineers,
architects, and technical contributors joining the Sentinel project ---
present and future Dependencies: This document precedes and
contextualizes all other documents in the repository. It introduces no
technical contracts of its own and defers to:

01-Product-Requirements.md 02-Domain-Model.md 03-Architecture.md
04-Database-Design.md 05-API-Specification.md backend/openapi.yaml
Revision History

Version Date Author Summary 1.0.0 Initial Founding Engineering Team
First canonical version of this document. 1. Executive Summary Sentinel
is a platform for deciding whether a digital asset can be trusted before
a human or system acts on it.

Every day, organizations receive content from outside their perimeter of
trust: PDFs, Word documents, images, emails, links, QR codes, compressed
archives. Historically, the tool used to evaluate this content has been
antivirus software, and the question it answers is narrow: is this a
known piece of malware?

That question is no longer sufficient. Modern threats --- phishing
documents, forged invoices, AI-generated fake content,
social-engineering links --- frequently contain no malware signature at
all. They rely on deception, not payloads. Signature-based detection has
nothing to say about them.

Sentinel exists to answer a broader and more useful question: can this
be trusted, and why? For any digital asset, Sentinel produces a verdict,
the evidence behind that verdict, a confidence level, and a recommended
action --- never a bare "safe" or "unsafe" label.

Sentinel is built for the teams and individuals who receive untrusted
content as part of their normal workflow --- security teams, operations
teams, and eventually any user who needs a second opinion before
opening, forwarding, or acting on a file or link.

Architecturally, Sentinel is not "a PDF scanner." It is a
general-purpose intake and reasoning pipeline --- upload, store, queue,
analyze, report --- where the specific intelligence applied to an asset
is a pluggable analyzer, not a hardcoded part of the pipeline. This
design decision, reached during the project's earliest design
discussions, is the single most important fact about Sentinel's
architecture and is the reason this document exists: so no future
contributor re-derives it from scratch or accidentally undoes it.

2.  Project Genesis 2.1 The original idea The project began with a
    narrow, concrete question:

"Can we build an AI system that analyzes files, emails, links, and other
digital assets before users trust them?"

The very first working assumption was narrower still: build a system
that analyzes PDF files for security risk --- malicious embedded
scripts, suspicious links, disguised executables, phishing indicators.
PDFs were chosen as the starting point because they are a common attack
vector, structurally complex enough to hide malicious content, and
ubiquitous in business workflows (invoices, contracts, reports).

2.2 The first assumptions At the outset, the working assumptions were:

The core problem was PDF-specific. The system would need one analysis
engine, tuned for PDF structure. The output would be something like a
virus scanner's output: a verdict per file. The primary technical
challenge was building a good PDF analyzer. 2.3 Where those assumptions
broke down As the design was worked through in detail, a pattern
emerged: almost none of the actual engineering work was PDF-specific.

Accepting a file (validation, size limits, virus-scanning at the
perimeter) is identical regardless of file type. Storing a file (object
storage, checksums, metadata) is identical regardless of file type.
Queueing work so that processing does not block the request path is
identical regardless of file type. Running a worker, capturing its
result, and persisting it is identical regardless of file type.
Presenting a report to a user is identical regardless of file type. The
only place where "PDF-ness" actually mattered was in one narrow
component: the piece of logic that inspects the content and produces a
judgment. Everything upstream (intake) and downstream (storage,
reporting) was generic.

This observation --- that the pipeline is asset-agnostic and only the
analyzer is asset-specific --- is the pivotal realization in Sentinel's
history. It reframed the project from a single-purpose scanner into a
platform.

2.4 The journey to a platform Once analyzers were understood to be a
plug-in concept rather than the core of the system, the natural next
question was: what else could plug into this pipeline?

The answer expanded the product's scope without changing its
architecture:

A Security Analyzer for malicious content (the original PDF use case,
generalized). An OCR Analyzer for extracting and inspecting text from
images and scanned documents. A Metadata Analyzer for inspecting file
properties, authorship, and structural anomalies. An AI Document
Analyzer for reasoning over document content and context using AI
providers. An Image Analyzer for detecting manipulated or fake imagery.
Future custom analyzers, built by the team or eventually by advanced
users, for needs not yet identified. None of this required inventing new
pipeline stages. It only required designing the pipeline, and the
Analyzer concept, generically enough to support them from day one. This
is why 02-Domain-Model.md defines Analyzer and Analysis as first-class,
extensible entities rather than baking a single analysis type into the
domain.

The project's name and framing changed to reflect this: from "PDF
Security Analyzer" to AI-native Digital Asset Intelligence Platform. The
scope of what can be analyzed grew. The how --- the pipeline --- did not
change and is not expected to change.

3.  Problem Statement Organizations and individuals routinely receive
    digital assets from sources they do not fully control:

PDFs and Word documents from vendors, applicants, or customers. Images
sent as attachments or shared via messaging. Emails from unfamiliar
senders. URLs embedded in messages or documents. QR codes printed on
physical materials or embedded in digital ones. ZIP archives bundling
any of the above. Traditional antivirus and endpoint security tools
answer one question about this content:

"Is this malware?"

That is a necessary question, but it is not the question most people
actually need answered. A phishing PDF with no embedded executable will
pass every antivirus check while still being an active threat. A forged
invoice with altered banking details contains no malicious code at all.
A QR code pointing to a credential-harvesting page is, to a signature
scanner, indistinguishable from a QR code pointing to a restaurant menu.

Sentinel is built to answer the questions that actually determine
whether a human should act on a piece of content:

Can I trust this? --- an overall trust assessment, not a binary malware
flag. Is this phishing? --- evaluating intent and deception, not just
payloads. Is this fake? --- evaluating authenticity of documents,
images, and claims. Is this suspicious? --- surfacing ambiguous cases
instead of forcing a false binary. What evidence supports that
conclusion? --- because an unexplained verdict cannot be acted on
responsibly. What should I do? --- because a verdict without a
recommendation leaves the user exactly as stuck as before. These are
fundamentally different problems from malware detection because they
require reasoning about context, intent, and plausibility, not just
pattern-matching against known-bad signatures. This is why Sentinel is
built around AI-assisted reasoning and structured evidence, rather than
signature databases, and why explainability is treated as a first-class
product requirement rather than a nice-to-have (see
01-Product-Requirements.md).

4.  Product Philosophy These principles are permanent. They are not
    implementation details subject to routine revision --- they are the
    reason the system is shaped the way it is, and any change to them
    should be treated as a fundamental redesign, not a feature update.

Platform-first. The system is never optimized for a single file type.
Every capability is built as a generic pipeline stage plus a pluggable
analyzer. This exists because the project's own history (Section 2)
proved that asset-specific optimization produces a dead end --- a tool
that only handles the case it was built for.

Analyzer independence. Analyzers are isolated units of intelligence with
a consistent contract to the pipeline. This exists so that adding a new
kind of analysis (a new AI model, a new heuristic, a new provider) never
requires touching the upload, storage, queueing, or reporting logic.

Immutable digital assets. A DigitalAsset never changes after creation.
If content changes, it is a new asset. This exists because mutable
content identity would make analysis history meaningless --- an analysis
is only valid for the exact bytes it examined.

Hash-based identity. A DigitalAsset's identity is its SHA-256 hash, not
its filename. This exists because filenames are unreliable,
attacker-controlled, and not unique --- two different files can share a
name, and the same file can arrive under many names. Content hashing
gives the platform a way to recognize "we have already seen this exact
content" instantly and unambiguously, which is also the mechanism used
for duplicate detection.

Append-only analyses. Analyses are never overwritten. If a better AI
model or analyzer version becomes available, it produces a new,
versioned Analysis rather than replacing the old one. This exists so
that historical judgments remain auditable --- an organization can
always see what was known, and by which analyzer version, at any point
in time.

Explainability over simple verdicts. Sentinel never returns a bare
"safe" or "unsafe" label. Every result carries evidence, a confidence
level, reasoning, and a recommendation. This exists because a trust
decision without justification cannot be defended, audited, or acted on
responsibly --- and because the product's entire value proposition
(Section 3) is reasoning, not classification.

API-first development. Nothing is exposed to the frontend, or to any
consumer, that does not first exist as a documented API. This exists to
keep the backend the single source of truth for behavior and to make the
system safely consumable by multiple clients (web frontend, future
integrations, SDKs) without divergence.

Asynchronous processing. Nothing that involves analysis is done
synchronously within a request/response cycle. This exists because
analysis work (especially AI-assisted reasoning) is inherently variable
in duration, and forcing it into a synchronous HTTP request would make
the system fragile and unresponsive under load.

Security by design. Authentication, authorization, and audit logging are
treated as core requirements from the first line of the domain model,
not layered on afterward. This exists because Sentinel itself is a
security-adjacent product --- a platform with weak security controls
would undermine its own value proposition.

Long-term maintainability. Architectural simplicity is preferred over
premature optimization for scale. This exists because the team's
priority, documented from the earliest decisions, is to ship a coherent,
debuggable system first, and to evolve toward higher scale only when
actual usage demands it (see Section 6, Modular Monolith).

4.5 What Sentinel Is Not

To preserve the project's scope and architectural integrity, Sentinel is
intentionally **not**:

-   A replacement for traditional antivirus or endpoint protection
    software.
-   A Security Information and Event Management (SIEM) platform.
-   An Endpoint Detection and Response (EDR) platform.
-   A cloud file storage or document management system.
-   A document editor or collaboration platform.

Sentinel complements existing security tooling by providing AI-assisted
trust analysis and explainable reasoning for digital assets rather than
replacing existing security controls.

5.  Evolution of the Architecture The pipeline below is the direct
    engineering consequence of the philosophy in Section 4. Each stage
    exists to solve one specific problem; none exist for their own sake.

text

Upload ↓ Validation ↓ Hash ↓ Duplicate Detection ↓ Object Storage ↓
Queue ↓ Workers ↓ Analysis ↓ Report ↓ Database ↓ API ↓ Frontend Upload
--- the single entry point for any digital asset, regardless of type.
This exists so that intake logic (auth, rate limiting, request handling)
is written once.

Validation --- rejects malformed, oversized, or disallowed content
before any expensive work happens. This exists to protect downstream
stages (storage, queue, workers) from wasted or abusive work.

Hash --- computes the SHA-256 of the content immediately after
validation. This exists because everything downstream --- duplicate
detection, asset identity, analysis association --- depends on having a
stable content identifier as early as possible.

Duplicate Detection --- compares the computed hash against existing
DigitalAsset records instead of comparing file contents or filenames.
This exists because hash comparison is a cheap indexed lookup, whereas
content comparison would be expensive and filename comparison would be
meaningless (Section 4).

Object Storage --- persists the raw bytes in S3-compatible storage
rather than the relational database. This exists because relational
databases are not designed to efficiently store or serve large binary
blobs, and separating binary storage from metadata storage keeps the
database small, fast, and easy to back up.

Queue --- hands off analysis work to be processed outside the
request/response cycle. This exists because analysis duration is
unpredictable and must not block the user-facing API (Section 4,
Asynchronous processing).

Workers --- consume queued jobs and execute analyzers. This exists so
that compute-heavy or AI-provider-dependent work is isolated from the
API process, can be scaled independently in the future, and never
communicates directly with the browser --- workers only write results;
the API is the only thing that ever talks to the browser.

Analysis --- the structured, versioned result of one analyzer run
against one asset. This exists as the atomic unit of "what did we
conclude, and based on what."

Report --- a human-facing presentation of one specific analysis. This
exists as a separate concept from Analysis because the two have
different audiences and different lifecycles: Analysis is a
system-of-record artifact meant to be immutable and precise; Report is a
presentation artifact meant to be readable and potentially rendered in
multiple formats (JSON, PDF, HTML) --- see Section 6 for the explicit
reasoning.

Database --- stores all structured metadata: users, uploads, assets,
analyzers, analyses, reports, audit logs. This exists as the system of
record for everything except raw binary content.

API --- the sole contract through which any client interacts with the
system. This exists to enforce API-first development (Section 4) and to
guarantee that the frontend, and any future client, only ever sees
officially supported behavior.

Frontend --- the first consumer of the API, not a privileged one. This
exists to keep the frontend replaceable and to prove, by construction,
that the API is complete enough to build a full product on top of it.

6.  Major Engineering Decisions Why Modular Monolith (not microservices)
    Problem: How should the system be decomposed to support multiple
    analyzers, asynchronous processing, and future growth, without
    over-engineering the initial build?

Alternatives considered: Microservices from day one, with separate
deployable services for upload handling, analysis orchestration, and
reporting.

Chosen solution: A single deployable modular monolith with clearly
separated internal modules (Presentation, Application, Domain,
Infrastructure --- see 03-Architecture.md).

Reason: Microservices solve organizational and scaling problems that
Sentinel does not yet have. At this stage, a microservices architecture
would add network overhead, deployment complexity, and debugging
difficulty without a corresponding benefit. A modular monolith gives the
same internal separation of concerns (so modules can be extracted later)
while keeping development, testing, and deployment fast and simple.

Trade-offs: The whole application currently scales as one unit, and a
bug in one module can, in principle, affect the process hosting all
modules. This is accepted because module boundaries are enforced at the
code level, keeping extraction possible later without a full rewrite.

6.2 Why FastAPI Problem: Need a backend framework that supports async I/O
(critical for a system built around queues and workers), strong typing,
and automatic OpenAPI generation.

Alternatives considered: Django (batteries-included but heavier and less
async-native), Flask (mature but requires assembling async support and
validation manually).

Chosen solution: FastAPI.

Reason: Native async support matches the asynchronous processing
philosophy (Section 4). Built-in request/response validation via Python type annotations
enforces the API-first contract. Automatic OpenAPI schema generation
aligns directly with the decision to treat openapi.yaml as a canonical,
machine-readable contract.

Trade-offs: Smaller ecosystem than Django for things like admin panels;
these are not currently required by Sentinel's use cases.

6.3 Why PostgreSQL Problem: Need a reliable system of record for structured
metadata with strong relational integrity (users, uploads, assets,
analyzers, analyses, reports, audit logs).

Alternatives considered: NoSQL document stores.

Chosen solution: PostgreSQL.

Reason: Sentinel's domain is inherently relational --- assets relate to
uploads, analyses relate to assets and analyzers, reports relate to
analyses. Foreign keys, constraints, and transactional guarantees
(documented in 04-Database-Design.md) are a natural fit and prevent data
integrity problems that would otherwise have to be enforced manually in
application code.

Trade-offs: Schema changes require migrations; this is accepted as the
cost of strong data integrity guarantees.

6.4 Why Object Storage (not storing files in PostgreSQL) Problem: Where
should raw binary file content live?

Alternatives considered: Storing file bytes directly in PostgreSQL as
BLOBs.

Chosen solution: S3-compatible object storage, with PostgreSQL storing
only metadata and a storage reference.

Reason: Databases are optimized for structured, transactional data, not
large binary blobs. Storing files in PostgreSQL would bloat the
database, slow down backups, and complicate replication. Object storage
is purpose-built for this, is horizontally scalable, and decouples
binary storage growth from database growth.

Trade-offs: Introduces a second storage system to operate and back up;
accepted because the alternative (files in Postgres) does not scale and
actively works against the database's strengths.

6.5 Why REST Problem: Need a client-facing API style that is well
understood, cacheable, and easy to document.

Alternatives considered: GraphQL.

Chosen solution: REST, with one resource per responsibility (POST
/uploads, GET /reports, etc., as documented in 05-API-Specification.md).

Reason: Sentinel's resources (uploads, assets, analyses, reports) map
cleanly onto REST resources and standard HTTP semantics. REST's
simplicity and universal tooling support (OpenAPI, Swagger UI, standard
HTTP caching/rate-limiting infrastructure) outweigh the flexibility
GraphQL would offer, especially given the platform does not have
complex, client-driven query-shape requirements.

Trade-offs: Clients that need many related resources in one call must
make multiple requests or rely on endpoint-specific composition;
accepted as a reasonable cost for REST's simplicity and tooling
maturity.

6.6 Why JWT Problem: Need stateless, verifiable authentication that works
across a REST API without server-side session storage.

Alternatives considered: Server-side session cookies.

Chosen solution: JWT access/refresh token pairs (bearerAuth /
refreshTokenAuth, as defined in backend/openapi.yaml).

Reason: JWTs are stateless and verifiable without a database round-trip
on every request, which fits a modular monolith intended to scale
horizontally later. Short-lived access tokens plus longer-lived refresh
tokens balance security (limited exposure window) with usability
(infrequent re-authentication).

Trade-offs: Token revocation is less immediate than with server-side
sessions; mitigated by short access-token lifetimes and an explicit
logout/refresh-revocation endpoint.

6.7 Why Background Workers Problem: Analysis work (especially AI-provider
calls) has unpredictable and often long duration.

Alternatives considered: Performing analysis synchronously within the
HTTP request.

Chosen solution: Dedicated background workers that consume queued jobs
and never communicate directly with the browser.

Reason: Synchronous analysis would tie up API resources for
unpredictable durations and produce a poor user experience (long-hanging
requests, timeouts). Workers decouple compute time from request/response
latency and can be scaled independently of the API layer.

Trade-offs: Requires clients to poll or otherwise retrieve results
rather than getting them immediately; accepted because it is the only
approach compatible with variable-length, AI-assisted analysis.

6.8 Why a Queue Problem: How should work be handed off from the API to
workers reliably?

Alternatives considered: Direct, synchronous function calls or ad hoc
background threads within the API process.

Chosen solution: A message queue between the API and workers.

Reason: A queue provides durability (jobs are not lost if a worker
crashes mid-processing), backpressure handling (workers pull work at
their own pace), and a clean boundary between the request-handling
process and the compute-handling process --- reinforcing the modular
monolith's internal separation of concerns even though it is one
deployable unit.

Trade-offs: Introduces eventual consistency between "analysis requested"
and "analysis complete," which is why analysis status polling (queued →
running → completed/failed) is a first-class part of the API contract.

6.9 Why SHA-256 Problem: Need a way to uniquely and reliably identify
content, independent of filename or metadata.

Alternatives considered: Weaker or faster hash functions (e.g., MD5,
SHA-1).

Chosen solution: SHA-256.

Reason: SHA-256 provides a strong collision resistance guarantee
appropriate for a security-focused product, and is a widely supported,
well-understood standard. Since hash comparison is the mechanism for
both asset identity and duplicate detection, correctness here directly
protects data integrity across the entire domain model.

Trade-offs: Marginally more compute-expensive than weaker hashes;
irrelevant given upload frequency and the strong integrity guarantees
required.

6.10 Why Immutable Assets See Section 4. Restated briefly: allowing a
DigitalAsset to change in place would invalidate the meaning of every
analysis ever run against it. Immutability is what makes the hash-based
identity model (and therefore duplicate detection) trustworthy.

6.11 Why Versioned Analyses See Section 4. Restated briefly: overwriting
analyses would destroy the audit trail of what the platform knew and
concluded at a given point in time --- a property Sentinel's own
trust-and-evidence mission requires it to uphold for itself.

6.12 Why Reports Are Separate From Analyses Problem: Should the system
present analysis results directly, or generate a distinct artifact for
presentation?

Alternatives considered: Exposing Analysis records directly to end users
as the final output.

Chosen solution: Report as a distinct entity that presents one specific
Analysis version.

Reason: Analysis is a precise, versioned, system-of-record artifact ---
it should remain stable and unambiguous for audit purposes. Report
serves a different purpose: human consumption, potentially in multiple
formats (JSON, PDF, HTML per 05-API-Specification.md), and potentially
with future presentation logic (formatting, localization, branding) that
has no place polluting the analysis record itself. Separating the two
keeps each entity's responsibility singular.

Trade-offs: Slight duplication of some fields (verdict, evidence,
confidence) between Analysis and Report; accepted because it preserves a
clean separation between system-of-record and presentation.

6.13 Why AI Providers Are Abstracted Problem: AI-assisted analyzers depend on
external AI providers whose APIs, models, and pricing change over time.

Alternatives considered: Calling a specific AI provider's API directly
from within analyzer logic.

Chosen solution: AI providers are accessed through an abstraction within
the Infrastructure layer (per 03-Architecture.md), never called directly
from Domain or Application logic.

Reason: Coupling analyzer logic to one provider's SDK would make it
difficult to swap providers, run multiple providers side by side, or
handle provider outages gracefully. Abstracting this dependency keeps
the Domain layer's business logic (what an analyzer decides) independent
of the Infrastructure detail (which provider computed the underlying
signal).

Trade-offs: Adds an abstraction layer that must be maintained; accepted
because provider churn is a near-certainty over the platform's lifetime.

7.  Terminology These definitions are authoritative and must remain
    consistent with 02-Domain-Model.md.

User --- An authenticated actor who interacts with Sentinel through the
API, holding a role (admin, analyst, or viewer) that determines their
permissions.

Upload --- A record of a single raw content submission through the
intake pipeline. An Upload tracks pipeline progress (validation,
hashing, storage) and resolves to a DigitalAsset, either newly created
or pre-existing (if the content was already seen).

Digital Asset --- An immutable, content-addressed representation of a
piece of content, identified by its SHA-256 hash rather than filename.
The unit against which all analysis is performed.

Analyzer --- A pluggable unit of intelligence (e.g., Security Analyzer,
OCR Analyzer, AI Document Analyzer) that can be run against a Digital
Asset to produce an Analysis. Analyzers are the only part of the system
that varies by asset type or intelligence need.

Analysis --- A single, immutable, versioned execution record of one
Analyzer against one Digital Asset, including verdict, evidence,
confidence, reasoning, and recommendation. Analyses are append-only;
re-running an analyzer produces a new version rather than overwriting
the previous one.

Report --- A human-facing presentation artifact for one specific
Analysis version, potentially rendered in multiple formats. Separate
from Analysis to keep system-of-record data and presentation concerns
independent.

Audit Log --- An immutable record of significant actions taken by users
or the system, used for accountability and traceability.

Worker --- A background process that consumes jobs from the Queue and
executes Analyzers. Workers never communicate directly with clients;
they only persist results, which are then exposed through the API.

Queue --- The durable hand-off mechanism between the API (which enqueues
analysis jobs) and Workers (which consume and execute them), enabling
asynchronous processing.

Object Storage --- The S3-compatible system responsible for storing raw
binary file content, kept separate from PostgreSQL, which stores only
structured metadata.

Application Service --- A component in the Application layer that
orchestrates a specific use case (e.g., "create an upload," "trigger an
analysis") by coordinating Domain entities and Infrastructure without
containing business rules itself.

Repository --- A component in the Infrastructure layer responsible for
persisting and retrieving Domain entities, abstracting the underlying
database from the rest of the system.

Domain Entity --- A core business object (User, Upload, DigitalAsset,
Analyzer, Analysis, Report, AuditLog) whose structure and invariants are
defined in 02-Domain-Model.md and enforced regardless of how it is
stored or exposed.

8.  End-to-End Lifecycle This section walks through the complete life of
    a single request, tying together every concept introduced above.

text

User ↓ Upload ↓ Validation ↓ Hash ↓ Duplicate Detection ↓ Storage ↓
Metadata ↓ Queue ↓ Worker ↓ Analyzer ↓ Analysis ↓ Report ↓ Database ↓
REST API ↓ Frontend User submits content via POST /uploads,
authenticated with a JWT access token. Upload record is created
immediately, in an initial pipeline status, and returned to the user so
the request does not block on processing. Validation checks file size,
MIME type, and basic structural sanity before any expensive work is
performed. Hash computes the SHA-256 of the content, establishing its
candidate identity. Duplicate Detection checks whether a DigitalAsset
with this hash already exists. If so, the Upload resolves to the
existing asset (isDuplicate: true) and no new asset is created. Storage
persists the raw bytes to object storage if the content is new. Metadata
extraction records structural and descriptive information about the
asset (e.g., page count, MIME type details) alongside the DigitalAsset
record in PostgreSQL. Queue receives one job per analyzer once a user
(or automated policy) requests analysis via POST /analyses. Worker picks
up each queued job independently, executing without any direct
connection to the requesting browser. Analyzer logic runs inside the
worker, producing a verdict, confidence score, structured evidence,
reasoning, and a recommendation. Analysis is written as a new,
versioned, immutable record --- never overwriting a prior version for
the same asset/analyzer pair. Report is generated to present the
completed Analysis in a human-readable form, optionally in multiple
formats. Database persists all of the above as structured, queryable
metadata; binary content remains solely in object storage. REST API
exposes every stage of this lifecycle --- Upload status, Analysis
status, and completed Reports --- as documented endpoints, allowing
clients to poll or fetch results at any point. Frontend (or any other
API client) consumes this API exactly as any external integrator would,
with no special access --- reinforcing the API-first principle. 9.
Relationship Between Documents The repository is deliberately ordered to
move from why to what to how, so that no document assumes context that
hasn't already been established.

text

00 Project Context ↓ 01 Product Requirements ↓ 02 Domain Model ↓ 03
Architecture ↓ 04 Database Design ↓ 05 API Specification ↓ OpenAPI
Contract ↓ Implementation 00 Project Context (this document) explains
why Sentinel exists --- its history, philosophy, and the reasoning
behind irreversible decisions. It contains no requirements, schemas, or
contracts of its own. 01 Product Requirements defines what problem is
being solved for whom --- vision, personas, goals, non-goals, and MVP
scope, building directly on the problem statement and philosophy
established here. 02 Domain Model defines what exists inside Sentinel
--- the core entities (User, Upload, DigitalAsset, Analyzer, Analysis,
Report, AuditLog) and the business rules that govern them, honoring the
immutability and versioning principles established here. 03 Architecture
defines how the platform is structured --- layers, components, and the
Modular Monolith decision, justified in detail in Section 6 of this
document. 04 Database Design defines how data is physically stored ---
tables, constraints, indexes --- consistent with the entities defined in
the Domain Model. 05 API Specification defines the contract between
backend and clients --- resources, endpoints, validation, and error
handling, consistent with the Domain Model and Architecture. OpenAPI
Contract (backend/openapi.yaml) is the machine-readable expression of
the API Specification, used directly by tooling (Swagger UI, ReDoc,
client generation, CI validation). Implementation is the code itself,
which must trace every behavior back through this chain --- no
implementation detail should exist that isn't justified by a document
above it. 10. Engineering Principles These are binding rules for anyone
contributing to Sentinel. They are derived directly from the philosophy
and decisions above, not invented independently.

Never identify a Digital Asset by filename. Identity is always the
SHA-256 content hash. Never overwrite an Analysis. New results are
always a new, incremented version. Never expose Workers directly to
clients. Workers only persist results; the API is the only interface
clients ever see. Never store binary file content inside PostgreSQL.
Binary content belongs in object storage; PostgreSQL stores metadata
only. Business rules belong in the Domain layer. They must not leak into
Infrastructure, Application services, or API handlers. Infrastructure
must never contain business logic. Its responsibility is persistence,
storage, and external integration only. Every API endpoint must map to a
real business capability defined in the Domain Model. No endpoint should
exist "because it's convenient" if it doesn't correspond to a documented
capability. Every database schema change must trace back to a
corresponding change in the Domain Model. The database is a reflection
of the domain, not the other way around. Every architectural change must
preserve existing invariants (immutability of assets, append-only
analyses, hash-based identity) unless this document is explicitly
revised to reflect a deliberate, reasoned change of philosophy. Every
analysis result must include evidence, confidence, and a recommendation.
A verdict without justification is not an acceptable output anywhere in
the system. 10.2 Non-Negotiable Design Constraints

The following architectural constraints must remain true unless the
project's philosophy is intentionally revised:

-   Digital Assets are immutable.
-   Digital Asset identity is the SHA-256 content hash.
-   Binary content is stored only in object storage.
-   Analyses are append-only and versioned.
-   Workers never communicate directly with clients.
-   Business rules belong in the Domain layer.
-   Every externally visible capability is exposed through the
    documented REST API.
-   Every implementation must trace back to the PRD, Domain Model,
    Architecture, and API Specification.

10.3 Operational Assumptions

The following are current operational assumptions, not permanent
architectural commitments. Each may be changed through the ADR process
(17-Architecture-Decision-Records-Guide) as requirements evolve.

-   Single-region deployment. Sentinel is initially deployed to a single
    cloud region. Multi-region replication and geo-distribution are not
    addressed in the current architecture.
-   English-only documentation and UI. All engineering documentation,
    API error messages, and user-facing text are in English.
    Internationalization is not a v1 concern.
-   UTC-normalized timestamps. All timestamps stored in PostgreSQL and
    emitted in API responses use UTC. No timezone conversion is performed
    by the backend.



---

## Developer Resources

For engineers working on the Sentinel codebase:

### Core Documentation (Reading Order)

1. **01-Product-Requirements.md** — What Sentinel does and why
2. **02-Domain-Model.md** — Core business entities and relationships
3. **03-Architecture.md** — System layers, components, and structure
4. **04-Database-Design.md** — PostgreSQL schema, tables, and constraints
5. **05-API-Specification.md** — REST API contract and endpoints
6. **backend/openapi.yaml** — Machine-readable API definition

### Backend Development

- **backend/ALEMBIC_SETUP.md** — Database migration workflow guide
  - Creating ORM models and generating migrations with Alembic
  - Testing migrations locally (upgrade/downgrade cycles)
  - Troubleshooting common migration issues
  - Reference: Alembic commands, environment variables, naming conventions

- **07-Backend-Development-Standards.md** — Code style, patterns, and practices
- **08-Security-Architecture.md** — Authentication, authorization, and secure coding
- **04-Database-Design.md** §3+ — ORM model patterns and schema design

### Infrastructure & Deployment

- **09-Deployment-Architecture.md** — How Sentinel deploys and scales
- **12-CI-CD-Architecture.md** — CI/CD pipeline and validation stages

### Quality & Process

- **11-Testing-Strategy.md** — Test types, coverage targets, and patterns
- **17-Architecture-Decision-Records-Guide.md** — How to document architectural decisions
- **19-Contributor-Guide.md** — Contribution process and code review

### Getting Started

1. Read **01-Product-Requirements.md** to understand what Sentinel does
2. Read **02-Domain-Model.md** to learn the core entities
3. Read **03-Architecture.md** to understand the system design
4. Read **04-Database-Design.md** to see the data model
5. For backend work: read **backend/ALEMBIC_SETUP.md** for migrations and **07-Backend-Development-Standards.md** for coding patterns
6. For features: read **05-API-Specification.md** to understand the API contract
7. For security work: read **08-Security-Architecture.md**
8. For deployment/operations: read **09-Deployment-Architecture.md** and **12-CI-CD-Architecture.md**
