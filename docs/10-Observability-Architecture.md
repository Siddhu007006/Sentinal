Document Information Document: docs/10-Observability-Architecture.md
Version: 1.0.2 Status: Final Owner: Site Reliability Engineering
Function (Founding Engineering Team) Audience: Backend engineers,
platform engineers, on-call responders, and any engineer operating
Sentinel in production Dependencies: This document defines the
observability layer for the system already described in
03-Architecture.md (Modular Monolith layering),
06-Repository-Structure.md (module boundaries),
07-Backend-Development-Standards.md (logging/error-handling standards),
08-Security-Architecture.md (audit and security event requirements),
09-Deployment-Architecture.md (runtime topology), and
backend/openapi.yaml (API surface). It introduces no new business
functionality and no architectural components beyond telemetry
collection, analysis, and alerting.

Revision History

Version Date Author Summary 1.0.0 Initial Site Reliability Engineering
Function First canonical observability architecture. 1. Purpose
Sentinel's core promise is to explain why something should or should not
be trusted (00-Project-Context.md). It would be a contradiction for the
system that produces that explanation to be itself unexplainable when
something goes wrong inside it. Observability is the mechanism by which
Sentinel's own behavior remains explainable --- to engineers, in
production, under pressure --- in the same way Analysis and Report make
an asset's trustworthiness explainable to users.

Logs alone are insufficient for operating a system with Sentinel's shape
for three concrete reasons rooted in the architecture already defined:

The pipeline spans multiple runtime components. A single upload flows
through the API, the Queue, a Worker, an Analyzer, and possibly an
external AI provider (00-Project-Context.md Section 8;
09-Deployment-Architecture.md Section 3). A log line from any single
component tells you what happened there --- it cannot by itself tell you
how a specific user's request behaved end-to-end. That requires
correlation and tracing, not just logging.

Asynchronous processing hides failure. Because analysis is deliberately
decoupled from the request/response cycle (00-Project-Context.md Section
4), a failure inside a Worker does not produce an HTTP error an engineer
would notice by simply watching API traffic. Without metrics on queue
depth, job outcome, and processing latency, a stalled or silently
failing analysis pipeline can go undetected until a user complains.

Numbers, not narratives, answer operational questions. "Is the system
healthy?", "Are we within our latency objective?", and "Is queue depth
growing faster than we can process it?" are quantitative questions. Logs
are the record of what happened; metrics are the record of how much and
how often; traces are the record of where time was spent across
components. Sentinel requires all three, integrated, not logs used to
answer questions they were never designed to answer efficiently.

This document treats observability as an architectural layer with the
same rigor as the API or data layer --- with defined ownership, defined
data shapes, and defined objectives --- rather than as an operational
afterthought bolted on after incidents occur.

2.  Observability Principles Structured logging. Every log entry is
    emitted as structured data (not free text), consistent with
    07-Backend-Development-Standards.md Section 10. This exists because
    structured data can be filtered, aggregated, and correlated
    programmatically at scale; free-text logs require human
    pattern-matching that does not scale past a handful of engineers or
    a handful of requests per second.

Single source of truth. Each class of telemetry (logs, metrics, traces)
has exactly one authoritative destination system; no component writes
the same telemetry to two independently-queried places. This exists to
prevent the specific failure mode where two dashboards disagree because
they read from different, silently diverging copies of the same
underlying data.

Correlation IDs. Every unit of work --- an HTTP request, a queued job, a
worker execution --- carries the X-Request-ID established in
08-Security-Architecture.md Section 7, propagated across every component
it touches. This exists because Sentinel's asynchronous, multi-component
pipeline (Section 1) makes it otherwise impossible to reconstruct a
single user action from independently-timestamped log lines.

Traceability. Every Analysis and Report outcome must be traceable back
through the specific API request, queue message, and worker execution
that produced it. This exists because Sentinel's explainability
principle (00-Project-Context.md Section 4) applies as much to the
platform's own operational behavior as to the verdicts it produces ---
an engineer must be able to answer "why did this analysis take four
minutes" or "why did this analysis fail" with evidence, not speculation.

High signal-to-noise ratio. Telemetry that does not inform a decision
--- an alert no one acts on, a log level enabled that floods aggregation
with routine detail, a dashboard panel no one reads --- is actively
removed, not left in place "just in case." This exists because
low-quality telemetry has a real cost: it trains engineers to ignore
signals, which is more dangerous than having no signal at all.

Actionable alerts. Every alert configured in the system corresponds to a
condition that requires a human decision or action, and states clearly
what that action should be. This exists because an alert that fires with
no clear next step trains on-call responders toward alert fatigue,
undermining the entire alerting system's credibility over time.

Minimal operational overhead. Observability instrumentation is added at
architectural boundaries (API entry, Application service invocation,
Infrastructure adapter calls) rather than scattered ad hoc throughout
business logic, consistent with the layered instrumentation approach
already implied in 07-Backend-Development-Standards.md Section 10. This
exists so that adding observability does not itself become a maintenance
burden that competes with feature and reliability work.

