18 - RFC Process Document Information Version: 1.0.1

Status: Final --- Canonical

Owner: Architecture Owner (as defined in 16-Engineering-Governance.md,
Section 3.1), with process custodianship shared across all Engineering
Owners

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
16-Engineering-Governance.md 17-Architecture-Decision-Records-Guide.md
backend/openapi.yaml Revision History:

Version Change Rationale 1.0 Initial canonical RFC process established
Sentinel required a structured, pre-decision proposal process to precede
Architecture Decision Records, fulfilling the Design Review requirement
defined in 16-Engineering-Governance.md, Section 5.3 1. Purpose RFCs
exist because not every significant technical question has an obvious
answer before it is discussed. Document 17 defines how a decision, once
made, is permanently recorded as an ADR. But many decisions are not
obvious enough to be proposed and approved in a single step --- they
require exploration of multiple viable approaches, input from more than
one domain owner, and iteration on the problem statement itself before a
decision can even be framed. The RFC process exists to provide a
structured space for that exploration, separate from the act of
recording a final decision.

Discussion should happen before implementation because the cost of
changing a decision rises sharply once code exists. A proposal discussed
on paper can be revised in minutes; the same change discovered after
weeks of implementation carries the cost of rework, wasted effort, and
potentially production risk if it ships before the flaw is found. The
RFC process front-loads disagreement and discovery into the cheapest
possible stage of the work, consistent with the Architecture Before
Implementation principle (16-Engineering-Governance.md, Section 2.2).

RFCs differ from ADRs in purpose, not authority. An RFC is a proposal
under discussion --- it may contain open questions, competing
alternatives, and unresolved trade-offs, and its outcome may be
rejection, withdrawal, or substantial revision. An ADR, as defined in
17-Architecture-Decision-Records-Guide.md, is a record of a decision
already made --- it documents what was decided and why, with the
expectation that it is enacted. Every ADR may originate from an RFC once
the proposal reaches consensus, but not every RFC produces an ADR (an
RFC may be rejected or withdrawn), and not every ADR requires a
preceding RFC (some architectural decisions are narrow enough to be
proposed and decided directly per
17-Architecture-Decision-Records-Guide.md, Section 4). The RFC is the
deliberation; the ADR is the verdict.

Relationship to Engineering Governance. This document operationalizes
the Design Reviews requirement in 16-Engineering-Governance.md, Section
5.3, which mandates that non-trivial changes receive written design
review before implementation begins. It also operationalizes the
Consensus and Escalation mechanisms defined in Section 5.5--5.6 of that
document, applying them specifically to the pre-decision proposal stage.
Where an RFC reaches a decision that meets the criteria in
17-Architecture-Decision-Records-Guide.md, Section 3, that decision is
subsequently recorded as an ADR; the RFC and the ADR together form a
complete, traceable record of both the deliberation and the outcome.

2.  RFC Principles 2.1 Proposal Before Implementation No significant
    technical work begins until its RFC (where required, per Section 3)
    has reached a decision. Why: implementation started during open
    deliberation creates pressure to conclude the discussion in favor of
    whatever has already been built, undermining the discussion's
    objectivity.

2.2 Open Technical Discussion RFCs are visible to, and open for comment
from, any engineer, not only the required reviewers. Why: significant
technical proposals frequently have consequences outside the domain the
author anticipated; open discussion surfaces those consequences from
people who would not otherwise have been consulted.

2.3 Evidence-Based Arguments Positions taken during RFC discussion ---
for or against a proposal --- are expected to be supported by evidence
(benchmarks, prior incidents, comparable systems), consistent with
16-Engineering-Governance.md, Section 2.6. Why: without this
expectation, RFC discussions devolve into unresolvable arguments of
preference rather than converging on a technically sound outcome.

2.4 Explicit Scope Every RFC states precisely what it does and does not
propose to change. Why: scope creep during discussion is one of the most
common ways RFCs stall --- without an explicit boundary, reviewers
debate adjacent concerns the RFC was never meant to resolve.

2.5 Alternatives Considered Every RFC documents the alternative
approaches evaluated, not only the preferred one. Why: a proposal
presented without alternatives cannot be evaluated on its merits
relative to other options, and reviewers are left unable to assess
whether the proposed approach is actually the best available one.

2.6 Transparent Review Review activity --- comments, objections,
revisions --- is preserved as part of the RFC's history, not conducted
through untracked conversation. Why: if the substance of review happens
outside the recorded process, the RFC becomes an incomplete account of
how the decision was actually reached, defeating its purpose as a
durable record.

