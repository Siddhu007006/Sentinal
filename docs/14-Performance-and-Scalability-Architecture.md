Document Information Document:
docs/14-Performance-and-Scalability-Architecture.md Version: 1.0.1
Status: Final Owner: Performance Architecture Function (Founding
Engineering Team) Audience: Principal engineers, performance engineers,
platform architects, and the Platform Architecture Review Board
Dependencies: This document defines performance and scalability
properties for the system already described in 00-Project-Context.md
through 13-Release-Engineering.md and backend/openapi.yaml. It
introduces no new business functionality, no new architectural
components, and no contradiction of any prior document. It builds
directly on 03-Architecture.md (Modular Monolith layering),
04-Database-Design.md (schema and indexing),
09-Deployment-Architecture.md (runtime topology and scaling strategy),
10-Observability-Architecture.md (telemetry used to validate
performance), and 11-Testing-Strategy.md (verification gates extended
here to include performance verification).

Revision History

Version Date Author Summary 1.0.0 Initial Performance Architecture
Function First canonical performance and scalability architecture. 1.
Purpose Performance is an architectural responsibility, not an
implementation optimization, because Sentinel's request and processing
paths --- validation, hashing, duplicate detection, storage, queueing,
analysis, reporting (00-Project-Context.md Section 5) --- were designed
as a sequence of composable stages specifically so that each stage's
performance characteristics could be reasoned about, bounded, and scaled
independently. If performance were treated as something addressed after
the fact, that composability would be wasted: a poorly performing stage
discovered in Production would require re-architecting a pipeline that
was supposed to already be structured to prevent exactly that outcome.

Scalability must be designed rather than added later for the same reason
the Modular Monolith was chosen deliberately in 03-Architecture.md:
Sentinel's architecture already anticipates growth along two independent
axes --- request volume (more users, more uploads) and processing volume
(more analyses, more analyzers, larger assets) --- and the API/Worker
separation established in 06-Repository-Structure.md and
09-Deployment-Architecture.md exists specifically so these two axes can
scale independently. Retrofitting that separation after a monolithic,
non-decomposed implementation had already shipped would require the kind
of disruptive rewrite the Modular Monolith was explicitly chosen to
avoid.

Predictable performance builds trust in a security platform for a reason
specific to what Sentinel does: a user submitting content for analysis
is, by definition, in a moment of uncertainty about whether to trust
that content. If the platform meant to resolve that uncertainty is
itself unpredictable --- sometimes fast, sometimes inexplicably slow,
occasionally timing out --- it introduces a second layer of uncertainty
on top of the first. Consistent with the Explainability principle in
00-Project-Context.md Section 4, Sentinel's credibility rests on the
platform being as dependable and legible in its own operation as it aims
to be in its judgments about uploaded content.

2.  Performance Principles Performance by Design. Every architectural
    decision in 03-Architecture.md and 09-Deployment-Architecture.md ---
    asynchronous processing, statelessness, adapter-based Infrastructure
    access --- is evaluated for its performance implications at design
    time, not discovered through post-hoc profiling. This exists because
    performance problems rooted in architecture (e.g., a synchronous
    call on a path that should be asynchronous) are far more expensive
    to fix after implementation than a performance problem rooted in a
    single inefficient function.

Horizontal Scalability. Capacity is added by running more stateless
instances (09-Deployment-Architecture.md Section 2), never by growing a
single instance indefinitely. This exists because vertical scaling has a
hard ceiling and a single point of failure, while horizontal scaling
aligns directly with Sentinel's stateless API and Worker design,
allowing capacity to grow in proportion to demand without an
architectural ceiling.

Efficient Resource Utilization. Every layer --- API, Worker, Database,
Object Storage --- is expected to use compute, memory, and I/O
proportionate to the work being done, avoiding both under-utilization
(wasted capacity) and over-utilization (degraded latency under load).
This exists because Sentinel's asynchronous pipeline
(00-Project-Context.md Section 5) only delivers its intended benefit ---
decoupling request latency from processing time --- if each stage
actually uses its allotted resources efficiently rather than masking
inefficiency behind the buffer the Queue provides.

Backpressure. When a component receives work faster than it can process
it, that pressure is made visible and bounded --- through queue depth
(10-Observability-Architecture.md Section 5), rate limiting
(08-Security-Architecture.md Section 7), or upload size limits
(backend/openapi.yaml) --- rather than absorbed silently until a
downstream component fails. This exists because an unbounded system does
not fail gracefully; it fails catastrophically and unpredictably,
precisely when load is highest and stability matters most.

Asynchronous Processing. As already established in 00-Project-Context.md
Section 4, no analysis work is performed synchronously within a
request/response cycle. This exists --- restated here specifically as a
performance principle --- because it is the single architectural
decision most responsible for Sentinel's ability to keep API latency low
and predictable regardless of how long any individual analysis takes.

Graceful Degradation. When a non-critical dependency (e.g., a specific
AI provider) is slow or unavailable, the platform continues to serve the
capabilities that do not depend on it, rather than failing the entire
system. This exists because Sentinel's platform-first design
(00-Project-Context.md Section 2) already separates concerns by
analyzer; performance architecture extends that separation into failure
and degradation behavior, so one degraded dependency does not become a
platform-wide outage.

Predictable Latency. Latency is optimized for consistency (a narrow,
predictable distribution) as much as for raw speed (a low average). This
exists because a user or integrator can plan around a system that is
reliably somewhat slow far more easily than one that is usually fast but
occasionally extremely slow --- consistent with the Service Level
Objective framework in 10-Observability-Architecture.md Section 10,
which measures the proportion of requests within a latency threshold,
not merely an average.