Production-first visibility. Telemetry is designed primarily around what
an engineer needs to know while operating Production, with Development
and Staging telemetry treated as useful but secondary. This exists
because Production is the only environment where real users are affected
by what observability fails to reveal (09-Deployment-Architecture.md
Section 4) --- instrumentation decisions are made by asking "would this
help someone on-call for Production," not "would this help someone
debugging locally."

3.  Observability Architecture Telemetry flows through Sentinel's
    runtime topology (09-Deployment-Architecture.md Section 3) as
    follows:

text

API ↓ Workers ↓ Infrastructure (Database, Queue, Object Storage, AI
Providers) ↓ Logs ──────────┐ Metrics ────────┼──→ Centralized
Aggregation ──→ Dashboards ──→ Engineers Traces ────────┘ ──→ Alerts ──→
On-Call API --- Emits structured logs for every request (Section 4),
metrics for request volume/latency/status (Section 5), and originates
the trace span for every request (Section 6). This is the point at which
the X-Request-ID correlation identifier is established or accepted from
the client, per 08-Security-Architecture.md Section 7.

Workers --- Emit structured logs for every job consumed (Section 4),
metrics for job processing outcome and duration (Section 5), and
continue the trace initiated at the API when the job's originating
request is known, or begin a new trace for scheduled/system-triggered
work (Section 6).

Infrastructure (Database, Queue, Object Storage, AI Providers) --- Each
adapter (09-Deployment-Architecture.md Section 5) emits metrics for call
latency and error rate, and contributes trace spans representing time
spent in that specific dependency, so that a slow request or job can be
attributed to a specific downstream system rather than treated as an
undifferentiated delay.

Logs / Metrics / Traces --- The three telemetry types are collected
independently but share the same correlation identifier and the same
environment/instance tagging (09-Deployment-Architecture.md Section 12),
which is what allows an engineer to pivot from a metric anomaly, to the
relevant trace, to the specific log lines, without re-deriving context
at each step.

Centralized Aggregation --- All telemetry, regardless of which container
or component emitted it, flows to environment-scoped centralized systems
(one logging destination, one metrics destination, one tracing
destination per environment), consistent with the Single Source of Truth
principle (Section 2). Staging and Production telemetry are never
intermingled, matching the environment isolation already established in
09-Deployment-Architecture.md Section 4.

Dashboards --- Present aggregated telemetry in the operational views
defined in Section 9, giving engineers a starting point for both routine
health checks and incident response without requiring ad hoc querying
for common questions.

Alerts --- Are derived from the same metrics and logs feeding the
dashboards, evaluated continuously against the thresholds defined by the
Service Level Objectives (Section 10) and the alerting strategy (Section
8), and routed to the on-call function defined in
09-Deployment-Architecture.md Section 14.

Engineers --- Are the end consumers of every stage above. This
architecture exists to serve them: to answer, as quickly and reliably as
possible, "is the system healthy," "what is happening right now," and
"why did this specific thing happen."

4.  Logging Architecture Structured logging. Every log entry is emitted
    in a consistent structured (JSON) format, never as an interpolated
    free-text string, per 07-Backend-Development-Standards.md
    Section 10. This is what allows logs to be filtered by field (e.g.,
    all logs for a given analysisId) rather than searched by substring.

Log format. Every log entry carries a minimum common set of fields:
timestamp (UTC, per 07-Backend-Development-Standards.md Section 3), log
level, the emitting component and module, the correlation ID
(X-Request-ID), and environment/instance identity
(09-Deployment-Architecture.md Section 12). Entries relevant to a
specific domain entity additionally carry that entity's identifier
(e.g., uploadId, assetId, analysisId) so that entity-scoped
investigation does not require string matching against free text.

Log levels. DEBUG is reserved for local Development use and is not
enabled by default in Staging or Production, consistent with the
sensitive-data risk noted in 08-Security-Architecture.md Section 8
regarding AI provider interactions. INFO records normal, expected
operational events (a request completed, a job was consumed). WARNING
records anomalous but handled conditions (a validation rejection, an
authorization denial, a retried transient failure). ERROR records
failures requiring investigation (an unhandled exception resulting in a
5xx response, a job that exhausted its retry budget). This tiering
exists so that filtering by level alone gives an engineer a meaningful
first cut of relevant information without an initial flood of noise.

Context propagation. The correlation ID and relevant entity identifiers
established at the point a request enters the API are propagated through
every layer the request touches --- Application services, Domain
operations, Infrastructure adapter calls --- and, critically, into the
Queue message payload so that the Worker consuming that job can continue
logging under the same correlation ID. This exists because, absent
explicit propagation, the asynchronous boundary between the API and
Workers would otherwise sever the connection between "a user requested
this analysis" and "this worker executed it."

Correlation IDs. As established in 08-Security-Architecture.md Section 7
and Section 10, X-Request-ID is the single correlation mechanism used
throughout the platform. No parallel or component-specific correlation
identifier scheme is introduced, consistent with the Single Source of
Truth principle (Section 2).

