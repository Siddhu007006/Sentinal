Document Information Document: docs/06-Repository-Structure.md Version:
1.0.0 Status: Final Owner: Founding Engineering Team Audience: All
engineers contributing code to the Sentinel repository Dependencies:
This document implements the layering defined in 03-Architecture.md, the
entities defined in 02-Domain-Model.md, the persistence model defined in
04-Database-Design.md, and the contract defined in
05-API-Specification.md / backend/openapi.yaml. It introduces no new
business functionality and does not alter any prior architectural
decision.

Revision History

Version Date Author Summary 1.0.0 Initial Founding Engineering Team
First canonical repository structure. 1. Purpose A repository is the
physical expression of an architecture. If the folder structure does not
match the layering decisions made in 03-Architecture.md, engineers will
eventually --- often unknowingly --- write code that violates those
decisions, because there is nothing in the day-to-day experience of the
codebase to stop them.

This document exists so that:

Every file has exactly one obvious place to live. Module boundaries
(API, Application, Domain, Infrastructure, Workers, Analyzers) are
enforced by the directory structure itself, not just by convention. A
new engineer can predict where to find or add code without asking a
teammate. Code review can catch architectural violations mechanically
(e.g., "why does domain/ import from infrastructure/?") rather than
through repeated verbal correction. The repository remains navigable as
the team grows from a handful of engineers to 10--30, and as the
codebase grows from an MVP into a mature platform. This document is
binding. Deviating from it requires updating this document first, not
the other way around.

2.  Repository Overview text

Sentinel/ ├── docs/ \# All engineering documentation (00--06+) ├──
backend/ \# FastAPI application, workers, analyzers ├── frontend/ \#
React application ├── infrastructure/ \# IaC, deployment configuration,
monitoring config ├── docker/ \# Dockerfiles and container-related
assets ├── scripts/ \# One-off and operational scripts ├── .github/ \#
CI/CD workflows, issue/PR templates ├── .env.example \# Documented
template of required environment variables ├── docker-compose.yml \#
Local development environment definition ├── README.md \# Entry point:
links to docs/00-Project-Context.md └── LICENSE Each top-level folder is
explained in the sections that follow. No file should be placed at the
repository root unless it is a genuine root-level concern (build
orchestration, licensing, top-level README, environment template,
editor/tooling config).

3.  Backend Structure The backend implements the four architectural
    layers defined in 03-Architecture.md (Presentation → Application →
    Domain → Infrastructure) plus two cross-cutting subsystems
    introduced in 00-Project-Context.md: Workers and Analyzers.

text

