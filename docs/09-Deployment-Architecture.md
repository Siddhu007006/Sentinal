Document Information Document: docs/09-Deployment-Architecture.md
Version: 1.0.2 Status: Final Owner: Infrastructure Architecture Function
(Founding Engineering Team) Audience: Platform engineers, backend
engineers, and any engineer responsible for deploying, operating, or
scaling Sentinel Dependencies: This document describes how the system
defined in 03-Architecture.md (Modular Monolith),
06-Repository-Structure.md (Docker layout),
07-Backend-Development-Standards.md, and 08-Security-Architecture.md
(network isolation, secrets management, least privilege) is deployed and
operated. It introduces no new business functionality, no new
architectural components, and no contradictions to any prior document.

Revision History

Version Date Author Summary 1.0.0 Initial Infrastructure Architecture
Function First canonical deployment architecture. 1. Purpose An
architecture that is correct on paper and fragile in production is not a
correct architecture. Sentinel's Modular Monolith (03-Architecture.md)
was chosen deliberately to minimize operational complexity while
preserving internal module boundaries --- a decision that only pays off
if the deployment topology actually reflects that intent. If deployment
is treated as an afterthought, the boundaries so carefully drawn in the
codebase (06-Repository-Structure.md) and defended in code review
(07-Backend-Development-Standards.md) can be silently undermined by, for
example, running the API and Worker as a single process that shares
failure domains, or by granting every container the same broad network
access.

This document exists to make deployment a first-class engineering
artifact, reviewed with the same rigor as the API contract or the domain
model, for three reasons:

Security depends on it. The network isolation, least-privilege
credentials, and secrets management principles defined in
08-Security-Architecture.md are only real if the runtime topology
actually enforces them --- a firewall rule described in a document but
not implemented in infrastructure provides no protection. Reliability
depends on it. Sentinel's asynchronous pipeline (00-Project-Context.md
Section 5) depends on the API, Workers, Queue, Database, and Object
Storage failing independently and recovering predictably. This is a
deployment property, not a code property. Evolvability depends on it.
The Modular Monolith is explicitly a stepping stone
(06-Repository-Structure.md Section 18) --- its ability to later split
into independently deployable services depends on the deployment
architecture already treating internal components (API, Workers) as
separable units today, not as one indivisible blob. 2. Deployment
Principles Immutable deployments. Once a container image is built for a
given version, it is never modified in place --- a new deployment is
always a new image, never a patch applied to a running instance. This
exists so that what is running in production is always traceable to an
exact, reviewable build artifact, eliminating an entire class of "it
worked when I checked it manually" incidents.

Infrastructure as Code. All infrastructure --- networks, compute,
storage buckets, database instances, firewall rules --- is defined
declaratively in version-controlled configuration (infrastructure/, per
06-Repository-Structure.md), never created or modified through manual
console operations. This exists so that infrastructure changes go
through the same review process as code changes, and so that an
environment can be reconstructed deterministically rather than depending
on undocumented manual steps.

Stateless services. The API and Worker processes hold no durable state
in memory or on local disk between requests or jobs --- all durable
state lives in PostgreSQL or Object Storage. This exists because it is
the precondition for horizontal scalability and zero-downtime
deployment: a stateless process can be started, stopped, or replaced at
any time without data loss.

Horizontal scalability. Capacity is added by running more instances of a
component, not by making a single instance larger. This exists because
it aligns directly with the queue-based, asynchronous design
(00-Project-Context.md Section 5) --- additional Worker instances simply
consume more of the same queue, and additional API instances simply
serve more of the same stateless request load, without requiring any
coordination between instances.

Environment parity. Development, Staging, and Production run the same
container images and the same infrastructure topology, differing only in
configuration (scale, credentials, external endpoints), never in
architecture. This exists because divergent environments are the most
common source of "it worked in staging" failures --- parity converts
environment-specific bugs into configuration bugs, which are far easier
to diagnose.

Zero-downtime deployment. A new version is deployed by bringing up new
instances and directing traffic to them only once healthy, then retiring
old instances --- never by stopping the old version before the new
version is ready. This exists because Sentinel is a platform users
depend on to evaluate content before acting on it; an avoidable outage
during a routine deployment is an unacceptable cost for a purely
operational event.

Reproducibility. Any environment can be rebuilt from its
Infrastructure-as-Code definitions and container images without relying
on the memory or availability of any specific engineer. This exists as
the direct consequence of Infrastructure as Code and Immutable
Deployments combined --- reproducibility is what makes disaster recovery
(Section 13) possible at all.