2.7 Consensus Building The RFC process is structured to converge
disagreement into a shared decision, rather than to declare a winner
between opposing positions. Why: proposals adopted over unresolved
objections from domain owners tend to be revisited and re-litigated
after implementation; building genuine consensus during the RFC stage
reduces the likelihood of costly rework later.

2.8 Reviewability An RFC is written so that a reviewer with no prior
involvement in the problem can understand the motivation, the proposal,
and the trade-offs without additional context. Why: RFCs are reviewed by
domain owners who may not have been part of the proposal's origin; a
document that assumes shared context excludes exactly the reviewers
whose independent judgment is most valuable.

2.9 Traceability Every RFC references the canonical documents (00--17)
it is constrained by or would affect, and any ADRs or prior RFCs it
builds upon or supersedes. Why: technical proposals are rarely
independent of prior decisions; traceability allows reviewers and future
readers to understand a proposal's place in Sentinel's decision history.

2.10 Living Process The RFC process itself is revisited and adjusted
based on how well it functions in practice, consistent with
16-Engineering-Governance.md, Section 2.9. Why: a proposal process that
cannot adapt to the friction or gaps discovered through its own use will
eventually be bypassed rather than improved.

3.  When an RFC Is Required An RFC is required whenever a proposal is
    significant enough to warrant deliberation among multiple
    perspectives before a decision can be made --- that is, when the
    right answer is not yet obvious and the consequences of a wrong
    answer are high. Specifically:

New architectural capability --- introducing a system-level capability
not currently described in 03-Architecture.md. Major feature proposal
--- a feature whose scope requires changes across multiple domains
(e.g., domain model, API, database) as defined in 02-Domain-Model.md and
05-API-Specification.md, within the bounds of existing product
requirements (01-Product-Requirements.md). Large refactoring --- a
refactoring effort whose scope crosses module boundaries defined in
06-Repository-Structure.md or affects more than one domain owner's area
of accountability. Technology adoption --- evaluating a new language,
framework, runtime, or major library where the right choice is not yet
clear and multiple viable options exist. Breaking API evolution --- a
proposed change to backend/openapi.yaml or 05-API-Specification.md that
would break backward compatibility, per the exception process referenced
in 16-Engineering-Governance.md, Section 2.7. Deployment strategy
changes --- proposed changes to the topology or environment strategy in
09-Deployment-Architecture.md where multiple approaches are viable.
Security model changes --- proposed changes to trust boundaries,
authentication, or authorization models in 08-Security-Architecture.md
that require security and architecture input together. Performance
strategy changes --- proposed changes to caching, concurrency, or
scaling strategy in 14-Performance-and-Scalability-Architecture.md where
the trade-offs are not yet well understood. Developer tooling ---
proposals to introduce or materially change internal tooling that
affects how engineers build, test, or ship Sentinel. Engineering
workflow --- proposals to change how engineering work itself is
conducted, where the change is technical in nature (e.g., CI/CD pipeline
structure per 12-CI-CD-Architecture.md), distinct from the governance
process defined in 16-Engineering-Governance.md itself. An RFC is NOT
required for:

Decisions narrow enough in scope and consequence to be proposed and
decided directly as an ADR without prior open discussion, per
17-Architecture-Decision-Records-Guide.md, Section 3. Routine code
changes, bug fixes, or internal refactoring that do not cross module
boundaries, per 16-Engineering-Governance.md, Section 7.4.
Implementation details that do not affect architecture, contracts, or
cross-domain concerns. Decisions where only one reasonable approach
exists and no meaningful alternative requires evaluation. Changes
governed entirely by an existing, already-approved RFC or ADR. Why this
boundary exists: the RFC process is deliberately reserved for decisions
that benefit from open deliberation --- where the right answer is
genuinely uncertain or the consequences of getting it wrong are high
enough to justify the cost of broad review. Requiring an RFC for every
decision would dilute the process's authority and slow down work that
does not need it, undermining the Continuous Improvement principle in
16-Engineering-Governance.md, Section 2.9. Where a decision is narrow
enough to be proposed and approved directly, the ADR process
(17-Architecture-Decision-Records-Guide.md) is the appropriate mechanism
rather than an RFC.

4.  RFC Lifecycle 4.1 Draft The author writes an initial version of the
    RFC using the mandatory template (Section 5), status Draft, before
    requesting any formal review. Why: allowing a private drafting stage
    lets the author develop the proposal's structure and initial
    reasoning without the overhead of public review on an unfinished
    idea.