backend/ ├── app/ │ ├── api/ \# Presentation layer: HTTP surface │ │ ├──
v1/ │ │ │ ├── routes/ │ │ │ ├── dependencies/ │ │ │ ├── middleware/ │ │
│ └── exception_handlers/ │ │ └── **init**.py │ │ │ ├── application/ \#
Application layer: use cases / orchestration │ │ ├── services/ │ │ ├──
use_cases/ │ │ ├── commands/ │ │ └── queries/ │ │ │ ├── domain/ \#
Domain layer: entities and business rules │ │ ├── entities/ │ │ ├──
value_objects/ │ │ ├── repositories/ \# Abstract interfaces only │ │ ├──
services/ │ │ └── events/ │ │ │ ├── infrastructure/ \# Infrastructure
layer: adapters to the outside world │ │ ├── database/ │ │ ├── storage/
│ │ ├── queue/ │ │ ├── ai_providers/ │ │ ├── email/ │ │ ├── logging/ │ │
└── config/ │ │ │ ├── workers/ \# Background job consumers │ │ ├──
analysis_worker/ │ │ ├── retry_worker/ │ │ └── scheduled/ │ │ │ ├──
analyzers/ \# Analyzer plugin system │ │ ├── base/ │ │ ├── registry/ │ │
├── security_analyzer/ │ │ ├── ocr_analyzer/ │ │ ├── metadata_analyzer/
│ │ ├── ai_document_analyzer/ │ │ └── image_analyzer/ │ │ │ ├── models/
\# ORM models (persistence representation) │ ├── schemas/ \# Pydantic
request/response schemas │ ├── core/ \# App bootstrap, settings, DI
container, constants │ ├── utils/ \# Generic, framework-agnostic helpers
│ └── main.py \# FastAPI app factory / entrypoint │ ├── tests/ │ ├──
unit/ │ ├── integration/ │ ├── api/ │ ├── workers/ │ ├── fixtures/ │ └──
mocks/ │ ├── migrations/ \# Alembic migrations (tracks
04-Database-Design.md) ├── alembic.ini ├── pyproject.toml ├──
openapi.yaml \# Canonical machine-readable API contract └── README.md
Directory responsibilities app/api/ --- The only layer permitted to know
about HTTP. Translates HTTP requests into Application layer calls and
Application layer results back into HTTP responses. Contains no business
logic. app/application/ --- Orchestrates use cases described in
01-Product-Requirements.md and 05-API-Specification.md by coordinating
Domain entities and Infrastructure adapters. Contains workflow logic,
not business rules. app/domain/ --- The pure business core, implementing
the entities and rules from 02-Domain-Model.md. Has no dependency on any
other layer. app/infrastructure/ --- Concrete implementations of
everything external: database access, object storage, queues, AI
provider clients, email, logging, configuration loading. app/workers/
--- Long-running or job-triggered processes that consume the Queue and
execute Analyzers, per the pipeline defined in 00-Project-Context.md
Section 5. app/analyzers/ --- The pluggable intelligence units described
in 02-Domain-Model.md. Structurally isolated from the pipeline that
invokes them. app/models/ --- SQLAlchemy (or equivalent ORM) models
mapping directly to the tables in 04-Database-Design.md. These are
persistence concerns, not Domain entities, and are kept in
Infrastructure's orbit even though they live in a top-level folder for
tooling convenience (Alembic autogeneration, etc.). app/schemas/ ---
Pydantic models mirroring the request/response shapes in
backend/openapi.yaml. Used exclusively at the API boundary. app/core/
--- Application bootstrapping: settings loading, dependency injection
wiring, startup/shutdown hooks, global constants. app/utils/ --- Small,
stateless, framework-agnostic helper functions with no business meaning
(e.g., string formatting, hashing helpers used across layers). tests/
--- Mirrors the app/ structure so every module has an obvious
corresponding test location (see Section 13). migrations/ --- Alembic
migration scripts, each one traceable to a specific change in
04-Database-Design.md. 4. API Layer The API layer (app/api/v1/) is the
only part of the backend that speaks HTTP. It is versioned from day one
(v1/) to allow the contract in 05-API-Specification.md to evolve without
breaking existing clients.

routes/ --- One module per resource group, mirroring the tags defined in
backend/openapi.yaml (auth.py, users.py, uploads.py, assets.py,
analyzers.py, analyses.py, reports.py, audit_logs.py, health.py). Each
route function's only responsibilities are: parse input via a schema,
call exactly one Application service or use case, and return a
schema-validated response. Routes never talk to app/domain/ or
app/infrastructure/ directly. dependencies/ --- FastAPI
dependency-injection providers: current-user extraction from JWT,
pagination parameter parsing, role-based access checks, idempotency-key
handling. These implement the cross-cutting concerns documented in
05-API-Specification.md (auth, pagination, idempotency) in one place.
middleware/ --- Request-scoped concerns applied globally: request ID
generation/propagation (X-Request-ID), request logging, rate limiting,
CORS. exception_handlers/ --- Central translation of Domain/Application
exceptions into the Error schema defined in backend/openapi.yaml,
guaranteeing every error response
(400/401/403/404/409/413/415/422/429/500/503) follows the same envelope
regardless of where it originated. Response models always come from
app/schemas/, never ad hoc dictionaries, so that the implementation and
the OpenAPI contract cannot silently drift apart. Versioning: a future
v2/ sits alongside v1/ under app/api/, sharing the same
Application/Domain/Infrastructure layers, so that breaking API changes
never require duplicating business logic. 5. Application Layer
app/application/ contains no HTTP or database awareness. It exists to
answer: "What happens, in what order, to fulfill this use case?"