Least privilege. Every deployed component runs with the minimum network
access, credentials, and system permissions required for its function,
directly extending the least-privilege principle already established in
08-Security-Architecture.md Section 2 from the application layer into
the infrastructure layer.

High availability. Critical components (API, Database, Object Storage)
are deployed such that the failure of a single instance does not cause a
full service outage. This exists because Sentinel's asynchronous
pipeline already tolerates transient delay (a queued analysis can wait),
but it must not tolerate the API itself becoming unreachable, since that
would block the very entry point of the platform.

3.  Runtime Topology Sentinel's runtime topology directly mirrors the
    pipeline established in 00-Project-Context.md and the layered
    architecture in 03-Architecture.md. It consists of the following
    components:

Frontend --- a static asset bundle (per 06-Repository-Structure.md's
React application) served independently of the backend, communicating
with the API exclusively over HTTPS per the API-first principle. API ---
the FastAPI application (app/api/, app/application/, app/domain/,
app/infrastructure/) that terminates all client-facing HTTP traffic. It
is the only component reachable from outside the private network.
Workers --- one or more processes (app/workers/) that consume jobs from
the Queue and execute Analyzers (app/analyzers/). Workers never accept
inbound connections from clients or the Frontend, consistent with
00-Project-Context.md's rule that workers never communicate with
browsers directly. PostgreSQL --- the system of record for all
structured metadata (04-Database-Design.md), reachable only from the API
and Worker components. Redis / Queue --- the durable hand-off mechanism
between the API (producer) and Workers (consumer), reachable only from
the API and Worker components. Object Storage --- the S3-compatible
store for raw binary content (00-Project-Context.md Section 6),
reachable only from the API and Worker components via their storage
adapter. Reverse Proxy / Load Balancer --- the single public ingress
point, responsible for TLS termination, routing, and distributing
traffic across API instances. Monitoring --- the metrics and alerting
system consuming telemetry emitted by the API, Workers, and
Infrastructure adapters (07-Backend-Development-Standards.md Section
10). Logging --- the centralized log aggregation system receiving
structured logs from every component. Backup system --- the automated
process responsible for producing and validating recoverable backups of
PostgreSQL and Object Storage (Section 13). Request flow A typical
synchronous request (e.g., GET /reports/{reportId}) flows: Frontend →
Reverse Proxy (TLS termination) → API instance → PostgreSQL/Object
Storage → API instance → Reverse Proxy → Frontend.

A typical asynchronous flow (e.g., POST /analyses followed by
processing) flows: Frontend → Reverse Proxy → API instance (enqueues
job, returns immediately) → Queue → Worker instance (executes Analyzer,
may call an AI provider through the Infrastructure adapter) → PostgreSQL
(persists Analysis) → later retrieved by Frontend → Reverse Proxy → API
instance → PostgreSQL.

At no point does a Worker instance receive a direct connection from the
Reverse Proxy or the Frontend --- this boundary is enforced at the
network layer (Section 6), not merely by convention.

4.  Deployment Environments Four environments are maintained, consistent
    with the servers already declared in backend/openapi.yaml
    (Development, Staging, Production) plus an internal Testing
    environment used exclusively by automated CI pipelines.

Development --- Purpose: local iteration by individual engineers.
Isolation: fully isolated per engineer, typically run via the local
Docker Compose definition (06-Repository-Structure.md Section 12), with
no shared state between engineers. Configuration differences: uses local
or emulated Object Storage and a local PostgreSQL/Redis instance; AI
provider calls may be directed at sandbox/test credentials. Promotion
policy: code is never promoted from Development directly --- Development
exists solely to validate changes before they enter the Testing/CI
pipeline via a pull request.

Testing --- Purpose: automated execution of the test suites defined in
07-Backend-Development-Standards.md Section 12 (unit, integration, API,
worker) within CI. Isolation: ephemeral --- infrastructure (database,
queue, storage emulation) is provisioned fresh for each CI run and
destroyed afterward, guaranteeing no cross-run contamination.
Configuration differences: uses disposable, minimally-privileged
credentials scoped only to the CI run's lifetime. Promotion policy: a
pull request cannot be merged unless its Testing-environment pipeline
passes in full, per the Definition of Done
(07-Backend-Development-Standards.md Section 15).