Sensitive data redaction. Consistent with 08-Security-Architecture.md
Sections 8 and 10, log entries never contain passwords, JWTs, full file
contents, full AI provider prompts/responses, or unnecessary personally
identifying information. Redaction is enforced as a structural property
of the logging helper used throughout the codebase
(app/infrastructure/logging/, per 06-Repository-Structure.md), not left
to the discretion of each call site, so that a new log statement cannot
accidentally reintroduce a previously-fixed leakage class.

Log retention. Logs are retained for a duration sufficient to support
incident investigation and any applicable compliance requirement, as
already specified in 08-Security-Architecture.md Section 10, with
Production retention held longer than Staging or Development given its
role as the environment of record for real user activity.

Audit logs. AuditLog entries (02-Domain-Model.md) are a distinct,
business-meaningful record --- not a byproduct of operational logging
--- and are written through the single centralized audit-logging path
described in 08-Security-Architecture.md Section 10. Operational logs
may reference the same event (e.g., an INFO log line noting a user was
deactivated) but the AuditLog record itself remains the authoritative,
immutable, and separately-retained account of that action, consistent
with Immutable Audit Trails (08-Security-Architecture.md Section 2).

Centralized aggregation. Every container defined in
09-Deployment-Architecture.md Section 5 ships its logs continuously to a
single, environment-scoped aggregation destination, never leaving logs
solely on local container disk, which would otherwise be lost the moment
a stateless container (Section 2 of 09-Deployment-Architecture.md) is
replaced.

5.  Metrics Architecture

Where supported by the telemetry backend, histogram exemplars should link latency metrics to representative traces to accelerate incident investigation.
 Metrics are grouped by the component or
    capability they describe. Each metric exists to answer a specific
    operational question that logs alone cannot answer efficiently at
    scale.

API --- Request count, latency distribution, and status code
distribution, each broken down by route and method. Why: answers "is the
API healthy and fast," and, broken down by route, isolates whether a
problem is platform-wide or specific to one capability (e.g., uploads
degrading while reports remain healthy).

Workers --- Job consumption rate, job processing duration, job outcome
(succeeded/failed/retried/cancelled), broken down by analyzer type. Why:
the asynchronous pipeline's health is invisible from the API's
perspective alone (Section 1); these metrics are the only way to know
whether analysis is actually completing, and which analyzer type is
responsible if it is not.

Queue --- Queue depth (messages waiting), enqueue rate, consumption
rate, and message age (time between enqueue and consumption start). Why:
queue depth growing faster than consumption rate is the earliest warning
sign of Worker under-capacity or a downstream dependency slowdown, well
before it becomes a user-visible delay.

Database --- Query latency distribution, connection pool utilization,
and transaction outcome (committed/rolled back), broken down by the
repository/operation issuing the query where feasible. Why: PostgreSQL
is the system of record for every entity in 02-Domain-Model.md; degraded
database performance affects every capability simultaneously, so its
health must be visible independent of any single endpoint's metrics.

Object Storage --- Upload/retrieve/delete call latency and error rate.
Why: object storage is on the critical path for both the upload intake
pipeline and report/file retrieval (00-Project-Context.md Section 8);
its latency directly determines user-perceived upload and download
performance.

AI Providers --- Call latency, error rate, and rate-limit/throttling
occurrence, broken down by provider and analyzer. Why: AI provider calls
are the least controllable dependency in the system
(08-Security-Architecture.md Section 8) and the most likely source of
variable latency; isolating their contribution prevents misattributing
AI provider slowness to Sentinel's own Worker or Analyzer code.

Authentication --- Login success/failure rate, token refresh rate, and
refresh-token revocation rate. Why: a spike in login failures is an
early indicator of credential-stuffing activity
(08-Security-Architecture.md Section 3); a drop in successful logins is
an early indicator of an authentication-path outage.

Uploads --- Upload creation rate, validation rejection rate (by
rejection reason: size, MIME type, magic-byte mismatch), and
duplicate-detection hit rate. Why: the duplicate-hit rate quantifies the
real-world effectiveness of the hash-based deduplication design
(02-Domain-Model.md); rejection-reason breakdown distinguishes user
error from a misconfigured allow-list or an attempted abuse pattern.

Analyses --- Analysis creation rate, completion rate, verdict
distribution (trusted/suspicious/malicious/phishing/inconclusive), and
version-count distribution per asset/analyzer pair. Why: verdict
distribution is a product-health signal as much as an operational one
--- a sudden shift toward inconclusive across many analyses may indicate
an Analyzer regression or an AI provider degradation rather than a
genuine change in uploaded content.

Reports --- Report generation rate and report download rate, broken down
by format (json/pdf/html). Why: confirms that completed analyses are
actually being consumed as reports, and surfaces whether any specific
format's rendering path is disproportionately slow or failing.

