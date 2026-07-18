# Sentinel --- CI/CD Architecture

## Document Information

  -----------------------------------------------------------------------
  Field                               Value
  ----------------------------------- -----------------------------------
  Version                             v0.2

  Status                              Draft

  Owner                               Siddhu

  Audience                            Platform engineers, reviewers,
                                      future maintainers

  Dependencies                        `01-Product-Requirements.md`,
                                      `02-Domain-Model.md`,
                                      `03-Architecture.md`,
                                      `11-Testing-Strategy.md`

  Revision History                    v0.1 --- initial draft, 2026-07-12
  -----------------------------------------------------------------------

This document was requested against thirteen prerequisite documents;
four exist. Everything below is grounded in the PRD, Domain Model,
Architecture, and Testing Strategy docs. Where the requested structure
assumes a not-yet-written specific (a database migration format, a
published OpenAPI contract, a provisioned staging environment), this
document states the policy that will govern it and names what it's
waiting on.

## 1. Purpose

CI/CD is architectural, not operational, because it's the mechanism that
decides whether everything in the preceding documents is actually true
in production or just true in theory. An invariant enforced in the
Domain layer, a failure scenario mitigated in the Architecture doc, a
guarantee proven in the Testing Strategy's suite --- all of it is only
as real as the pipeline that ensures the code carrying those guarantees
is what's actually running. A gap in this pipeline is a gap in every
other document.

Deployment safety is designed here rather than improvised for the same
reason testing is a strategy rather than an afterthought
(`11-Testing-Strategy.md` Section 1): a safety property that depends on
a person remembering the right sequence of manual steps, correctly,
under the pressure of an incident, isn't a safety property --- it's luck
wearing a process costume. Designing it means the safe path and the fast
path are the same path.

## 2. CI/CD Principles

-   **Automation First.** A manual step is a step that gets skipped
    exactly once, at the worst possible time --- under deadline
    pressure, or mid-incident, which is precisely when a shortcut looks
    most reasonable and costs most.
-   **Repeatable Builds.** The same commit produces the same artifact
    regardless of who builds it or when. Without this, "it worked on my
    machine" is a permanent, unfalsifiable excuse, and a production
    investigation can't trust that what's running matches what's in
    source control.
-   **Immutable Artifacts.** Once built, an artifact is never modified
    in place. Patching a running container directly, however
    well-intentioned, breaks the link between "what was tested" and
    "what's deployed" --- the single most important guarantee this whole
    document exists to protect.
-   **Build Once, Deploy Many.** The exact artifact validated in CI is
    the same bytes promoted through every environment, never rebuilt at
    each stage. Rebuilding per stage means every environment is
    technically running a different artifact than the one that was
    tested --- silently reintroducing the "worked in staging" gap this
    principle exists to close.