4.2 Proposal The author publishes the RFC to the repository (Section 8)
and formally requests review, status changes to Proposed. Why:
publication marks the transition from private thinking to a proposal the
organization is accountable for engaging with, starting the clock on the
review period (Section 7.2).

4.3 Review Required reviewers (Section 7.1) examine the proposal against
the Proposal Quality Standards (Section 6). Why: review at this stage
exists to ensure the proposal is complete and technically sound enough
to support productive open discussion, rather than allowing an
underdeveloped proposal to consume broad review attention.

4.4 Discussion The RFC is open for comment from any engineer, consistent
with the Open Technical Discussion principle (2.2). Discussion is
recorded as part of the RFC's history (2.6). Why: the discussion stage
is where the RFC process delivers its primary value --- surfacing
perspectives and objections that the author and required reviewers alone
would not have identified.

4.5 Revision The author revises the RFC in response to discussion, with
substantive revisions noted in the document's history. Why: unlike an
accepted ADR (17-Architecture-Decision-Records-Guide.md, Section 2.2),
an RFC is expected to change during its lifecycle; revision is the
mechanism by which discussion actually improves the proposal rather than
merely commenting on a fixed document.

4.6 Decision Once discussion converges, the required reviewers make an
explicit decision on the RFC: Accepted, Rejected, or return to Revision
if not yet resolved. Why: an RFC that lingers indefinitely in discussion
without a decision provides none of the benefit of a proposal process
--- it must reach a clear conclusion to be useful.

4.7 Accepted The RFC's status changes to Accepted, signifying the
proposal is approved to move forward. Why: acceptance is the formal
governance checkpoint that authorizes the next stage (implementation
handoff or ADR creation) to begin.

4.8 Rejected The RFC's status changes to Rejected, with the rationale
recorded in the Decision section. Why: recording rejection with
rationale prevents the same proposal from being re-litigated later
without new information, consistent with the value described for
rejected ADRs (17-Architecture-Decision-Records-Guide.md, Section 7.6).

4.9 Withdrawn The author may withdraw an RFC before a decision is
reached, status changes to Withdrawn, with the reason recorded. Why:
authors sometimes discover, through discussion, that the proposal is no
longer necessary or has been superseded by a better-framed alternative;
withdrawal preserves that outcome honestly rather than forcing an
artificial rejection.

4.10 Archived Accepted, Rejected, and Withdrawn RFCs remain permanently
in the repository in an archived state. Why: consistent with the
Traceability principle (2.9), the historical record of what was proposed
and how it was resolved has lasting value regardless of outcome.

4.11 Implementation Handoff For Accepted RFCs, implementation work is
scoped and begun based on the RFC's Proposal and Implementation
Considerations sections. Why: the handoff stage exists to ensure
implementation proceeds against the specific, reviewed proposal rather
than against the author's evolving private understanding of it.

4.12 ADR Creation Where the accepted RFC's decision meets the criteria
in 17-Architecture-Decision-Records-Guide.md, Section 3, an ADR is
created referencing the RFC, recording the final decision in the
permanent architectural record. Why: the RFC captures the deliberation,
but 17-Architecture-Decision-Records-Guide.md establishes the ADR as the
canonical record of architecture-level decisions; routing accepted RFCs
through ADR creation keeps a single, consistent decision-record
mechanism for architecture regardless of whether the decision originated
from open discussion or a direct proposal.

5.  RFC Template Every RFC contains the following mandatory sections.

RFC Number --- A unique, sequential identifier (Section 8.3). Exists to
allow unambiguous reference from discussion, code, and other documents.

Title --- A concise statement of the proposal's subject. Exists to make
the repository index scannable and to distinguish this RFC from others
addressing related topics.

Status --- One of Draft, Proposed, Accepted, Rejected, Withdrawn
(Section 8.5). Exists to make the proposal's current standing
immediately visible without reading the full discussion history.

Date --- The date the RFC was proposed and, separately, the date of its
most recent status transition. Exists to place the proposal in time
relative to other concurrent work and to measure review duration
(Section 7.2).

Authors --- The engineer(s) who wrote the proposal. Exists to identify
who is accountable for revising the RFC in response to discussion.

Reviewers --- The domain owner(s), per 16-Engineering-Governance.md
Sections 3--4, required to review the proposal. Exists to establish
accountability for the eventual decision.

Summary --- A short, plain-language description of what is being
proposed. Exists to let a reader determine relevance to them within
seconds, before investing time in the full document.

Background --- The relevant history and current state that motivates the
proposal, referencing Documents 00--17 as applicable. Exists because a
proposal cannot be evaluated without understanding the situation it
responds to.

