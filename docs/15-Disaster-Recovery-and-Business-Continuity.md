Document Information Document:
docs/15-Disaster-Recovery-and-Business-Continuity.md Version: 1.0.1
Status: Final Owner: Site Reliability Engineering Function (Founding
Engineering Team) Audience: Principal SREs, platform architects,
infrastructure engineers, security engineers, and release/on-call
leadership Dependencies: This document defines resilience, recovery, and
continuity properties for the system already described in
00-Project-Context.md through
14-Performance-and-Scalability-Architecture.md and backend/openapi.yaml.
It introduces no new business functionality and no architectural
components beyond recovery mechanisms for what already exists. It builds
directly on 09-Deployment-Architecture.md Section 13 (which this
document supersedes in depth, not in principle),
08-Security-Architecture.md (incident response, audit trails),
10-Observability-Architecture.md (detection signals), and
13-Release-Engineering.md (rollback governance, which is the
release-time counterpart to the infrastructure-time recovery described
here).

Revision History

Version Date Author Summary 1.0.0 Initial Site Reliability Engineering
Function First canonical disaster recovery and business continuity
architecture. 1. Purpose Resilience is an architectural property, not an
operational afterthought, because the failure modes a system can survive
are determined at design time --- by whether state is stored durably and
separably from compute (00-Project-Context.md Section 6), by whether
components fail independently (03-Architecture.md), and by whether every
piece of infrastructure can be reconstructed from a declarative
definition (09-Deployment-Architecture.md Section 2). No amount of
operational effort at the moment of a disaster can retrofit these
properties into a system that was not built with them. This document
does not introduce new architecture; it specifies how the resilience
properties already established in prior documents are exercised,
verified, and governed when things go wrong.

Disaster recovery must be designed before Production, not after an
incident, for a reason specific to Sentinel's own logic:
02-Domain-Model.md establishes that a DigitalAsset's identity is its
SHA-256 hash and that an Analysis is immutable once created. These are
not just data-integrity conveniences --- they are the mechanism by which
a restored system can be proven correct after recovery, by recomputing
hashes and comparing them against recorded state. If disaster recovery
were designed reactively, after data loss had already occurred, this
built-in verification capability would not be understood or exercised in
time to matter. It has to be part of the architecture's use of itself,
planned before the first incident, not discovered during one.

Business continuity differs from disaster recovery in scope and in
question asked. Disaster recovery answers: how do we restore the
technical system --- data, infrastructure, running services --- to a
correct and functioning state after a failure? Business continuity
answers a broader question: which of Sentinel's capabilities must remain
available, in what reduced form, while full recovery is underway, and
how do we keep users and stakeholders appropriately informed throughout?
A platform can have excellent disaster recovery (it eventually restores
perfectly) and poor business continuity (users have no idea what is
happening and no reduced-capability path in the meantime). This document
addresses both, deliberately treating them as related but distinct
concerns.

2.  Resilience Principles Defense in Depth. No single control or backup
    is relied upon as the sole safeguard against data loss or downtime
    --- database backups, Object Storage backups, Infrastructure-as-Code
    definitions, and immutable append-only domain records (Analyses,
    Audit Logs) each independently contribute to recoverability. This
    exists because any single recovery mechanism can itself fail (a
    corrupted backup, an unavailable region) --- overlapping,
    independent safeguards ensure one failure does not cascade into
    unrecoverable loss, directly extending the same principle already
    established in 08-Security-Architecture.md Section 2.

Redundancy. Critical infrastructure components (Database, Object
Storage) are deployed with redundancy sufficient to survive the loss of
a single underlying instance without data loss, consistent with the High
Availability principle in 09-Deployment-Architecture.md Section 2. This
exists because a single point of failure in the system of record would
make every other resilience investment moot --- no amount of
application-layer fault tolerance protects against losing the data
itself.

Fault Isolation. Failures are contained to the component in which they
originate wherever architecturally possible --- a Worker failure does
not affect API availability, an AI provider outage does not affect
analyzers that do not depend on it
(14-Performance-and-Scalability-Architecture.md Section 10). This exists
because a system where every failure propagates everywhere has, in
effect, no fault isolation at all --- its actual availability is only as
good as its least reliable component, which is precisely the outcome the
Modular Monolith's internal boundaries (03-Architecture.md) were
designed to prevent.

Graceful Degradation. When full functionality cannot be sustained, the
system preserves as much capability as safely possible rather than
failing completely, consistent with
14-Performance-and-Scalability-Architecture.md Section 2. This exists
because partial availability during a disaster is materially better for
users than total unavailability, provided the degraded state is itself
safe and clearly understood (Section 4).

Recovery over Perfection. The goal of disaster recovery is restoring the
system to a correct, trustworthy state within an acceptable time --- not
achieving zero data loss or zero downtime unconditionally, which is
neither architecturally guaranteed nor economically justified for every
failure class. This exists because pursuing an unattainable standard of
perfection delays the far more valuable discipline of practicing and
validating recovery that actually works (Section 10).