6.  Distributed Tracing Request tracing. Every inbound HTTP request to
    the API originates a trace, with the root span covering the full
    request lifecycle from the Reverse Proxy handoff
    (09-Deployment-Architecture.md Section 3) to the response being
    returned. This exists to give a single, navigable timeline of
    exactly where a request spent its time --- in validation, in a
    database call, in an Infrastructure adapter --- rather than an
    aggregate latency number with no internal breakdown.

Queue tracing. When the API enqueues an analysis job (POST /analyses),
the trace context is attached to the queue message alongside the
correlation ID (Section 4). This exists so that the delay between "job
enqueued" and "job consumed" --- itself a meaningful signal per Section
5's queue metrics --- is visible as an explicit span within the same
trace, rather than appearing as a gap with no attributable cause.

Worker tracing. When a Worker consumes a job carrying trace context, it
continues the same trace rather than starting a new, disconnected one,
with a span covering job consumption, Analyzer execution, and result
persistence. This exists to fulfill the Traceability principle (Section
2): an engineer investigating why a specific Analysis took an unusually
long time can view a single, continuous trace spanning the original API
request through to the Worker's completion of that analysis.

External API tracing. Calls to AI providers, made through the
Infrastructure adapter (08-Security-Architecture.md Section 8), are
represented as explicit child spans within the Worker's trace, tagged
with the provider and analyzer involved but never with the request or
response content itself (consistent with the prompt-logging restrictions
in 08-Security-Architecture.md Section 8). This exists to isolate AI
provider latency as a distinct, attributable segment of total analysis
time.

Database tracing. Significant database operations (particularly those
backing repository methods invoked from the Application layer, per
07-Backend-Development-Standards.md Section 5) are represented as child
spans within the relevant API or Worker trace, allowing slow-query
investigation to be scoped to the specific business operation that
triggered it rather than requiring a separate, uncorrelated
database-side investigation.

Trace propagation. Trace context propagates through every layer boundary
defined in 03-Architecture.md (API → Application → Domain →
Infrastructure) and across the asynchronous Queue boundary (Section 4),
consistent with the Traceability principle. No layer is permitted to
silently drop trace context, as doing so would break the end-to-end
visibility this section depends on.

Trace identifiers. The trace identifier and the X-Request-ID correlation
identifier are kept consistent and cross-referenceable --- logs
reference the correlation ID, traces reference the same identifier as a
trace attribute --- so that an engineer can pivot from a log line to its
full trace, or from a trace to its corresponding logs, without
maintaining two separate mental mappings.

7.  Health Monitoring Health checks. As established in
    09-Deployment-Architecture.md Section 10, every container exposes a
    distinction between "the process is alive" and "the process can
    currently serve traffic or consume work correctly." Observability's
    role is to make both signals continuously visible to engineers, not
    just to the orchestration layer that acts on them automatically.

Readiness. An API instance's readiness state --- and the specific
dependency check (database, queue, object storage) that caused a
not-ready state, if any --- is surfaced as a metric and logged on
transition, so that a pattern of instances repeatedly failing readiness
against a specific dependency is visible as a trend, not just as
individual, easily-dismissed restart events.

Liveness. Liveness check outcomes are similarly tracked as a metric over
time. A rising rate of liveness failures, even if each individual
failure is automatically remediated by a restart
(09-Deployment-Architecture.md Section 10), is itself an actionable
signal of underlying instability that warrants investigation before it
escalates.

Dependency health. The API and Worker containers' own health checks
incorporate the reachability of their critical dependencies (Section 3's
Infrastructure layer), and each dependency's specific health is also
monitored independently and directly, so that a database or queue
degradation is visible as its own signal rather than only being
inferable indirectly through API/Worker readiness failures.

Queue health. Beyond the queue depth and latency metrics in Section 5,
the queue broker's own availability is monitored directly (connection
success, cluster status where applicable), since a queue outage affects
every asynchronous capability in the platform simultaneously and must be
distinguishable from a mere capacity/backlog issue.

Database health. PostgreSQL's availability, replication lag (if read
replicas are in use, per 09-Deployment-Architecture.md Section 9), and
connection saturation are monitored directly, independent of any single
API route's latency, since database degradation is a platform-wide risk.

Storage health. Object Storage availability and error rate are monitored
directly as an infrastructure-level signal, distinct from the per-call
metrics in Section 5, to detect a broader storage-service-level incident
versus an isolated client-side call failure.

AI provider health. Each configured AI provider's availability and error
rate are monitored as a distinct dependency health signal, given their
categorization in 08-Security-Architecture.md Section 8 and
09-Deployment-Architecture.md as the least controllable external
dependency --- engineers must be able to quickly determine "is this our
problem or the provider's" during an incident.

8.  Alerting Strategy Critical alerts page the on-call function
    immediately and represent conditions where user-facing capability is
    degraded or at imminent risk: API unavailability, database
    unreachability, queue unavailability, sustained elevated 5xx rate,
    or a Service Level Objective (Section 10) being actively breached.
    These exist because delay in response directly translates to
    extended user impact.