services/ --- Coordinating objects grouped by capability
(upload_service.py, analysis_service.py, report_service.py,
auth_service.py). A service method typically: validates preconditions,
invokes one or more Domain entities/services, calls Infrastructure
adapters through Domain-defined repository interfaces, and returns a
plain result to the API layer. use_cases/ --- Where a workflow is
complex enough to warrant its own object rather than a service method
(e.g., CreateUploadUseCase, TriggerAnalysisUseCase,
CancelAnalysisUseCase). Each use case corresponds to exactly one
capability described in 05-API-Specification.md. commands/ --- Input
data structures representing an intent to change state (e.g.,
CreateUploadCommand, CreateAnalysisCommand), decoupled from the API's
request schema so that the Application layer does not depend on
app/schemas/. queries/ --- Input data structures representing a request
to read state (e.g., ListAnalysesQuery, GetReportQuery), supporting the
filtering/pagination behavior defined in the API Specification. Business
workflows --- Multi-step processes such as the upload intake pipeline
(validate → hash → duplicate-check → store → enqueue) and the analysis
pipeline (validate asset → enqueue per analyzer → track status) are
implemented here, calling into Domain and Infrastructure but owning the
sequence themselves. The Application layer must remain a thin
coordinator. Any rule that would still be true even if the framework,
database, or delivery mechanism changed belongs in the Domain layer
instead.

6.  Domain Layer app/domain/ is the pure business core described in
    02-Domain-Model.md. It has zero dependencies on FastAPI, SQLAlchemy,
    Celery/Redis, S3 clients, or any other framework or infrastructure
    library.

entities/ --- User, Upload, DigitalAsset, Analyzer, Analysis, Report,
AuditLog --- plain Python objects encoding identity and invariants
(e.g., a DigitalAsset entity enforces that its identity is derived from
its hash; an Analysis entity enforces that it is immutable once
created). value_objects/ --- Small, immutable types with no identity of
their own (e.g., Sha256Hash, ConfidenceScore, Verdict), used to make
illegal states unrepresentable rather than validated ad hoc.
repositories/ --- Abstract interfaces only (e.g., UploadRepository,
DigitalAssetRepository, AnalysisRepository), defining what persistence
operations the Domain requires without specifying how they are
implemented. Concrete implementations live in
app/infrastructure/database/. services/ --- Domain services encapsulate
business rules that don't naturally belong to a single entity (e.g.,
duplicate-detection logic that compares a computed hash against existing
assets --- the rule, not the database query itself). events/ --- Domain
events representing meaningful state transitions (e.g., UploadCompleted,
AnalysisFinished) that the Application layer can react to, keeping the
Domain layer decoupled from what happens as a result of those
transitions. What must NOT exist in this layer No imports of FastAPI,
Pydantic (API schemas), SQLAlchemy, Celery, boto3/S3 clients, or any AI
provider SDK. No HTTP status codes, request/response objects, or
serialization concerns. No direct SQL or ORM queries --- only calls
through the abstract repository interfaces. No knowledge of the Queue,
Workers, or how/when an Analyzer is actually invoked --- the Domain
knows that an Analysis is versioned and immutable, not how it gets
executed. 7. Infrastructure Layer app/infrastructure/ implements every
abstract interface defined by the Domain and provides access to the
outside world. Every subfolder is an adapter: it translates between the
Domain's vocabulary and a specific external technology.

