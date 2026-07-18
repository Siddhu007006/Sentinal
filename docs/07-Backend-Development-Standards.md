Document Information Document: docs/07-Backend-Development-Standards.md
Version: 1.0.2 Status: Final Owner: Founding Engineering Team Audience:
All backend engineers contributing to the Sentinel codebase
Dependencies: This document defines how code is written to satisfy the
architecture in 03-Architecture.md, the domain rules in
02-Domain-Model.md, the persistence model in 04-Database-Design.md, the
contract in 05-API-Specification.md / backend/openapi.yaml, and the
repository layout in 06-Repository-Structure.md. It introduces no new
business functionality, no architectural changes, and no repository
reorganization.

Revision History

Version Date Author Summary 1.0.0 Initial Founding Engineering Team
First canonical backend engineering standard. 1. Purpose Architecture
defines the shape of the system. Coding standards determine whether that
shape survives contact with dozens of engineers making thousands of
individual decisions over years of development.

Sentinel's architecture (03-Architecture.md) and repository structure
(06-Repository-Structure.md) already encode strict layering,
immutability, and explainability requirements. None of that matters if
individual engineers implement those layers inconsistently --- one
service catching exceptions differently than another, one repository
leaking ORM models into the Domain layer, one route validating input
manually instead of through schemas. Inconsistency is not a style
problem; it is how architectural intent quietly erodes.

This document exists so that:

Any two engineers solving similar problems produce similarly shaped
code, making review, debugging, and onboarding faster. The boundaries
defined in 06-Repository-Structure.md are enforced through discipline,
not just folder placement. A new backend engineer can read this document
once and write production-acceptable code on their first pull request,
without needing verbal correction on fundamentals. Consistency is
prioritized over individual coding style. A codebase where every file
"feels the same" is easier to review, easier to refactor, and easier to
trust than one where each engineer's personal preferences are visible in
the code. Personal style preferences are always subordinate to the rules
in this document.

2.  Engineering Philosophy These principles govern every line of backend
    code written for Sentinel. They are derived directly from the
    architecture and domain decisions already made, not introduced
    independently.

Readability over cleverness. Code is read far more often than it is
written. A clever one-liner that saves three lines but costs a reviewer
thirty seconds of decoding is a net loss. If a solution requires a
comment explaining "why this works," it usually should be rewritten so
the comment is unnecessary.

Explicit over implicit. Function signatures, return types, and side
effects must be visible from the code itself. Hidden state mutation,
implicit type coercion, and "magic" framework behavior that isn't
obvious from the call site are avoided wherever a more explicit
alternative exists.

Composition over inheritance. Behavior is built by composing small,
focused objects and functions rather than through deep inheritance
hierarchies. Inheritance is reserved for genuine is-a relationships with
a shared, stable contract (e.g., the analyzer base interface in
06-Repository-Structure.md Section 9) --- not as a shortcut for code
reuse.

Small functions, single responsibility. A function should do one thing
at one level of abstraction. If a function name needs "and" to describe
it, it should be split. This applies at every layer: route handlers,
service methods, domain methods, repository methods.

Dependency inversion. Higher-level layers depend on abstractions, not
concrete implementations, as already mandated by the dependency rules in
06-Repository-Structure.md Section 14. This is not optional
architectural guidance --- it is enforced at the code level through the
Domain layer's abstract repository interfaces and the Application
layer's reliance on them.

Fail fast. Invalid state is rejected as early as possible --- at the API
boundary via schema validation, and within the Domain layer via
entity/value-object invariants --- rather than allowed to propagate and
fail confusingly downstream.