Elastic Capacity. Capacity is provisioned to match observed and forecast
demand (Section 6), scaling up during periods of higher load and back
down when load recedes, rather than being permanently sized for peak.
This exists because Sentinel's workload --- driven by upload and
analysis volume --- is not expected to be constant, and permanently
over-provisioning for peak would violate Cost Awareness without a
corresponding reliability benefit.

Cost Awareness. Performance and scalability decisions are made with
explicit awareness of their cost implications --- additional Worker
capacity, AI provider call volume (10-Observability-Architecture.md
Section 11), and storage growth all carry real operating cost. This
exists because a scaling strategy that ignores cost is not sustainable,
and because AI provider usage in particular (08-Security-Architecture.md
Section 8) is a variable cost directly tied to Analyzer execution volume
that must be factored into capacity decisions, not treated as free.

Capacity Planning. Resource needs are forecast ahead of demand using the
trends described in Section 6, rather than reactively provisioned only
after a capacity constraint has already caused degradation. This exists
because Sentinel's asynchronous design can mask early warning signs of
capacity exhaustion (a growing queue does not immediately produce a
user-visible error) --- deliberate capacity planning is what prevents
that masking from becoming a delayed, larger-scale incident.

3.  Workload Characteristics Authentication (POST /auth/login, POST
    /auth/refresh, POST /auth/logout, GET /auth/me)

Purpose: Establish and maintain a user's authenticated session per
08-Security-Architecture.md Section 4. Performance characteristics: High
frequency, low computational cost per request except for password
hashing (login), which is deliberately computationally expensive by
design (08-Security-Architecture.md Section 4) as a security trade-off
against brute-force attempts. Scaling considerations: Scales
horizontally with API instance count (Section 5); password hashing cost
must be tuned to balance security and throughput, since it is the single
most CPU-intensive operation in this workload category. Failure impact:
An authentication outage blocks all subsequent platform use, making this
workload's availability the platform's effective availability floor.
File uploads (POST /uploads)

Purpose: Accept raw content into the intake pipeline
(00-Project-Context.md Section 5). Performance characteristics: Variable
duration proportional to file size (up to the 100 MB limit in
backend/openapi.yaml), dominated by network transfer time and hashing
computation, with duplicate detection providing a fast-path
short-circuit for previously-seen content (02-Domain-Model.md). Scaling
considerations: Bound primarily by network throughput and Object Storage
write throughput (Section 9) rather than API CPU; scales horizontally
with API instance count, but individual upload latency is bounded by
file size regardless of instance count. Failure impact: An upload-path
failure blocks new content from entering the platform but does not
affect already-queued analysis or previously stored assets, consistent
with the pipeline's stage independence. Analysis jobs (POST /analyses,
queue enqueue)

Purpose: Request one or more Analyzer executions against a DigitalAsset
(02-Domain-Model.md). Performance characteristics: The API-facing
operation itself is lightweight --- it validates the request and
enqueues jobs, returning 202 Accepted immediately per
backend/openapi.yaml --- deliberately decoupling this workload's
user-perceived latency from the actual analysis duration. Scaling
considerations: Scales horizontally with API instance count for the
enqueue operation; actual analysis throughput is governed by Worker
capacity (Section 8), not by this endpoint. Failure impact: A failure
here prevents new analyses from being requested but does not affect
in-flight or completed analyses. Worker execution (Analyzer processing)

Purpose: Execute the actual analysis logic --- the core computational
and, for AI-assisted analyzers, externally-dependent work of the
platform. Performance characteristics: Highly variable duration
depending on analyzer type --- a signature-based static analyzer
completes quickly; an AI Document Analyzer's duration is dominated by
external AI provider latency (Section 10). Scaling considerations:
Scales horizontally with Worker instance count (Section 5); throughput
is additionally bounded by external AI provider rate limits, which do
not scale simply by adding more Worker instances. Failure impact: A
Worker-layer failure delays analysis completion but, due to the Queue's
durability (09-Deployment-Architecture.md Section 3), does not lose
queued work --- jobs remain pending until a healthy Worker becomes
available. Database operations (all repository reads/writes across every
entity in 02-Domain-Model.md)

Purpose: Persist and retrieve all structured metadata underlying every
other workload category. Performance characteristics: Read-heavy overall
(list and retrieval endpoints outnumber write endpoints in
backend/openapi.yaml), with a smaller volume of writes concentrated
around upload intake and analysis completion. Scaling considerations:
Vertical scaling first, then read replicas for read-heavy patterns, per
09-Deployment-Architecture.md Section 9 --- this workload does not scale
purely horizontally the way the API and Worker layers do. Failure
impact: Database degradation affects every other workload category
simultaneously, making it the platform's single most consequential
shared dependency. Report retrieval (GET /reports, GET
/reports/{reportId}, GET /reports/{reportId}/download)

Purpose: Deliver the human-facing presentation of completed analyses.
Performance characteristics: Read-only, generally low-latency for
metadata retrieval; the download operation's latency is dominated by
Object Storage streaming throughput for larger report formats (e.g.,
PDF). Scaling considerations: Scales horizontally with API instance
count; streaming (Section 9) prevents large report downloads from
consuming disproportionate API instance memory. Failure impact: A
failure here affects the platform's ability to deliver already-completed
conclusions to users, distinct from and independent of the platform's
ability to produce new ones. History queries (GET
/assets/{assetId}/analyses, GET /analyses, GET /audit-logs)