Automation First. Recovery procedures are automated wherever they can
be, with manual intervention reserved for judgment calls (Section 7)
rather than mechanical execution. This exists because manual recovery
steps performed under the stress and time pressure of an actual incident
are a significant source of human error (Section 3) --- automation
removes that risk from the mechanical parts of recovery, preserving
human attention for genuine decisions.

Immutable Infrastructure. As already established in
09-Deployment-Architecture.md Section 2, infrastructure is never patched
in place --- a compromised or corrupted environment is rebuilt from its
Infrastructure-as-Code definitions rather than repaired incrementally.
This exists because a "repaired" environment carries the risk of
retaining some undetected trace of whatever caused the original failure;
a rebuilt environment is provably clean by construction.

Backup Verification. A backup that has not been tested for successful
restoration is not considered a valid backup, only a candidate one, per
09-Deployment-Architecture.md Section 8. This exists because backup
failures are disproportionately discovered at the worst possible moment
--- during an actual recovery attempt --- unless verification happens
continuously, ahead of need.

Recovery Validation. Every recovery action is validated against the same
integrity checks the domain model itself provides (hash verification for
DigitalAsset content, version continuity for Analysis records) before
the recovered system is considered trustworthy again. This exists
because a recovery that restores availability without restoring
correctness has not actually succeeded --- it has merely made the
failure less visible.

Continuous Improvement. Every recovery event, whether a real disaster or
a planned exercise (Section 10), produces a review that feeds back into
this document, the architecture, or operational practice. This exists
because a disaster recovery capability that is defined once and never
revisited degrades silently as the system evolves around it ---
continuous improvement is what keeps this document accurate rather than
aspirational.

3.  Failure Model API failure

Failure characteristics: One or more API instances become unresponsive
or begin returning elevated error rates, due to resource exhaustion, a
defective release, or an underlying infrastructure fault. Detection:
Readiness/liveness check failures and elevated 5xx rate, per
10-Observability-Architecture.md Sections 5 and 7. Immediate impact:
Degraded or unavailable access to every synchronous capability
(authentication, uploads, retrieval); no impact on already-queued or
in-progress analysis jobs, since Workers operate independently
(09-Deployment-Architecture.md Section 3). Recovery strategy: The
Reverse Proxy routes traffic away from unhealthy instances automatically
(09-Deployment-Architecture.md Section 10); failed instances are
replaced per the Restart Strategy already defined there. If the failure
is release-caused, Rollback Governance (13-Release-Engineering.md
Section 10) applies. Worker failure

Failure characteristics: One or more Worker instances stop consuming
jobs or crash mid-execution, due to a defective release, resource
exhaustion, or an Analyzer-specific fault. Detection: Rising queue depth
and message age, falling job consumption rate, per
10-Observability-Architecture.md Section 5. Immediate impact: Delayed
analysis completion; no job loss, because the Queue's acknowledgment
model preserves unacknowledged jobs
(14-Performance-and-Scalability-Architecture.md Section 8). Recovery
strategy: Failed Worker instances are restarted automatically
(09-Deployment-Architecture.md Section 10); queued jobs are picked up by
remaining or replacement Worker capacity without manual intervention.
Database failure

Failure characteristics: PostgreSQL becomes unreachable, corrupted, or
experiences data loss due to underlying storage failure, an operational
error, or an infrastructure fault. Detection: Database health check
failures, connection errors across API and Worker instances, per
10-Observability-Architecture.md Section 7. Immediate impact:
Platform-wide outage --- every workload category in
14-Performance-and-Scalability-Architecture.md Section 3 depends on
PostgreSQL as the shared system of record. Recovery strategy: Restore
from the most recent valid backup, per Section 5 and Section 6,
replaying any available transaction log to minimize data loss,
consistent with the Database Recovery approach in
09-Deployment-Architecture.md Section 13. Queue failure

Failure characteristics: The Redis/queue broker becomes unreachable or
loses durability guarantees. Detection: Enqueue failures from the API,
consumption failures from Workers, per 10-Observability-Architecture.md
Section 7. Immediate impact: New analysis requests cannot be enqueued;
in-flight jobs already delivered to a Worker may complete, but jobs not
yet acknowledged may be at risk depending on the broker's own durability
configuration at the time of failure. Recovery strategy: Restore or
replace the broker from its Infrastructure-as-Code definition
(09-Deployment-Architecture.md Section 2); any Analysis requests lost
during the outage window are recoverable because the originating POST
/analyses request itself is not silently discarded by the API --- a
failed enqueue surfaces as an error to the caller rather than a silent
loss, consistent with the Fail Safe principle
(08-Security-Architecture.md Section 2). Object Storage failure

Failure characteristics: The S3-compatible store becomes unreachable or
experiences data loss. Detection: Elevated error rate and latency on
storage adapter calls, per 10-Observability-Architecture.md Sections 5
and 7. Immediate impact: New uploads cannot be stored; existing
report/file downloads fail; database metadata remains intact and
unaffected, since PostgreSQL and Object Storage are architecturally
decoupled (00-Project-Context.md Section 6). Recovery strategy: Restore
from the most recent Object Storage backup (Section 5); verify restored
content integrity by recomputing SHA-256 hashes and comparing against
the DigitalAsset records in PostgreSQL, per the Recovery Validation
principle (Section 2) and consistent with 09-Deployment-Architecture.md
Section 13. AI provider outage