Business rules live in the Domain layer, nowhere else. If a rule would
still be true regardless of framework, database, or API shape (e.g., "an
Analysis is immutable once created," "a DigitalAsset's identity is its
hash"), it belongs in app/domain/. If it changes based on delivery
mechanism (e.g., "this endpoint requires a Bearer token"), it belongs in
app/api/.

Framework independence of business logic. FastAPI, SQLAlchemy, and
Celery/Redis are implementation details of the Presentation and
Infrastructure layers. The Domain and, to the extent possible, the
Application layer should be understandable and testable without knowing
which framework Sentinel uses.

Long-term maintainability over short-term speed. A shortcut that saves
an hour today and costs a day of confusion in six months is not a
shortcut. Every implementation decision should be made as if the
engineer who inherits the code will not have access to ask questions.

3.  Python Standards Python version. Sentinel targets the latest stable
    Python 3.12.x release available at the time of implementation.
    Language features not yet available in that version must not be
    used.

Formatting. Code is formatted automatically using a single, project-wide
formatter (Black) with no manual overrides of its default style
decisions. Formatting is enforced in CI; a pull request with unformatted
code fails the build, not the reviewer's patience.

Linting. A single linter configuration (Ruff or equivalent) is enforced
project-wide, covering unused imports, unreachable code, and common
correctness issues. Linter warnings are treated as build failures, not
suggestions.

Imports. Imports are absolute, per 06-Repository-Structure.md Section
16, grouped in the standard order (standard library, third-party,
first-party) and automatically sorted by tooling (isort or the
formatter's equivalent). Wildcard imports (from module import \*) are
prohibited without exception.

Typing. Every function signature --- parameters and return type --- must
be fully type-annotated. Any is permitted only at genuine integration
boundaries (e.g., deserializing an unstructured third-party API
response) and must be narrowed to a concrete type immediately after.
Static type checking (mypy or equivalent) runs in CI and is a merge
blocker.

Dataclasses vs. Pydantic. Pydantic models are used exclusively at the
API boundary (app/schemas/) for request/response validation and
serialization, and within Infrastructure adapters where external data
must be parsed and validated (e.g., AI provider responses). Domain
entities and value objects (app/domain/) use plain dataclasses (or an
equivalent immutable, framework-free construct) --- never Pydantic ---
to keep the Domain layer free of any framework dependency, per Section
2.

Docstrings. Every public class and function in app/application/,
app/domain/, and app/infrastructure/ requires a docstring describing
intent and behavior --- not a restatement of the signature. Docstrings
answer "why does this exist" or "what business rule does this enforce,"
not "what are its parameters" (types already answer that).

Comments. Comments explain why, never what. A comment restating what the
next line of code obviously does is deleted in review. Comments
referencing a business rule should cite the relevant section of
02-Domain-Model.md where practical, so the rule's origin remains
traceable.

Constants. All fixed values with business or configuration meaning
(e.g., maximum upload size, token expiry, pagination defaults) are named
constants defined in app/core/constants.py or the relevant module's own
constants section --- never inline. Constants that mirror
backend/openapi.yaml values (e.g., max file size, allowed MIME types)
must exactly match the contract.

Magic numbers. Prohibited outright. Any bare numeric or string literal
with domain meaning must be extracted to a named constant or enum
member. This is a merge blocker, not a suggestion.

Enums. Any field with a fixed, closed set of valid values --- matching
an enum in backend/openapi.yaml (e.g., UploadStatus, AnalysisStatus,
AnalysisVerdict, UserRole) --- must be represented as a Python Enum
(typically str, Enum for JSON serialization compatibility), never as a
bare string compared against literals scattered through the codebase.

UUID handling. All entity identifiers are UUIDs, generated using UUIDv4
unless a specific ordering property is required (in which case the
choice and rationale must be documented at the point of use). IDs are
typed as UUID objects throughout the Domain and Application layers and
only serialized to string at the API/Infrastructure boundary.

Datetime handling. All timestamps are timezone-aware and
stored/transmitted in UTC, matching the date-time format used throughout
backend/openapi.yaml. Naive datetime objects (without timezone
information) are prohibited anywhere in the codebase. Local time
conversion, if ever required, happens only at the presentation boundary
(frontend), never in the backend.

4.  FastAPI Standards Route organization. Routes are grouped by
    resource, one module per resource group under app/api/v1/routes/,
    mirroring the tags in backend/openapi.yaml exactly (auth, users,
    uploads, assets, analyzers, analyses, reports, audit_logs, health).
    A route module contains only route definitions --- no business
    logic, no direct database access.

Route handler responsibility. Each route handler does exactly three
things: (1) receive validated input via a Pydantic schema and FastAPI
dependencies, (2) invoke exactly one Application-layer service or use
case, (3) return a response conforming to the schema declared in
response_model. Any handler doing more than this is a signal that logic
needs to move into the Application layer.

Dependency Injection. FastAPI's dependency system is the only mechanism
for supplying route handlers with authenticated user context, database
sessions, and Application services. Constructing services or
repositories manually inside a route handler is prohibited --- it
bypasses the dependency graph and makes testing harder.

Response models. Every route declares an explicit response_model
matching a schema in app/schemas/, which must itself match the
corresponding schema in backend/openapi.yaml. Returning raw dictionaries
or ORM models directly from a route handler is prohibited.

Validation. All request validation (required fields, string length,
format, enum values, ranges) is expressed declaratively through Pydantic
schema definitions, mirroring the constraints already defined in
backend/openapi.yaml. Manual if validation inside route handlers for
anything already expressible in the schema is prohibited.

Exception handling. Route handlers do not use try/except to translate
errors into HTTP responses. Instead, Domain and Application exceptions
(Section 9) are translated into the standard Error envelope by
centralized exception handlers registered in
app/api/v1/exception_handlers/, guaranteeing every endpoint returns
errors in the same shape without each handler reimplementing that logic.

Middleware. Cross-cutting request concerns (request ID propagation via
X-Request-ID, request logging, rate limiting, CORS) are implemented once
as middleware in app/api/v1/middleware/, never duplicated inside
individual route handlers.

Background tasks. FastAPI's BackgroundTasks mechanism is not used for
analysis processing or any work described in 00-Project-Context.md's
asynchronous pipeline --- that work belongs exclusively to the
Queue/Worker system. BackgroundTasks may only be used for genuinely
fire-and-forget, non-critical side effects (e.g., emitting a
non-essential log line) where losing the task on process restart is
acceptable.

Versioning. All routes live under /api/v1 per
06-Repository-Structure.md. A breaking change to any existing endpoint's
contract requires a new version namespace (v2), never an in-place
breaking change to v1. Additive, backward-compatible changes (new
optional fields, new endpoints) do not require a new version.

5.  Application Layer Standards Use cases vs. services. A service in
    app/application/services/ groups related, relatively simple
    orchestration methods for a capability (e.g., AuthService.login,
    AuthService.refresh). A dedicated use_case in
    app/application/use_cases/ is used when a single workflow is complex
    enough to warrant its own object with a single execute entry point
    (e.g., CreateUploadUseCase, TriggerAnalysisUseCase) --- typically
    when the workflow involves multiple sequential steps, compensating
    actions on failure, or coordination across several repositories.

Commands and queries. Every state-changing operation is represented by
an explicit Command object (app/application/commands/) and every read
operation by an explicit Query object (app/application/queries/),
decoupled from the API schema that produced them. This ensures the
Application layer's public interface does not silently depend on
app/schemas/, preserving the dependency direction in
06-Repository-Structure.md Section 14.

Orchestration only. Application services and use cases coordinate calls
to Domain entities, Domain services, and repository interfaces. They
must not contain business rules themselves (e.g., an Application service
must not decide how duplicate detection works --- it calls a Domain
service that does). If an if statement in the Application layer encodes
a business rule rather than a workflow branch, it belongs in the Domain
layer instead.

Transactions. A single Application-layer operation that must be atomic
(e.g., "create an Upload record and enqueue the intake job") is wrapped
in a single transaction boundary managed by the Application layer, using
a Unit-of-Work pattern provided by Infrastructure. Repositories
themselves do not commit transactions --- the Application layer decides
when a unit of work is complete.

Idempotency. Any use case reachable from an endpoint documented as
idempotent in backend/openapi.yaml (currently POST /uploads and POST
/analyses via the Idempotency-Key header) must implement idempotency
handling at the Application layer, keyed on the supplied idempotency
key, so that retried requests return the original result rather than
creating duplicate resources.

Return values. Application services and use cases return plain Domain
entities or simple result objects --- never Pydantic schemas, never ORM
models, never raw dictionaries. Mapping to an API response shape happens
exclusively in app/api/.

6.  Domain Layer Standards Entities. Each entity (User, Upload,
    DigitalAsset, Analyzer, Analysis, Report, AuditLog) is implemented
    as an immutable-by-default dataclass with methods that enforce its
    own invariants (e.g., a DigitalAsset cannot be constructed without a
    valid SHA-256 hash; an Analysis cannot transition from completed
    back to queued). State transitions are expressed as methods
    returning a new entity instance or explicitly mutating in a
    controlled way --- never through direct attribute assignment from
    outside the entity.

Value objects. Concepts without independent identity (Sha256Hash,
ConfidenceScore, Verdict, Email) are modeled as immutable value objects
that validate themselves on construction, making invalid states
unrepresentable (e.g., a Sha256Hash value object cannot be constructed
from a string that isn't 64 hex characters). This eliminates repeated ad
hoc validation scattered across the codebase.

Repositories. app/domain/repositories/ contains only abstract interfaces
(e.g., using Protocol or ABC), defining the persistence operations the
Domain requires (get_by_id, get_by_hash, save, list) without specifying
SQL, ORM, or any storage technology. Naming describes business intent
(get_by_content_hash), not storage mechanics (select_where_hash_equals).

Domain services. Business rules that don't naturally belong to a single
entity --- most notably duplicate detection (comparing a computed hash
against existing assets) and versioning logic (determining the next
version number for an Analysis) --- are implemented as Domain services.
A Domain service depends only on other Domain constructs and repository
interfaces, never on Infrastructure implementations.

Domain events. Meaningful state transitions (UploadCompleted,
AnalysisFinished, AnalysisFailed) are represented as explicit event
objects raised by entities or Domain services. The Application layer is
responsible for reacting to these events (e.g., triggering an audit log
entry); the Domain layer only raises them, it does not know or care what
happens as a result.

Business rules enforced here, and only here. Examples of rules that must
live in the Domain layer: a DigitalAsset's identity is derived from its
content hash, not filename; an Analysis is append-only and versioned; a
Report presents exactly one Analysis version; a verdict is never
returned without accompanying evidence. These rules must not be
duplicated or re-implemented in the API or Infrastructure layers ---
they exist once, in the Domain.

Prohibited dependencies. As stated in 06-Repository-Structure.md Section
14: no imports of FastAPI, Pydantic (schema classes), SQLAlchemy,
Celery, boto3, or any AI provider SDK anywhere in app/domain/. A Domain
module that cannot be imported and unit-tested without installing a web
framework has violated this standard.

7.  Infrastructure Standards Database. All database access happens
    through SQLAlchemy, confined to app/infrastructure/database/.
    Concrete repository implementations here fulfill the interfaces
    defined in app/domain/repositories/ and are the only code in the
    entire backend permitted to construct or execute a SQLAlchemy query.

Storage. The object storage adapter (app/infrastructure/storage/)
exposes a narrow interface (upload, retrieve, delete, exists) to the
rest of the system, hiding all S3-specific client details (credentials,
bucket naming, multipart upload mechanics) behind that interface.

Queue. The queue adapter (app/infrastructure/queue/) exposes
enqueue/consume-style operations to the Application layer and Workers
respectively. No code outside this adapter should construct a Celery
task signature or Redis connection directly.

AI Providers. Every AI provider integration is wrapped in an adapter
implementing a common internal interface (e.g.,
AiReasoningProvider.analyze(content) -\> ProviderResult), per the "AI
providers are abstracted" decision in 00-Project-Context.md. Analyzer
code depends on this interface, never on a specific provider's SDK,
request format, or response schema.

Logging. Logging configuration and structured-log emission helpers live
in app/infrastructure/logging/. Application, Domain, and API code obtain
a logger through a shared, injected interface --- never by instantiating
a provider-specific logging client directly.

Configuration. All environment-derived configuration is loaded once,
validated (type-checked, required fields enforced) at startup in
app/infrastructure/config/, and exposed to the rest of the application
as a typed settings object. Reading os.environ directly anywhere outside
this module is prohibited.

External APIs. Any additional third-party integration follows the same
adapter pattern: a narrow, Domain-meaningful interface, with the
vendor-specific implementation entirely contained within
app/infrastructure/.

Adapter rules. Every adapter is responsible for translating
vendor-specific exceptions into Domain-meaningful exceptions (Section 9)
before they propagate upward. An adapter must never leak a raw
third-party exception type (e.g., boto3.exceptions.*, sqlalchemy.exc.*)
past its own boundary.

8.  Database Standards SQLAlchemy usage. The ORM's declarative models in
    app/models/ map directly to the tables defined in
    04-Database-Design.md --- column names, types, and constraints must
    match exactly. ORM models are used only inside
    app/infrastructure/database/; they are never returned from
    repositories, which instead map ORM models to Domain entities before
    returning them.

Alembic migrations. Every schema change is accompanied by an Alembic
migration in migrations/, generated and then reviewed (not blindly
autogenerated and merged). Each migration file is renamed following the
convention in 06-Repository-Structure.md Section 15 and its description
references the relevant section of 04-Database-Design.md. Migrations
must be reversible (downgrade implemented) unless a documented, reviewed
exception applies (e.g., destructive data migrations).

Transactions. Multi-statement writes that must be atomic are wrapped in
a single database transaction, managed at the Application layer's
Unit-of-Work boundary (Section 5), not scattered across multiple
independent repository calls.

Indexes. Every column used in a WHERE, JOIN, or ORDER BY clause in a
repository's query methods must have a corresponding index defined in
the migration, matching the indexing strategy already specified in
04-Database-Design.md. New query patterns introduced during
implementation that aren't covered by an existing index require a new
migration adding one --- not a decision to accept a slow query.

Soft deletes. Entities that are soft-deleted per 04-Database-Design.md
(rather than hard-deleted) are always filtered by their active/deleted
flag at the repository layer by default; a repository method must opt in
explicitly (e.g., include_deleted=True) to return soft-deleted records,
so deleted data cannot leak into normal application flows by accident.

Naming conventions. Table and column names use snake_case and are always
singular for column names, plural for table names (e.g., table
digital_assets, column sha256_hash), matching the conventions already
established in 04-Database-Design.md.

9.  Error Handling Domain exceptions. The Domain layer defines its own
    exception hierarchy (e.g., DomainError as a base, with subclasses
    like InvalidAssetHashError, AnalysisAlreadyCompletedError)
    representing violations of business rules. These exceptions carry no
    HTTP awareness whatsoever.

Application exceptions. The Application layer may define its own
exceptions for orchestration-level failures (e.g.,
ResourceNotFoundError, ConflictError) or allow Domain exceptions to
propagate unchanged when they already convey the correct meaning. The
Application layer must not catch a Domain exception only to silently
swallow it --- errors are handled explicitly or allowed to propagate to
a layer that can.

API exceptions. The API layer never constructs raw HTTP error responses
inline. Centralized exception handlers (app/api/v1/exception_handlers/)
map each known Domain/Application exception type to the correct HTTP
status code and populate the Error schema defined in
backend/openapi.yaml, including a generated requestId and timestamp.
Unmapped exceptions are caught by a final catch-all handler that logs
the full exception and returns a generic 500 Internal Server Error ---
the caller never sees an unhandled stack trace.

Error response consistency. Every error response, regardless of origin,
uses the single Error envelope defined in the OpenAPI contract. No
endpoint may return an error in a bespoke shape.

Logging on error. Every exception that results in a 5xx response is
logged with full context (stack trace, request ID, relevant entity
identifiers) at ERROR level. Exceptions resulting in expected 4xx
responses (validation errors, not-found, conflict) are logged at WARNING
or INFO level at most, since they represent normal client-driven
outcomes, not system failures.

Retry strategy. Transient Infrastructure failures (e.g., a temporary AI
provider timeout, a momentary storage unavailability) are retried within
the adapter or worker using bounded exponential backoff, per the
retry_worker design in 06-Repository-Structure.md Section 8. Retries are
never applied to errors representing invalid business state (e.g.,
retrying a validation failure achieves nothing and must not be
attempted).

10. Logging & Observability Structured logging. All log output is
    structured (JSON), never freeform string interpolation, so that logs
    are machine-parseable in aggregation tooling. Every log entry
    includes a minimum common set of fields: timestamp, level,
    logger/module name, and request ID (when available).

Correlation IDs. The X-Request-ID header, generated by middleware if not
supplied by the client, is propagated through every layer of a single
request's execution --- including into any queued job created as a
result of that request --- so that a single user action can be traced
end-to-end across the API and Worker processes.

Audit logging. Actions that must produce an AuditLog entry per
02-Domain-Model.md (e.g., resource creation, deletion, permission
changes) are recorded through a single, centralized audit-logging
service in the Application layer, never written ad hoc from individual
route handlers. This guarantees audit coverage is consistent and cannot
be accidentally skipped by a new endpoint.

Metrics. Each layer emits metrics appropriate to its responsibility: the
API layer tracks request counts, latencies, and status code
distributions per route; Workers track job processing duration,
success/failure counts, and queue depth; Infrastructure adapters track
external call latency and error rates (e.g., AI provider call duration).
Metrics are emitted through a single shared interface in
app/infrastructure/logging/ (or a dedicated metrics module), not through
provider-specific client calls scattered through business code.

Tracing. Distributed tracing spans are created at layer boundaries (API
entry, Application use case execution, Infrastructure adapter calls) so
that the time spent in each layer for a given request is individually
visible, supporting future performance investigation without requiring
code changes at that time.

Sensitive data handling. Passwords, JWT secrets, access/refresh tokens,
and full file contents must never appear in logs under any circumstance.
Email addresses and other personally identifying fields are logged only
when operationally necessary and are never logged at DEBUG level in a
way that could be inadvertently left enabled in production. Logging
statements are reviewed for sensitive data exposure as part of every
code review (Section 14).

11. Security Standards JWT. Access and refresh tokens are signed using a
    strong, project-standard algorithm (e.g., HS256 or RS256, chosen
    once and documented in app/infrastructure/config/) with secrets/keys
    sourced exclusively from environment configuration, never hardcoded.
    Access token lifetime and refresh token lifetime match the values
    already reflected in backend/openapi.yaml (expiresIn). Token
    validation (signature, expiry, issuer) happens in a single shared
    dependency in app/api/v1/dependencies/, used by every protected
    route --- never reimplemented per route.

Password hashing. Passwords are never stored or logged in plaintext. A
modern, adaptive hashing algorithm (e.g., bcrypt or Argon2) with an
appropriately tuned work factor is used exclusively through a single
shared utility, so that hashing parameters are defined and upgraded in
one place.

Input validation. Every piece of client-supplied input is validated at
the API boundary via Pydantic schemas matching backend/openapi.yaml
exactly (required fields, formats, lengths, enums, ranges). No route
handler or Application service should assume input is well-formed just
because it passed schema validation for a different, looser purpose.

File validation. Uploaded files are validated against the maximum size
and MIME type allow-list defined in backend/openapi.yaml before any
processing occurs, per the pipeline in 00-Project-Context.md Section 5.
File content type is verified against actual file content (not just the
client-supplied Content-Type header) wherever feasible, since the latter
is trivially spoofable.

Secrets. All secrets (database credentials, JWT signing keys, AI
provider API keys, object storage credentials) are sourced from
environment variables or a dedicated secrets manager, never committed to
source control, and never logged. .env.example (per
06-Repository-Structure.md) documents variable names only, never real
values.

Least privilege. Database credentials, object storage credentials, and
any service-to-service credentials used by the backend are scoped to the
minimum permissions required for their function (e.g., the application's
database user should not have superuser privileges; the object storage
credential should be scoped to the specific bucket it needs).

Dependency management. Third-party Python packages are pinned to
specific versions in a lockfile, and dependency updates are reviewed
deliberately rather than applied automatically without review. Security
advisories for direct and transitive dependencies are monitored as part
of routine maintenance, not left to be discovered incidentally.

12. Testing Standards Unit tests. Cover Domain entities, value objects,
    Domain services, and Application services/use cases with all
    Infrastructure dependencies replaced by mocks/fakes conforming to
    the Domain's repository interfaces. Unit tests must run without a
    database, network access, or any external service, and must execute
    quickly enough to be run on every save during development.

Integration tests. Verify that concrete Infrastructure implementations
(database repositories, storage adapter, queue adapter) correctly
fulfill their Domain-defined contracts against real (test-scoped)
instances of Postgres, object storage, and the queue.

API tests. Exercise the full FastAPI application over HTTP (using the
framework's test client), asserting that responses match the schemas,
status codes, and error envelopes defined in backend/openapi.yaml
exactly. These tests are the primary safeguard that the implementation
has not drifted from the published contract.

Worker tests. Verify the complete lifecycle described in
06-Repository-Structure.md Section 8: a job enqueued with a given
payload results in the correct persisted Analysis, including correct
behavior on analyzer failure and retry exhaustion.

Coverage philosophy. Coverage percentage is a diagnostic signal, not a
target to be gamed. The Domain layer, being the most business-critical
and easiest to test in isolation, is expected to have close to complete
coverage of its invariants and rules. The Application and Infrastructure
layers are expected to have coverage of all realistic success and
failure paths. Coverage numbers are reviewed for gaps in critical logic,
not enforced as an arbitrary global percentage.

Test naming. Test names describe behavior and expected outcome in plain
language (e.g.,
test_upload_with_duplicate_hash_does_not_create_new_asset), not
implementation mechanics (test_upload_service_1). A failing test name
should tell the reader what business expectation broke without opening
the test body.

Fixtures. Shared test data construction (a sample Upload, a sample
DigitalAsset with a valid hash, a sample authenticated user) is
centralized in backend/tests/fixtures/, per 06-Repository-Structure.md
Section 13, so that every test suite constructs domain objects
identically and changes to entity construction only need to be updated
in one place.

Mocks. Mocks and fakes implement the same abstract interfaces defined in
app/domain/repositories/ and Infrastructure adapter interfaces --- never
ad hoc, untyped mock objects --- so that a mock's behavior stays honest
to the real contract it stands in for.

13. Performance Guidelines Database queries. Every repository method is
    written with its query plan in mind: filters use indexed columns
    (Section 8), and no repository method should perform an unbounded
    table scan on a table expected to grow (uploads, digital assets,
    analyses, audit logs).

Pagination. Every list endpoint uses the pagination parameters and
response shape defined in backend/openapi.yaml (page, pageSize,
PaginationMeta). Returning an entire unbounded collection from any list
endpoint is prohibited regardless of current data volume --- pagination
is enforced structurally, not added later "when needed."

Streaming. Large binary content (file downloads, report downloads) is
streamed from object storage directly to the HTTP response rather than
being fully loaded into application memory first, per the downloadReport
behavior in backend/openapi.yaml.

Caching. Read-heavy, rarely-changing data (e.g., the list of available
Analyzers) may be cached at the Infrastructure layer with an explicit,
short, documented TTL. Caching is never applied to data whose staleness
could produce an incorrect trust verdict (e.g., Analysis results are
never cached in a way that could serve a stale or superseded version).

Async programming. I/O-bound operations (database calls, object storage
calls, AI provider calls, queue operations) use FastAPI's async
capabilities end-to-end --- an async route handler must not call a
blocking, synchronous I/O function directly, as doing so blocks the
event loop for all concurrent requests.

Avoiding N+1 queries. Any operation that returns a collection of
entities along with related data (e.g., a list of Analyses with their
Analyzer names) must fetch related data through a single, explicit join
or batched query at the repository layer --- never by looping over
results and issuing one additional query per item.

Batch operations. When an Application use case needs to act on multiple
entities (e.g., creating one Analysis per requested analyzer in POST
/analyses), the underlying repository writes are batched into a single
database round trip wherever the database driver supports it, rather
than issuing one write per entity in a loop.

14. Code Review Checklist Every pull request is reviewed against the
    following, regardless of author seniority:

Architecture compliance. Does the change respect the dependency rules in
06-Repository-Structure.md Section 14? Does business logic live in the
Domain layer, and orchestration in the Application layer, with no
leakage in either direction? Naming. Do file, class, function, and
variable names follow Section 15 (this document) and
06-Repository-Structure.md Section 15 exactly? Testing. Are there unit
tests for new Domain/Application logic, integration tests for new
Infrastructure code, and API tests for any new or changed endpoint? Do
test names clearly describe behavior (Section 12)? Security. Is all new
input validated? Are secrets absent from the diff? Is any new logging
statement free of sensitive data (Section 10)? Performance. Are new
queries indexed appropriately? Is pagination applied to any new list
endpoint? Is there any newly introduced N+1 pattern? Error handling. Are
new failure modes represented by appropriate Domain/Application
exceptions, and mapped correctly to the Error schema at the API boundary
(Section 9)? Documentation. If the change affects the API surface, has
backend/openapi.yaml been updated in the same pull request? If the
change affects the schema, is a migration included? Consistency with
existing documents. Does the change introduce any concept, entity, or
endpoint not already justified by 01--05? If so, the reviewer must block
the change and request a documentation update first, per the guiding
principle in 00-Project-Context.md. 15. Definition of Done A backend
feature or change is not complete --- and must not be merged --- until
all of the following are true:

All new and existing automated tests pass, including unit, integration,
and API test suites relevant to the change. backend/openapi.yaml has
been updated to reflect any change in API behavior, request/response
shape, or error condition, and validates successfully. Any schema change
is accompanied by a corresponding, reviewed Alembic migration.
Structured logging has been added for any new significant operation or
failure mode, following Section 10. The change has been reviewed against
the Security Standards in Section 11, with particular attention to input
validation and secret handling. Error handling follows the standard
exception hierarchy and produces a correctly mapped Error response for
every new failure path. The change has been reviewed by at least one
other engineer against the checklist in Section 14 and received explicit
approval. Relevant documentation (docs/) has been updated if the change
affects anything described in a prior document; no code is merged that
silently contradicts an existing document. 16. Appendix Naming Cheat
Sheet Element Convention Example Python file snake_case.py
analysis_service.py Python class PascalCase AnalysisService Python
function/variable snake_case create_upload Enum PascalCase class,
UPPER_SNAKE_CASE or lowercase members matching OpenAPI enum values
AnalysisStatus.QUEUED Environment variable UPPER_SNAKE_CASE DATABASE_URL
Test file test\_`<module>`{=html}.py test_analysis_service.py Migration
file `<timestamp>`{=html}\_`<description>`{=html}.py
20240115_add_digital_assets_table.py Table name snake_case, plural
digital_assets Column name snake_case, singular sha256_hash Folder Cheat
Sheet Refer to 06-Repository-Structure.md Appendix for the full
repository tree and dependency table. This document does not redefine
folder placement --- only how code within each folder must be written.

Review Checklist (Condensed) Respects layer boundaries and dependency
direction Business rules in Domain, orchestration in Application only
Naming conventions followed Unit / integration / API tests present and
passing backend/openapi.yaml updated if API changed Migration included
if schema changed No secrets, no sensitive data in logs Input and file
validation present at API boundary Pagination applied to new list
endpoints No N+1 query patterns introduced Errors mapped to standard
Error envelope No new business concept introduced without a
corresponding prior document update Common Mistakes Returning an ORM
model or raw dictionary directly from a route handler instead of a
declared response schema. Placing a business rule (e.g., duplicate
detection logic) inside an Application service instead of a Domain
service. Catching a broad Exception in a route handler and returning a
generic error, bypassing the centralized exception-handling mechanism.
Introducing a new magic string or numeric literal instead of a named
constant or enum member. Writing a Domain entity or value object using
Pydantic instead of a framework-free dataclass. Adding a new list
endpoint without pagination, "temporarily," with the intention to add it
later. Logging a full request or response body that may contain a
password, token, or file content. Generating an Alembic migration and
merging it without reviewing the generated diff against
04-Database-Design.md. Modifying backend/openapi.yaml after
implementation, rather than treating it as the contract implementation
must satisfy.

------------------------------------------------------------------------

## 17. Engineering Governance

This document is part of Sentinel's engineering contract and complements
the Project Context, Architecture, Repository Structure, and API
Specification.

### Governance Rules

-   New coding standards should be added here rather than communicated
    informally.
-   Any rule that changes architectural boundaries must first update the
    Architecture and Repository Structure documents.
-   Coding standards should evolve only when they improve consistency,
    correctness, maintainability, or security.
-   Individual preferences must never override documented engineering
    standards.

## 18. Review Notes (v1.0.1)

Review outcome:

-   Verified consistency with Documents 00--06.
-   Reinforced governance for future contributors.
-   No engineering standards, dependency rules, or implementation
    guidance were changed.