-   **Fail Fast.** Cheapest, fastest checks run first (Testing Strategy
    Section 13's ordering, applied to the whole pipeline) --- a build
    destined to fail on a formatting error should fail in seconds, not
    after a slow integration suite that never needed to run.
-   **Shift Left.** A defect caught at commit time is a code review
    comment. The same defect caught in staging is a delay. Caught in
    production, it's an incident with users affected. The cost of the
    same bug rises by an order of magnitude at each stage it survives.
-   **Secure Supply Chain.** An artifact is only as trustworthy as
    everything that went into building it --- a compromised dependency
    or a tampered build step is a production compromise even when every
    line of Sentinel's own code is correct.
-   **Least Privilege.** Each pipeline stage holds exactly the access
-   **Ephemeral credentials.** Prefer OIDC-issued short-lived cloud credentials over long-lived static secrets whenever supported.

    its one job requires. A stage that reads source and runs tests has
    no legitimate reason to hold production deployment credentials ---
    granting it anyway just enlarges the blast radius of any pipeline
    compromise.
-   **Reproducibility.** Any commit's build must be reconstructable
    later. For an audit, an incident investigation, or simply
    understanding what changed, "how was this built" needs a real,
    re-runnable answer, not institutional memory.
-   **Release Traceability.** Every artifact in production traces back
    to an exact commit, an exact set of passed checks, and an exact
    approval. "What's running right now, and why" is the first question
    in every incident --- a pipeline that can't answer it immediately
    turns a technical problem into an archaeology problem.

## 3. Delivery Pipeline Overview

``` mermaid
flowchart TB
    DEV[Developer] --> COMMIT[Commit]
    COMMIT --> PR[Pull Request]
    PR --> STATIC[Static Analysis]
    STATIC --> UNIT[Unit Tests]
    UNIT --> INTEG[Integration Tests]
    INTEG --> SEC[Security Scans]
    SEC --> BUILD[Artifact Build]
    BUILD --> SIGN[Artifact Signing]
    SIGN --> STORE[Artifact Storage]
    STORE --> DEPLOY[Deployment]
    DEPLOY --> VERIFY[Verification]
    VERIFY --> PROMOTE[Promotion]
    PROMOTE --> PROD[Production]
```

  -----------------------------------------------------------------------
  Stage                   What happens            Why it exists
  ----------------------- ----------------------- -----------------------
  Commit                  Change committed to a   The unit CI reasons
                          short-lived feature     about
                          branch                  

  Pull Request            Change proposed against Where automated and
                          main                    human review both
                                                  engage, before anything
                                                  reaches shared history

  Static Analysis         Formatting, linting,    Cheapest, fastest
                          type checking           signal --- Fail Fast

  Unit Tests              Domain and Application  Fast and numerous;
                          layer tests             catches most logic
                                                  defects cheaply
                                                  (Testing Strategy
                                                  Section 4)

  Integration Tests       Infrastructure adapters Verifies what unit
                          against real            tests can't (Testing
                          Postgres/object storage Strategy Section 5)

  Security Scans          Dependency, secret,     Shift Left --- a
                          container, and static   vulnerability found
                          application scanning    pre-merge is a comment;
                                                  found post-release,
                                                  it's an incident

  Artifact Build          API and Worker images   One build, from one
                          built from the merged   commit, everything
                          commit                  downstream reuses ---
                                                  Build Once, Deploy Many

  Artifact Signing        The build is            Proves what's deployed
                          cryptographically       is what this pipeline
                          signed                  actually built

  Artifact Storage        The signed artifact is  A durable, addressable
                          pushed to a registry    record of every
                                                  artifact ever built

  Deployment              The artifact is         Automated ---
                          deployed to an          Automation First
                          environment             

  Verification            Smoke tests and health  A deployment that
                          checks confirm the      "completed" but serves
                          deployment is healthy   errors isn't done ---
                                                  it's a new incident
                                                  (Section 10)

  Promotion               The same, unchanged     Build Once, Deploy
                          artifact advances to    Many, applied at every
                          the next environment    transition

  Production              The artifact serves     The only environment
                          real traffic            where correctness
                                                  reaches a real user
  -----------------------------------------------------------------------

## 4. Source Control Strategy

**Main branch:** protected, always deployable. This is the property the
rest of CI/CD's promise rests on --- if main can be in a broken state,
every downstream stage inherits that uncertainty.

**Feature branches:** short-lived, one branch per unit of work, merged
via pull request. Long-lived feature branches accumulate drift from
main, and the eventual merge becomes exactly the kind of high-risk,
low-confidence event this document exists to avoid.

**Release branches:** deliberately not used. For a modular monolith
under continuous delivery (Architecture Section 6.3), a long-lived
release branch adds a second line of history to keep synchronized with
main for no corresponding benefit. A release here is a tag on a specific
main commit plus the artifact built from it (Section 7) --- not a
branch.

**Hotfix branches:** branch from the last known-good production tag, not
from current main, which may hold unreleased changes. This is the one
branching exception, made for a specific reason (Section 11).