Staging --- Purpose: validating a release candidate under
production-like conditions before it reaches real users. Isolation: a
fully separate deployment of every runtime component, with its own
database, queue, and storage bucket --- no data or credentials are
shared with Production. Configuration differences: identical container
images and infrastructure topology to Production (Environment Parity,
Section 2), differing only in scale (typically smaller instance counts)
and the use of non-production external credentials (AI provider sandbox
keys where available). Promotion policy: only artifacts that have passed
the Testing pipeline are deployed to Staging; manual or automated smoke
verification in Staging is a prerequisite for promotion to Production.

Production --- Purpose: serving real users and real data. Isolation: the
only environment with access to production credentials, production AI
provider accounts, and real user data; no engineer or process outside
the deployment pipeline modifies Production infrastructure directly
(Section 14). Configuration differences: full scale, full monitoring and
alerting sensitivity, strictest rate limiting and security header
enforcement. Promotion policy: an artifact reaches Production only after
successful Staging verification and explicit release approval (Section
14) --- there is no direct path from a developer's machine or the
Testing environment to Production.

5.  Container Architecture Consistent with 06-Repository-Structure.md
    Section 12, Sentinel is deployed as a small set of purpose-built
    containers rather than as microservices, reflecting the Modular
    Monolith decision while still allowing independent scaling and
    failure isolation between the API and Worker roles.

Backend (API) container --- Built from docker/backend.Dockerfile. Runs
the FastAPI application (app/api/, app/application/, app/domain/,
app/infrastructure/). Responsibility: terminate HTTP requests, enforce
authentication/authorization, enqueue asynchronous work, and read/write
PostgreSQL and Object Storage through Infrastructure adapters. This
container accepts inbound connections only from the Reverse Proxy.

Worker container --- Built from docker/worker.Dockerfile, from the same
application codebase as the API container but started with a different
entrypoint (app/workers/). Responsibility: consume jobs from the Queue,
execute Analyzers (app/analyzers/), and persist results via the
Application layer. This container accepts no inbound connections at all
--- it is purely a consumer.

Frontend container --- Built from docker/frontend.Dockerfile. Serves the
compiled static React application. Responsibility: deliver the client
application to browsers; it holds no business logic and no credentials,
consistent with the Frontend being an unprivileged API consumer
(06-Repository-Structure.md Section 10).

Database container/service --- Runs PostgreSQL. In Development, this is
a container defined in docker-compose.yml; in Staging and Production,
this is typically a managed database service rather than a self-managed
container, chosen for operational reliability, though the architectural
boundary (a single PostgreSQL endpoint reachable only by API and Worker
containers) is identical in either case.

Redis/Queue container or service --- Runs the queue broker. As with the
database, this may be a managed service in Staging/Production and a
local container in Development, with the same architectural boundary
maintained regardless.

Object Storage --- An S3-compatible service. In Development, this may be
an emulated local container; in Staging and Production, this is a
managed object storage service. The API and Worker containers interact
with it exclusively through the storage adapter
(app/infrastructure/storage/), meaning the underlying implementation can
differ between environments without any application code change --- a
direct benefit of the adapter pattern established in 03-Architecture.md.

Container communication Containers communicate exclusively over the
network paths defined in Section 6 --- there is no shared filesystem or
shared memory between the API and Worker containers. Any data one needs
from the other passes through PostgreSQL, the Queue, or Object Storage,
reinforcing statelessness (Section 2) and mirroring the "workers never
communicate with browsers directly, they store results, backend exposes
results" rule from 00-Project-Context.md.

Container lifecycle Every container exposes a startup sequence that
validates its configuration (Section 7) before accepting traffic or
consuming jobs, and a graceful shutdown sequence that stops accepting
new work, completes in-flight work up to a bounded timeout, and exits
cleanly (Section 10). Containers are never assumed to run indefinitely
without replacement --- the deployment pipeline (Section 11) routinely
replaces running containers with new ones as part of normal operation,
not only during incidents.

6.  Networking Architecture Ingress. The Reverse Proxy/Load Balancer is
    the sole public ingress point for the platform. It terminates client
    connections to the Frontend's static assets and to the API's public
    HTTPS endpoint. No other component in the topology is reachable from
    the public internet, directly implementing the Zero Trust and
    firewall strategy established in 08-Security-Architecture.md Section
    9.

Internal networking. API, Worker, Database, Queue, and Object Storage
components reside within a private network segment. Communication
between them uses internal, non-publicly-routable addresses. This exists
so that even a misconfiguration in the public ingress layer cannot
expose the database or queue directly to the internet --- the private
network boundary is a second, independent layer of defense (Defense in
Depth, 08-Security-Architecture.md Section 2).