Motivation --- Why this proposal matters now --- what problem,
limitation, or opportunity it addresses. Exists to separate the
justification for acting at all from the specific mechanism proposed to
act.

Problem Statement --- A precise statement of the question the RFC
answers. Exists to keep the proposal and its discussion anchored to a
specific, evaluable question rather than a broad area of concern.

Proposal --- The specific approach being proposed, described in enough
detail for reviewers to evaluate its soundness without requiring
implementation-level code. Exists as the core content the rest of the
RFC supports and justifies.

Alternatives --- Other approaches considered and why they were not the
primary proposal, per the Alternatives Considered principle (2.5).
Exists to demonstrate the proposal was arrived at deliberately and to
prevent reviewers from raising already-considered options as if they
were overlooked.

Trade-offs --- What is gained and given up by adopting this proposal.
Exists to give reviewers an honest, complete basis for judgment rather
than a one-sided case for adoption.

Risks --- Known risks introduced by the proposal, referencing
08-Security-Architecture.md,
14-Performance-and-Scalability-Architecture.md, or
15-Disaster-Recovery-and-Business-Continuity.md as relevant. Exists to
satisfy the Risk Evaluation expectation established in
16-Engineering-Governance.md, Section 5.4, applied at the proposal
stage.

Open Questions --- Aspects of the proposal not yet resolved at the time
of publication. Exists to invite the discussion stage to focus
explicitly on the proposal's genuine uncertainties rather than
relitigating settled aspects.

Dependencies --- Other RFCs, ADRs, or system components this proposal
depends on. Exists to make sequencing and prerequisite relationships
explicit, consistent with the Traceability principle (2.9).

Related Documents --- The canonical documents (00--17) and
backend/openapi.yaml sections this proposal is constrained by or would
affect. Exists to anchor the proposal to Sentinel's existing Single
Source of Truth model (16-Engineering-Governance.md, Section 2.3).

Implementation Considerations --- Practical considerations relevant to
implementing the proposal if accepted (sequencing, migration, rollout),
without prescribing implementation code. Exists to inform the
Implementation Handoff stage (Section 4.11) without turning the RFC into
an implementation plan.

Decision --- The final outcome and its rationale, completed at the
Decision stage (Section 4.6). Exists to record not just what was decided
but why, consistent with the emphasis on rationale established in
17-Architecture-Decision-Records-Guide.md, Section 1.

Outcome --- A retrospective note, added after implementation, on whether
the proposal achieved its intended effect. Exists to close the feedback
loop on the RFC's original Motivation and Proposal, informing future
proposals of similar kind.

6.  Proposal Quality Standards An RFC is not considered ready to move
    from Review (4.3) into Discussion (4.4) unless it meets the
    following standards.

Evidence. Claims made in Motivation or Proposal are supported by data or
precedent referenced in Background, not asserted without support,
consistent with the Evidence-Based Arguments principle (2.3). Why:
unsupported claims invite unproductive disagreement rather than
converging discussion toward resolution.

Architecture. The Proposal explicitly states its relationship to
03-Architecture.md and 02-Domain-Model.md --- whether it fits within
existing boundaries or requires their evolution. Why: a proposal that
silently assumes an architectural change without stating so will surface
that assumption late in discussion, wasting review effort already spent.

Security. The Risks section states whether the proposal has security
implications, and if so, the Security Owner is included among required
reviewers (Section 7.1) per 16-Engineering-Governance.md, Section 10.4.
Why: security consequences of new proposals are frequently indirect and
are only reliably caught by including the Security Owner explicitly
rather than assuming general reviewers will notice them.

Performance. The Trade-offs section states expected performance impact
relative to 14-Performance-and-Scalability-Architecture.md, where
relevant. Why: performance consequences that are not stated up front are
typically discovered only after implementation, when they are far more
expensive to address.

Maintainability. The Trade-offs section states the proposal's expected
effect on long-term maintainability, consistent with
16-Engineering-Governance.md, Section 2.10. Why: proposals that are
attractive in the short term but costly to maintain must be evaluated
honestly against that cost before adoption, not discovered afterward.

Compatibility. The Proposal states whether it preserves backward
compatibility with the API contract (05-API-Specification.md,
backend/openapi.yaml) and database schema (04-Database-Design.md),
consistent with 16-Engineering-Governance.md, Section 2.7. Why:
compatibility impact must be an explicit, reviewed decision rather than
a side effect discovered during implementation.

