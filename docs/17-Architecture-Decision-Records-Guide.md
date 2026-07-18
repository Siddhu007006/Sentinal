17 - Architecture Decision Records Guide Document Information Version: 1.0.1

Status: Final --- Canonical

Owner: Architecture Owner (as defined in 16-Engineering-Governance.md,
Section 3.1)

Audience: Engineering contributors, Principal/Staff Engineers,
Architecture Review participants, Platform Engineering leaders, future
engineering leadership, auditors

Dependencies:

00-Project-Context.md 01-Product-Requirements.md 02-Domain-Model.md
03-Architecture.md 04-Database-Design.md 05-API-Specification.md
06-Repository-Structure.md 07-Backend-Development-Standards.md
08-Security-Architecture.md 09-Deployment-Architecture.md
10-Observability-Architecture.md 11-Testing-Strategy.md
12-CI-CD-Architecture.md 13-Release-Engineering.md
14-Performance-and-Scalability-Architecture.md
15-Disaster-Recovery-and-Business-Continuity.md
16-Engineering-Governance.md backend/openapi.yaml Revision History:

Version Change Rationale 1.0 Initial canonical ADR process established
Sentinel required a permanent, repeatable process for recording
architecture-level decisions, fulfilling the Decision Records
requirement defined in 16-Engineering-Governance.md, Section 5.7 1.
Purpose Document 16 establishes that architecture-level decisions
require a Decision Record (16-Engineering-Governance.md, Section 5.7)
and that Sentinel's Architecture Governance
(16-Engineering-Governance.md, Section 7) depends on deviations and
changes being explicitly recorded rather than silently absorbed into the
codebase. This document defines the concrete process, format, and
lifecycle by which that requirement is fulfilled: the Architecture
Decision Record (ADR).

Architecture decisions require permanent records because architecture is
invisible in code. Reading Sentinel's implementation reveals what the
system does, but not why it was built that way, what alternatives were
rejected, or what constraints shaped the outcome. Without a permanent
record, that reasoning exists only in the memory of the engineers
involved --- memory that fades, leaves the organization, or is simply
wrong in hindsight. An ADR converts a moment of reasoning into a durable
artifact that outlives the individuals who produced it.

Rationale is as important as the decision itself because a decision
without rationale cannot be safely revisited. When circumstances change
--- new evidence, new scale, new requirements --- engineers must be able
to determine whether the original reasoning still holds. If only the
decision was recorded, every reconsideration requires re-deriving the
reasoning from scratch, which is slower, less rigorous, and prone to
repeating past mistakes. If the rationale was recorded, reconsideration
becomes an evaluation of whether the recorded assumptions still hold.

ADRs preserve institutional knowledge that would otherwise be lost.
Sentinel is intended to remain in production and under active
development for years, likely staffed by engineers who were not present
for its original architectural decisions (03-Architecture.md). ADRs are
the mechanism by which the reasoning behind those decisions transfers to
future engineers without requiring direct access to the original
decision-makers.

Relationship to Engineering Governance. This document operationalizes
the Decision Making process defined in 16-Engineering-Governance.md,
Section 5, and the Architecture Governance rules defined in Section 7.
Where Document 16 establishes that architecture-level decisions must be
recorded, reviewed, and escalated when necessary, this document
establishes how --- the format, repository structure, review workflow,
and lifecycle that make Decision Records a practiced, auditable process
rather than an abstract obligation. The permanent governance commitments
recorded as Governance Decision Records in 16-Engineering-Governance.md,
Section 14, are meta-level commitments about the governance model
itself; ADRs, by contrast, are the ongoing, per-decision artifacts
produced as Sentinel's architecture evolves. Every ADR is a Decision
Record in the sense defined by Document 16; this document is the
canonical guide for producing them.

2.  ADR Principles 2.1 One Decision per ADR Each ADR documents exactly
    one architectural decision. Why: bundling multiple decisions into a
    single record makes it impossible to supersede or revisit one
    decision without disturbing unrelated ones, and obscures which
    specific choice a given piece of rationale supports.