TLS termination. TLS is terminated at the Reverse Proxy. Internal service-to-service traffic also uses TLS where supported. for all public
traffic, consistent with the HTTPS-only requirement in
08-Security-Architecture.md Section 7. Internal traffic between the
Reverse Proxy and API instances, and between API/Worker instances and
PostgreSQL/Redis/Object Storage, is also encrypted in transit, ensuring
no unencrypted hop exists anywhere in the request or job-processing
path.

Service communication. The API communicates with PostgreSQL, Redis, and
Object Storage over their respective client protocols, authenticated
with scoped, least-privilege credentials (Section 7). Workers
communicate with the same services identically, but never receive
inbound connections themselves. Neither the API nor the Workers
communicate directly with an AI provider's network location except
through the abstracted adapter (08-Security-Architecture.md Section 8),
which itself only makes outbound calls.

Network isolation. The Worker component's network policy explicitly
denies any inbound connection attempt --- it is a pure consumer of the
Queue and a client of PostgreSQL/Object Storage/AI providers, with no
listening port intended for external or internal peer traffic. This
structurally enforces, at the network level, the architectural rule that
workers never communicate with browsers.

Firewall boundaries. Firewall rules follow a default-deny posture:
PostgreSQL and Redis accept connections only from the API and Worker
containers' network identities; Object Storage accepts connections only
from the same; the Reverse Proxy is the only component with an open
public-facing port. This mirrors and operationally enforces the firewall
strategy already documented in 08-Security-Architecture.md Section 9.

Public vs. private services. Public: Reverse Proxy (and, through it, the
Frontend's static assets and the API's HTTPS endpoint). Private: API's
internal health/readiness endpoints where distinct from public routes,
Workers, PostgreSQL, Redis, Object Storage, and the internal AI provider
adapter's outbound path. This classification is the basis for every
firewall and access-control decision in this section.

7.  Configuration Management Environment variables. All
    environment-specific values (database connection strings, queue
    endpoints, object storage credentials, JWT signing configuration, AI
    provider credentials, CORS allow-lists) are supplied via environment
    variables, never hardcoded in container images, consistent with
    08-Security-Architecture.md Section 9 and
    07-Backend-Development-Standards.md Section 3.

Configuration hierarchy. Configuration is resolved in a single,
deterministic order: built-in application defaults (least specific) are
overridden by environment-specific variables (most specific), with no
environment permitted to silently fall back to a different environment's
values. This exists to prevent a Staging misconfiguration from
accidentally reading Production values, or vice versa.

Secrets. Secrets (database credentials, JWT signing keys, object storage
credentials, AI provider API keys) are managed through a secrets manager
or the deployment platform's equivalent mechanism, injected into
containers at startup rather than baked into images or committed to
Infrastructure-as-Code definitions, per 08-Security-Architecture.md
Section 9.

Feature flags. Sentinel's current Product Requirements and API
Specification do not define a feature-flagging system. No feature-flag
infrastructure is introduced here, as doing so would be a capability not
justified by prior documents. If feature flags become a requirement,
this section must be revised to define their storage, evaluation point,
and audit implications explicitly.

Runtime configuration. All configuration is resolved once at container
startup into a validated, typed settings object
(app/infrastructure/config/, per 07-Backend-Development-Standards.md
Section 7) and is not re-read or mutated during the container's
lifetime. This exists so that a running container's behavior is fully
determined by its startup configuration, making behavior reproducible
and eliminating an entire class of "configuration changed mid-request"
bugs.

Configuration validation. A container that fails configuration
validation at startup (missing required variable, malformed value,
unreachable dependency) exits immediately with a clear error rather than
starting in a degraded or partially-functional state, consistent with
the Fail Safe principle (08-Security-Architecture.md Section 2) extended
to the infrastructure layer. This also ensures the deployment pipeline's
health checks (Section 10) correctly detect misconfiguration before
traffic is routed to the affected instance.

8.  Storage Architecture PostgreSQL persistence. PostgreSQL is the
    durable system of record for all structured metadata defined in
    04-Database-Design.md. Its underlying storage volume is persistent
    and independent of any single API or Worker container's lifecycle
    --- restarting or replacing application containers has no effect on
    database state.

Object storage. Raw binary content (uploaded files) persists in
S3-compatible Object Storage, entirely decoupled from the database and
from any application container's lifecycle, consistent with
00-Project-Context.md's decision to never store files inside PostgreSQL.

Temporary storage. Where a Worker container must materialize file
content to local disk during Analyzer execution
(08-Security-Architecture.md Section 6), this storage is ephemeral,
local to that specific container instance, and never relied upon to
persist beyond a single job's execution --- a Worker container may be
replaced at any time without any expectation that its local disk
contents matter.