Failure characteristics: An external AI provider becomes unavailable,
degraded, or rate-limited beyond expected bounds. Detection: Elevated AI
provider error/timeout rate, circuit breaker activation, per
14-Performance-and-Scalability-Architecture.md Section 10 and
10-Observability-Architecture.md Section 7. Immediate impact: Analyses
depending on the affected provider remain queued or fail; analyses using
unaffected analyzers continue processing normally, per the Fault
Isolation and Graceful Degradation principles (Section 2). Recovery
strategy: Circuit breaker
(14-Performance-and-Scalability-Architecture.md Section 10) prevents
further calls during the outage; affected jobs are retried automatically
once the provider recovers, per the retry policy already defined in
07-Backend-Development-Standards.md Section 9. Network partition

Failure characteristics: Connectivity is lost between components that
are normally able to reach each other (e.g., API to Database, Worker to
Queue) without either component itself failing. Detection: Connection
timeouts and errors observed on one side of the partition without a
corresponding health-check failure on the other, distinguishable from a
genuine component failure through correlated telemetry
(10-Observability-Architecture.md Section 3). Immediate impact:
Equivalent to the failure of whichever dependency became unreachable
from each affected component's perspective --- the impact profile
matches the corresponding component failure above. Recovery strategy:
Resolved once network connectivity is restored; components are designed
to reconnect and resume automatically (stateless design,
09-Deployment-Architecture.md Section 2) without requiring a manual
restart once the partition clears. Infrastructure outage

Failure characteristics: A broader failure of the underlying hosting
environment (e.g., an availability zone or provider-level outage)
affecting multiple components simultaneously. Detection: Correlated,
simultaneous health-check failures across otherwise-unrelated
components, distinguishing this from an isolated single-component
failure. Immediate impact: Potentially platform-wide, depending on the
scope of the underlying outage and the redundancy (Section 2) already in
place across affected components. Recovery strategy: Infrastructure is
reconstructed from its Infrastructure-as-Code definitions
(09-Deployment-Architecture.md Section 2) in an unaffected environment
or availability zone, with data restored from backup as needed (Section
6), consistent with the Infrastructure Rebuild capability already
anticipated in 09-Deployment-Architecture.md Section 13. Configuration
error

Failure characteristics: A deployed configuration change (environment
variable, Infrastructure-as-Code definition) causes incorrect or
degraded behavior without any underlying component actually being
broken. Detection: Configuration validation failure at container startup
(09-Deployment-Architecture.md Section 7) for the most severe cases;
more subtle misconfigurations surface through anomalous metrics or
unexpected behavior reported through normal observability channels.
Immediate impact: Varies with the specific misconfiguration --- ranges
from a single instance failing to start (contained, low impact) to a
platform-wide behavioral defect (high impact) if the misconfiguration
reaches Production undetected. Recovery strategy: Treated as a
release-caused incident where applicable, resolved through Rollback
Governance (13-Release-Engineering.md Section 10) reverting to the last
known-good configuration, since configuration changes follow the same
Infrastructure-as-Code review process as code changes
(09-Deployment-Architecture.md Section 14). Human error

Failure characteristics: An authorized engineer or operator performs an
unintended destructive or incorrect action --- an accidental deletion,
an incorrect manual data change, an erroneous administrative action.
Detection: Anomalous audit log entries (08-Security-Architecture.md
Section 10), unexpected data state discovered through normal operation,
or direct self-reporting by the engineer involved. Immediate impact:
Varies by the specific action; because destructive actions on core
entities are constrained by the Domain Model's invariants (immutable
DigitalAsset, append-only Analysis, per 02-Domain-Model.md), the scope
of what a single human error can irrecoverably destroy is
architecturally limited by design. Recovery strategy: Restoration from
the most recent backup (Section 5) for data-level errors; for
administrative action errors (e.g., an incorrect user deactivation),
reversal through the same administrative capability that caused it,
guided by the audit log record of exactly what changed. Security
incident

Failure characteristics: Unauthorized access, data exfiltration, or
malicious tampering, per the threat model already defined in
08-Security-Architecture.md Section 3. Detection: The security
monitoring, audit logging, and anomaly signals defined in
08-Security-Architecture.md Sections 10 and 13, and
10-Observability-Architecture.md Section 9's Security dashboard.
Immediate impact: Varies by incident type, ranging from a single
compromised credential (bounded, per least-privilege scoping) to broader
data exposure or integrity concerns. Recovery strategy: Follows the
Incident Response process already defined in 08-Security-Architecture.md
Section 13 (detection, containment, recovery, communication,
post-incident review), with this document's backup and restoration
mechanisms (Section 5, Section 6) providing the technical means of the
recovery phase specifically, and the immutable audit trail
(08-Security-Architecture.md Section 2) providing the evidentiary basis
for determining scope. 4. Business Continuity Strategy Critical
services. Consistent with the workload categories defined in
14-Performance-and-Scalability-Architecture.md Section 3, the services
whose continuity matters most are: authentication (the gateway to all
other capability), upload intake, analysis processing, and
report/history retrieval. These four map directly to the core pipeline
described in 00-Project-Context.md Section 5 --- the platform's
fundamental promise to accept content, evaluate it, and explain the
evaluation.