database/ --- SQLAlchemy engine/session setup, and concrete repository
implementations (SqlUploadRepository, SqlDigitalAssetRepository, etc.)
fulfilling the interfaces from app/domain/repositories/. Schema shape is
governed entirely by 04-Database-Design.md. storage/ --- S3-compatible
object storage client and adapter, responsible for persisting and
retrieving raw file bytes, per the "files are never stored in
PostgreSQL" decision in 00-Project-Context.md. queue/ --- Redis/Celery
(or equivalent) producer adapter used by the Application layer to
enqueue analysis jobs; the consumer side lives in app/workers/.
ai_providers/ --- Adapters wrapping external AI provider SDKs/APIs
(e.g., OpenAiProvider), implementing a common internal interface so
Analyzers depend on an abstraction, never a specific vendor SDK directly
(per the "AI providers are abstracted" decision). email/ --- Adapter for
transactional email delivery (e.g., account verification,
notifications), if/when required by product requirements. logging/ ---
Structured logging configuration and request/audit log emission helpers.
config/ --- Environment-variable loading and validated settings objects,
consumed by app/core/ at startup. External APIs --- Any other
third-party integration adapters are added here as their own subfolder,
following the same adapter pattern. Adapter responsibility: every
adapter's job is translation and error mapping --- converting
infrastructure-specific exceptions into Domain-meaningful outcomes
(e.g., an S3 timeout becomes a Domain-level StorageUnavailableError, not
a raw boto3 exception leaking upward). No adapter contains business
rules; it only fulfills a contract defined above it.

8.  Workers app/workers/ hosts the consumer side of the asynchronous
    pipeline described in 00-Project-Context.md Section 5 and 8. Workers
    never receive HTTP requests and never respond directly to a browser;
    they consume jobs, execute logic via the Application/Domain layers,
    and persist results through Infrastructure.

analysis_worker/ --- Consumes analysis jobs from the Queue, resolves the
requested Analyzer, executes it against the target DigitalAsset, and
persists the resulting Analysis via the Application layer. This is the
primary worker type in the MVP. retry_worker/ --- Handles retryable
failures (e.g., a transient AI provider timeout), applying backoff
policy before re-queueing or marking an Analysis as failed. scheduled/
--- Time-triggered jobs (e.g., periodic cleanup, housekeeping tasks)
that are not triggered by a queued event but by a schedule. future
workers --- Any new worker type (e.g., a dedicated report-generation
worker) is added as its own sibling folder under app/workers/, following
the same lifecycle contract below. Worker lifecycle Receive a job
message from the Queue (job payload contains identifiers only --- never
raw file bytes). Resolve required entities via Application-layer
queries/services. Execute the relevant business logic (for
analysis_worker, this means invoking the resolved Analyzer). Persist the
outcome through the Application layer, which in turn uses Domain
repository interfaces. Acknowledge the job (or trigger retry/failure
handling) with the Queue. Workers depend on app/application/ and,
transitively, app/domain/ and app/infrastructure/ --- never on app/api/.

9.  Analyzer System app/analyzers/ implements the plugin architecture
    that makes Sentinel a platform rather than a single-purpose tool, as
    established in 00-Project-Context.md. This section defines structure
    only --- no analyzer logic is implemented here.

text

app/analyzers/ ├── base/ │ ├── analyzer_interface.py \# Abstract base
class every analyzer implements │ └── analyzer_result.py \# Common
result shape (verdict, evidence, confidence, recommendation) ├──
registry/ │ └── analyzer_registry.py \# Maps Analyzer identity -\>
executable implementation ├── security_analyzer/ ├── ocr_analyzer/ ├──
metadata_analyzer/ ├── ai_document_analyzer/ ├── image_analyzer/ └──
custom/ \# Placeholder for future, non-built-in analyzers base/ ---
Defines the contract every analyzer must fulfill: given a DigitalAsset
reference, produce a result matching the EvidenceItem/Analysis shape
defined in 02-Domain-Model.md and backend/openapi.yaml. This contract is
the only thing the Worker and Application layers know about analyzers.
registry/ --- Resolves an Analyzer domain record (by ID) to its
corresponding executable implementation at runtime, so that adding a new
analyzer means registering a new implementation, not modifying pipeline
code. One folder per analyzer type --- Each analyzer
(security_analyzer/, ocr_analyzer/, metadata_analyzer/,
ai_document_analyzer/, image_analyzer/) is self-contained: its own
logic, its own configuration, its own tests, implementing the shared
base/ interface. An analyzer may depend on
app/infrastructure/ai_providers/ for AI-assisted reasoning but must not
depend on app/api/ or bypass the shared result contract. custom/ ---
Reserved location for analyzers added after the MVP, including any
future third-party or user-defined analyzers, preserving the "future
custom analyzer" extensibility named in 00-Project-Context.md without
requiring structural changes elsewhere. Adding a new analyzer must never
require changes to app/workers/analysis_worker/, app/api/, or the Domain
layer --- only a new folder under app/analyzers/ and a registry entry.