**Commit strategy:** atomic, one logical change per commit, with
structured, type-prefixed messages (distinguishing a fix from a feature
from a breaking change --- the Conventional Commits convention is a
reasonable reference point). This isn't a style preference; it's what
makes automated release-note generation (Section 11) possible without
someone reconstructing history from memory.

**Merge policy:** squash merge into main. Main's history becomes one
commit per logical change, which is what makes "which commit introduced
this" --- Release Traceability --- a trivial lookup instead of an
archaeology exercise through a PR's exploratory and fixup commits.

**Protected branches:** main requires passing status checks and review
before merge, enforced by the platform, not by convention or trust
(Section 5).

## 5. Pull Request Standards

**Required reviews:** no change reaches main without independent review.
At this project's current single-maintainer stage, that's satisfied by
structured self-review against a fixed checklist rather than a second
engineer --- the checklist substitutes for the reviewer, but the
requirement itself doesn't relax; it's the same bar, applied by
whichever mechanism is actually available.

**Required approvals:** an approval records that the review actually
happened, not just that no one objected --- a stale, unreviewed PR
sitting open isn't equivalent to an approved one.

**Required status checks:** every stage through Security Scans (Section
3) must pass. No override, no "merge anyway" on a red build --- a check
that can be bypassed isn't a gate, it's a suggestion.

**Documentation updates:** a PR that changes a documented invariant, API
contract, or architectural decision updates the relevant document in the
same PR (Testing Strategy Section 14) --- not as a follow-up that may
never happen.

**Architecture validation:** a PR that touches the layered structure
(Architecture Section 4) or crosses a dependency-direction rule is
flagged explicitly in review. This is the natural moment an ADR gets
written --- when a PR represents a real architectural decision worth a
permanent record, not just a code change.

**Definition of Ready:** work has a clear, traceable link to a PRD use
case, a Domain Model entity, or an Architecture decision before it
starts. Undefined scope doesn't get picked up on the assumption it'll
clarify itself mid-implementation.

**Definition of Done:** merged, tests passing at every relevant layer,
documentation current, and deployed and verified in at least one
non-production environment (Sections 9, 10) --- "done" means verified,
not just written.

## 6. Continuous Integration

Formatting, linting, type checking, and static analysis mirror the
Quality Gates in `11-Testing-Strategy.md` Section 14; this section
treats them as pipeline stages rather than restating their rationale.

-   **Testing:** unit and integration suites, per the layering and
    rationale already established in Testing Strategy Sections 3--5.
-   **Dependency validation:** declared dependencies resolve and lock
    correctly --- a broken lockfile is a CI failure, not a deploy-time
    surprise.
-   **OpenAPI validation:** not yet active --- pending
    `05-API-Specification.md` and `backend/openapi.yaml`. Once they
    exist, the schema FastAPI generates from the running code is diffed
    against the published contract on every build; drift blocks merge.
-   **Schema validation:** pending `04-Database-Design.md`'s migration
    format --- once defined, migrations are validated to apply cleanly
    against a fresh database as part of CI, not discovered as a surprise
    at deploy time.
-   **Container build validation:** the API and Worker images actually
    build successfully as part of CI itself --- Shift Left applied to
    the build step, not just the code.

## 7. Build Architecture