Backups. PostgreSQL and Object Storage are each backed up on a regular,
automated schedule independent of application deployment activity.
Backups are stored in a location and with access controls distinct from
the primary data store, so that a compromise or failure affecting
primary storage does not also affect the backup copy.

Retention. Backup retention follows the same data-minimization
discipline established in 08-Security-Architecture.md Section 2 and
Section 11 --- backups are retained long enough to meet recovery
objectives (Section 13) and no longer, avoiding indefinite accumulation
of sensitive data copies.

Recovery. Both PostgreSQL and Object Storage backups are periodically
tested for successful restoration, not merely created and assumed valid
--- an untested backup provides only the appearance of disaster recovery
capability, not the substance of it.

Storage boundaries. No application container ever treats its own local
filesystem as a source of durable truth. This boundary --- durable state
lives only in PostgreSQL and Object Storage --- is what makes the
Stateless Services principle (Section 2) actually true in practice
rather than aspirational.

9.  Scaling Strategy API. Scales horizontally by running additional API
    container instances behind the Reverse Proxy/Load Balancer. Because
    the API is stateless (Section 2), any instance can serve any
    request, and instances are added or removed based on request
    throughput and latency without coordination between instances.

Workers. Scale horizontally by running additional Worker instances, each
independently consuming jobs from the same Queue. Because analysis jobs
are independent units of work (00-Project-Context.md Section 8), Worker
throughput scales linearly with instance count up to the Queue's and
downstream AI providers' own capacity limits. Worker scaling is driven
by queue depth and job processing latency rather than by request volume,
since it operates entirely outside the request/response cycle.

Queue. Scales according to the chosen broker's own horizontal scaling
mechanism (e.g., clustering), sized to sustain the combined enqueue rate
from the API and the consumption rate of all Worker instances without
unbounded queue growth.

Database. PostgreSQL scales vertically first (larger instance) and, if
read load grows beyond a single instance's capacity, through read
replicas for read-heavy query patterns (e.g., listing analyses, reports,
audit logs), with all writes continuing to flow through a single primary
to preserve the transactional integrity required by
04-Database-Design.md.

Object storage. Scales natively and near-limitlessly as a managed
service property, requiring no application-level scaling strategy beyond
ensuring the storage adapter's request patterns (Section 8) do not
introduce unnecessary load (e.g., avoiding redundant re-uploads of
already-deduplicated content, per the hash-based duplicate detection in
02-Domain-Model.md).

Frontend. Scales as a static asset deployment, typically distributed
through a content delivery layer in front of the Reverse Proxy, since it
involves no server-side computation and no state.

Future microservice extraction. When deployed on Kubernetes or an equivalent orchestrator, availability policies (for example disruption budgets and topology spread constraints) should be configured at the orchestration layer rather than implemented in application code.

Future microservice extraction. As anticipated in
06-Repository-Structure.md Section 18, the Worker component --- already
network-isolated, independently containerized, and communicating with
the rest of the system only through the Queue, PostgreSQL, and Object
Storage --- is the component best positioned for extraction into an
independently deployed service should scale eventually require it. This
deployment architecture does not require any topology change to support
that future extraction; it only requires promoting an already-separate
container into an already-separate deployment unit.

10. Availability Health checks. Every container exposes a health check
    distinguishing two concerns: whether the process is alive at all,
    and whether it is currently able to serve traffic or consume work
    correctly.

Readiness. An API instance is marked ready only once it has validated
its configuration (Section 7) and confirmed connectivity to PostgreSQL,
Redis, and Object Storage. The Reverse Proxy routes traffic only to
instances reporting ready, ensuring a newly started instance never
receives requests before it can actually fulfill them.

Liveness. A liveness check confirms the process itself is still
responsive and not deadlocked. A container that fails its liveness check
for a sustained period is restarted automatically, since a hung process
is otherwise indistinguishable from a slow one and would otherwise
silently degrade capacity.

Graceful shutdown. On receiving a termination signal (e.g., during a
deployment or scale-down event), an API instance stops accepting new
connections but allows in-flight requests to complete up to a bounded
timeout before exiting. A Worker instance similarly stops pulling new
jobs from the Queue but completes its current job (or safely returns it
to the Queue) before exiting, preventing a mid-processing analysis job
from being silently lost.