10. Frontend Structure The frontend is a consumer of the API with no
    privileged access, per the API-first principle in
    00-Project-Context.md.

text

frontend/ ├── src/ │ ├── pages/ \# Route-level views (Login, Dashboard,
Uploads, AssetDetail, Reports, Admin) │ ├── components/ \# Reusable,
presentation-focused UI components │ ├── hooks/ \# Reusable React hooks
(data fetching, auth state, pagination) │ ├── services/ \#
Business-oriented wrappers around the generated API client │ ├── api/ \#
Generated/typed API client (from backend/openapi.yaml) │ ├── state/ \#
Global state management (auth session, current user, UI state) │ ├──
assets/ \# Static assets: images, icons, fonts │ ├── styles/ \# Global
styles, theme definitions │ ├── utils/ \# Frontend-only helper functions
│ ├── types/ \# Shared TypeScript types not covered by the generated API
client │ └── App.tsx ├── tests/ │ ├── unit/ │ ├── components/ │ └── e2e/
├── public/ ├── package.json └── README.md pages/ --- One component per
route, composing components and hooks; contains no direct API calls.
components/ --- Presentational and reusable UI building blocks,
organized by feature when a group grows large enough (e.g.,
components/uploads/, components/reports/). hooks/ --- Encapsulate
data-fetching and state logic (e.g., useUploads, useAnalysisStatus) so
pages remain declarative. services/ --- Thin, business-named wrappers
over the generated API client (e.g., uploadService.create()), giving the
rest of the app a stable interface even if the generated client's shape
changes. api/ --- The TypeScript client generated directly from
backend/openapi.yaml, kept out of hand-edited code paths so it can be
regenerated safely. state/ --- Global, cross-page state such as the
authenticated session, distinct from component-local state. Frontend
tests mirror src/ structure, per Section 13. 11. Shared Resources Some
concerns are shared across layers or across backend/frontend and must
have a single, unambiguous home rather than being duplicated.

Configuration --- Backend configuration lives in app/core/ (loading) and
app/infrastructure/config/ (validated settings objects); frontend
configuration lives in frontend/.env files, following the same variable
names documented in .env.example at the repository root wherever both
sides need the same value (e.g., API base URL). Constants ---
Backend-wide constants (e.g., max upload size, allowed MIME types ---
matching backend/openapi.yaml) live in app/core/constants.py.
Frontend-wide constants live in frontend/src/utils/constants.ts. These
must be kept numerically consistent with the OpenAPI contract; the
contract is the source of truth. Environment variables --- All required
environment variables, for every environment
(Development/Staging/Production per backend/openapi.yaml servers), are
documented in the root .env.example. No environment variable should be
introduced without a corresponding entry there. Shared types --- Where
the frontend needs a type that mirrors a backend schema, it is generated
from backend/openapi.yaml into frontend/src/api/, never hand-maintained
twice. Utilities --- Cross-cutting, non-business helper functions live
in app/utils/ (backend) or frontend/src/utils/ (frontend). If a
"utility" starts encoding a business rule, it belongs in the Domain
layer instead. 12. Infrastructure text