Purpose: Provide the append-only, versioned view of past analyses and
administrative audit history (02-Domain-Model.md). Performance
characteristics: Read-heavy, growing in data volume over time since
these tables are append-only by design (04-Database-Design.md), making
pagination (Section 7) essential rather than optional. Scaling
considerations: Query efficiency depends heavily on indexing strategy
(Section 7) given continuous, unbounded table growth; read replicas are
particularly well-suited to this workload category. Failure impact: A
failure here affects the platform's explainability and auditability
capabilities (00-Project-Context.md Section 4,
08-Security-Architecture.md Section 10) without affecting the ability to
create new uploads or analyses. Administrative operations (GET /users,
PATCH /users/{userId}, DELETE /users/{userId}, DELETE /assets/{assetId})

Purpose: Support platform administration per the admin role defined in
08-Security-Architecture.md Section 5. Performance characteristics: Low
frequency, low volume, not performance-sensitive relative to other
workload categories. Scaling considerations: No special scaling
treatment required given low expected volume; correctness and
authorization rigor (08-Security-Architecture.md Section 5) take
precedence over throughput optimization for this workload. Failure
impact: Limited to administrative capability; does not affect core
upload, analysis, or reporting workloads. Background maintenance
(scheduled workers, per 06-Repository-Structure.md Section 8)

Purpose: Periodic housekeeping tasks not triggered by a specific user
request (e.g., retry-eligible job re-queueing per
07-Backend-Development-Standards.md Section 9). Performance
characteristics: Low frequency, predictable timing, resource usage
bounded by the scope of the maintenance task itself. Scaling
considerations: Scheduled workers run independently of request-driven
scaling and are sized for their specific task rather than for overall
platform load. Failure impact: A missed or delayed maintenance run is
generally recoverable at the next scheduled interval, making this the
lowest-urgency workload category from a performance-impact perspective.
4. Performance Architecture API layer. Responsible for request
validation, authentication/authorization, and orchestration hand-off to
the Application layer (03-Architecture.md), all executed asynchronously
(Section 2) so that I/O-bound operations (database calls, Object Storage
calls, queue enqueue) never block the event loop for concurrent requests
(07-Backend-Development-Standards.md Section 13). The API layer's
performance responsibility is to keep its own processing overhead ---
everything other than the I/O it delegates to --- negligible relative to
that I/O.

Worker layer. Responsible for consuming queued jobs and executing
Analyzers, with concurrency tuned per instance (Section 8) to maximize
throughput without exceeding the resource or external-rate-limit
constraints of the analyzers it runs. The Worker layer's performance
responsibility is to keep pace with the Queue's enqueue rate under
expected load, and to fail predictably (via retry, per
07-Backend-Development-Standards.md Section 9) rather than unpredictably
when it cannot.

Queue. Responsible for absorbing the timing mismatch between enqueue
rate (API-driven, bursty) and consumption rate (Worker-driven,
throughput-bound), per 00-Project-Context.md Section 8. Its performance
responsibility is durability and low enqueue/dequeue latency --- the
Queue itself should never be the bottleneck; if a bottleneck exists, it
should be visible as growing queue depth
(10-Observability-Architecture.md Section 5), attributable to Worker
capacity, not hidden inside the Queue's own processing.

Database. Responsible for transactional integrity and efficient query
execution across every entity defined in 02-Domain-Model.md. Its
performance responsibility, detailed in Section 7, is to serve the
read-heavy access patterns typical of Sentinel's workload (Section 3)
through appropriate indexing, and to isolate write contention to the
specific tables experiencing concurrent writes rather than serializing
unrelated operations.

Object storage. Responsible for durable binary content storage and
retrieval (00-Project-Context.md Section 6), with a performance
responsibility to support both upload ingestion and report/file download
at throughput proportional to network capacity, via streaming (Section
9) rather than full in-memory buffering.

AI provider integrations. Responsible, through the Infrastructure
adapter (08-Security-Architecture.md Section 8), for isolating the
variable and sometimes slow latency of external AI calls from the rest
of the Worker's execution, applying the timeout and retry strategy
defined in Section 10 so that one slow provider call does not
indefinitely occupy Worker capacity that could otherwise process other
queued jobs.

Frontend. Responsible for efficient consumption of the API --- applying
pagination correctly (Section 7), avoiding redundant requests, and
rendering large report content without blocking the user interface. As
an unprivileged API consumer (06-Repository-Structure.md Section 10),
the Frontend's performance responsibility is bounded to its own
rendering and request efficiency; it has no influence over backend
processing performance.

5.  Scalability Model API instances scale horizontally behind the
    Reverse Proxy/Load Balancer (09-Deployment-Architecture.md Section
    3), since the API is stateless by design (Section 2 of this
    document; Section 2 of 09-Deployment-Architecture.md). Additional
    instances linearly increase request-handling capacity with no
    coordination required between instances.

Worker instances scale horizontally by running additional independent
consumers of the same Queue (09-Deployment-Architecture.md Section 9).
Because analysis jobs are independent units of work
(00-Project-Context.md Section 8), Worker throughput scales close to
linearly with instance count, up to the point where external AI provider
rate limits (Section 10) become the binding constraint rather than
Worker capacity itself.

Queue processing scales via the broker's own horizontal scaling
mechanism (e.g., clustering, per 09-Deployment-Architecture.md Section
9), sized to sustain peak enqueue rate from the API without unbounded
growth, and monitored via the queue depth and message age metrics
defined in 10-Observability-Architecture.md Section 5.