Restart strategy. Failed containers are restarted automatically by the
orchestration layer, with backoff between repeated restart attempts to
avoid a crash-looping container consuming resources indefinitely without
surfacing the underlying problem.

Failure isolation. Because the API and Worker roles run as separate
containers (Section 5), a failure or resource exhaustion in Worker
processing (e.g., a misbehaving AI provider integration) does not
degrade the API's ability to serve requests, and vice versa --- this
separation is itself the primary availability benefit of splitting the
two roles at the container level despite sharing a single codebase.

Recovery. Following any instance failure, the system recovers without
manual intervention: the orchestration layer replaces the failed
instance, the Reverse Proxy stops routing to it once its health check
fails and resumes once a replacement is ready, and any job a failed
Worker had in progress is either resumed (if not yet acknowledged to the
Queue) or retried through the retry mechanism defined in
07-Backend-Development-Standards.md Section 9.

11. Deployment Pipeline Build. A container image is built once per
    commit that passes CI (06-Repository-Structure.md Section 12), from
    the pinned dependencies and formatted, linted, type-checked source
    code required by 07-Backend-Development-Standards.md.

Artifact creation. Container images should additionally be referenced by immutable image digest during deployment wherever the orchestration platform supports it.

Artifact creation. The built image is tagged with an immutable
identifier tied to the source commit, and pushed to an image registry.
This artifact is the single unit that moves through every subsequent
environment --- the same image deployed to Staging is the exact image
later promoted to Production, never rebuilt in between (Immutable
Deployments, Section 2).

Validation. Before deployment to any environment, the artifact must have
passed the full Testing-environment pipeline (unit, integration, API,
worker tests per 07-Backend-Development-Standards.md Section 12) and the
OpenAPI contract validation referenced in 06-Repository-Structure.md
Section 12.

Deployment. The validated artifact is deployed by starting new instances
running the new image alongside existing instances, directing traffic to
new instances only once they report ready (Section 10), then retiring
old instances --- the mechanism underlying Zero-Downtime Deployment
(Section 2).

Rollback. Because artifacts are immutable and every prior artifact
remains available in the registry, rolling back is defined as
redeploying the immediately preceding known-good artifact through the
same deployment mechanism, never as attempting to reverse-patch a
running instance.

Verification. Following deployment to Staging, and again following
deployment to Production, automated smoke checks confirm core request
flows (authentication, upload intake, analysis retrieval) succeed
against the newly deployed instances before the deployment is considered
complete.

Promotion. An artifact is promoted from Staging to Production only after
successful Staging verification, never deployed to Production directly
from a Testing-environment pass alone --- Staging exists specifically to
catch issues that only manifest under production-like infrastructure
conditions.

Release approval. Promotion to Production additionally requires explicit
release approval (Section 14), ensuring a human decision point exists
between "this artifact works in Staging" and "this artifact is now
serving real users."

12. Observability Integration Logging. Every container ships its
    structured logs (08-Security-Architecture.md Section 10) to the
    centralized Logging component continuously, not only on failure, so
    that normal operational behavior is queryable alongside
    incident-time behavior.

Metrics. The API, Workers, and Infrastructure adapters emit the metrics
defined in 07-Backend-Development-Standards.md Section 10 (request
latency and status distribution, job processing duration and outcome,
external call latency) to the Monitoring component, tagged with
environment and instance identity so that Staging and Production
telemetry never intermix.

Tracing. Distributed traces initiated at the API's entry point
(correlated via X-Request-ID, per 08-Security-Architecture.md Section
10) extend across the Queue hand-off into Worker execution, giving
operators visibility into the full lifecycle of a single upload or
analysis request across container and process boundaries.

Alerting. The Monitoring component is configured to alert on conditions
that indicate a violation of this document's availability principles
(Section 10) --- sustained readiness-check failures, abnormal restart
frequency, queue depth growing without bound, or elevated 5xx rates ---
routed to the on-call function responsible for Production per Section
14.

Health monitoring. Readiness and liveness check results (Section 10) are
themselves fed into Monitoring as a continuous signal, not only consumed
by the orchestration layer for restart decisions, so that a pattern of
transient health-check failures is visible to operators even if no
single failure was severe enough to trigger a restart.

13. Disaster Recovery Backups. As established in Section 8, PostgreSQL
    and Object Storage are backed up on a regular, automated schedule to
    a location independent of the primary infrastructure, with periodic
    restoration testing to confirm backup validity.

Recovery objectives. Recovery Point Objective (maximum acceptable data
loss) and Recovery Time Objective (maximum acceptable downtime) are
defined per environment, with Production held to the strictest
objectives given its role serving real users and real data, consistent
with the High Availability principle (Section 2).