Operational Impact. The Implementation Considerations section addresses
effects on deployment (09), observability (10), and incident response,
consistent with Operational Responsibility
(16-Engineering-Governance.md, Section 2.8). Why: proposals that are
technically sound but operationally difficult transfer hidden cost onto
whoever runs the system in production.

Cost. Where the proposal introduces new infrastructure, tooling, or
external dependencies, the Trade-offs section states the associated
operational or licensing cost. Why: cost is a legitimate factor in
evaluating a proposal and must be visible to reviewers rather than
assumed away.

Risk. The Risks section states likelihood and severity for each
identified risk, referencing
15-Disaster-Recovery-and-Business-Continuity.md where applicable. Why:
unstated risk cannot be weighed by reviewers, and an RFC that omits it
produces a decision made with incomplete information.

7.  Review Process 7.1 Required Reviewers The required reviewers for an
    RFC are the domain owner(s), per 16-Engineering-Governance.md
    Sections 3--4, whose domain is affected by the proposal. The
    Architecture Owner is a required reviewer whenever the RFC's scope
    includes a change to architecture, domain model, or module
    boundaries (Section 3). Why: requiring the relevant domain owners
    ensures the proposal is evaluated by those most capable of judging
    its soundness in their area, while including the Architecture Owner
    whenever architecture is implicated preserves system-wide oversight.

RFC review service-level expectations. Each RFC should declare an expected review window, an owner responsible for driving it to resolution, and an expected target decision date. If those expectations are exceeded, the RFC should be explicitly extended, closed, or escalated rather than remaining indefinitely active.

7.2 Review Periods Each RFC has a defined minimum review period,
published at the time it enters Proposed status, during which discussion
remains open before a decision may be finalized. Why: a minimum review
period ensures engineers outside the immediate proposal team have a
genuine opportunity to engage, consistent with the Open Technical
Discussion principle (2.2); without a minimum period, decisions could be
rushed before broader input is possible.

7.3 Consensus Reviewers and participants work toward consensus during
Discussion (Section 4.4), consistent with the Consensus Building
principle (2.7) and the Consensus model in 16-Engineering-Governance.md,
Section 5.5. Why: consensus produces decisions that are more durable and
less likely to be revisited, because dissenting views were addressed
rather than overridden.

7.4 Escalation When required reviewers cannot reach consensus, the RFC
escalates to the Architecture Owner for a binding decision, per
16-Engineering-Governance.md, Section 5.6. The escalation and its
resolution are recorded in the RFC's Decision section. Why: recording
the escalation preserves the fact that the proposal was contested and
documents the reasoning that ultimately resolved it, which is valuable
to anyone revisiting the topic later.

7.5 Approval An RFC is approved (status Accepted) only with explicit
sign-off from all required reviewers, recorded in the Reviewers field.
Why: as with ADR approval (17-Architecture-Decision-Records-Guide.md,
Section 7.2), implicit approval through silence does not constitute a
defensible governance record.

7.6 Rejection An RFC may be rejected by its required reviewers, with
rationale recorded in the Decision section, per Section 4.8. Why: a
documented rejection preserves the reasoning against a proposal,
preventing it from being re-proposed later without accounting for the
reasons it was previously declined.

7.7 Withdrawal An author may withdraw an RFC at any point before a
decision is finalized, per Section 4.9, with the reason for withdrawal
recorded. Why: allowing authors to withdraw preserves an honest record
when a proposal is no longer worth pursuing, rather than forcing a
formal rejection that misrepresents why the proposal did not proceed.

8.  Repository Organization 8.1 Directory Structure RFCs reside in a
    dedicated docs/rfc/ directory, separate from both the canonical
    numbered documents (00--17) and the ADR repository (docs/adr/, per
    17-Architecture-Decision-Records-Guide.md, Section 8.1). Why:
    keeping RFCs, ADRs, and canonical documents in distinct locations
    reflects their distinct roles --- proposal, decision record, and
    current specification, respectively --- and prevents confusion about
    which artifact is authoritative for a given purpose.

8.2 Naming Convention Each RFC file is named using its sequential number
and a short slug derived from its title (e.g., 0001-title-slug.md),
matching the convention established for ADRs in
17-Architecture-Decision-Records-Guide.md, Section 8.2. Why: consistent
naming conventions across the RFC and ADR repositories reduce cognitive
overhead for engineers navigating both.

8.3 Sequential Numbering RFC numbers are assigned sequentially and are
never reused, including for rejected or withdrawn RFCs. Why: a stable,
permanent identifier is required to reference an RFC unambiguously from
discussion, code, or a subsequent ADR, regardless of its eventual
outcome.