Warning alerts notify the responsible team without necessarily paging
immediately, representing conditions that are not yet user-impacting but
are trending toward a critical state: queue depth growing steadily,
elevated authentication failure rate potentially indicating
credential-stuffing activity (08-Security-Architecture.md Section 3), or
an AI provider's error rate rising but not yet fully unavailable. These
exist to enable proactive intervention before a Critical alert is
warranted.

Operational alerts are informational, routed to a non-paging channel,
and represent conditions worth awareness but no immediate action: a
scheduled backup completing successfully, a routine capacity threshold
being approached (Section 11), or a deployment completing
(09-Deployment-Architecture.md Section 11). These exist to keep
engineers informed of system state without contributing to alert fatigue
for conditions requiring no response.

Noise reduction. Every alert is deliberately reviewed against the
Actionable Alerts principle (Section 2) before being enabled and
periodically thereafter; an alert that fires repeatedly without ever
requiring action is either recalibrated or removed. This exists because
an alerting system's long-term effectiveness depends entirely on the
on-call responder trusting that every page requires genuine attention.

Escalation. A Critical alert that is not acknowledged within a defined
window automatically escalates to a secondary responder or a broader
team, consistent with the Release Ownership and Rollback Authority
principles in 09-Deployment-Architecture.md Section 14 --- availability
of a clear escalation path is itself a reliability property, not a
separate concern.

On-call philosophy. On-call responders are equipped, by the dashboards
(Section 9) and traceability (Section 6) described in this document, to
diagnose and mitigate the majority of Critical alerts without requiring
the original author of the affected code to be immediately available.
This exists because bus-factor risk in incident response is itself an
availability risk (09-Deployment-Architecture.md Section 2, High
Availability).

Alert ownership. Every alert has a clearly identified owning team or
function responsible for its continued accuracy and relevance,
consistent with the Operational Governance model in Section 13 --- an
alert with no owner is an alert no one is accountable for maintaining,
and is a candidate for removal.

9.  Dashboards Each dashboard exists to answer a specific, recurring
    operational question at a glance, without requiring ad hoc query
    construction.

Platform Overview --- Aggregate request rate, error rate, and latency
across the entire API; overall queue depth and worker processing rate.
Answers: "Is Sentinel healthy right now, at a glance?" --- the first
dashboard opened during any suspected incident.

API --- Per-route request rate, latency distribution, and status code
breakdown, matching the resource groups in backend/openapi.yaml.
Answers: "Which specific capability, if any, is degraded?"

Workers --- Job consumption rate, processing duration, and outcome
breakdown per analyzer type. Answers: "Is analysis processing keeping
pace with demand, and which analyzer, if any, is responsible for a
slowdown or failure spike?"

Queue --- Queue depth over time, message age distribution, enqueue
vs. consumption rate. Answers: "Is the asynchronous pipeline backing up,
and how quickly?"

Database --- Query latency, connection pool utilization, transaction
outcome rate. Answers: "Is the system of record itself a bottleneck or
risk right now?"

Uploads --- Upload creation rate, validation rejection breakdown,
duplicate-detection hit rate. Answers: "Is the intake pipeline healthy,
and is deduplication behaving as designed?"

AI Providers --- Per-provider call latency, error rate, and throttling
occurrence. Answers: "Is an external AI dependency responsible for
degraded analysis performance?"

Infrastructure --- Container health (readiness/liveness pass rate),
resource utilization (Section 11), and deployment status per
09-Deployment-Architecture.md Section 12. Answers: "Is the underlying
runtime environment itself healthy?"

Security --- Authentication success/failure trends, authorization denial
rate, rate-limit trigger frequency, and audit log volume, directly
supporting the security monitoring described in
08-Security-Architecture.md Section 13. Answers: "Is there an ongoing
security-relevant anomaly requiring investigation?"

10. Service Level Objectives Sentinel's Service Level Objectives (SLOs)
    are defined as a framework here; specific numeric targets are owned
    and periodically reviewed by the function identified in Section 13,
    since committing to arbitrary numbers without operational data would
    itself violate the evidence-based philosophy underlying this entire
    platform (00-Project-Context.md Section 4).

Availability objectives. Measured as the proportion of API requests that
receive a successful (non-5xx) response over a rolling window, scoped
separately for synchronous read/write operations (uploads, listings,
authentication) since these represent the platform's baseline "is it
usable at all" contract with users.

Latency objectives. Measured as the proportion of API requests
completing within a defined latency threshold, per route category,
distinguishing lightweight operations (authentication, listings) from
inherently heavier operations (upload intake, which involves hashing and
storage per 00-Project-Context.md Section 8). A single latency target
across all routes would be architecturally dishonest given these
categories have fundamentally different expected costs.

Queue processing objectives. Measured as the proportion of enqueued
analysis jobs that begin processing within a defined time window of
being enqueued. This exists as a distinct objective from API latency
because the asynchronous pipeline's user-perceived performance is
governed by queue-to-worker latency, not API response time --- the API
response for POST /analyses is fast by design (202 Accepted, per
backend/openapi.yaml), so API latency alone would not reveal a degraded
analysis experience.