Database scales vertically first, then through read replicas for
read-heavy access patterns (Section 3's History and Report Retrieval
workloads), consistent with 09-Deployment-Architecture.md Section 9 ---
this is a deliberate exception to the platform's general
horizontal-scaling preference, made because PostgreSQL's transactional
write path does not horizontally scale as simply as a stateless API or
Worker process, and because 04-Database-Design.md's relational integrity
guarantees depend on a single authoritative write path.

Object storage scales natively as a managed service property
(09-Deployment-Architecture.md Section 9), requiring no explicit
application-level scaling strategy.

Monitoring and logging infrastructure (10-Observability-Architecture.md
Section 3) scales independently of the components it observes, sized to
the telemetry volume produced by the current fleet of API and Worker
instances, and reviewed periodically alongside overall capacity planning
(Section 6) so that observability capacity does not silently become a
bottleneck of its own.

Future service decomposition. As anticipated in
06-Repository-Structure.md Section 18 and 09-Deployment-Architecture.md
Section 9, the Worker component is the most natural candidate for
extraction into an independently deployed and independently scaled
service, since it already communicates with the rest of the system
exclusively through the Queue, Database, and Object Storage. This
scalability model does not depend on that extraction occurring --- it is
designed to work identically whether the Worker runs as a container role
within the Modular Monolith's deployment or as a fully separate service.

Why horizontal scaling is preferred. Horizontal scaling aligns directly
with the stateless design mandated in 09-Deployment-Architecture.md
Section 2, avoids the single point of failure inherent in vertical
scaling, and allows capacity to be added or removed incrementally in
response to observed demand (Elastic Capacity, Section 2) rather than
requiring disruptive resizing of a single large instance. It is the
scaling strategy that best matches Sentinel's actual workload shape
(Section 3): bursty, user-driven request volume for the API, and
throughput-bound, queue-fed processing for Workers --- both of which are
naturally parallelizable across many small instances rather than
requiring one large one.

6.  Capacity Planning Capacity planning at Sentinel is a methodology. Capacity reviews occur on a recurring operational cadence and after significant workload changes so planning remains aligned with observed production behavior.

Capacity planning at Sentinel is a methodology,
    not a fixed set of numbers --- specific thresholds are derived from
    observed telemetry (10-Observability-Architecture.md Section 11) and
    reviewed periodically, since committing to arbitrary figures without
    operational data would contradict the evidence-based philosophy
    underlying the platform itself (00-Project-Context.md Section 4).

CPU. Planned by tracking per-instance CPU utilization trends (API and
Worker separately, per 10-Observability-Architecture.md Section 11)
against the horizontal scaling thresholds defined operationally, adding
instances before sustained utilization reaches a level that would
degrade latency (API) or throughput (Worker).

Memory. Planned by tracking per-instance memory usage over time to
distinguish expected steady-state consumption from gradual growth
indicating a leak, since Sentinel's stateless design (Section 2) implies
memory usage per request or job should be bounded and should not grow
with container uptime.

Disk. Relevant primarily for temporary file handling during Worker
Analyzer execution (08-Security-Architecture.md Section 6) and Database
storage volume; planned by ensuring temporary storage is sized for the
largest expected concurrent file processing load and cleaned up promptly
(Section 9), and Database disk is monitored per the storage growth
methodology below.

Storage growth. Planned by tracking Object Storage volume and object
count growth rate over time (10-Observability-Architecture.md Section
11), informed directly by the hash-based deduplication rate
(02-Domain-Model.md) --- since deduplication reduces actual stored
volume relative to raw upload volume, the effective growth rate to plan
against is post-deduplication, not raw intake volume.

Network. Planned by tracking bandwidth utilization for Object Storage
transfer (upload ingestion and report download, Section 9) and outbound
AI provider calls (Section 10), anticipated to grow proportionally with
upload volume and analysis volume respectively.

Queue depth. Planned by tracking the relationship between enqueue rate
and consumption rate over time (10-Observability-Architecture.md Section
5); a sustained upward trend in queue depth --- as opposed to transient
spikes that recede --- is the primary signal that Worker capacity
planning needs to move ahead of schedule.

Database growth. Planned by tracking data volume and index size growth
per table (10-Observability-Architecture.md Section 11), with particular
attention to the append-only analyses and audit_logs tables
(04-Database-Design.md), which by design never shrink and therefore
require proactive planning for read replica introduction or partitioning
(Section 7) well before growth becomes a query-performance problem.

Concurrent users. Planned by tracking authentication and active-session
volume trends (10-Observability-Architecture.md Section 5) against API
instance capacity, since concurrent user volume is the primary driver of
API-layer horizontal scaling needs (Section 5).

Concurrent analyses. Planned by tracking the number of simultaneously
in-flight (queued/running) analyses against Worker instance capacity
and, critically, against known AI provider rate limits (Section 10),
since Worker capacity alone does not guarantee analysis throughput once
an external provider's own limits become the binding constraint.

Future organizational growth. Planned by extrapolating observed per-user
or per-organization usage patterns (upload frequency, analysis
frequency) against anticipated user or customer growth, translating
product-level adoption forecasts into the underlying infrastructure
metrics above, rather than treating infrastructure capacity planning as
disconnected from product growth expectations.

The methodology throughout is consistent: observe the relevant metric
via the pipeline already established in 10-Observability-Architecture.md
Section 3, establish its trend, and provision ahead of the point where
that trend would otherwise breach a Service Level Objective
(10-Observability-Architecture.md Section 10) --- never provisioning
reactively only after degradation has already occurred.