infrastructure/ ├── terraform/ \# (or equivalent IaC) --- cloud resource
definitions ├── monitoring/ \# Dashboards, alerting rules └──
environments/ ├── development/ ├── staging/ └── production/

docker/ ├── backend.Dockerfile ├── frontend.Dockerfile └──
worker.Dockerfile

.github/ └── workflows/ ├── ci-backend.yml ├── ci-frontend.yml ├──
openapi-validate.yml └── deploy.yml

scripts/ ├── seed_db.py ├── run_migrations.sh └──
generate_frontend_client.sh infrastructure/ --- Infrastructure-as-code
and environment-specific configuration, kept separate from application
code so that deployment changes don't require application code review
and vice versa. docker/ --- One Dockerfile per deployable unit (API,
worker, frontend), reflecting that the backend is a modular monolith but
may run as more than one container (e.g., API process and worker
process) even though the codebase itself is not split into
microservices. docker-compose.yml (root) --- Wires together the API,
workers, PostgreSQL, Redis/queue, and object storage emulator for local
development, matching the Development server defined in
backend/openapi.yaml. .github/workflows/ --- CI pipelines: backend
tests, frontend tests, and a dedicated openapi-validate.yml that
lints/validates backend/openapi.yaml on every change, enforcing the
"OpenAPI contract must always validate" requirement from prior
documents. scripts/ --- Operational one-off scripts (database seeding,
running migrations, regenerating the frontend API client from
backend/openapi.yaml). Scripts orchestrate; they must not contain
business logic themselves. 13. Testing Structure Tests mirror the
structure of the code they verify, so that finding a test for a given
file never requires guessing.

text

backend/tests/ ├── unit/ │ ├── domain/ \# Entity and value-object
invariant tests │ ├── application/ \# Service/use-case tests
(Infrastructure mocked) │ └── analyzers/ \# Analyzer logic tests, in
isolation ├── integration/ │ ├── database/ \# Repository implementations
against a real test DB │ ├── storage/ \# Object storage adapter tests │
└── queue/ \# Queue adapter tests ├── api/ \# Full HTTP request/response
tests against the FastAPI app ├── workers/ \# Worker lifecycle tests
(job in -\> result persisted) ├── fixtures/ \# Shared test data builders
(e.g., factory for DigitalAsset) └── mocks/ \# Fake/mock implementations
of Infrastructure interfaces Unit tests --- Fast, isolated, no I/O.
Domain tests never touch a database; Application tests mock
Infrastructure via the Domain's repository interfaces. Integration tests
--- Exercise real Infrastructure adapters (Postgres, object storage,
queue) against test instances, verifying that adapters correctly fulfill
Domain contracts. API tests --- Black-box tests against the running
FastAPI app, asserting responses match backend/openapi.yaml (status
codes, schemas, error envelopes). Worker tests --- Verify that a queued
job results in the correct persisted Analysis, including retry and
failure paths. Fixtures/Mocks --- Centralized so that every test suite
builds domain objects (e.g., a sample Upload or DigitalAsset) the same
way, preventing drift between tests. text

frontend/tests/ ├── unit/ \# Pure function / hook tests ├── components/
\# Component rendering and interaction tests └── e2e/ \# End-to-end
flows against a running backend (or mocked API layer) 14. Dependency
Rules Dependencies flow in one direction only, matching
03-Architecture.md:

text

API ↓ Application ↓ Domain ↓ Infrastructure (implements Domain
interfaces) Concretely:

app/api/ may import from app/application/ and app/schemas/. It must not
import from app/domain/, app/infrastructure/, or app/models/ directly.
app/application/ may import from app/domain/. It may reference
Infrastructure only through interfaces defined in
app/domain/repositories/, never by importing app/infrastructure/ modules
directly --- the concrete implementation is injected (via app/core/
wiring), not imported. app/domain/ must import nothing from app/api/,
app/application/, app/infrastructure/, app/workers/, or app/analyzers/.
It is the innermost, dependency-free layer. app/infrastructure/ may
import from app/domain/ (to implement its interfaces) but never from
app/application/ or app/api/. app/workers/ may import from
app/application/ (to execute use cases) and, transitively,
app/domain//app/infrastructure/. It must not import from app/api/.
app/analyzers/ may import from app/infrastructure/ai_providers/ and from
app/analyzers/base/. It must not import from app/api/, app/application/,
or app/domain/ beyond the shared value objects needed to construct a
result (e.g., Verdict, ConfidenceScore). Explicitly prohibited
app/domain/ importing anything from FastAPI, SQLAlchemy, Celery, or any
SDK. Any layer importing "upward" (e.g., app/infrastructure/ importing
app/application/). app/models/ (ORM) being imported anywhere outside
app/infrastructure/database/ --- Application and Domain code must
interact with data through repository interfaces and Domain entities,
never raw ORM models. frontend/ importing backend code directly, or vice
versa --- the only contract between them is backend/openapi.yaml. 15.
Naming Conventions Files (Python): snake_case.py (e.g.,
upload_service.py, analysis_repository.py). Files (TypeScript/React):
PascalCase.tsx for components (UploadList.tsx), camelCase.ts for
hooks/services/utils (useUploads.ts, uploadService.ts).
Packages/Directories: snake_case throughout the backend
(digital_assets/, ai_providers/); kebab-case or camelCase consistently
within frontend/src/ (prefer camelCase to match TypeScript conventions).
Classes: PascalCase (e.g., DigitalAsset, UploadRepository,
AnalysisService). Functions/Methods: snake_case in Python
(create_upload), camelCase in TypeScript (createUpload). Variables:
snake_case in Python, camelCase in TypeScript, matching the naming
convention already established for JSON payloads in
backend/openapi.yaml. Tests: Mirror the module under test with a test\_
prefix (test_upload_service.py) or .test.ts(x) suffix on the frontend
(UploadList.test.tsx). Migrations: Alembic auto-generated revision files
are renamed to `<timestamp>`{=html}\_`<short_description>`{=html}.py
(e.g., 20240115_add_digital_assets_table.py), always traceable to a
section of 04-Database-Design.md. Configuration files/environment
variables: UPPER_SNAKE_CASE for environment variables (e.g.,
DATABASE_URL, JWT_SECRET_KEY), matching standard 12-factor app
conventions. 16. Import Rules Absolute imports are used throughout the
backend (e.g., from app.domain.entities.upload import Upload),
configured via the project's package root, to keep import paths stable
regardless of a file's location within its layer. Relative imports are
permitted only for closely related files within the same immediate
subfolder (e.g., within a single analyzer's own package), never across
layer boundaries. Circular dependency prevention: Because dependencies
flow strictly downward (Section 14), circular imports between layers
should be structurally impossible if the rules are followed. Within a
layer, if two modules need each other, the shared logic must be
extracted into a third module both can depend on (e.g., a shared value
object), rather than importing each other directly. Frontend imports use
absolute paths from src/ (configured via TypeScript path aliases, e.g.,
@/components/...) to avoid deep relative import chains (../../../..).
17. Code Ownership Guidance for where new work belongs:

Adding a... Goes in... New API endpoint
app/api/v1/routes/`<resource>`{=html}.py, backed by a new/updated
Application use case, and reflected first in backend/openapi.yaml New
analyzer New folder under app/analyzers/, implementing
app/analyzers/base/analyzer_interface.py, registered in
app/analyzers/registry/ New worker New folder under app/workers/,
following the lifecycle in Section 8 New database model app/models/,
paired with a new Alembic migration under migrations/, tracing back to
04-Database-Design.md New repository Abstract interface in
app/domain/repositories/; concrete implementation in
app/infrastructure/database/ New schema (API request/response)
app/schemas/, kept in sync with backend/openapi.yaml New migration
migrations/, generated via Alembic, named per Section 15 New Application
service/use case app/application/services/ or app/application/use_cases/
New test Mirrored path under backend/tests/ or frontend/tests/, matching
the module under test New frontend page/feature frontend/src/pages/ plus
supporting components/, hooks/, services/ Any new capability must first
be justified by 01-Product-Requirements.md or 02-Domain-Model.md; if it
isn't, the correct first step is proposing a documentation change, not
writing code.

18. Future Evolution The modular monolith is deliberately structured so
    that individual modules can be extracted into independent services
    later without a rewrite, per the trade-off accepted in
    00-Project-Context.md Section 6.

Because dependencies flow strictly downward and Infrastructure adapters
already isolate external systems:

app/workers/ (and the analyzers it invokes) could be extracted into a
standalone service that consumes the same Queue, since it already
depends only on app/application/, app/domain/, and app/infrastructure/
--- never on app/api/. Individual analyzers under app/analyzers/ could
be extracted into independently deployable analysis services behind the
same base/analyzer_interface.py contract, with the registry updated to
dispatch remotely instead of in-process. app/infrastructure/ adapters
are already the only code aware of specific external systems (Postgres,
S3, Redis, AI providers), so replacing or scaling any one of them
independently does not ripple into Domain or Application code. The API
layer could be split by resource group (e.g., a dedicated Reports
service) since routes already delegate entirely to Application use cases
with no shared mutable state at the API layer itself. No such extraction
is planned or required at this stage; this section exists solely to
confirm that today's structure does not foreclose it.

Appendix Repository Tree (Quick Reference) text

Sentinel/ ├── docs/ ├── backend/ │ ├── app/ │ │ ├──
api/v1/{routes,dependencies,middleware,exception_handlers} │ │ ├──
application/{services,use_cases,commands,queries} │ │ ├──
domain/{entities,value_objects,repositories,services,events} │ │ ├──
infrastructure/{database,storage,queue,ai_providers,email,logging,config}
│ │ ├── workers/{analysis_worker,retry_worker,scheduled} │ │ ├──
analyzers/{base,registry,security_analyzer,ocr_analyzer,metadata_analyzer,ai_document_analyzer,image_analyzer,custom}
│ │ ├── models/ │ │ ├── schemas/ │ │ ├── core/ │ │ └── utils/ │ ├──
tests/{unit,integration,api,workers,fixtures,mocks} │ ├── migrations/ │
└── openapi.yaml ├── frontend/ │ ├──
src/{pages,components,hooks,services,api,state,assets,styles,utils,types}
│ └── tests/{unit,components,e2e} ├──
infrastructure/{terraform,monitoring,environments} ├── docker/ ├──
.github/workflows/ └── scripts/ Directory Cheat Sheet Folder Layer May
depend on app/api/ Presentation Application, Schemas app/application/
Application Domain (interfaces only) app/domain/ Domain Nothing (pure)
app/infrastructure/ Infrastructure Domain (implements interfaces)
app/workers/ Cross-cutting Application, Domain, Infrastructure
app/analyzers/ Cross-cutting Infrastructure (AI providers), Domain value
objects app/models/ Infrastructure detail Used only inside
app/infrastructure/database/ app/schemas/ Presentation detail Used only
inside app/api/

------------------------------------------------------------------------

## 19. Repository Governance

The repository structure defined in this document is considered an
architectural contract.

-   New top-level directories require an architectural review.
-   New cross-cutting modules should be added only after evaluating
    whether an existing module can own the responsibility.
-   Changes to dependency rules must be reflected in both this document
    and the Architecture document before implementation.
-   Code organization should optimize long-term maintainability rather
    than short-term convenience.

This section introduces governance only; it does not change any
repository layout or architectural decisions.

## 20. Review Notes (v1.0.1)

This review intentionally preserves the repository structure.

Minor improvements: - Added repository governance guidance. - Reinforced
that structural changes should follow architectural review. - No
folders, layers, dependencies, or responsibilities were modified.