Service prioritization. During a partial outage, recovery effort is
prioritized in the following order, reflecting dependency structure
rather than arbitrary preference: (1) Database and Object Storage, since
every other capability depends on them; (2) Authentication and the API
layer generally, since it is the sole entry point for all synchronous
capability; (3) the Queue and Worker layer, since analysis processing
can tolerate a longer restoration window without permanent data loss,
owing to Queue durability (Section 3); (4) administrative and audit-log
capabilities, which are important but not blocking for core user-facing
functionality.

Essential functionality. At minimum, during degraded conditions,
Sentinel aims to preserve the ability to authenticate, retrieve
already-completed Reports and Analyses, and --- where the affected
component allows --- accept new Uploads for later processing once
Workers recover. This reflects the Graceful Degradation principle
(Section 2): a user should be able to retrieve what Sentinel has already
concluded even if the platform cannot currently produce new conclusions.

Graceful degradation. Where a specific dependency is degraded (e.g., a
single AI provider, per Section 3), the platform's response is scoped
precisely to the affected capability --- other analyzers, other API
routes, and previously completed data remain available, consistent with
the Fault Isolation principle (Section 2) and the analyzer independence
already established in 00-Project-Context.md Section 4.

Operational continuity. The on-call and incident response functions
defined in 09-Deployment-Architecture.md Section 14 and
08-Security-Architecture.md Section 13 remain the operating model during
a disaster --- this document does not introduce a separate continuity
organization, since doing so would fragment accountability rather than
strengthen it.

Recovery communication templates. Predefined internal and external communication templates are maintained so incident communication remains consistent, accurate, and timely during high-pressure events.

Communication principles. Consistent with the Release Communication
principles in 13-Release-Engineering.md Section 8, users and
stakeholders are informed of degraded capability and expected recovery
timelines as soon as those can be responsibly estimated ---
communicating an accurate "we are degraded and working on it" is
preferable to silence, and preferable to a premature, inaccurate "all
clear."

5.  Backup Strategy Database backups. PostgreSQL is backed up on a
    regular, automated schedule independent of application deployment
    activity, consistent with 09-Deployment-Architecture.md Section 8,
    capturing a full, point-in-time-consistent snapshot sufficient to
    reconstruct every entity defined in 02-Database-Design.md (Users,
    Uploads, DigitalAssets, Analyzers, Analyses, Reports, AuditLogs).
    Where the underlying database technology supports it, continuous
    write-ahead log archiving supplements periodic full snapshots,
    narrowing the potential data-loss window between the last snapshot
    and the point of failure.

Object storage backups. Raw file content is backed up on a schedule
commensurate with its role as the durable store for uploaded content
(00-Project-Context.md Section 6), stored in a location and with access
controls distinct from the primary bucket, consistent with
09-Deployment-Architecture.md Section 8's requirement that backup and
primary storage not share a single point of failure or compromise.

Configuration backups. Runtime configuration values (excluding secrets,
handled separately below) are captured as part of the
Infrastructure-as-Code definitions themselves
(09-Deployment-Architecture.md Section 2) --- because configuration is
declared, not manually applied, it is inherently backed up by virtue of
being version-controlled, requiring no separate backup mechanism.

Infrastructure definitions. All Infrastructure-as-Code artifacts
(06-Repository-Structure.md Section 12) are stored in version control,
which itself is redundantly hosted and backed up independently of
Sentinel's own infrastructure --- this is what makes full environment
reconstruction (Section 6) possible even in the event of a complete
infrastructure loss.

Secrets management. Secrets (database credentials, JWT signing keys,
object storage credentials, AI provider API keys) are backed up through
the secrets manager's own redundancy mechanisms, consistent with
08-Security-Architecture.md Section 9 --- secrets are never included in
general-purpose configuration or infrastructure backups, since doing so
would create an additional, less-controlled copy of highly sensitive
material, violating Least Privilege (08-Security-Architecture.md Section
2).

Backup validation. Every backup --- Database and Object Storage alike
--- is periodically validated through an actual restoration test
(Section 10), not merely confirmed to have completed without error,
consistent with the Backup Verification principle (Section 2). A backup
job reporting success is a necessary but not sufficient condition for
that backup being trustworthy.

Retention. Backup retention balances the Recovery Point Objective
framework (Section 8) against the Data Minimization principle already
established in 08-Security-Architecture.md Section 2 and Section 11 ---
backups are retained long enough to meet recovery needs and applicable
compliance requirements, and are not retained indefinitely, since an
indefinitely retained backup is itself a growing liability and attack
surface.