2.2 Immutable History Once accepted, an ADR's content is never rewritten
to reflect new thinking; it is superseded by a new ADR instead. Why: if
ADRs could be edited after acceptance, the historical record of what was
actually decided --- and why, at that time --- would be lost, defeating
the purpose of a permanent record. History must be appended to, not
overwritten.

2.3 Evidence-Based Decisions Every ADR's decision is justified by
evidence --- benchmarks, incident data, security findings, load-testing
results --- consistent with 16-Engineering-Governance.md, Section 2.6.
Why: decisions justified only by opinion cannot be defended under later
scrutiny and cannot be objectively re-evaluated when circumstances
change.

2.4 Explicit Trade-offs Every ADR states what is gained and what is
given up by the decision, not merely why the chosen option was
preferred. Why: architecture is the practice of choosing among imperfect
options; omitting the costs of a decision gives future readers a false
impression that the choice was without downside, leading them to be
surprised by consequences that were, in fact, foreseeable.

2.5 Architecture Before Implementation An ADR is written and reviewed
before the decision it describes is implemented, consistent with
16-Engineering-Governance.md, Section 2.2. Why: an ADR written after
implementation is not a decision record but a justification for a fait
accompli, and loses its function as a design review checkpoint.

2.6 Traceability Every ADR references the canonical documents (00--16)
and, where applicable, prior ADRs it depends on, modifies, or
supersedes. Why: architectural decisions do not exist in isolation;
traceability allows a reader to reconstruct the full chain of reasoning
that led to the current state of the system.

2.7 Reviewability Every ADR is written to be understandable and
evaluable by someone who was not present for the original discussion.
Why: an ADR that assumes shared context available only to its authors
fails the primary purpose of a permanent record, which is to inform
readers who lack that context.

2.8 Long-Term Maintainability ADRs favor decisions and rationale that
hold up over multi-year horizons, consistent with
16-Engineering-Governance.md, Section 2.10. Why: architecture decisions
are the most expensive to reverse; an ADR process that tolerates
short-term reasoning without acknowledging long-term cost undermines the
purpose of recording decisions at the architectural level at all.

2.9 Living Documentation While an ADR's content is immutable (2.2), its
status is actively maintained --- an ADR is marked Superseded,
Deprecated, or Implemented as the system evolves. Why: an ADR repository
where every record still claims to be "Proposed" or "Accepted"
regardless of what has actually happened in the system becomes
untrustworthy; status must reflect current reality even though content
does not change.

3.  When an ADR Is Required An ADR is required whenever a decision has
    system-wide, long-lived, or hard-to-reverse consequences.
    Specifically:

Architecture changes --- any change to service boundaries, module
responsibilities, or system-level data flow as defined in
03-Architecture.md. Module boundary changes --- any change to the
responsibilities or interfaces between modules described in
02-Domain-Model.md and 06-Repository-Structure.md. Database strategy
changes --- schema strategy, storage engine choice, indexing strategy,
or data partitioning approach affecting 04-Database-Design.md. API
contract changes --- additions, removals, or semantic changes to the
contract defined in 05-API-Specification.md and backend/openapi.yaml
that affect consumers. Security architecture changes --- any change to
authentication, authorization, data protection, or trust boundaries
defined in 08-Security-Architecture.md. Deployment architecture changes
--- any change to the topology, environment strategy, or infrastructure
model defined in 09-Deployment-Architecture.md. Technology adoption ---
introduction of a new language, framework, runtime, or major library
that becomes a long-term dependency of the system. External dependency
introduction --- adoption of a new external service, provider, or
infrastructure dependency, consistent with the Dependency Rules in
16-Engineering-Governance.md, Section 7.6. Significant performance
strategy changes --- changes to caching strategy, concurrency model, or
scaling approach defined in
14-Performance-and-Scalability-Architecture.md. Disaster recovery
strategy changes --- changes to backup strategy, recovery objectives, or
failover approach defined in
15-Disaster-Recovery-and-Business-Continuity.md. An ADR is NOT required
for:

Routine code changes that do not alter documented architecture,
contracts, or boundaries. Bug fixes that restore documented behavior
rather than change it. Internal refactoring that does not change
external behavior, as defined in 16-Engineering-Governance.md, Section
7.4. Configuration changes that operate within already-documented
deployment parameters. Test additions or improvements that do not change
what is being tested or how. Documentation corrections that do not
reflect a decision, only a clarification of existing, unchanged intent.
Why this boundary exists: requiring an ADR for every change would make
the process an obstacle rather than a safeguard, diluting its authority
and training engineers to treat ADRs as bureaucratic overhead. Reserving
ADRs for decisions with lasting, system-wide consequence keeps the
process proportionate to the risk it exists to manage, consistent with
the Continuous Improvement principle in 16-Engineering-Governance.md,
Section 2.9.

4.  ADR Lifecycle An ADR moves through the following stages. Each stage
    exists to enforce a specific governance guarantee established in
    Document 16.

4.1 Proposal An engineer identifies a decision requiring an ADR (Section
3) and drafts it using the mandatory template (Section 5), status
Proposed. Why: the proposal stage exists to force the decision to be
written down and made explicit before any implementation begins, in
accordance with the Architecture Before Implementation principle (2.5).

4.2 Review The proposal is reviewed by the required reviewers defined in
Section 7.1. Why: review is the mechanism by which the Review Before
Merge principle (16-Engineering-Governance.md, Section 2.4) is applied
at the architectural level, before implementation cost is incurred.

4.3 Discussion Reviewers and the author resolve open questions,
challenge assumptions, and request revisions to the Alternatives
Considered and Trade-offs sections. Why: discussion exists to surface
objections and blind spots while the decision is still cheap to change,
consistent with the purpose of Design Reviews in
16-Engineering-Governance.md, Section 5.3.

4.4 Approval The ADR is formally approved by the required approvers
(Section 7.1) and its status changes to Accepted. Why: approval is the
explicit governance checkpoint that authorizes implementation to begin;
without it, "discussion" could continue indefinitely without ever
becoming a binding decision.

4.5 Implementation Implementation proceeds according to the accepted
ADR. The ADR's "Implementation Status" field is updated to reflect
progress. Why: tracking implementation status against the ADR ensures
the decision record and the system's actual state do not silently
diverge, consistent with the Documentation Governance synchronization
requirement in 16-Engineering-Governance.md, Section 6.6.

4.6 Verification Once implemented, the decision is verified against the
evidence and expectations stated in the ADR (e.g., a performance ADR is
verified against the benchmark it predicted). Why: verification closes
the loop on the Evidence-Based Decisions principle (2.3) --- a decision
that was justified by an expectation must be checked against the
outcome, or the evidence-based process becomes merely evidence-cited.

4.7 Superseding When a later decision replaces an earlier one, a new ADR
is written referencing the original, and the original's status changes
to Superseded, pointing to the superseding ADR. Why: superseding rather
than editing preserves Immutable History (2.2) while still keeping the
repository's active guidance current.

4.8 Archiving ADRs that are superseded, deprecated, or rejected remain
permanently in the repository in an archived state; they are never
deleted. Why: the historical record has value independent of current
relevance --- future engineers benefit from understanding not only
current architecture but the path that led to it, including abandoned
directions.

5.  ADR Template Every ADR contains the following mandatory sections.

ADR Number --- A unique, sequential identifier (Section 8.2). Exists to
allow unambiguous reference from other ADRs, code comments, and
documents.