8.4 Status Management Every RFC's status is one of: Draft, Proposed,
Accepted, Rejected, Withdrawn. Status transitions follow the lifecycle
in Section 4 and are recorded in the file itself and in the repository
index. Why: a small, well-defined set of statuses keeps the lifecycle
model consistent and prevents ambiguous or inconsistent labeling across
the repository.

8.5 Cross-References RFCs reference related RFCs, ADRs, and canonical
documents explicitly by number/filename in the Dependencies and Related
Documents fields. Why: explicit cross-referencing makes the Traceability
principle (2.9) a practical, navigable property of the repository,
particularly important given that an accepted RFC may later produce one
or more ADRs.

8.6 Repository Index The docs/rfc/ directory maintains an index (e.g.,
README.md or INDEX.md) listing every RFC by number, title, status, and
(where applicable) the ADR(s) it produced. Why: without an index,
discovering whether a topic has already been proposed requires scanning
every file individually, discouraging engineers from checking prior
proposals before drafting a new one.

9.  Relationship to Existing Documentation RFCs are proposals --- they
    represent a stage of deliberation, not a canonical specification of
    Sentinel's current state. They never replace the authority of the
    canonical documents (00--17) or backend/openapi.yaml.

01-Product-Requirements.md --- RFCs never introduce new product
functionality; they propose technical approaches to needs already
established in the PRD. An RFC that appears to require new product
functionality is out of scope and must be redirected to product
requirements review. 03-Architecture.md --- An accepted RFC that changes
architecture results in both an ADR (per Section 4.12) and an update to
Document 03 in the same change set, per 16-Engineering-Governance.md,
Section 6.4. The RFC itself is never treated as the current architecture
reference. 04-Database-Design.md, 05-API-Specification.md,
backend/openapi.yaml --- RFCs may propose schema or contract changes,
but the schema and contract remain authoritative only in these
documents, consistent with Single Source of Truth
(16-Engineering-Governance.md, Section 2.3). An accepted RFC's changes
are reflected there before being considered in effect.
08-Security-Architecture.md, 09-Deployment-Architecture.md --- RFCs
proposing changes to security or deployment architecture require the
relevant domain owner as a required reviewer (Section 7.1); the
canonical documents remain the operative reference once a proposal is
accepted and implemented. 11-Testing-Strategy.md --- RFCs may propose
strategic changes to testing approach; day-to-day test design does not
require an RFC (Section 3). 16-Engineering-Governance.md --- This
document operationalizes the Design Reviews requirement in Section 5.3
and the Consensus/Escalation model in Sections 5.5--5.6, applied
specifically to the pre-decision proposal stage.
17-Architecture-Decision-Records-Guide.md --- RFCs and ADRs are
complementary, not redundant: the RFC captures deliberation and may
resolve open questions across alternatives; the ADR captures the
resulting decision in Sentinel's permanent architectural record. An
accepted RFC that meets the ADR criteria in that document's Section 3
always produces a corresponding ADR (Section 4.12 of this document). Why
this relationship is structured this way: if RFCs were treated as
authoritative specifications, Sentinel would risk having proposals ---
some rejected, some still under revision --- competing with the
canonical documents for authority, violating Single Source of Truth.
Structuring RFCs strictly as pre-decision proposals, with ADRs and
canonical document updates as the actual mechanisms of record, preserves
exactly one authoritative description of Sentinel's current state at any
time while still capturing the full deliberative process that produced
it.

Implementation outcome validation. After implementation resulting from an accepted RFC is complete, the Outcome section should be updated with objective evidence describing whether the proposal achieved its intended goals and whether follow-up RFCs or ADRs are required.

10. Governance 10.1 Ownership The Architecture Owner is accountable for
    the integrity of the RFC process and repository, consistent with
    their accountability for architecture-level decision-making
    established in 16-Engineering-Governance.md, Section 3.1, and
    17-Architecture-Decision-Records-Guide.md, Section 10.1. Why: the
    RFC process feeds directly into architecture-level decisions; the
    same accountable party must oversee both stages to ensure
    consistency between them.

10.2 Periodic Review The Architecture Owner periodically reviews open
RFCs to confirm they are progressing through the lifecycle (Section 4)
and are not stalled indefinitely in Discussion or Revision. Why: RFCs
left open indefinitely without a decision undermine the Proposal Before
Implementation principle (2.1) by creating ambiguity about whether work
may proceed.