7.  Database Performance Index strategy. Every column used in a WHERE,
    JOIN, or ORDER BY clause across the repository query methods defined
    in 06-Repository-Structure.md Section 6 has a corresponding index,
    consistent with the requirement already established in
    07-Backend-Development-Standards.md Section 8. This exists because
    Sentinel's read-heavy workload (Section 3) makes query latency
    directly dependent on index coverage --- an unindexed query pattern
    on a growing table (e.g., analyses, audit_logs) degrades predictably
    worse over time as data volume increases, exactly the kind of latent
    performance problem Performance by Design (Section 2) is meant to
    prevent.

Query efficiency. Repository methods are written to avoid N+1 query
patterns (07-Backend-Development-Standards.md Section 13), fetching
related data through explicit joins or batched queries rather than
iterative per-item queries --- most relevant for endpoints like GET
/assets/{assetId}/analyses, which return a collection with associated
Analyzer information.

Pagination. Every list endpoint defined in backend/openapi.yaml enforces
pagination via the page/pageSize parameters and PaginationMeta response
shape, with no code path permitted to return an unbounded collection
(07-Backend-Development-Standards.md Section 13). This exists because
Sentinel's append-only entities (Analysis, AuditLog) grow without bound
by design --- pagination is what keeps query and response cost constant
regardless of how much historical data has accumulated.

Transactions. Multi-statement writes requiring atomicity (e.g., creating
an Upload record and enqueueing the corresponding intake job) are
wrapped in a single transaction managed at the Application layer's
Unit-of-Work boundary (07-Backend-Development-Standards.md Section 5),
keeping transaction scope as narrow as the atomicity requirement
actually demands --- a transaction held open longer than necessary
increases lock contention and directly degrades concurrent write
throughput.

Connection management. The API and Worker layers each maintain a bounded
connection pool to PostgreSQL, sized to match their respective
horizontal scaling model (Section 5), monitored via the connection pool
utilization metric defined in 10-Observability-Architecture.md Section 5
--- connection pool exhaustion is treated as a capacity signal requiring
either pool resizing or additional database capacity, not merely a
transient error to retry past.

Migration impact. Schema migrations (07-Backend-Development-Standards.md
Section 8) are reviewed for their performance impact on a live,
populated database --- specifically, whether an index creation or column
addition requires a table lock that would degrade or block concurrent
access --- and are executed using non-blocking migration techniques
wherever the underlying database supports them, consistent with the
Zero-Downtime Deployment principle in 09-Deployment-Architecture.md
Section 2.

Long-running queries. Any query pattern observed to exceed expected
latency thresholds (via the query latency metrics in
10-Observability-Architecture.md Section 5) is treated as a capacity or
indexing signal requiring investigation, not tolerated as an accepted
cost of a specific feature --- consistent with the Predictable Latency
principle (Section 2).