Database recovery. In the event of PostgreSQL data loss or corruption,
recovery proceeds by restoring the most recent valid backup to a fresh
database instance, then replaying any available write-ahead log or
transaction log beyond that backup point to minimize data loss, before
redirecting the API and Worker containers to the restored instance.

Object storage recovery. In the event of Object Storage data loss,
recovery proceeds by restoring from the most recent backup snapshot.
Because DigitalAsset records reference content by SHA-256 hash
(02-Domain-Model.md), any restored content's integrity can be
independently verified by recomputing its hash and comparing it against
the corresponding database record --- a direct, built-in integrity check
that the deployment architecture inherits for free from the domain
model's design.

Infrastructure rebuild. Because all infrastructure is defined as code
(Section 2), a full environment --- networking, compute, database
instance, queue, storage buckets --- can be reconstructed from its
Infrastructure-as-Code definitions in the event of a complete
environment loss, with data subsequently restored from the most recent
valid backup. This capability is what makes Reproducibility (Section 2)
a disaster recovery guarantee rather than merely a convenience.

14. Deployment Governance Versioning. Every deployed artifact is
    versioned according to its source commit, per Section 11, and every
    API-visible change is additionally versioned according to the API
    versioning policy in 07-Backend-Development-Standards.md Section 4
    --- deployment versioning and API versioning are related but
    distinct concerns, and both are tracked explicitly.

Release ownership. Each Production release has a clearly identified
responsible engineer or team who initiated the promotion, accountable
for monitoring the release's verification (Section 11) and for
coordinating any necessary rollback.

Rollback authority. Any engineer observing a Production incident
attributable to a recent deployment has the authority to initiate an
immediate rollback to the last known-good artifact (Section 11) without
requiring prior approval, consistent with prioritizing availability
recovery speed over process formality during an active incident.
Post-rollback review follows the same process as any other incident
(08-Security-Architecture.md Section 13).

Infrastructure changes. Changes to Infrastructure-as-Code definitions
follow the same review process as application code changes
(07-Backend-Development-Standards.md Section 14) --- no infrastructure
change is applied to Staging or Production without having been reviewed
and merged through version control first.

Change approval. Promotion to Production (Section 11) requires explicit
approval from a designated release approver, distinct from the engineer
who authored the change where practical, consistent with the Separation
of Duties principle established in 08-Security-Architecture.md Section
2.

15. Future Evolution The following directions are not implemented today
    because current scale and product requirements do not yet justify
    their additional operational complexity, but the architecture
    described in this document does not foreclose any of them:

Multi-region deployment. The stateless design of the API and Worker
containers (Section 2) means additional regions could run identical
copies of these components; the primary evolution required would be in
the Database and Object Storage layers (replication or multi-region
managed service tiers), not in application architecture.

Multi-cloud. Because Object Storage and AI provider access are already
mediated through Infrastructure adapters (03-Architecture.md,
08-Security-Architecture.md Section 8), migrating or distributing across
cloud providers primarily involves reconfiguring or extending those
adapters, not rewriting Application or Domain logic.

Autoscaling. The horizontal scaling strategy described in Section 9 is a
natural precondition for automated autoscaling based on request
throughput (API) or queue depth (Workers), which can be introduced as an
operational policy without any change to the underlying container or
network architecture.

Kubernetes (or equivalent orchestration). The container-per-role
architecture in Section 5, combined with the health check and graceful
shutdown behavior in Section 10, is already shaped to map directly onto
a container orchestration platform's deployment and scaling primitives,
should the operational complexity of managing containers directly exceed
what the current deployment pipeline (Section 11) comfortably supports.

Managed services. Staging and Production already favor managed database,
queue, and object storage services over self-managed containers (Section
5) where practical; further migration toward managed services for any
remaining self-managed component follows the same rationale --- reduced
operational burden without any change to the application's view of these
components through their adapters.

Enterprise deployment. Should Sentinel need to be deployed within a
customer's own infrastructure rather than operated centrally, the
Infrastructure-as-Code and environment-parity principles (Section 2)
already provide the foundation for a repeatable, documented deployment
process --- this would primarily require packaging existing definitions
for external consumption, not redesigning them.