Restoration verification. Following any restoration --- whether a test
(Section 10) or an actual recovery (Section 6) --- the restored Database
and Object Storage content is cross-validated against each other: every
DigitalAsset record's declared SHA-256 hash is checked against the
actual restored content's computed hash, and referential integrity
between restored tables is confirmed. This is the direct, practical
application of the Recovery Validation principle (Section 2), made
possible specifically because the Domain Model already encodes
hash-based identity and relational integrity as first-class properties
(02-Domain-Model.md, 04-Database-Design.md).

6.  Recovery Architecture API. Recovery is achieved by deploying the
    last known-good artifact (09-Deployment-Architecture.md Section 11)
    to replacement instances, since the API is stateless by design
    (09-Deployment-Architecture.md Section 2) --- there is no
    API-specific data to restore, only compute capacity to re-provision,
    which the Immutable Deployments and Infrastructure-as-Code
    principles (Section 2) make a fully reproducible operation.

Workers. Recovery follows the same pattern as the API --- stateless
compute re-provisioned from the last known-good artifact --- with the
additional property that any jobs interrupted mid-processing remain
safely represented in the Queue (Section 3) and are picked up
automatically once healthy Worker capacity is restored, requiring no
manual job resubmission.

Database. Recovery involves restoring the most recent validated backup
(Section 5) to a fresh database instance, replaying any available
write-ahead log beyond that backup point to minimize data loss within
the Recovery Point Objective framework (Section 8), then redirecting API
and Worker instances to the restored instance --- consistent with the
Database Recovery approach already outlined in
09-Deployment-Architecture.md Section 13, elaborated here with explicit
restoration verification (Section 5).

Queue. Recovery involves reconstructing the broker from its
Infrastructure-as-Code definition (Section 2); because the Queue's role
is to durably hold jobs pending consumption rather than to serve as a
permanent system of record, its recovery is oriented around restoring
service availability quickly rather than restoring historical queue
state, with any jobs lost during an outage remaining recoverable at the
originating API layer, per Section 3's Queue Failure analysis.

Object Storage. Recovery involves restoring from the most recent
validated backup (Section 5) and performing the hash-based integrity
verification described there, ensuring that recovered content is not
merely present but provably correct against the corresponding
DigitalAsset metadata retained in PostgreSQL.