10.3 Compliance Implementation of an accepted RFC is expected to conform
to the accepted Proposal and its subsequent ADR (where applicable),
consistent with the compliance expectations in
16-Engineering-Governance.md, Section 7.1, and
17-Architecture-Decision-Records-Guide.md, Section 10.5. Why: an
accepted RFC that can be silently disregarded during implementation
provides no governance value.

10.4 Archival Accepted, Rejected, and Withdrawn RFCs remain permanently
in the repository (Section 4.10) and are never deleted. Why: consistent
with the Traceability principle (2.9) and the archival rationale
established for ADRs (17-Architecture-Decision-Records-Guide.md, Section
4.8), the record of what was proposed --- including what was ultimately
declined --- retains lasting institutional value.

10.5 Auditability The RFC repository, together with the ADR repository
(17-Architecture-Decision-Records-Guide.md), the canonical documents
(00--17), and CI/CD evidence (12-CI-CD-Architecture.md), forms part of
Sentinel's audit evidence, consistent with 16-Engineering-Governance.md,
Section 12.6. Why: reconstructing why a given architectural or technical
decision exists frequently requires understanding not just the final
decision (the ADR) but the alternatives considered and the discussion
that shaped it (the RFC) --- both are necessary for a complete audit
trail.

11. Future Evolution This RFC process is proportionate to Sentinel's
    current engineering scale and is expected to evolve without
    requiring replacement of its underlying principles (Section 2):

Architecture Review Board. As anticipated in
16-Engineering-Governance.md, Section 13, and
17-Architecture-Decision-Records-Guide.md, Section 11, the Architecture
Owner's review and escalation authority (Sections 7.1, 7.4) is expected
to evolve into a board of senior engineers, preserving the same review
and decision workflow with a board replacing a single decision-maker.

Voting Support. As the number of engineers participating in RFC
discussion grows beyond what informal consensus (7.3) can efficiently
resolve, a structured voting mechanism among required reviewers is
expected to supplement --- not replace --- consensus-seeking discussion,
reserved for cases where genuine consensus cannot be reached even after
escalation.

Automated RFC Validation. Structural compliance with the mandatory
template (Section 5) --- verifying required sections are present and
cross-references resolve --- is expected to be automated as part of the
CI/CD quality gates defined in 12-CI-CD-Architecture.md, consistent with
the equivalent evolution described for ADRs
(17-Architecture-Decision-Records-Guide.md, Section 11).

Knowledge Graph Integration. As the RFC and ADR repositories grow,
cross-references between RFCs, their resulting ADRs, and affected
canonical documents are expected to be represented as a navigable graph,
allowing engineers to trace a decision's full lineage from initial
proposal to current implementation.

Enterprise Governance. As Sentinel's compliance obligations grow,
consistent with 16-Engineering-Governance.md, Section 13, the RFC
repository is expected to serve as part of the audit evidence for formal
attestation processes, given its role described in Section 10.5.

None of these evolutions alter the RFC Principles in Section 2; they
change the mechanisms by which those principles are enforced as the
organization and system scale.

12. RFC Decision Records The following are the permanent commitments
    established by this document regarding the RFC process itself.

RC-001 --- Significant proposals meeting the criteria in Section 3 must
complete the RFC process before implementation begins. Rationale:
Enforces Proposal Before Implementation (2.1) and fulfills the Design
Reviews requirement in 16-Engineering-Governance.md, Section 5.3.

RC-002 --- RFC discussion is open to any engineer, not limited to
required reviewers. Rationale: Preserves Open Technical Discussion
(2.2), ensuring proposals benefit from perspectives beyond the
immediately obvious stakeholders.

RC-003 --- Every RFC decision --- Accepted, Rejected, or Withdrawn ---
is permanently retained in the repository. Rationale: Preserves
institutional knowledge of what was proposed and why it was or was not
adopted (Section 4.10, 10.4).

RC-004 --- An accepted RFC that meets ADR criteria always produces a
corresponding ADR before implementation is considered fully governed.
Rationale: Ensures the permanent architectural record defined in
17-Architecture-Decision-Records-Guide.md remains the single mechanism
for recording architecture-level decisions, regardless of whether they
originated from open discussion (Section 4.12).

RC-005 --- RFCs never supersede the canonical documents (00--17) or
backend/openapi.yaml as the authoritative description of Sentinel's
current state. Rationale: Preserves Single Source of Truth
(16-Engineering-Governance.md, Section 2.3) by keeping proposals
distinct from specifications.

RC-006 --- RFC numbering is sequential and permanent; numbers are never
reused. Rationale: Guarantees a stable, unambiguous identifier for every
proposal for the lifetime of the system (Section 8.3).