Future partitioning. Should the append-only analyses and audit_logs
tables grow to a scale where index size and query performance degrade
despite adequate indexing (Section 6's Database Growth planning), table
partitioning (e.g., by time range) is the anticipated next step,
consistent with 04-Database-Design.md's existing normalization and
constraint model --- this document does not implement partitioning now,
as it is not yet justified by current data volume, but the append-only,
timestamp-ordered nature of these tables makes them naturally
well-suited to it when the time comes.

8.  Queue & Worker Performance Queue throughput. The Queue is sized and
    monitored (10-Observability-Architecture.md Section 5) to sustain
    the API's peak enqueue rate without unbounded growth in queue depth,
    consistent with the Backpressure principle (Section 2) --- a growing
    queue is a visible, measurable signal rather than a silent failure.

Worker concurrency. Each Worker instance processes a bounded number of
jobs concurrently, tuned to balance throughput against per-job resource
consumption (particularly memory during Analyzer execution, per Section
6) and against external AI provider rate limits (Section 10) ---
concurrency that exceeds what a downstream AI provider can sustain
produces throttling rather than genuine additional throughput, so
concurrency tuning is bound by the slowest relevant downstream
constraint, not by Worker CPU/memory alone.

Retry behavior. Transient failures (e.g., a temporary AI provider
timeout) are retried using bounded exponential backoff, per
07-Backend-Development-Standards.md Section 9 and the retry_worker role
defined in 06-Repository-Structure.md Section 8. This exists so that a
transient downstream issue produces a delayed successful analysis rather
than a permanently failed one, while bounded backoff prevents retries
themselves from compounding load on an already-struggling dependency.

Backpressure. When queue depth or message age
(10-Observability-Architecture.md Section 5) exceeds expected bounds,
this is treated as a direct signal to scale Worker capacity (Section 5)
rather than allowing the backlog to grow indefinitely --- the Queue's
durability (09-Deployment-Architecture.md Section 3) ensures no work is
lost while this scaling response occurs, but sustained backpressure
without a scaling response would eventually degrade the Analysis-related
Service Level Objectives defined in 10-Observability-Architecture.md
Section 10.

Job prioritization. Sentinel's current API Specification and Domain
Model do not define differentiated priority levels for analysis jobs ---
all queued analyses are treated as equally prioritized, processed in the
order the Queue delivers them. This document does not invent a
prioritization scheme not justified by prior documents; if
differentiated priority becomes a product requirement, it must first be
reflected in 01-Product-Requirements.md and 02-Domain-Model.md before
being implemented here.

Resource isolation. Analyzer execution within a Worker is bounded (time
and memory limits appropriate to the analyzer type) so that a single
misbehaving or unexpectedly resource-intensive analysis job cannot
exhaust the resources available to other jobs being processed by the
same Worker instance, consistent with the least-privilege and
resource-bounding posture already established for Worker containers in
08-Security-Architecture.md Section 6 and 09-Deployment-Architecture.md
Section 5.

Failure recovery. A Worker instance that fails mid-job does not lose
that job, since the Queue's acknowledgment model
(09-Deployment-Architecture.md Section 3) ensures an unacknowledged job
becomes available for another Worker to consume --- this is the
mechanism by which Worker-layer failures (Section 3's Worker Execution
failure impact) remain recoverable without manual intervention,
consistent with the Recovery behavior defined in
09-Deployment-Architecture.md Section 10.

9.  Storage Performance Upload throughput. Bound primarily by network
    transfer time for the file itself and by the SHA-256 hashing
    computation performed during intake (00-Project-Context.md Section
    5), both of which scale predictably with file size up to the 100 MB
    limit defined in backend/openapi.yaml --- no additional
    computational overhead is introduced beyond what the validation and
    hashing pipeline requires.

Streaming. Both upload ingestion and report/file download (GET
/reports/{reportId}/download) stream content directly between the
client, the API, and Object Storage rather than fully buffering file
content in API instance memory, consistent with
07-Backend-Development-Standards.md Section 13. This exists because
buffering a 100 MB file in memory per concurrent request would make API
instance memory consumption directly proportional to concurrent
upload/download volume --- an avoidable and unnecessary scaling
constraint.

Temporary storage. Where a Worker must materialize file content to local
disk for Analyzer processing (08-Security-Architecture.md Section 6),
this storage is sized to accommodate the Worker's configured concurrency
(Section 8) at the maximum permitted file size, and is cleaned up
immediately upon job completion --- including on failure paths --- so
that temporary storage consumption remains bounded and does not
accumulate across jobs.

Object storage. Scales natively as a managed service property (Section
5) and is not a performance bottleneck under normal conditions; the
platform's own responsibility is to use it efficiently --- avoiding
redundant writes for content already identified as a duplicate via
SHA-256 hash comparison (02-Domain-Model.md), which directly reduces
both storage volume and write throughput demand.

Large-file handling. The 100 MB upload limit defined in
backend/openapi.yaml establishes a known upper bound on any single
file's processing cost, which is what allows Worker resource limits
(Section 8) and temporary storage sizing to be planned deterministically
rather than needing to accommodate unbounded file sizes.

Retention. Object Storage retention follows the data retention policy
referenced in 08-Security-Architecture.md Section 11; from a performance
perspective, retention policy directly determines long-term storage
growth (Section 6), making retention decisions a capacity-planning
input, not solely a compliance one.

Cleanup. Deleted DigitalAsset content (via the admin-only purge
operation in backend/openapi.yaml) is removed from Object Storage as
part of the deletion operation itself, preventing orphaned content from
silently accumulating and inflating storage growth beyond what active,
referenced assets actually require.

10. External Dependency Performance AI providers represent Sentinel's
    least controllable performance dependency
    (08-Security-Architecture.md Section 8), since their latency,
    availability, and rate limits are governed by a third party rather
    than by Sentinel's own architecture. Performance architecture treats
    this dependency as a bounded, isolated risk rather than assuming it
    behaves as reliably as internal Infrastructure.

Timeout strategy. Every call to an AI provider through the
Infrastructure adapter (08-Security-Architecture.md Section 8) is
bounded by an explicit timeout, sized to the expected latency profile of
AI-assisted analysis while preventing a single slow or hung provider
call from indefinitely occupying Worker capacity that Section 8's
concurrency model assumes will free up in a bounded time.

Retry policy. Consistent with 07-Backend-Development-Standards.md
Section 9 and Section 8 of this document, transient AI provider failures
(timeouts, transient 5xx responses) are retried with bounded exponential
backoff; failures indicating a non-transient problem (e.g., a malformed
request, an authentication failure) are not retried, since retrying a
deterministic failure only wastes capacity without any chance of
success.

Circuit breaker philosophy. When an AI provider's error or timeout rate
crosses a threshold indicating sustained degradation rather than
isolated transient failure, the Infrastructure adapter should stop
sending further calls to that provider for a defined cool-down period
rather than continuing to attempt and fail --- consistent with the Fail
Safe and Graceful Degradation principles (Section 2, and
08-Security-Architecture.md Section 2) --- protecting both Worker
capacity (which would otherwise be consumed by calls likely to fail or
time out) and the provider relationship itself from being overwhelmed by
continued traffic during an outage.

Graceful degradation. When an AI-assisted analyzer's provider is
unavailable, jobs depending on it remain queued for retry (Section 8)
rather than being force-failed, and --- consistent with
00-Project-Context.md's platform-first design --- other analyzers not
depending on the affected provider continue to process normally, since
analyzers are independent, pluggable units (06-Repository-Structure.md
Section 9) with no shared dependency by default.

Dependency isolation. Each AI provider integration is isolated within
its own adapter implementation (08-Security-Architecture.md Section 8),
meaning a performance or reliability problem specific to one provider's
SDK or API does not propagate into the code paths serving other
providers or other analyzer types --- a direct performance benefit of
the provider abstraction decision already justified architecturally in
00-Project-Context.md Section 6.

11. Performance Verification Benchmarking. Baseline performance
    characteristics --- API latency per route, Worker job processing
    duration per analyzer type --- are established and recorded as part
    of the verification activities extending 11-Testing-Strategy.md,
    providing the reference point against which future regression
    detection (below) is measured.

Load testing. The platform is periodically subjected to expected-peak
request and analysis volume in a Staging-equivalent environment
(09-Deployment-Architecture.md Section 4) to validate that the
horizontal scaling model (Section 5) actually delivers the throughput it
is designed to provide, rather than assuming linear scaling without
confirmation.

Stress testing. The platform is periodically subjected to load beyond
expected peak to observe how it degrades --- confirming that
Backpressure (Section 2) and Graceful Degradation (Section 2) behave as
designed (visible queue growth, rate-limit responses, circuit-breaker
activation) rather than producing an uncontrolled failure mode.

Soak testing. The platform is run under sustained, moderate load over an
extended period to detect issues that only manifest over time --- memory
growth (Section 6), connection pool exhaustion (Section 7), or gradual
Object Storage/temporary storage accumulation (Section 9) --- which
shorter load tests would not reveal.

Regression detection. Performance metrics from each release candidate
(13-Release-Engineering.md Section 9) are compared against established
baselines as part of Post-release Validation, so that a latency or
throughput regression is caught and attributed to a specific release
before it accumulates unnoticed across multiple releases.

Capacity validation. Load and stress testing results are periodically
reconciled against the capacity planning trends in Section 6, confirming
that observed real-world scaling behavior matches the assumptions
capacity planning is based on --- a mismatch here indicates the capacity
planning methodology itself needs recalibration, not just an
infrastructure resizing.

Performance reviews. Significant architectural or implementation changes
affecting a performance-critical path (any workload category in Section
3) undergo a dedicated performance review, consistent with the Code
Review Checklist's Performance criterion in
07-Backend-Development-Standards.md Section 14, before being approved
for release per 13-Release-Engineering.md Section 6.

12. Performance Governance Ownership. Each workload category in Section
    3 has a clearly identified owning team, consistent with the Metric
    Ownership model in 10-Observability-Architecture.md Section 13 ---
    performance ownership and observability metric ownership are the
    same accountability, viewed from different angles.

Performance budgets. Each performance-sensitive workload category
(Section 3) operates within an implicit performance budget derived from
its corresponding Service Level Objective
(10-Observability-Architecture.md Section 10) --- a change that would
consume a disproportionate share of that budget is flagged during
Performance Review (Section 11) before it reaches Production, consistent
with the Error Budget philosophy already established in
10-Observability-Architecture.md Section 10.

Review process. Performance-sensitive changes are reviewed against the
Code Review Checklist (07-Backend-Development-Standards.md Section 14)
at the code level and against the Release Readiness criteria
(13-Release-Engineering.md Section 6) at the release level, ensuring
performance is evaluated at both the granularity of an individual change
and the granularity of a complete release.

Regression policy. A detected performance regression (Section 11) is
treated with the same severity as a functional regression --- subject to
the Rollback Governance model in 13-Release-Engineering.md Section 10 if
discovered post-release, or blocking Release Readiness
(13-Release-Engineering.md Section 6) if discovered before release ---
consistent with treating performance as a first-class correctness
property, not a secondary concern.

Optimization policy. Optimization work is prioritized based on observed
impact against Service Level Objectives and capacity trends (Section 6),
not based on speculative or premature optimization of code paths without
demonstrated performance impact --- consistent with the Long-Term
Maintainability principle in 07-Backend-Development-Standards.md Section
2, which favors clarity over premature cleverness.

Technical debt management. Performance-related technical debt (e.g., a
known-inefficient query pattern accepted temporarily under a documented
exception) is tracked explicitly and revisited on a defined cadence,
rather than being allowed to persist indefinitely once the immediate
pressure that justified the shortcut has passed.

Performance budget ownership. Every critical workload has an explicitly assigned owner responsible for maintaining its latency, throughput, and capacity budgets. Budget overruns require review before release.

13. Future Evolution The following directions extend Sentinel's current
    performance and scalability model without contradicting it, deferred
    because current scale and product requirements do not yet require
    them:

Autoscaling. The horizontal scaling model described in Section 5 is the
direct precondition for automated autoscaling driven by request
throughput (API) or queue depth (Worker), which can be introduced as an
operational policy without any change to the underlying container or
network architecture already defined in 09-Deployment-Architecture.md.

Distributed workers. Should Worker throughput requirements exceed what a
single deployment region or cluster can efficiently provide, Worker
execution could be distributed across multiple independent clusters
consuming from the same or federated Queues, building directly on the
Worker's already-established isolation from the API layer (Section 5).

Multi-region deployment. As anticipated in 09-Deployment-Architecture.md
Section 15, the stateless design of the API and Worker layers means
additional regions could run identical component copies; the primary
performance consideration would shift to Database and Object Storage
replication latency across regions, an extension of the existing scaling
model rather than a departure from it.

CDN integration. Frontend static assets and, potentially, publicly
cacheable API responses could be served through a content delivery layer
positioned in front of the Reverse Proxy (09-Deployment-Architecture.md
Section 3), reducing latency for geographically distributed users
without any change to backend processing architecture.

Edge services. Certain lightweight, latency-sensitive operations (e.g.,
initial upload validation) could in principle be pushed closer to the
user at an edge layer in the future, though this is not required by
current product requirements and would need to preserve the same
validation guarantees currently enforced centrally
(08-Security-Architecture.md Section 6).

Advanced caching. Beyond the limited, explicitly-scoped caching already
described in 07-Backend-Development-Standards.md Section 13 (e.g., the
Analyzer list), a more comprehensive caching strategy could reduce
Database load for other read-heavy, slowly-changing data --- implemented
carefully to preserve the guarantee that Analysis results are never
served stale (07-Backend-Development-Standards.md Section 13).

Adaptive workload management. Future Worker scheduling could dynamically
prioritize or throttle specific analyzer types based on observed AI
provider health (Section 10) or current queue composition, building on
the circuit-breaker philosophy already established here rather than
introducing a fundamentally new mechanism.

14. Performance Decision Records The following are permanent performance
    and scalability commitments, derived directly from this document and
    the prior architecture, and should not be revisited without a
    deliberate, reviewed revision:

No analysis work is ever performed synchronously within an API
request/response cycle. This is the foundational decision enabling
predictable API latency regardless of analysis complexity (Section 2,
extending 00-Project-Context.md Section 4). All list endpoints are
paginated with no exception, since Sentinel's append-only entities grow
without bound by design (Section 7). API and Worker layers scale
horizontally as the default strategy; the Database is the sole
deliberate exception, scaling vertically first and via read replicas
thereafter (Section 5). Every list/query repository method must have
corresponding index coverage for its filter, join, and sort columns
before it ships (Section 7, extending
07-Backend-Development-Standards.md Section 8). All AI provider calls
are bounded by explicit timeouts and isolated per-provider, so that one
degraded external dependency cannot exhaust Worker capacity or propagate
failure into unrelated analyzer types (Section 10). Upload and download
of file content is always streamed, never fully buffered in API instance
memory (Section 9). A detected performance regression is treated with
the same severity as a functional regression for release governance
purposes (Section 12, extending 13-Release-Engineering.md Section 6).
Capacity planning thresholds are derived from observed telemetry, never
fixed arbitrarily, and are reviewed on an ongoing basis against actual
growth trends (Section 6). Appendix Workload Taxonomy Workload Primary
Bottleneck Scaling Lever Failure Blast Radius Authentication Password
hashing CPU cost API horizontal scaling Platform-wide (blocks all
access) File uploads Network transfer + hashing API horizontal scaling,
Object Storage throughput Intake only; existing data unaffected Analysis
job creation Negligible (enqueue only) API horizontal scaling Blocks new
analysis requests only Worker execution Analyzer compute / AI provider
latency Worker horizontal scaling (bounded by provider limits) Delays
completion; no data loss (queue durability) Database operations Query
efficiency, write contention Vertical + read replicas Platform-wide
(shared dependency) Report retrieval Object Storage streaming throughput
API horizontal scaling Read-only capability affected History queries
Index coverage on growing tables Read replicas Read-only capability
affected Administrative operations Negligible (low volume) Not
scaling-sensitive Administrative capability only Background maintenance
Task-specific Scheduled, independent of request load Recoverable at next
scheduled run Scalability Matrix Component Scaling Direction Primary
Constraint Notes API Horizontal Stateless --- no upper bound from
architecture Bound by Database/Object Storage capacity in aggregate
Worker Horizontal AI provider rate limits Linear scaling until
provider-bound Queue Horizontal (broker clustering) Broker throughput
Sized to peak enqueue rate Database Vertical + read replicas
Single-writer transactional integrity Deliberate exception to
horizontal-first preference Object Storage Native (managed service) None
(application-level) Scales without application intervention Frontend
Horizontal / CDN-served Static, stateless No backend processing
dependency Capacity Planning Checklist CPU and memory utilization trends
reviewed per component against horizontal scaling thresholds. Queue
depth and message age trend reviewed for sustained (non-transient)
growth. Database data volume and index size growth reviewed per
append-only table. Object Storage volume growth reviewed against
deduplication-adjusted intake rate. AI provider call volume and cost
reviewed against current and forecast Worker concurrency. Network
bandwidth utilization reviewed for upload/download and outbound AI
provider traffic. Concurrent user and concurrent analysis trends
reviewed against forecast organizational growth. Capacity thresholds
validated against most recent load/stress testing results (Section 11).
Performance Review Checklist Change evaluated against the relevant
workload category's performance characteristics (Section 3). Any new or
modified query reviewed for index coverage and N+1 risk (Section 7). Any
new list endpoint confirmed to implement pagination (Section 7). Any new
external dependency call reviewed for timeout, retry, and
circuit-breaker behavior (Section 10). Any new file-handling code path
reviewed for streaming vs. full-buffering behavior (Section 9).
Benchmark or load test results reviewed against established baselines
for regression (Section 11). Performance budget impact assessed against
the relevant Service Level Objective (Section 12;
10-Observability-Architecture.md Section 10). \## 15. Performance
Operational Readiness

A performance architecture is considered operationally ready only when
all of the following conditions are continuously satisfied:

-   Performance baselines exist for every performance-critical workload
    category.
-   Load, stress, and soak testing have been successfully completed
    against the current release candidate.
-   No unresolved performance regressions exist relative to the
    established baseline.
-   Capacity planning has been reviewed using current production
    telemetry.
-   Database query plans for new or modified endpoints have been
    validated.
-   Queue depth, message age, and worker throughput remain within
    expected operating ranges.
-   AI provider latency and failure trends have been reviewed before
    release.
-   Resource utilization demonstrates predictable behavior under
    expected workload.
-   Rollback performance characteristics have been verified.
-   Performance dashboards and alerts accurately reflect the deployed
    architecture. \## 16. Review Notes (v1.0.1)

Review Outcome

-   Reviewed against Documents 00--13 and backend/openapi.yaml.
-   Verified architectural consistency with the Modular Monolith
    architecture.
-   Confirmed alignment with Deployment, Observability, Testing, CI/CD,
    and Release Engineering documents.
-   Reinforced operational governance without modifying the performance
    architecture.
-   No changes were made to workload characteristics, scalability model,
    database strategy, queue architecture, capacity planning
    methodology, or performance principles.
-   This review introduces governance improvements only and preserves
    all previously established architectural decisions.