Title --- A short, descriptive statement of the decision, phrased as a
decision rather than a topic (e.g., "Use logical replication for read
replicas" rather than "Database replication"). Exists to make the
repository index scannable at a glance.

Status --- One of Proposed, Accepted, Rejected, Implemented, Superseded,
Deprecated (Section 8.4). Exists to make the current standing of the
decision immediately visible without reading the full record.

Date --- The date the ADR was proposed and, separately, the date it was
last transitioned in status. Exists to place the decision in time
relative to the system's evolution and other concurrent decisions.

Authors --- The engineer(s) who proposed the decision. Exists to
identify who can be consulted for context not captured in the written
record.

Reviewers --- The domain owner(s), per 16-Engineering-Governance.md
Section 3--4, who reviewed and approved the decision. Exists to satisfy
the Reviewability principle (2.7) and to record accountability for the
approval.

Context --- The circumstances, constraints, and forces that made this
decision necessary, referencing relevant sections of Documents 00--16.
Exists because a decision cannot be evaluated without understanding the
situation that produced it.

Problem Statement --- A precise statement of the question the ADR
answers. Exists to prevent the ADR from drifting into solving multiple,
loosely related problems (violating the One Decision per ADR principle,
2.1).

Decision --- The specific choice made, stated unambiguously. Exists as
the core, actionable content of the record --- everything else supports
or contextualizes this statement.

Alternatives Considered --- Other options that were evaluated, including
why they were not chosen. Exists to demonstrate the decision was
evidence-based and deliberate (2.3), and to prevent future engineers
from re-proposing an alternative that was already rejected for reasons
that still apply.

Trade-offs --- What is gained and what is given up by this decision, per
the Explicit Trade-offs principle (2.4). Exists to give future readers
an honest accounting of the decision's cost, not just its benefit.

Consequences --- The downstream effects of the decision on other parts
of the system, including which canonical documents (00--16) must be or
were updated as a result. Exists to make the ripple effects of the
decision explicit rather than discovered later by accident.

Risks --- Known risks introduced by the decision, and how they are
mitigated or monitored, referencing 08-Security-Architecture.md,
14-Performance-and-Scalability-Architecture.md, or
15-Disaster-Recovery-and-Business-Continuity.md as relevant. Exists to
satisfy the Risk Evaluation requirement in 16-Engineering-Governance.md,
Section 5.4.

Dependencies --- Other ADRs, systems, or external factors this decision
depends on. Exists to make sequencing and prerequisite relationships
explicit, supporting Traceability (2.6).

Related Documents --- The canonical documents (00--16) and
backend/openapi.yaml sections that this ADR affects or is constrained
by. Exists to keep the ADR anchored to the Single Source of Truth model
established in 16-Engineering-Governance.md, Section 2.3.

Implementation Status --- Whether the decision has been implemented,
partially implemented, or is pending, updated over time. Exists to
prevent the ADR from silently diverging from the actual state of the
system (Section 4.5).

Superseded By --- A reference to the ADR that superseded this one, if
applicable, left blank otherwise. Exists to allow readers to navigate
forward in the decision's history rather than acting on an outdated
record.

6.  Decision Quality Standards An ADR is not considered ready for
    approval unless it meets the following standards, each of which
    exists to prevent a specific known failure mode of architectural
    decision-making.

Evidence. The Decision section must be supported by data referenced in
Context or Alternatives Considered, not asserted without support. Why:
unsupported decisions cannot be objectively re-evaluated later and erode
confidence in the ADR process itself.

Benchmarks. Where the decision makes a performance claim, it must
reference actual measurement against the criteria in
14-Performance-and-Scalability-Architecture.md, not a theoretical
expectation. Why: performance intuition is frequently wrong, and
unverified performance claims in an ADR create false confidence in
future capacity planning.

Security Impact. The Risks section must explicitly state whether the
decision has security implications, and if so, must be reviewed by the
Security Owner per 16-Engineering-Governance.md, Section 10.4. Why:
security consequences of architectural decisions are frequently indirect
and easy to overlook unless explicitly required as a checklist item.

Performance Impact. The Consequences section must state the decision's
expected effect on latency, throughput, or resource usage relative to
14-Performance-and-Scalability-Architecture.md. Why: architectural
decisions routinely have performance consequences that are not obvious
from the decision statement alone.

Operational Impact. The Consequences section must state the decision's
effect on deployment (09), observability (10), and incident response,
consistent with Operational Responsibility
(16-Engineering-Governance.md, Section 2.8). Why: a decision that is
architecturally sound but operationally unmanageable transfers hidden
cost onto whoever operates the system in production.

Maintainability. The Trade-offs section must state the decision's effect
on long-term maintainability, per the Long-Term Maintainability
principle (2.8). Why: without an explicit maintainability assessment,
decisions optimized for short-term convenience are indistinguishable
from decisions optimized for durability.

Compatibility. The Consequences section must state whether the decision
preserves backward compatibility with the API contract
(05-API-Specification.md, backend/openapi.yaml) and database schema
(04-Database-Design.md), per 16-Engineering-Governance.md, Section 2.7.
Why: compatibility breaks are among the most consequential and
irreversible outcomes of an architectural decision, and must never be an
unstated side effect.

Cost. Where the decision introduces new infrastructure or external
dependencies, the Consequences section must state the operational cost
implication. Why: architecture decisions are also resourcing decisions,
and omitting cost from the record produces decisions that look free but
are not.

Risk. The Risks section must state the likelihood and severity of the
identified risks and, where applicable, reference
15-Disaster-Recovery-and-Business-Continuity.md for recovery
implications. Why: unstated risk is unmanaged risk; naming it is the
first step toward mitigating or consciously accepting it.

7.  Review Process 7.1 Required Reviewers The required reviewers for an
    ADR are the domain owner(s), as defined in
    16-Engineering-Governance.md, Section 3--4, whose domain is affected
    by the decision. The Architecture Owner is a required reviewer for
    every ADR, regardless of domain, because every ADR by definition
    concerns architecture. Why: requiring the Architecture Owner on
    every ADR ensures a consistent, system-wide perspective is applied
    even when a decision appears narrowly scoped to a single domain.

7.2 Approval Workflow An ADR requires explicit approval from all
required reviewers before its status changes to Accepted. Approval is
recorded in the Reviewers field of the template. Why: implicit approval
(e.g., silence or lack of objection) does not constitute a defensible
governance record; explicit approval creates unambiguous accountability.

7.3 Consensus Reviewers reach consensus through discussion (Section
4.3), consistent with the Consensus model defined in
16-Engineering-Governance.md, Section 5.5. Why: consensus-based review
at Sentinel's current scale is proportionate and avoids the overhead of
formal voting mechanisms while still requiring genuine agreement rather
than passive non-objection.

7.4 Escalation When reviewers cannot reach consensus, the decision
escalates to the Architecture Owner for a binding resolution, per
16-Engineering-Governance.md, Section 5.6. The escalation and its
resolution are recorded in the ADR's Context or Decision section for
future reference. Why: recording the escalation itself preserves the
fact that the decision was contested, which is valuable context for
anyone reconsidering it later.

7.5 Revision During review, an ADR may be revised prior to acceptance;
these revisions are not subject to the Immutable History principle (2.2)
because the ADR has not yet reached Accepted status. Once accepted, no
further revision of content occurs --- only status transitions and
superseding ADRs (Section 4.7). Why: distinguishing pre-acceptance
revision from post-acceptance immutability allows the review process to
function iteratively while still preserving a stable historical record
once a decision is final.

7.6 Rejection An ADR may be rejected by its required reviewers, in which
case its status changes to Rejected and it remains in the repository
permanently with its rationale intact. Why: a rejected ADR is still
valuable institutional knowledge --- it records that an option was
considered and why it was not chosen, preventing future engineers from
re-proposing the same option without new information.

8.  ADR Repository Organization 8.1 Directory Structure ADRs reside in a
    dedicated docs/adr/ directory, separate from the canonical numbered
    documents (00--17). Why: separating ADRs from the canonical document
    set preserves the distinction established in Section 9 --- ADRs
    supplement the canonical documents but are not themselves canonical
    architecture specifications.

8.2 Naming Convention and Numbering Each ADR file is named using its
sequential number and a short slug derived from its title (e.g.,
0001-title-slug.md). Numbers are assigned sequentially and never reused,
including for rejected or superseded ADRs. Why: sequential, non-reused
numbering guarantees every ADR has a stable, permanent identifier that
can be referenced from other documents and code without ambiguity,
consistent with the Immutable History principle (2.2).

8.3 Status Lifecycle Every ADR's status is one of: Proposed, Accepted,
Rejected, Implemented, Superseded, Deprecated. Status transitions follow
the lifecycle defined in Section 4 and are recorded in the file itself
(Status field) and in the repository index. Why: a single, small set of
well-defined statuses keeps the lifecycle model consistent across the
entire repository and prevents ad hoc, inconsistent status labeling.

8.4 Cross-References ADRs reference other ADRs and canonical documents
explicitly by number/filename in the Dependencies and Related Documents
fields. Why: explicit cross-referencing is what makes Traceability (2.6)
a practical, navigable property of the repository rather than an
abstract principle.

8.5 Indexing The docs/adr/ directory maintains an index (e.g., README.md
or INDEX.md) listing every ADR by number, title, and current status.
Why: without an index, discovering relevant prior decisions requires
scanning every file individually, which discourages engineers from
checking prior decisions before proposing new ones --- undermining the
entire purpose of the repository.

9.  Relationship to Existing Documentation ADRs supplement, and never
    replace, the canonical documents (00--16) and backend/openapi.yaml.
    The canonical documents describe the current, authoritative state of
    Sentinel's requirements, architecture, and operational posture. ADRs
    describe the decisions and reasoning that produced that state and,
    going forward, the decisions that will change it.

01-Product-Requirements.md --- ADRs never introduce new product
functionality; they record architectural responses to requirements
already established there. Any ADR whose decision appears to require new
product functionality is out of scope and must be redirected to product
requirements review, not resolved within the ADR process.
03-Architecture.md --- Document 03 is the current authoritative
architecture description. ADRs record the reasoning behind that
architecture and any subsequent changes to it. When an ADR changes the
architecture, Document 03 is updated in the same change set, per the
Documentation Update Policy (16-Engineering-Governance.md, Section 6.4);
the ADR is not a substitute for that update. 04-Database-Design.md,
05-API-Specification.md, backend/openapi.yaml --- ADRs record the
rationale for schema and contract decisions; the schema and contract
themselves remain authoritative only in Document 04, Document 05, and
the OpenAPI specification respectively, consistent with Single Source of
Truth (16-Engineering-Governance.md, Section 2.3).
08-Security-Architecture.md, 09-Deployment-Architecture.md,
10-Observability-Architecture.md --- ADRs record the reasoning behind
changes to these architectures; the documents themselves remain the
operative reference for current security controls, deployment topology,
and observability design. 11-Testing-Strategy.md --- ADRs may record
decisions that affect testing approach at a strategic level (e.g.,
adopting a new test category), but day-to-day test design decisions do
not require an ADR (Section 3). 16-Engineering-Governance.md --- This
document operationalizes Document 16's Decision Records requirement
(Section 5.7) and Architecture Governance rules (Section 7). ADRs are
the artifact type through which those governance requirements are
fulfilled for architecture-level decisions specifically. Why this
relationship is structured this way: if ADRs were treated as
authoritative in place of the canonical documents, Sentinel would have
two competing sources of truth about its own architecture --- the
numbered documents and the ADR repository --- violating Single Source of
Truth (16-Engineering-Governance.md, Section 2.3). Structuring ADRs as
the historical record of why, while the canonical documents remain the
record of what is currently true, preserves a single authoritative
description of the system at any point in time while still preserving
the reasoning that produced it.

10. Governance 10.1 Ownership The Architecture Owner is accountable for
    the integrity of the ADR process and repository, consistent with
    their accountability for 03-Architecture.md under
    16-Engineering-Governance.md, Section 3.1. Why: the same
    accountability that governs the architecture itself must govern the
    record of how that architecture came to be, or the two could diverge
    in authority.

ADR review cadence. The Architecture Owner reviews the ADR repository after major architectural changes and on a recurring operational cadence to ensure accepted ADRs continue to reflect the implemented system.

10.2 Periodic Review The Architecture Owner periodically reviews the ADR
repository to confirm that Accepted and Implemented ADRs still
accurately reflect the system's current architecture, and flags any that
require superseding. Why: without periodic review, ADRs marked as
current guidance can silently become stale as the system evolves through
changes that were not properly recorded, violating the Living
Documentation principle (2.9).

10.3 Deprecation An ADR is marked Deprecated when its decision is no
longer relevant to the system (e.g., the component it concerns was
removed) without being formally superseded by a replacement decision.
Why: distinguishing deprecation from superseding preserves the accuracy
of the historical record --- not every ADR that stops applying was
replaced by a new decision; some simply became moot.

10.4 Supersession An ADR is marked Superseded only when a new, formally
accepted ADR explicitly replaces its decision, per Section 4.7. Why:
requiring a formal replacement (rather than informal abandonment)
ensures every architectural change remains fully traceable, with no gap
between an old decision losing effect and a new decision taking effect.

10.5 Compliance Implementation is expected to comply with Accepted and
Implemented ADRs in the same manner it complies with the canonical
documents, per 16-Engineering-Governance.md, Section 7.1. Deviation from
an accepted ADR follows the same Allowed Deviations process defined in
16-Engineering-Governance.md, Section 7.2. Why: an ADR that can be
silently ignored during implementation provides no actual governance
value; compliance expectations must be identical to those applied to the
canonical documents.

10.6 Auditability The ADR repository, together with the canonical
documents (00--16) and CI/CD evidence (12-CI-CD-Architecture.md), forms
part of Sentinel's audit evidence per 16-Engineering-Governance.md,
Section 12.6. Why: the ability to reconstruct why any architectural
property of Sentinel exists is a compliance and operational necessity,
not merely a historical curiosity, particularly during incident
postmortems or external audits.

Decision verification evidence. When an ADR reaches the Implemented state, objective evidence (benchmarks, tests, migration validation, security review, or operational verification as applicable) should be linked from the ADR so future engineers can verify that the expected outcome was achieved.

11. Future Evolution This ADR process is proportionate to Sentinel's
    current engineering scale and is expected to evolve without
    requiring replacement of its underlying principles (Section 2):

Architecture Review Board. As anticipated in
16-Engineering-Governance.md, Section 13, the single Architecture
Owner's review authority (Section 7.1) is expected to evolve into a
board of senior engineers who collectively serve as required reviewers,
preserving the same approval workflow (Section 7.2) with a board
replacing a single reviewer.

Automated ADR Validation. Structural compliance with the mandatory
template (Section 5) --- such as verifying that all required sections
are present, that referenced documents exist, and that cross-references
resolve --- is expected to be automated as part of the CI/CD quality
gates defined in 12-CI-CD-Architecture.md, reducing reliance on manual
review for mechanically verifiable completeness.

Knowledge Graph Integration. As the ADR repository grows,
cross-references between ADRs and canonical documents (Section 8.4) are
expected to be represented as a navigable graph, allowing engineers to
trace the full lineage of a given architectural property across multiple
superseding decisions.

Decision Analytics. The Engineering Metrics defined in
16-Engineering-Governance.md, Section 11, are expected to extend to
ADR-specific metrics --- time from proposal to acceptance, frequency of
supersession, and rate of decisions that fail verification (Section 4.6)
--- to measure whether the ADR process itself remains healthy.

Enterprise Governance. As Sentinel's compliance obligations grow,
consistent with 16-Engineering-Governance.md, Section 13, the ADR
repository is expected to serve as a direct input to formal audit and
attestation processes, given its role as part of the audit evidence
described in Section 10.6.

None of these evolutions alter the ADR Principles in Section 2; they
change the mechanisms by which those principles are enforced as the
organization and system scale.

12. ADR Decision Records The following are the permanent commitments
    established by this document regarding the ADR process itself.

PC-001 --- Every architecture-level decision defined in Section 3 must
be recorded as an ADR before implementation begins. Rationale: Enforces
Architecture Before Implementation (2.5) and fulfills the Decision
Records requirement in 16-Engineering-Governance.md, Section 5.7.

PC-002 --- Accepted ADR content is immutable; changes are made only
through superseding ADRs. Rationale: Preserves the integrity of the
historical record (2.2) and ensures the reasoning behind past decisions
can never be silently rewritten.

PC-003 --- Rejected and superseded ADRs are retained permanently and
never deleted. Rationale: Prevents the loss of institutional knowledge
about paths considered and not taken (Section 4.8).

PC-004 --- The Architecture Owner is a required reviewer on every ADR
regardless of domain. Rationale: Guarantees a consistent, system-wide
perspective is applied to every architectural decision, however narrow
it initially appears (Section 7.1).

PC-005 --- ADRs supplement but never supersede the canonical documents
(00--16) or backend/openapi.yaml as the authoritative description of the
current system. Rationale: Preserves Single Source of Truth
(16-Engineering-Governance.md, Section 2.3) by keeping a clear
separation between the record of why and the record of what is currently
true.

PC-006 --- Numbering is sequential and permanent; numbers are never
reused. Rationale: Guarantees every ADR has a stable, unambiguous
identifier for the lifetime of the system (Section 8.2).

Appendix A.1 ADR Template text

\# ADR-`<number>`{=html}:
```{=html}
<Title>
```
Status: \<Proposed \| Accepted \| Rejected \| Implemented \| Superseded
\| Deprecated\> Date: `<proposal date>`{=html} (last updated:
`<date>`{=html}) Authors: `<names>`{=html} Reviewers:
`<names/roles>`{=html}

## Context

\<Situation, constraints, and forces motivating this decision\>

## Problem Statement

`<Precise question this ADR answers>`{=html}

## Decision

`<The specific choice made>`{=html}

## Alternatives Considered

`<Other options evaluated and why they were not chosen>`{=html}

## Trade-offs

`<What is gained and what is given up>`{=html}

## Consequences

\<Downstream effects, including canonical documents affected/updated\>

## Risks

\<Known risks and mitigations, including security/performance/DR
implications\>

## Dependencies

`<Other ADRs or systems this decision depends on>`{=html}

## Related Documents

\<Canonical documents (00--16) and OpenAPI sections affected\>

## Implementation Status

\<Not started \| In progress \| Complete\>

## Superseded By

\<Reference to superseding ADR, if applicable\> A.2 ADR Status Diagram
text

Proposed \| v \[Review + Discussion\] \| +--\> Rejected (permanent,
archived) \| v Accepted \| v Implementation \| v Implemented ----\>
Verification \| +--\> Deprecated (no longer relevant, no replacement) \|
+--\> Superseded (formally replaced by new ADR) A.3 Review Workflow
Author drafts ADR using the mandatory template (Appendix A.1), status
Proposed. Required reviewers identified per Section 7.1 (affected domain
owner(s) + Architecture Owner). Review and discussion occur; revisions
made as needed (Section 7.5). Consensus reached, or escalation to
Architecture Owner if not (Section 7.4). Required reviewers formally
approve; status changes to Accepted. Implementation proceeds;
Implementation Status field updated. Upon completion, status changes to
Implemented; decision verified against original evidence (Section 4.6).
If later replaced, a new ADR is written referencing this one; this ADR's
status changes to Superseded. A.4 Directory Layout text

docs/ adr/ README.md (index of all ADRs by number, title, status)
0001-`<slug>`{=html}.md 0002-`<slug>`{=html}.md 0003-`<slug>`{=html}.md
... A.5 Naming Examples
0001-use-logical-replication-for-read-replicas.md
0002-adopt-structured-event-schema-for-audit-log.md
0003-introduce-external-secrets-provider.md
0004-supersede-0001-migrate-to-managed-replication-service.md A.6
Decision Checklist Before submitting an ADR for review, confirm:

Does this decision meet one of the criteria in Section 3, or is an ADR
unnecessary? Is exactly one decision being recorded (Section 2.1)? Is
the Decision supported by evidence, not assertion (Section 6)? Are
Alternatives Considered documented with reasons for rejection? Are
Trade-offs stated honestly, including downsides? Are security,
performance, operational, and compatibility impacts addressed (Section
6)? Are Risks stated with mitigation or monitoring approach? Are Related
Documents and Dependencies correctly cross-referenced? Has the
Architecture Owner been included as a reviewer (Section 7.1)? If this
ADR supersedes a prior one, has the prior ADR's status been updated
accordingly (Section 4.7)?

## 13. ADR Operational Readiness

The ADR process is considered operationally ready only when:

-   Every architecture-level decision requiring an ADR is identified
    before implementation.
-   Required reviewers are assigned according to Engineering Governance.
-   Canonical documents are updated in the same change set as accepted
    architectural changes.
-   ADR cross-references resolve correctly to related documents and
    prior ADRs.
-   Accepted ADRs are periodically reviewed for continued applicability.
-   Superseded and deprecated ADRs remain permanently available for
    historical traceability.

## 14. Review Notes (v1.0.1)

Review Outcome

-   Reviewed against Documents 00--16 and backend/openapi.yaml.
-   Confirmed alignment with Engineering Governance, Architecture,
    Deployment, Security, and Release Engineering.
-   Strengthened governance documentation only.
-   No ADR lifecycle, review workflow, repository organization, template
    structure, or decision quality standards were modified.