Appendix A.1 RFC Template text

\# RFC-`<number>`{=html}:
```{=html}
<Title>
```
Status: \<Draft \| Proposed \| Accepted \| Rejected \| Withdrawn\> Date:
`<proposal date>`{=html} (last updated: `<date>`{=html}) Authors:
`<names>`{=html} Reviewers: `<names/roles>`{=html}

## Summary

\<Short, plain-language description of the proposal\>

## Background

`<Relevant history and current state>`{=html}

## Motivation

`<Why this proposal matters now>`{=html}

## Problem Statement

`<Precise question this RFC answers>`{=html}

## Proposal

`<The specific approach being proposed>`{=html}

## Alternatives

`<Other approaches considered and why they were not chosen>`{=html}

## Trade-offs

`<What is gained and what is given up>`{=html}

## Risks

\<Known risks, including security/performance/DR implications\>

## Open Questions

`<Aspects not yet resolved>`{=html}

## Dependencies

\<Other RFCs, ADRs, or systems this proposal depends on\>

## Related Documents

\<Canonical documents (00--17) and OpenAPI sections affected\>

## Implementation Considerations

\<Practical considerations for implementation, if accepted\>

## Decision

`<Final outcome and rationale>`{=html}

## Outcome

\<Post-implementation retrospective, added later\> A.2 Lifecycle Diagram
text

Draft \| v Proposed \| v \[Review\] \| v \[Discussion\]
\<----------------+ \| \| v \| \[Revision\] --------------------+ \| v
[Decision](#decision) \| +--\> Rejected (archived, permanent) \| +--\>
Withdrawn (archived, permanent; may occur at any stage before Decision)
\| v Accepted (archived, permanent) \| v Implementation Handoff \| v ADR
Creation (if criteria met per 17-Architecture-Decision-Records-Guide.md,
Section 3) A.3 Repository Layout text

docs/ rfc/ README.md (index of all RFCs by number, title, status,
resulting ADR if any) 0001-`<slug>`{=html}.md 0002-`<slug>`{=html}.md
0003-`<slug>`{=html}.md ... adr/ README.md 0001-`<slug>`{=html}.md ...
A.4 Naming Examples 0001-adopt-event-driven-notification-pipeline.md
0002-evaluate-read-replica-strategy.md
0003-introduce-feature-flag-service.md
0004-restructure-backend-module-boundaries.md A.5 Review Checklist
Before an RFC moves from Review (4.3) into Discussion (4.4), confirm:

Does this proposal meet one of the criteria in Section 3, or should it
instead go directly to ADR (17-Architecture-Decision-Records-Guide.md)
or standard review? Is the Problem Statement precise and the Scope
explicit (2.4)? Are Alternatives documented with reasons for exclusion
(2.5)? Are Trade-offs stated honestly, including downsides? Are
security, performance, compatibility, and operational impacts addressed
per Section 6? Are Risks stated with likelihood and severity? Are
Related Documents and Dependencies correctly cross-referenced? Are the
correct required reviewers identified per Section 7.1? A.6 Decision
Checklist Before finalizing an RFC's Decision (4.6), confirm:

Has the minimum review period (7.2) elapsed? Have all required reviewers
responded, or has escalation (7.4) been invoked if consensus was not
reached? Are all Open Questions resolved, or explicitly deferred with
rationale? Is the Decision section complete with rationale, consistent
with the emphasis on rationale in
17-Architecture-Decision-Records-Guide.md? If Accepted and the proposal
meets ADR criteria, has ADR creation (4.12) been scheduled? If Rejected
or Withdrawn, is the rationale recorded clearly enough to prevent
uninformed re-proposal?

## 13. RFC Operational Readiness

The RFC process is considered operationally ready only when:

-   Every proposal meeting the RFC criteria is documented before
    implementation begins.
-   Required reviewers are assigned according to the Engineering
    Governance ownership model.
-   RFCs maintain valid cross-references to related ADRs and canonical
    documents.
-   Accepted RFCs that require architectural decisions result in
    corresponding ADRs.
-   Repository indexes accurately reflect RFC status and lifecycle
    transitions.
-   Archived RFCs remain permanently available for historical
    traceability and audit.

## 14. Review Notes (v1.0.1)

Review Outcome

-   Reviewed against Documents 00--17 and backend/openapi.yaml.
-   Confirmed alignment with Engineering Governance and the ADR process.
-   Strengthened governance documentation only.
-   No RFC principles, lifecycle, repository organization, review
    workflow, or proposal quality standards were modified.