**Artifact creation:** two artifacts per build --- an API image and a
Worker image --- built from the same commit and the same shared codebase
(Architecture Section 6.3's modular monolith) but packaged separately,
since they scale independently (Architecture Section 10).

**Container images:** the natural packaging for the "stateless,
horizontally scalable compute" already established in Architecture
Section 8 --- a container is a reproducible, immutable unit schedulable
onto any compute instance without environment-specific setup.

**Versioning:** each build carries an immutable identifier tied to its
commit (e.g., a short commit SHA) --- this is distinct from the
human-facing release version, which is assigned later, at promotion
(Section 11).

**Image immutability:** once built and signed, an image is never
altered. A fix is a new build, never a patch applied in place --- the
direct application of principle 3 (Section 2).

**SBOM generation:** a Software Bill of Materials --- a full inventory
of direct and transitive dependencies --- generated at build time.
"What's actually in this artifact" needs to be answerable instantly,
especially the moment a CVE is disclosed for some dependency three
layers deep that nobody remembers including.

**Artifact signing:** cryptographic proof that an artifact came from
this pipeline and hasn't been altered since.

**Build provenance:** generate signed build provenance (SLSA-compatible where practical) so every artifact can be traced to its exact source, workflow, and dependencies. Deployment refuses to run
an artifact that isn't validly signed --- this is what actually closes
the gap between "built by CI" and "running in production," rather than
merely asserting it.

**Artifact registry:** the durable, addressable store of every image
ever built. This is what makes Release Traceability and rollback
(Section 9 --- promoting a previous artifact, never rebuilding one)
actually possible rather than aspirational.

## 8. Security Gates

-   **Secret scanning:** extends Testing Strategy Section 9's policy to
    the pipeline itself --- CI credentials and signing keys must never
    appear in logs, source, or build output.
-   **Dependency scanning:** known-vulnerability scanning run against
    the SBOM (Section 7) --- the concrete reason SBOM generation exists,
    not just an inventory exercise for its own sake.
-   **Container scanning:** the built image itself scanned for
    vulnerabilities in its base layers and installed packages, distinct
    from scanning the application's own declared dependencies.
-   **License compliance:** dependencies checked against acceptable
    license terms automatically --- cheap to catch here, expensive to
    discover after the fact.
-   **SAST:** static analysis of Sentinel's own source for known
    vulnerable patterns --- distinct from linting (style and common
    bugs) and from dependency scanning (other people's code); this is
    specifically about Sentinel's code.
-   **Future DAST:** scanning the running application rather than its
    source, sequenced deliberately after the basics are solid, since it
    needs a stable environment (staging) to run against.
-   **Supply chain protection:** the sum of signing, SBOM, and scanning
    together --- treating the build process itself, not only the code,
    as attack surface. A compromised CI runner is as dangerous as a
    compromised dependency.

## 9. Continuous Delivery

**Environment promotion:** the same artifact (Section 2, Build Once
Deploy Many) moves through environments in order --- never rebuilt,
never substituted for something "close enough."

**Staging:** planned, not yet provisioned --- a production-like
environment for pre-release verification, consistent with Testing
Strategy Section 12's treatment of the same gap.

**Production:** the final promotion target, serving real traffic.

**Approval workflow:** promotion from staging to production requires an
explicit, recorded approval step. At the current single-maintainer
stage, that approval is the same person deliberately deciding to promote
--- the point is that a conscious decision happens, not that a deploy is
fully automatic the moment CI turns green, given the current absence of
deeper automated verification like canary analysis (Section 13).

**Rollback:** because artifacts are immutable and every prior one is
retained in the registry (Section 7), rollback means promoting the
previous artifact back into production --- not reverting source and
rebuilding, which would violate Build Once Deploy Many and, worse, be
slower exactly when speed matters most.

**Verification:** the gate between deployment and promotion, detailed in
Section 10.

**Release candidate:** the artifact that has passed every gate through
staging becomes the release candidate --- the same bytes either promoted
to production or not. There is no separate "production build."

## 10. Deployment Verification

-   **Smoke tests:** a minimal, fast check that the newly deployed
    version responds at all --- not the full suite (Testing Strategy
    Section 13).
-   **Health validation:** the liveness/readiness distinction --- a
    process that's running (alive) but can't reach Postgres isn't ready
    to serve traffic, and routing to it is worse than not deploying at
    all.
-   **Observability validation:** confirms the new version still emits
    the logs, metrics, and traces every future deploy's verification
    depends on --- a silent regression here is only discovered when it's
    too late to matter, at the next incident.
-   **SLO validation:** post-deploy error rate and latency compared
    against Service Level Objectives. A deploy that "succeeds" but
    quietly doubles p99 latency is a regression, not a success --- this
    is the gate that catches it.
-   **Rollback triggers:** specific, predefined conditions --- e.g., an
    error-rate threshold crossed within a fixed window of promotion ---
    that trigger rollback automatically or flag it immediately for a
    human decision. Defined in advance, not decided in the moment of an
    incident, when judgment is at its worst.
-   **Release acceptance:** the explicit, final determination that a
    release is good --- closing the loop from release candidate
    (Section 9) to a fully verified production release.

## 11. Release Governance

**Versioning strategy:** semantic versioning (MAJOR.MINOR.PATCH) for the
human-facing release identity, distinct from the immutable build
identifier (Section 7). The build ID says what was built; the release
version says what it means to anything depending on it --- a breaking
API change bumps MAJOR, directly tied to the "Version compatibility"
testing concern in Testing Strategy Section 6.

**Release ownership:** whoever proposes a release owns verifying it and,
if necessary, rolling it back --- extending Testing Strategy Section
15's "whoever owns the code owns its tests" to releases specifically.

**Change approval:** not a new step --- it's the compounding of the
review (Section 5) and promotion approval (Section 9) already in place.
Release governance doesn't add a gate; it's the point those existing
gates become a numbered, tracked release.

**Emergency releases:** fast-tracked, never exempted. Every pipeline
stage in Section 3 still runs; the turnaround for human review is simply
expedited. The one genuine difference is procedural, not a skipped
check: a hotfix branches from the last known-good production tag
(Section 4), so it isn't accidentally bundled with unrelated in-flight
work.

**Release notes:** generated from commit history since the previous
release --- the direct payoff of the structured commit format required
in Section 4. A release note reconstructed from memory after the fact is
usually wrong or incomplete.

**Audit trail:** every release traces to its exact commit, its exact
passed checks, and its exact approver --- Release Traceability
(principle 10, Section 2) as a concrete, queryable artifact rather than
an aspiration.

## 12. CI/CD Governance

**Pipeline ownership:** the pipeline definition is owned and reviewed
with the same rigor as application code. A pipeline change that quietly
makes a security scan non-blocking is exactly as consequential as a code
change introducing a vulnerability, and warrants the same scrutiny.

**Workflow versioning:** pipeline configuration lives in version control
alongside the code it builds --- not managed out-of-band in a UI with no
diff-able history.

**Tool upgrades:** CI/CD tooling is upgraded on a deliberate, scheduled
review, not deferred indefinitely until a security advisory forces an
urgent, unplanned one.

**Pipeline reviews:** the pipeline's own health --- flaky steps, growing
build times, aging tooling --- is reviewed periodically and treated as
real technical debt, not excused because "it still works."

**Infrastructure ownership:** the compute the pipeline runs on, the
artifact registry, and the signing keys all have a named, explicit
owner. At this project's scale that's one person, but the ownership is
stated rather than assumed --- "the pipeline" is credentials and
infrastructure, not only configuration files.

## 13. Future Evolution

-   **Progressive delivery** --- the umbrella the following techniques
    belong to: releasing to production in controlled, reversible
    increments rather than all at once.
-   **Blue/Green deployment** --- two full production environments with
    traffic switched atomically between them; the fastest possible
    rollback, at the cost of running double the infrastructure.
-   **Canary releases** --- a small percentage of real traffic routed to
    a new release before full promotion, catching regressions that smoke
    tests and synthetic verification miss, at the cost of needing real
    traffic-splitting infrastructure.
-   **GitOps** --- the desired state of the deployed system declared in
    version control, with an automated reconciler applying it, making
    "what should be running" as traceable as "what is running."
-   **Policy-as-Code** --- the governance in this document (required
    checks, approval rules) expressed as enforced, machine-checked
    policy rather than documentation that can silently drift from actual
    practice.
-   **Supply-chain attestation** --- verifiable, cryptographic claims
    about *how* an artifact was built, not only *that* it was signed ---
    a deeper guarantee than Section 7's signing alone provides.
-   **Multi-region deployments** --- relevant once there's a concrete
    reason: real geographic traffic or availability requirements beyond
    a single region. Not needed at this project's current scale,
    consistent with Architecture Section 9's honest acknowledgment of
    Postgres as a single point of failure at this stage.

## 14. CI/CD Decision Records

  -----------------------------------------------------------------------
  Decision                            Reasoning
  ----------------------------------- -----------------------------------
  Trunk-based development; no         Simplicity; avoids branch
  long-lived release branches         divergence --- a release is a tag
                                      plus an artifact, not a branch
                                      (Section 4)

  Squash merge to main                One commit per logical change;
                                      keeps Release Traceability a
                                      lookup, not an investigation

  Build once; the same artifact is    The only way "verified in staging"
  promoted through every environment  and "running in production" refer
                                      to the same bytes

  Rollback promotes the previous      Faster than a rebuild, and doesn't
  artifact; it is never rebuilt       depend on old source still building
                                      cleanly under newer tooling

  Hotfixes branch from the last       Avoids bundling an emergency fix
  production tag, not from main       with unrelated in-flight changes

  Emergency releases are              An incident is precisely when
  fast-tracked, never exempted from   skipping verification is most
  pipeline stages                     tempting and most dangerous
  -----------------------------------------------------------------------

## Appendix

**Pipeline diagram:** see Section 3.

**Branch strategy**

  -----------------------------------------------------------------------
  Branch type       Lifetime          Branches from     Merges to
  ----------------- ----------------- ----------------- -----------------
  `main`            Permanent         ---               ---

  Feature branch    Days              `main`            `main`, via
                                                        reviewed PR

  Hotfix branch     Hours             Last production   `main`, via
                                      tag               expedited but
                                                        complete PR
  -----------------------------------------------------------------------

**Promotion matrix**

  -----------------------------------------------------------------------
  Environment       Artifact          Verification      Approval
  ----------------- ----------------- ----------------- -----------------
  CI (ephemeral)    Freshly built     Full test suite   Automatic on
                    candidate         (Testing          passing checks
                                      Strategy)         

  Staging           Signed release    Smoke, health,    Automatic on CI
  *(planned)*       candidate         observability     pass
                                      checks            

  Production        The same signed   Smoke, health,    Explicit,
                    artifact promoted SLO validation    recorded approval
                    from staging                        
  -----------------------------------------------------------------------

**Quality gate matrix (condensed):** formatting · linting · type
checking · unit tests · integration tests · dependency scan · secret
scan · container scan · SAST · license compliance · SBOM generated ·
artifact signed.

**Release checklist** - All required status checks passing - Security
gates clear (Section 8) - SBOM generated and artifact signed -
Documentation updated for any changed contract or invariant - Staging
verification passed (once staging exists) - Explicit promotion approval
recorded - Rollback target identified *before* promoting, not looked up
during an incident

## 15. Pipeline Operational Readiness

A pipeline is considered production-ready only when the following
conditions are continuously satisfied:

-   Every merge to the protected branch executes the complete mandatory
    validation pipeline.
-   Artifact provenance can be traced from production back to the
    originating commit.
-   Every release can be rolled back using a previously verified
    artifact.
-   Pipeline execution history is retained for audit and incident
    investigation.
-   Pipeline credentials are rotated and managed independently from
    application credentials.
-   Any change to the delivery pipeline follows the same review and
    approval process as application code.

## 16. Review Notes (v1.0.1)

Review outcome:

-   Verified consistency with Documents 00--11.
-   Preserved the CI/CD architecture and governance model.
-   No delivery stages, branching strategy, release workflow, security
    gates, or deployment policies were modified.