Upload objectives. Measured as the proportion of valid uploads that
complete the full intake pipeline (validation through storage) within a
defined time window, and the proportion of upload attempts that fail due
to platform error (as opposed to legitimate validation rejection, which
is not a platform failure and must be excluded from this measurement).

Analysis objectives. Measured as the proportion of queued analyses that
reach a terminal state (completed or failed, per backend/openapi.yaml's
AnalysisStatus) within a defined time window, and separately, the
proportion that reach completed rather than failed. These are tracked as
two distinct objectives because a slow-but-eventually-successful
analysis pipeline and a fast-but-frequently-failing one represent very
different operational problems requiring different responses.

Error budget philosophy. Each SLO implies an error budget --- the
acceptable amount of objective-violating behavior within a measurement
window. Consuming the error budget faster than the window allows is
treated as a signal to prioritize reliability work over new feature work
for the affected capability, consistent with the Long-Term
Maintainability principle in 07-Backend-Development-Standards.md Section
2. The error budget is a prioritization tool, not solely a reporting
metric.

Measurement strategy. Every SLO is measured from the same metrics
pipeline described in Section 5 and Section 3 --- never from a separate,
purpose-built measurement path --- consistent with the Single Source of
Truth principle (Section 2). This ensures the SLO reported to
stakeholders is mathematically identical to what the dashboards and
alerts (Sections 8--9) are already observing, eliminating any
possibility of the two disagreeing.

11. Capacity Planning CPU --- Monitored per container role (API, Worker)
    to detect sustained saturation that would degrade latency (API) or
    throughput (Workers) before it becomes user-visible, informing the
    horizontal scaling decisions described in
    09-Deployment-Architecture.md Section 9.

Memory --- Monitored per container to detect gradual growth (a leak)
versus expected steady-state usage, since Sentinel's stateless design
(09-Deployment-Architecture.md Section 2) means legitimate memory usage
should remain bounded and predictable per request/job rather than
growing unbounded over a container's lifetime.

Storage (database) --- PostgreSQL data volume growth is tracked over
time, segmented where practical by table (particularly uploads,
digital_assets, analyses, audit_logs, per 04-Database-Design.md, since
these are the tables expected to grow continuously with platform usage),
to forecast when vertical scaling or read-replica introduction
(09-Deployment-Architecture.md Section 9) will be required.

Queue depth --- Tracked not only as an alerting signal (Section 8) but
as a capacity trend, distinguishing transient spikes from a sustained
upward trend indicating Worker capacity has fallen behind sustained
demand.

Database growth --- Beyond raw storage volume, index size and table
growth rate are tracked, since these directly inform when additional
indexing strategy review (07-Backend-Development-Standards.md Section 8)
or partitioning consideration becomes necessary --- particularly
relevant for the append-only Analysis and AuditLog tables, which by
design never shrink.

Object storage growth --- Tracked as aggregate stored volume and object
count, informing cost and retention policy discussions
(08-Security-Architecture.md Section 11) even though Object Storage
itself scales natively (09-Deployment-Architecture.md Section 9) without
requiring application-level capacity intervention.