Observability. The logging, metrics, and tracing infrastructure defined
in 10-Observability-Architecture.md Section 3 is itself recovered from
Infrastructure-as-Code, prioritized early in any broader infrastructure
recovery sequence (Section 8's Dependency Ordering) because
observability visibility is what allows engineers to confirm the
correctness of every other recovery step as it happens --- recovering
blind is both riskier and slower.

CI/CD. The build, test, and deployment pipeline defined in
12-CI-CD-Architecture.md is recovered from its own
Infrastructure-as-Code definitions; its prompt recovery matters because
it is the mechanism through which every other component's recovery
artifacts (Section 6's API/Worker recovery) are produced and validated
--- a prolonged CI/CD outage would bottleneck recovery of everything
else.

Deployment. The deployment pipeline described in
09-Deployment-Architecture.md Section 11 is the mechanism by which all
of the above recoveries are actually executed --- its own resilience
depends on the same Infrastructure-as-Code reproducibility principle,
and its availability is treated as a precondition for recovering any
other component rather than a parallel concern.

7.  Recovery Governance Recovery ownership. Each disaster recovery event
    has a named Recovery Owner, analogous to the Release Owner role in
    13-Release-Engineering.md Section 7, accountable for coordinating
    the recovery from detection through post-recovery review (Section 3,
    Section 10) and for ensuring the recovery follows this document's
    defined architecture rather than improvised action.

Recovery approval. Recovery actions with irreversible consequences ---
most notably restoring a database backup, which discards any writes made
after the backup's point-in-time --- require explicit approval from a
designated authority before execution, consistent with the Change
Authorization principle in 13-Release-Engineering.md Section 7, except
in cases of active, severe data-loss risk where immediate action
outweighs the delay of seeking approval, mirroring the Emergency Release
exception model in 13-Release-Engineering.md Section 5.

Recovery verification. No recovery is considered complete until the
Restoration Verification steps in Section 5 and the health/SLO checks in
10-Observability-Architecture.md Sections 7 and 10 confirm the restored
system is both available and correct --- matching the Recovery
Validation principle (Section 2).

Documentation. Every recovery event is documented with the same rigor as
a Production release record (13-Release-Engineering.md Section 12) ---
what failed, what was restored, from which backup or artifact, who
approved and executed the recovery, and what verification was performed.

Post-recovery review. Every recovery event, successful or not, triggers
a review identifying whether a Section 2 principle was insufficiently
applied, whether a Section 8 objective was met, and what change --- to
architecture, to backup strategy, or to this document --- should follow,
directly extending the Continuous Improvement principle (Section 2) and
mirroring the Post-Incident Review process in
08-Security-Architecture.md Section 13.

8.  Recovery Objectives Recovery Time Objective (RTO) and Recovery Point
    Objective (RPO) are defined here as a framework, not as fixed
    numeric commitments, consistent with the evidence-based,
    non-arbitrary approach to capacity and performance targets already
    established in 14-Performance-and-Scalability-Architecture.md
    Section 6 and 10-Observability-Architecture.md Section 10 ---
    specific target values are derived from the actual criticality of
    each component and reviewed periodically against real backup/restore
    timings observed during validation exercises (Section 10), not
    asserted without evidence.

Recovery Time Objective (RTO) is defined per component according to its
position in the Service Prioritization ordering (Section 4): components
on which every other capability depends (Database, Object Storage) carry
the strictest RTOs, since their downtime is platform-wide; components
with greater architectural isolation (a single AI provider, per Fault
Isolation, Section 2) carry more relaxed RTOs, since their failure does
not halt the whole platform.

Recovery Point Objective (RPO) is defined per data store according to
its mutability and business criticality: PostgreSQL, holding the
append-only Analysis and AuditLog records central to Sentinel's
explainability and accountability guarantees (00-Project-Context.md
Section 4, 08-Security-Architecture.md Section 2), warrants the tightest
RPO the backup architecture (Section 5) can support --- continuous
log-based recovery narrowing the loss window as far as practical. Object
Storage, holding immutable content that is only ever added, not modified
(02-Domain-Model.md), can tolerate a comparatively longer RPO, since the
risk is losing recently uploaded content rather than corrupting existing
content.

Recovery prioritization. Within a single multi-component disaster (e.g.,
an Infrastructure Outage, Section 3), recovery proceeds in the order
established by the Service Prioritization strategy (Section 4) and the
Recovery Architecture's Dependency Ordering (below) --- recovery effort
is not divided evenly across all affected components simultaneously,
since doing so would delay restoration of the components everything else
depends on.

Dependency ordering. Recovery follows the dependency graph implied by
the runtime topology in 09-Deployment-Architecture.md Section 3:
Infrastructure-as-Code and secrets management must be available first
(nothing else can be rebuilt without them); Database and Object Storage
are restored next (the system of record); the Queue is restored in
parallel with or immediately after; the API and Workers are redeployed
once their dependencies are confirmed healthy; Observability is
prioritized early enough to provide visibility throughout the remainder
of the sequence, per Section 6.

9.  Incident Coordination Detection. As established in
    10-Observability-Architecture.md Section 12, the alerting and
    health-monitoring infrastructure is the primary detection mechanism
    for the failure modes described in Section 3 --- disaster recovery
    coordination begins from the same detection signals already defined
    for day-to-day incident response, rather than a separate
    disaster-specific monitoring system.

Classification. Upon detection, an incident is classified by scope
(single-component vs. multi-component/infrastructure-wide) and by the
failure category in Section 3, since classification determines which
Recovery Architecture procedure (Section 6) and which Recovery Objective
(Section 8) applies.

Escalation. Incidents classified as platform-wide or involving
irreversible data-loss risk escalate immediately to the Recovery Owner
and, where a security dimension is present, to the process defined in
08-Security-Architecture.md Section 13, consistent with the Escalation
model already established for alerting in
10-Observability-Architecture.md Section 8.

Communication. Internal communication follows the same principles
established in 13-Release-Engineering.md Section 8 --- engineering,
on-call, and support functions are informed promptly and accurately,
distinguishing what is known from what is still being investigated.

Stakeholder updates. For incidents with user-visible impact, updates are
issued at a cadence proportional to severity, communicating current
status, expected next update time, and --- once known --- expected
resolution timeline, consistent with the Customer Confidence principle
in 13-Release-Engineering.md Section 2, applied here to disaster
scenarios rather than routine releases.

Incident closure. An incident is not closed until Recovery Verification
(Section 7) confirms the restored system is both available and correct,
and the Post-Recovery Review (Section 7) has been scheduled or completed
--- mirroring the Completion stage already defined for releases in
13-Release-Engineering.md Section 3, applied here to recovery events.

10. Validation & Testing Backup restoration testing. Database and Object
    Storage backups are periodically restored to an isolated environment
    and validated against the Restoration Verification criteria in
    Section 5, confirming both that the backup mechanism functions and
    that recovered data passes the hash and referential integrity checks
    the Domain Model makes possible.

Disaster recovery exercises. The full Recovery Architecture (Section 6)
is periodically exercised end-to-end in a Staging-equivalent environment
(09-Deployment-Architecture.md Section 4) --- simulating a Database or
Object Storage failure and executing the actual recovery procedure ---
to validate that the documented procedure works in practice, not only in
principle, consistent with the Recovery over Perfection principle
(Section 2): an untested recovery plan is a hypothesis, not a
capability.

Failover testing. Where redundancy exists (Section 2), the actual
failover mechanism --- traffic rerouting away from a failed instance,
automatic instance replacement (09-Deployment-Architecture.md Section
10) --- is periodically validated by deliberately removing a healthy
instance from service and confirming the system continues operating
within its Service Level Objectives (10-Observability-Architecture.md
Section 10) throughout.

Recovery verification. Every exercise concludes with the same Recovery
Verification step required of an actual recovery event (Section 7),
ensuring exercises are held to the same standard of proof as real
incidents, rather than being considered successful merely because the
mechanical restoration step completed.

Simulation exercises. Beyond technical restoration testing, incident
coordination itself (Section 9) is periodically rehearsed ---
classification, escalation, and communication --- since the human and
organizational elements of disaster recovery are as prone to failure
under pressure as the technical elements, and are equally valuable to
practice in advance.

Lessons learned. Every exercise, like every real recovery event, feeds
the Post-Recovery Review process (Section 7) and the Continuous
Improvement principle (Section 2) --- an exercise that reveals no gap is
itself a useful data point, but an exercise treated as a checkbox rather
than a genuine test undermines the entire validation program's value.

11. Compliance & Audit Recovery evidence. Every recovery event and every
    validation exercise (Section 10) produces a durable record --- what
    was tested or recovered, what was found, what verification was
    performed --- retained consistent with the evidence retention
    approach already established for release records in
    13-Release-Engineering.md Section 12.

Backup auditability. Backup completion, validation outcomes, and
retention compliance are recorded continuously, not reconstructed after
the fact, so that "is our backup strategy actually working" is always an
answerable, evidence-backed question rather than an assumption.

Recovery documentation. The Recovery Architecture (Section 6) and
Recovery Objectives (Section 8) described in this document are kept
synchronized with the actual system as it evolves --- consistent with
the guiding principle established in 00-Project-Context.md that no
implementation should exist without corresponding documentation, applied
here specifically to disaster recovery procedures.

Testing records. Disaster recovery exercises, failover tests, and backup
restoration tests (Section 10) are recorded with the same rigor as
release testing evidence (13-Release-Engineering.md Section 12), forming
a continuous record of the platform's demonstrated --- not merely
claimed --- recovery capability.

Operational traceability. Combined, recovery evidence, backup
auditability, and testing records allow any historical question about
Sentinel's resilience posture at a given point in time to be answered
from durable records, directly extending the Auditability principle
already established in 08-Security-Architecture.md Section 2 and
13-Release-Engineering.md Section 2 into the disaster recovery domain.

12. Future Evolution The following directions extend Sentinel's current
    resilience model without contradicting it, deferred because current
    scale and product requirements do not yet require them:

Cross-region deployment. As anticipated in 09-Deployment-Architecture.md
Section 15, the stateless API and Worker design already provides the
foundation for running redundant copies across regions; the primary
evolution required for disaster recovery purposes would be establishing
cross-region Database and Object Storage replication, extending the
Redundancy principle (Section 2) beyond a single region's failure
domain.

Multi-cloud resilience. Building on the provider-abstracted design of
Object Storage and AI provider access (08-Security-Architecture.md
Section 8, 09-Deployment-Architecture.md Section 15), a multi-cloud
posture would extend Defense in Depth (Section 2) to the level of the
infrastructure provider itself, protecting against a provider-wide
outage rather than only a regional one within a single provider.

Automated failover. Extending the currently automated instance-level
failover (09-Deployment-Architecture.md Section 10) to component-level
failover --- for example, automatic Database failover to a standby
replica without manual intervention --- would reduce the Recovery Time
Objective for the platform's most critical dependency, consistent with
the Automation First principle (Section 2).

Geo-redundancy. A natural extension of cross-region deployment,
geo-redundancy would allow Sentinel to continue serving users from an
unaffected region during a full regional outage, representing the
strongest form of the Redundancy principle (Section 2) applied at the
broadest possible scope.

Chaos engineering. Systematically and deliberately injecting failures
into a controlled environment --- beyond the planned Disaster Recovery
Exercises in Section 10 --- would validate resilience against failure
combinations and timings that scheduled exercises might not anticipate,
strengthening confidence in Fault Isolation and Graceful Degradation
(Section 2) under more realistic, less predictable conditions.

Continuous resilience testing. Rather than periodic, scheduled
validation (Section 10), continuously and automatically exercising
backup restoration and failover as a standing part of the CI/CD and
observability pipelines (12-CI-CD-Architecture.md,
10-Observability-Architecture.md) would shift resilience validation from
a point-in-time activity to an ongoing property of the system, directly
extending the Continuous Improvement principle (Section 2) into full
automation.

13. Disaster Recovery Decision Records The following are permanent
    resilience commitments, derived directly from this document and the
    prior architecture, and should not be revisited without a
    deliberate, reviewed revision:

No backup is considered valid until it has been successfully restored
and verified, per the Backup Verification principle (Section 2, Section
5) --- a completed backup job alone is insufficient evidence of
recoverability. Recovered Object Storage content is always
cross-validated against its recorded SHA-256 hash in PostgreSQL before
being considered trustworthy, directly leveraging the Domain Model's
hash-based identity guarantee (02-Domain-Model.md) as a built-in
recovery integrity check. Infrastructure is always rebuilt from
Infrastructure-as-Code definitions during recovery, never patched in
place, consistent with Immutable Infrastructure (Section 2) and
09-Deployment-Architecture.md Section 2. Database restoration requires
explicit approval except in cases of active, severe, and irreversible
data-loss risk, mirroring the Emergency Release exception model already
established in 13-Release-Engineering.md Section 5. Recovery priority
always follows the dependency ordering in Section 8 ---
Infrastructure-as-Code and secrets first, then Database/Object Storage,
then Queue, then API/Workers, with Observability restored early enough
to guide the remainder of the sequence. Every recovery event and every
disaster recovery exercise concludes with a Post-Recovery Review,
feeding the Continuous Improvement principle (Section 2) --- no
recovery, successful or not, is closed without one. Secrets are never
included in general infrastructure or configuration backups, and are
recovered exclusively through the secrets manager's own redundancy
mechanisms, preserving Least Privilege (08-Security-Architecture.md
Section 2) even during recovery. Appendix Failure Matrix Failure Type
Detection Signal Immediate Impact Scope Data Loss Risk API failure
Readiness/liveness failure, elevated 5xx Synchronous capability only
None (stateless) Worker failure Queue depth/age growth Delayed analysis
completion None (queue durability) Database failure Health check
failure, connection errors Platform-wide Bounded by RPO (Section 8)
Queue failure Enqueue/consumption failure New analysis requests Possible
for unacknowledged jobs Object Storage failure Storage adapter errors
Upload/download capability Bounded by RPO (Section 8) AI provider outage
Provider error/timeout rate, circuit breaker Affected analyzer type only
None Network partition Correlated one-sided connection errors Matches
affected dependency None (transient) Infrastructure outage Correlated
multi-component health failures Potentially platform-wide Bounded by
redundancy (Section 2) Configuration error Startup validation failure or
anomalous metrics Varies by scope None (reversible via rollback) Human
error Audit log anomaly, self-report Varies, bounded by domain
invariants Bounded by RPO (Section 8) Security incident Security
monitoring, audit anomaly Varies by incident type Bounded by containment
speed Recovery Dependency Graph text

Infrastructure-as-Code + Secrets Management │ ▼ Database ◄──────► Object
Storage │ ▼ Queue │ ┌─────────┴─────────┐ ▼ ▼ API Workers │ ▼
Observability (restored early, guides remainder of sequence) │ ▼ CI/CD │
▼ Deployment Pipeline Backup Matrix Data Store Backup Frequency Basis
Validation Method Retention Basis PostgreSQL Regular snapshot +
continuous log archiving Restoration + referential integrity check RPO +
compliance requirement Object Storage Regular snapshot Restoration +
SHA-256 hash cross-check against DB RPO + compliance requirement
Infrastructure-as-Code Continuous (version control) Successful
environment reconstruction Indefinite (version history) Secrets Secrets
manager's native redundancy Secrets manager's own validation Per secrets
manager policy Recovery Validation Checklist Failure classified per the
Failure Model (Section 3). Recovery Owner assigned (Section 7). Recovery
approval obtained where required (Section 7), or emergency exception
explicitly recorded. Recovery executed per the Dependency Ordering
(Section 8). Restored Database data passes referential integrity checks.
Restored Object Storage content passes SHA-256 hash cross-validation
against PostgreSQL records. Health, readiness, and SLO signals confirmed
nominal post-recovery (10-Observability-Architecture.md Sections 7, 10).
Recovery documented per Section 11. Post-Recovery Review scheduled or
completed (Section 7). Incident formally closed (Section 9). Incident
Severity Matrix Severity Scope Example Escalation Critical
Platform-wide, data-loss risk Database failure, infrastructure outage
Immediate escalation, may invoke emergency approval exception High Major
capability degraded Queue failure, Object Storage failure Prompt
escalation, standard approval path Moderate Single capability or
dependency affected AI provider outage, single Worker failure Standard
on-call response, no special escalation Low Contained, self-resolving,
or already mitigated Transient network partition, single API instance
restart Logged and monitored, no escalation required

## Recovery readiness review cadence. Disaster recovery readiness is reviewed after every major architectural change and at a recurring operational cadence so documented procedures never drift from deployed reality.

14. Recovery Operational Readiness

A disaster recovery capability is considered operationally ready only
when:

-   Recovery procedures have been exercised successfully in a
    non-production environment.
-   Backup restoration has been verified rather than assumed.
-   Recovery ownership and approval responsibilities are documented.
-   Infrastructure-as-Code definitions are current and reproducible.
-   Recovery dependencies are validated in the documented order.
-   Observability is available to verify each recovery stage.
-   Post-recovery validation confirms both availability and data
    integrity.
-   Every recovery exercise produces actionable review findings.

## 15. Review Notes (v1.0.1)

Review Outcome

-   Reviewed against Documents 00--14 and backend/openapi.yaml.
-   Confirmed consistency with deployment, observability, release
    engineering, and performance architecture.
-   Strengthened governance only; no recovery strategy, backup model,
    resilience principle, or continuity policy was modified.