Appendix Deployment Topology (Summary) text

                         ┌────────────────────┐
                         │   Reverse Proxy /   │
                         │   Load Balancer      │  ← Public HTTPS ingress (only public entry point)
                         └─────────┬───────────┘
                                   │
                 ┌─────────────────┼─────────────────┐
                 │                                     │
        ┌────────▼────────┐                  ┌─────────▼─────────┐
        │  Frontend (static)│                  │   API instances    │
        └───────────────────┘                  │   (stateless,       │
                                                │   horizontally      │
                                                │   scaled)            │
                                                └─────────┬───────────┘
                                                          │
                          ┌───────────────────────────────┼───────────────────────────────┐
                          │                                │                                │
                  ┌───────▼───────┐               ┌────────▼────────┐             ┌─────────▼─────────┐
                  │  PostgreSQL     │               │  Redis / Queue    │             │  Object Storage      │
                  │  (system of      │◄──────────────┤                     ├────────────►│  (S3-compatible)      │
                  │   record)         │               │                     │             │                        │
                  └───────▲───────┘               └────────┬────────┘             └─────────▲─────────┘
                          │                                 │                                │
                          │                        ┌────────▼────────┐                       │
                          └────────────────────────┤  Worker instances │───────────────────────┘
                                                     │  (no inbound        │
                                                     │   connections)       │
                                                     └────────┬────────┘
                                                              │
                                                     ┌────────▼────────┐
                                                     │  AI Providers      │
                                                     │  (via adapter,       │
                                                     │   outbound only)     │
                                                     └───────────────────┘

        Logging & Monitoring receive telemetry from every component above (not shown for clarity).

Component Communication Matrix From  To Reverse Proxy Frontend API
Worker PostgreSQL Redis/Queue Object Storage AI Providers Public
Internet Inbound HTTPS --- --- --- --- --- --- --- Reverse Proxy ---
Serves static assets Routes requests --- --- --- --- --- API --- --- ---
Enqueues jobs Read/Write Produce Read/Write --- Worker --- --- --- ---
Read/Write Consume Read/Write Outbound calls PostgreSQL --- --- --- ---
--- --- --- --- Redis/Queue --- --- --- --- --- --- --- --- Object
Storage --- --- --- --- --- --- --- --- AI Providers --- --- --- --- ---
--- --- --- Blank cells indicate no permitted connection; this matrix is
the basis for firewall rule definitions (Section 6).

Environment Comparison Aspect Development Testing Staging Production
Purpose Local iteration Automated CI validation Pre-release verification
Serving real users Data Local/synthetic Ephemeral, disposable
Non-production, production-like Real, sensitive Infrastructure Local
containers Ephemeral CI-provisioned Full topology, smaller scale Full
topology, full scale Credentials Local/dummy Disposable, CI-scoped
Non-production Production, most restricted Deployment trigger Manual,
local Automatic on PR Automatic on merge to main Manual approval
required Monitoring sensitivity Minimal N/A Moderate Highest Deployment
Checklist Artifact built from a commit that passed linting, type
checking, and the full Testing-environment pipeline.
backend/openapi.yaml validated and, if changed, reviewed for consistency
with the deployed artifact's actual behavior. Any accompanying database
migration reviewed and confirmed reversible, per
07-Backend-Development-Standards.md Section 8. Configuration for the
target environment validated (Section 7) with no missing or
default-fallback secrets. Health check, readiness, and graceful shutdown
behavior confirmed for any new or modified container. Staging
verification completed successfully before Production promotion is
requested. Release approval obtained per Section 14 before deployment to
Production. Rollback artifact identified and available before deployment
begins. Monitoring and alerting confirmed to be receiving telemetry from
the newly deployed instances before the deployment is considered
complete.

------------------------------------------------------------------------

## 16. Deployment Decision Records

This section summarizes the permanent deployment decisions established
by this document.

-   Immutable container images are the only deployable artifacts.
-   Infrastructure is managed exclusively through Infrastructure as
    Code.
-   API and Worker roles are deployed as separate runtime units.
-   All durable application state resides only in PostgreSQL or Object
    Storage.
-   The Reverse Proxy is the sole public ingress.
-   Internal services remain private by default.
-   Horizontal scaling is the preferred scaling strategy.
-   Staging is the mandatory promotion gate before Production.
-   Production releases require explicit approval and support immediate
    rollback.

## 17. Operational Readiness Checklist

A deployment is operationally ready only when all of the following are
satisfied:

-   Infrastructure changes have been reviewed.
-   Environment configuration has been validated.
-   Secrets have been provisioned securely.
-   Health, readiness, and liveness checks succeed.
-   Monitoring, logging, and alerting are active.
-   Backup and recovery procedures have been verified.
-   Rollback has been validated.
-   Release ownership has been assigned.