AI usage --- Call volume and, where the provider relationship is
usage-billed, associated cost, tracked per analyzer and provider. This
exists because AI provider usage is both a capacity concern (throughput
limits, per Section 5's throttling metric) and a cost concern that must
be visible to avoid unexpected billing impact from a runaway or
misbehaving analyzer.

Network --- Bandwidth utilization, particularly for Object Storage
transfer (upload ingestion and report/file download) and outbound AI
provider calls, is monitored to anticipate when network-level scaling or
a content-delivery strategy adjustment (09-Deployment-Architecture.md
Section 9) becomes necessary.

Future scaling. Capacity trends observed here directly inform the
scaling strategy already defined in 09-Deployment-Architecture.md
Section 9 --- this section's role is to ensure those scaling decisions
are made from continuously observed data rather than reactively, after a
capacity constraint has already caused user-visible degradation.

12. Incident Diagnostics Incident detection. The alerting strategy
    (Section 8), grounded in the SLOs (Section 10) and health monitoring
    (Section 7), is the primary detection mechanism --- incidents are
    expected to be identified by the observability system before they
    are reported by users, consistent with the Production-First
    Visibility principle (Section 2).

Root cause analysis. The combination of correlated logs, metrics, and
traces (Section 3) allows an engineer to move from "the Platform
Overview dashboard shows elevated error rate" to "this specific trace
shows the failure occurred in the Object Storage adapter" to "these
specific log lines show the underlying error" --- a progressively
narrowing investigation path enabled directly by the correlation and
traceability principles established in Section 2.

Performance investigation. Because tracing (Section 6) attributes
latency to specific spans (database call, AI provider call, Analyzer
execution), performance investigations do not require speculative code
review to locate a bottleneck --- the trace data itself identifies which
component consumed the time.

Security investigations. The Security dashboard (Section 9) and the
authentication/authorization metrics (Section 5) provide the immediate
operational view supporting the detection and containment phases of
Incident Response already defined in 08-Security-Architecture.md Section
13. Audit logs (Section 4) provide the durable, tamper-resistant record
required for the recovery and post-incident review phases of that same
process.

Regression analysis. Because metrics and SLO measurements (Sections 5,
10) are continuously recorded, a regression introduced by a specific
deployment (09-Deployment-Architecture.md Section 11) can be identified
by correlating the timing of a metric shift with the deployment
timeline, directly supporting the Rollback Authority process defined in
09-Deployment-Architecture.md Section 14.

13. Operational Governance Dashboard ownership. Each dashboard defined
    in Section 9 has a named owning team responsible for keeping it
    accurate as the underlying system evolves --- a dashboard that
    silently stops reflecting reality (e.g., after a new route is added
    but not represented) is a governance failure, not merely a cosmetic
    one.

Metric ownership. Each metric category in Section 5 is owned by the team
responsible for the corresponding component (API, Workers,
Infrastructure adapters), consistent with the module ownership
boundaries already established in 06-Repository-Structure.md. Adding a
new capability without adding its corresponding metrics is treated as an
incomplete implementation, not an optional follow-up, per the Definition
of Done in 07-Backend-Development-Standards.md Section 15.

Alert ownership. As stated in Section 8, every alert has a named owner
accountable for its continued relevance, review, and eventual retirement
if it no longer serves the Actionable Alerts principle (Section 2).

Telemetry review. Dashboards, metrics, and alerts are periodically
reviewed against actual usage and incident history --- an alert that
never fires usefully, a dashboard panel no one has viewed, or a metric
that no longer maps to a real operational question is a candidate for
removal, keeping the observability surface itself maintainable rather
than growing without bound.

Observability standards. Any new endpoint, worker, or Infrastructure
adapter introduced per 06-Repository-Structure.md Section 17 must
include, as part of its own definition of done, the logging, metrics,
and tracing instrumentation described in this document --- observability
is not an optional enhancement added after a feature ships, but a
required component of the feature itself.

14. Future Evolution The following directions extend the current
    observability architecture without contradicting it, and are
    deferred because current scale and product requirements do not yet
    require them:

OpenTelemetry adoption. Standardizing instrumentation on OpenTelemetry
(or an equivalent vendor-neutral standard) would allow logs, metrics,
and traces to be collected through a single, consistent instrumentation
layer across the API, Workers, and Infrastructure adapters, reducing the
risk of divergent instrumentation approaches as the team grows, without
changing the architectural principles in Section 2.

Advanced tracing. Deeper trace sampling strategies (e.g., adaptive
sampling that retains 100% of error traces while sampling successful
traces) would reduce tracing infrastructure cost at scale while
preserving full diagnostic capability for the traces that matter most
for incident diagnostics (Section 12).

Predictive alerting. Extending the current threshold-based alerting
(Section 8) with trend-based or forecasting-based alerts --- for
example, alerting on a queue depth trajectory that will breach capacity
within a projected window, rather than only alerting once the threshold
is already breached --- would shift some Warning-level alerts (Section
8) earlier in the causal chain.

AI-assisted operations. Given Sentinel's own reliance on AI-assisted
reasoning for Analyzers (00-Project-Context.md Section 3), a natural
extension is applying similar reasoning to operational telemetry itself
--- for example, AI-assisted root cause suggestion drawing on the
correlated logs, metrics, and traces described in Section 3 ---
implemented as a tool layered on top of existing telemetry, not a
replacement for the underlying observability data.

Anomaly detection. Automated detection of statistically unusual patterns
in metrics (beyond fixed thresholds) --- such as an unusual verdict
distribution shift (Section 5's Analyses metrics) --- could surface
subtle Analyzer regressions or AI provider drift earlier than a human
reviewing dashboards would notice.

Enterprise monitoring. Should Sentinel be deployed within enterprise
customer environments (09-Deployment-Architecture.md Section 15), the
observability architecture described here would need an equivalent,
customer-operated counterpart or a secure telemetry export mechanism,
preserving the same principles (Section 2) within a boundary the
platform operator does not directly control.

15. Observability Decision Records The following decisions are permanent
    architectural commitments, consistent with and derived from prior
    documents, and should not be revisited without a deliberate,
    reviewed revision to this document:

OpenTelemetry semantic conventions SHOULD be followed for logs, metrics, and traces where applicable.

Structured logging is mandatory platform-wide. No component emits
unstructured, free-text logs. (Derived from
07-Backend-Development-Standards.md Section 10.) X-Request-ID is the
single correlation mechanism across logs, metrics context, and traces.
No parallel correlation scheme is introduced. (Derived from
08-Security-Architecture.md Section 7.) Trace context is propagated
across the Queue boundary. Asynchronous processing does not break
end-to-end traceability. (Extends 00-Project-Context.md Section 8's
async pipeline design into the observability layer.) AuditLog records
are the authoritative account of business-significant actions, distinct
from and not replaced by operational logging, and remain immutable.
(Derived from 02-Domain-Model.md and 08-Security-Architecture.md Section
2.) DEBUG-level logging is never enabled by default outside Development,
due to the sensitive-data risk associated with AI provider interaction
logging. (Derived from 08-Security-Architecture.md Section 8.) SLOs are
measured from the same telemetry pipeline used for dashboards and alerts
--- there is no separate, purpose-built SLO measurement system. (Single
Source of Truth, Section 2.) Every new endpoint, worker, or
Infrastructure adapter must ship with its corresponding observability
instrumentation as part of its definition of done, not as a follow-up
task. (Derived from 07-Backend-Development-Standards.md Section 15.)
Alerts without a clear owner and a clear required action are not
permitted to remain enabled. (Derived from the Actionable Alerts
principle, Section 2.) Appendix Telemetry Flow Diagram text

Client Request │ ▼ ┌─────────────┐ emits logs/metrics, originates trace
│ API │──────────────────────────────────────┐ └──────┬───────┘ │ │
enqueues job (propagates trace + request ID) │ ▼ │ ┌─────────────┐ │ │
Queue │── emits queue depth/latency metrics ────┤ └──────┬───────┘ │ │
consumed by │ ▼ ▼ ┌─────────────┐ emits logs/metrics, continues trace
┌───────────────────┐ │ Worker
│─────────────────────────────────────────► Centralized │
└──────┬───────┘ │ Aggregation │ │ calls │ (Logs/Metrics/ │ ▼ │ Traces)
│ ┌─────────────────────────────┐ emits latency/error
└─────────┬─────────┘ │ Infrastructure (DB, Storage,
│───────────────────────────────────►│ │ AI Providers) │ ▼
└─────────────────────────────┘ ┌───────────────┐ │ Dashboards │
└───────┬───────┘ │ ▼ ┌───────────────┐ │ Alerts │ └───────┬───────┘ │ ▼
┌───────────────┐ │ Engineers / │ │ On-Call │ └───────────────┘ Metric
Taxonomy Category Examples Primary Question Answered API request rate,
latency, status distribution Is the API healthy and fast? Workers job
duration, outcome, consumption rate Is analysis processing keeping pace?
Queue depth, message age, enqueue/consume rate Is the pipeline backing
up? Database query latency, pool utilization, transaction outcome Is the
system of record a bottleneck? Object Storage call latency, error rate
Is upload/download performance healthy? AI Providers latency, error
rate, throttling Is an external dependency degraded? Authentication
login success/failure, refresh rate Is auth healthy or under attack?
Uploads creation rate, rejection breakdown, dedup hit rate Is intake
healthy and behaving as designed? Analyses creation/completion rate,
verdict distribution Is analysis output healthy and trustworthy? Reports
generation/download rate by format Are completed analyses being
consumed? Logging Taxonomy Level Meaning Example DEBUG Development-only
diagnostic detail Internal state dump during local debugging INFO
Normal, expected operational event Request completed, job consumed
WARNING Anomalous but handled condition Validation rejection, retried
transient failure ERROR Failure requiring investigation Unhandled
exception, retry budget exhausted Dashboard Catalog Dashboard Primary
Audience Core Question Platform Overview Everyone, first responder Is
Sentinel healthy right now? API Backend engineers Which capability is
degraded? Workers Backend/platform engineers Is analysis processing
healthy? Queue Platform engineers Is the pipeline backing up? Database
Platform/backend engineers Is the system of record at risk? Uploads
Backend engineers Is intake and dedup behaving correctly? AI Providers
Backend engineers Is an external dependency responsible for issues?
Infrastructure Platform/SRE Is the runtime environment healthy? Security
Security/on-call Is there an ongoing security anomaly? Alert
Classification Class Response Expectation Example Critical Immediate
page, active response API unavailable, SLO breach in progress Warning
Timely, non-paging attention Queue depth trending upward, elevated auth
failures Operational Informational only Successful backup, deployment
completed

------------------------------------------------------------------------

## 16. Operational Readiness Review

This section complements the observability architecture by defining the
minimum review required before a release is promoted to Production.

### Review Checklist

-   All critical dashboards accurately reflect the current architecture.
-   Every production alert has a documented owner and escalation path.
-   New endpoints, workers, and infrastructure adapters emit logs,
    metrics, and traces.
-   Correlation identifiers propagate across synchronous and
    asynchronous boundaries.
-   Health, readiness, and liveness telemetry are verified.
-   Sensitive information is absent from operational logs.
-   Service Level Objective measurements originate from the production
    telemetry pipeline.
-   Any observability changes have been reviewed together with
    deployment and security implications.

## 17. Review Notes (v1.0.1)

Review outcome:

-   Verified consistency with Documents 00--09.
-   Reinforced operational governance without modifying the
    architecture.
-   No telemetry flows, monitoring strategy, dashboards, metrics,
    tracing model, or alerting philosophy were changed.
