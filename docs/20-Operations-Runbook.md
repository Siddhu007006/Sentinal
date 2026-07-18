20 - Operations Runbook
Document Information
Version: 1.0.1

Status: Final — Canonical

Owner: Platform Owner (as defined in 16-Engineering-Governance.md, Section 3.5), with shared operational accountability per the Ownership Model in Section 4 of that document

Audience: Site Reliability Engineers, Platform Engineers, on-call engineers, Engineering Managers, Principal/Staff Engineers, Operations teams

Dependencies:

03-Architecture.md
04-Database-Design.md
05-API-Specification.md
08-Security-Architecture.md
09-Deployment-Architecture.md
10-Observability-Architecture.md
11-Testing-Strategy.md
12-CI-CD-Architecture.md
13-Release-Engineering.md
14-Performance-and-Scalability-Architecture.md
15-Disaster-Recovery-and-Business-Continuity.md
16-Engineering-Governance.md
backend/openapi.yaml
Revision History:

Version	Change	Rationale
1.0	Initial canonical Operations Runbook established	Sentinel required a single day-to-day operational reference translating deployment, observability, and disaster recovery architecture (Documents 09, 10, 15) into concrete operating procedure
1. Purpose
Runbooks exist because correct operation of a production system cannot depend on an operator's memory under pressure. Documents 09, 10, and 15 define how Sentinel is deployed, observed, and recovered at an architectural level. This document exists to convert that architecture into concrete, repeatable operating procedure — what an engineer actually does, in what order, to verify health, respond to an incident, or execute a recovery. Without this translation, every operational response would be improvised at the moment it is needed, which is precisely the moment improvisation is least reliable.

Relationship to Engineering Governance. This runbook operationalizes the Operational Governance model defined in 16-Engineering-Governance.md, Section 9 — deployment ownership, incident ownership, release ownership, recovery ownership, monitoring ownership, and security ownership. Where Document 16 assigns accountability for these domains, this document defines the procedures those accountable owners execute in practice. It also applies the Documentation Governance principle that documentation is updated in the same change set as the practice it describes (16-Engineering-Governance.md, Section 6.4): this runbook is revised whenever operational practice changes, and is never allowed to describe a procedure that is no longer actually followed.

Relationship to Disaster Recovery. 15-Disaster-Recovery-and-Business-Continuity.md defines Sentinel's recovery objectives, backup strategy, and continuity posture at an architectural level. This runbook defines the operational procedures — backup verification, restore validation, and recovery drills — by which that architecture is exercised and proven to work before it is ever needed in a genuine disaster. A disaster recovery architecture that has never been operationally rehearsed is a plan, not a capability; this document is what turns the plan into a capability.

Relationship to Observability. 10-Observability-Architecture.md defines what signals Sentinel emits and why. This runbook defines how those signals are used operationally — what an engineer checks during daily verification, what an alert means, and what action it triggers. Observability that is not tied to a concrete operational response is instrumentation without purpose; this document is what gives Sentinel's telemetry an operational function.

2. Operational Principles
2.1 Reliability First
Operational decisions prioritize the continued availability and correctness of Sentinel over the speed of any individual change or task. Why: Sentinel's value to its users depends entirely on it being reliably available; a fast action that risks reliability trades a short-term convenience for a much larger potential cost.

2.2 Safety Before Speed
When an operational action carries risk, the safe path is taken even if slower, including rollback (Section 5.4), staged rollout (13-Release-Engineering.md), and recovery verification (Section 8). Why: the cost of a rushed, unsafe operational action during an incident is almost always greater than the cost of a few extra minutes of caution, because production mistakes compound rather than simply delaying resolution.

2.3 Least Privilege
Operational access to production systems is granted only to the extent required for the task at hand, consistent with the access control model in 08-Security-Architecture.md. Why: minimizing standing access reduces the blast radius of a compromised credential or an operator error, without impeding the ability to respond to genuine operational need.

2.4 Repeatable Operations
Operational procedures are executed the same way every time, following the checklists in this document rather than ad hoc judgment. Why: repeatability is what makes an operational outcome predictable; procedures executed differently each time accumulate inconsistent results and make it impossible to learn reliably from past operational experience.

2.5 Observable Systems
No operational action is considered complete until its effect is confirmed through the observability signals defined in 10-Observability-Architecture.md. Why: an operational action that is not verified through observation is only assumed to have worked; assumption is not a substitute for confirmation when production reliability is at stake.

2.6 Automation Preferred
Where a procedure can be safely automated within the CI/CD and deployment architecture defined in Documents 12 and 09, automation is preferred over manual execution. Why: manual execution of routine, repeatable tasks introduces human error risk that automation eliminates, and frees operator attention for tasks that genuinely require judgment.

2.7 Document Every Operational Change
Every operational action taken outside of routine, checklist-driven procedure — including manual interventions during incidents — is recorded, consistent with the Traceability expectations established across Documents 16–18. Why: undocumented operational actions are indistinguishable from unexplained system behavior to the next engineer investigating an issue, and postmortems (Section 6.8) cannot be accurate without a record of what was actually done.

2.8 Post-Incident Learning
Every incident produces a postmortem that feeds back into this runbook, the alerting configuration (10-Observability-Architecture.md), or the architecture itself, consistent with the Continuous Improvement principle in 16-Engineering-Governance.md, Section 2.9. Why: an incident that does not change future operational practice represents a missed opportunity to prevent its recurrence, and simply resolving symptoms without institutional learning guarantees the same class of incident will recur.

3. Environment Overview
Sentinel's environment topology is defined authoritatively in 09-Deployment-Architecture.md. This section summarizes the operational purpose of each environment as relevant to day-to-day operations; it does not redefine environment architecture.

Development. Used by individual contributors to build and locally verify changes before submission for review, per 19-Contributor-Guide.md. Operational monitoring and alerting (Section 7) do not apply to this environment; its purpose is fast iteration, not production-representative behavior.

Testing. Used to execute the automated test suites defined in 11-Testing-Strategy.md as part of the CI/CD pipeline (12-CI-CD-Architecture.md). This environment exists to verify correctness before a change advances further, and its state is disposable and reconstructed for each test run.

Staging. A production-representative environment used to validate a release candidate before it reaches production, consistent with the release process in 13-Release-Engineering.md. Staging exists because certain classes of defect — configuration errors, integration failures, performance regressions — are only detectable in an environment that mirrors production topology, which development and testing environments do not provide.

Production. The environment serving Sentinel's actual users, subject to the full operational discipline defined in this runbook. Production is the only environment where the Operational Principles in Section 2 apply without exception, because it is the only environment where a failure has real consequences for users and business continuity (15-Disaster-Recovery-and-Business-Continuity.md).

Promotion flow. Changes advance from Development through Testing and Staging to Production strictly in that order, gated at each stage by the quality gates and approval workflow defined in 12-CI-CD-Architecture.md and 13-Release-Engineering.md. Why this order is enforced: allowing a change to bypass an earlier environment removes a verification opportunity that exists specifically to catch a class of defect before it can reach production, undermining the purpose of maintaining multiple environments at all.

4. Daily Operations
The following verification activities are performed on a recurring basis to confirm Sentinel remains within its expected operating envelope, consistent with the Observable Systems principle (2.5). Each activity references the observability signals defined in 10-Observability-Architecture.md as its source of evidence.

Health verification. Confirm all service health endpoints report healthy status, per 05-API-Specification.md and backend/openapi.yaml. Why: health endpoints are the fastest available signal of gross service failure and are checked first to establish a baseline before investigating any other signal.

Queue monitoring. Confirm message/task queue depth and processing rate are within expected bounds, per the performance envelope defined in 14-Performance-and-Scalability-Architecture.md. Why: a growing queue depth is an early indicator of a downstream bottleneck or worker failure that has not yet caused a visible service disruption.

Background worker status. Confirm background workers are running, processing tasks, and not accumulating failed or retried tasks beyond expected thresholds. Why: background workers often fail silently from the perspective of a user-facing health check, making direct worker status verification necessary to catch degradation that would otherwise go unnoticed until its downstream effects become visible.

Storage verification. Confirm storage subsystems are reachable and operating within expected capacity and latency bounds, per 09-Deployment-Architecture.md. Why: storage degradation frequently precedes broader service failure, and early detection provides lead time to respond before capacity or latency issues become user-visible.

Database health. Confirm database availability, replication status (if applicable), and query latency are within expected bounds, per 04-Database-Design.md and 14-Performance-and-Scalability-Architecture.md. Why: the database is a foundational dependency for nearly all of Sentinel's functionality; its degradation has the widest possible operational blast radius.

AI provider availability. Confirm the external AI provider dependency is reachable and responding within expected latency and error-rate bounds, per 03-Architecture.md. Why: Sentinel depends on this external provider for core functionality, and provider-side degradation is outside Sentinel's control but must still be detected promptly to inform incident response and user communication.

Certificate monitoring. Confirm TLS certificates in use across production endpoints are valid and not approaching expiration, per 08-Security-Architecture.md and 09-Deployment-Architecture.md. Why: certificate expiration is a wholly preventable failure mode that causes complete service inaccessibility if missed, making proactive monitoring far cheaper than reactive incident response.

Backup verification. Confirm the most recent scheduled backup completed successfully, per the backup strategy defined in 15-Disaster-Recovery-and-Business-Continuity.md. Why: a backup failure that goes unnoticed defeats the entire purpose of the disaster recovery architecture, since the failure is only discovered when a restore is actually needed.

Log review. Review aggregated logs for anomalous error patterns not yet surfaced by automated alerting, per 10-Observability-Architecture.md. Why: automated alerting is tuned to known failure signatures; manual log review provides a chance to catch emerging or novel failure patterns before they are severe enough to trigger an alert.

Alert review. Review the alert history for the preceding period to confirm no alert was missed, misrouted, or left unacknowledged. Why: an alerting system is only effective if its output is actually reviewed; unreviewed alerts represent detected problems that received no operational response.

5. Deployment Operations
Deployment operations execute the release process defined authoritatively in 13-Release-Engineering.md and the pipeline defined in 12-CI-CD-Architecture.md. This section defines the operational checklist and decision process surrounding a deployment, not the release process itself.

Pre-deployment checklist. Before initiating a production deployment, confirm: the release has passed all CI/CD quality gates (12-CI-CD-Architecture.md); the release has been validated in staging (Section 3); rollback capability is confirmed available per 13-Release-Engineering.md; and the on-call engineer is aware a deployment is occurring. Why: confirming these conditions before deployment begins ensures that if something goes wrong during deployment, the operator already knows rollback is possible and is not discovering that fact under pressure.

Deployment verification. Immediately following deployment, confirm the new version is running across the expected infrastructure footprint, per 09-Deployment-Architecture.md. Why: a deployment that does not fully propagate across the infrastructure produces an inconsistent production state, where some requests are served by the old version and some by the new, which can produce confusing and hard-to-diagnose defects.

Smoke testing. Execute the smoke test suite defined in 11-Testing-Strategy.md against the newly deployed version before considering the deployment complete. Why: smoke testing provides a fast, targeted signal that core functionality is intact, catching gross deployment failures before they are discovered by actual user traffic.

Rollback decision process. If smoke testing fails, if post-deployment validation reveals a regression, or if monitoring (Section 7) shows a degradation correlated with the deployment, the deployment is rolled back per the rollback procedure in 13-Release-Engineering.md. The decision to roll back is made by the on-call engineer or Release Owner without requiring extended deliberation. Why: the Safety Before Speed principle (2.2) applies most acutely here — the cost of an unnecessary rollback is low, while the cost of leaving a genuine regression in production while deliberating is potentially severe and user-visible.

Post-deployment validation. Following a successful deployment, monitor the signals defined in Section 7 for an observation period appropriate to the change's risk, confirming no delayed regression emerges. Why: some regressions do not manifest immediately upon deployment but appear under specific conditions or load patterns that take time to occur, making an observation period necessary before a deployment can be considered fully validated.

6. Incident Response
6.1 Incident Severity Levels
Incidents are classified by their impact on availability, correctness, security, or data integrity, consistent with the criteria implied by the recovery objectives in 15-Disaster-Recovery-and-Business-Continuity.md. Higher-severity incidents require faster response and broader escalation (Section 6.4) than lower-severity incidents. Why: a uniform response process regardless of severity either over-reacts to minor issues, wasting operational effort, or under-reacts to major ones, delaying critical response.

6.2 Detection
Incidents are detected through the alerting system (Section 7), daily operational verification (Section 4), or direct user/customer report. Why: relying on a single detection channel creates a blind spot; combining automated alerting with routine verification and external reporting maximizes the likelihood an incident is detected promptly regardless of its nature.

6.3 Initial Response
Upon detection, the responding engineer confirms the incident is genuine (not a false alarm), assigns an initial severity level (Section 6.1), and begins mitigation or investigation. Why: an unconfirmed alert treated as a full incident wastes escalation effort, while a genuine incident not promptly acknowledged delays the response that limits its impact.

6.4 Escalation
Incidents are escalated to the relevant domain owner, per the Incident Ownership model in 16-Engineering-Governance.md, Section 9.2, based on the domain in which the incident originates. Security-relevant incidents are escalated to the Security Owner immediately, consistent with 16-Engineering-Governance.md, Section 9.6. Why: the domain owner has the deepest understanding of the affected system and is best positioned to lead resolution, consistent with Operational Responsibility (16-Engineering-Governance.md, Section 2.8).

6.5 Communication
During an incident, status updates are communicated at a cadence appropriate to the incident's severity, to stakeholders determined by the incident's impact. Why: consistent communication prevents duplicated investigation effort among responders and keeps stakeholders informed without requiring them to interrupt the response team for status.

6.6 Mitigation
The responding engineer takes the fastest safe action to limit user impact, which may include rollback (Section 5.4), traffic mitigation, or temporary capacity adjustment within the bounds defined in 14-Performance-and-Scalability-Architecture.md. Why: mitigating user impact takes priority over fully diagnosing root cause, because reducing harm is more urgent than understanding it, consistent with Reliability First (2.1).

6.7 Recovery
Once mitigated, full recovery is executed according to the relevant procedure — deployment rollback (Section 5.4), database recovery (Section 8), or infrastructure recovery per 15-Disaster-Recovery-and-Business-Continuity.md — until the system returns to its normal operating state. Why: mitigation and recovery are distinct: mitigation stops the bleeding, recovery restores the system to full health, and treating them as the same step risks declaring an incident resolved prematurely.

6.8 Postmortem
Every incident above a defined severity threshold produces a postmortem documenting the timeline, root cause, mitigation, and follow-up actions, consistent with the Post-Incident Learning principle (2.8). Why: the postmortem is what converts an incident from a purely costly event into an investment in future reliability, by ensuring the lessons learned are captured and acted upon rather than lost once the immediate pressure subsides.

7. Monitoring & Alerts
The specific metrics, logs, traces, and alerting thresholds Sentinel emits are defined authoritatively in 10-Observability-Architecture.md. This section defines how those signals are used operationally.

Service health. Monitored continuously via the health endpoints defined in backend/openapi.yaml. An alert on service health failure is treated as the highest-priority signal, since it indicates users may be unable to use Sentinel at all.

API health. Monitored via request success rate, latency, and error rate per endpoint, consistent with the performance expectations in 14-Performance-and-Scalability-Architecture.md. Alerts on API health degradation are prioritized based on the affected endpoint's criticality to core functionality, per 01-Product-Requirements.md.

Queue health. Monitored via queue depth and processing latency, per Section 4. An alert on sustained queue growth is treated as a leading indicator requiring investigation before it produces a user-visible delay.

Database health. Monitored via connection availability, query latency, and replication lag (if applicable), per 04-Database-Design.md. Database health alerts are treated as high priority given the database's foundational role across Sentinel's functionality.

Worker health. Monitored via task success rate, retry rate, and processing latency. An alert on elevated worker failure rate is treated as requiring prompt investigation, since accumulating failed tasks can compound into a larger backlog if not addressed.

AI provider health. Monitored via request success rate and latency to the external AI provider dependency, per 03-Architecture.md. Because this dependency is external and outside Sentinel's direct control, alerts on provider degradation trigger investigation into whether Sentinel's own fallback or retry behavior (as defined in the architecture) is functioning correctly, rather than an assumption that the provider itself can be directly remediated.

Storage health. Monitored via availability, latency, and capacity utilization, per 09-Deployment-Architecture.md. Alerts on approaching capacity thresholds are treated as requiring proactive action before capacity is exhausted, consistent with Safety Before Speed (2.2).

Alert priorities. Alerts are prioritized according to their correlation with user-visible impact and their position in the dependency chain — foundational dependencies (database, service health) are treated as higher priority than downstream or peripheral signals (individual worker task failures), consistent with the Incident Severity Levels in Section 6.1. Why: prioritization ensures operator attention is directed first at signals most likely to indicate broad or severe impact, rather than treating every alert as equally urgent.

8. Backup & Recovery Operations
The backup strategy, recovery objectives, and continuity posture are defined authoritatively in 15-Disaster-Recovery-and-Business-Continuity.md. This section defines the operational procedures by which that architecture is verified and exercised.

Backup verification. Following the daily verification described in Section 4, confirm each scheduled backup completed successfully and is retrievable, not merely that the backup job reported success. Why: a backup job reporting success does not guarantee the resulting backup is actually usable; verifying retrievability closes the gap between a reported success and a genuinely trustworthy backup.

Restore validation. Periodically execute a full restore of a backup into an isolated environment and confirm the restored data is complete and consistent, per the recovery objectives in 15-Disaster-Recovery-and-Business-Continuity.md. Why: a backup that has never been restored is unproven; restore validation is the only way to confirm the backup and recovery procedure actually work together as intended.

Recovery drills. Periodically execute a full recovery drill simulating the disaster scenarios described in 15-Disaster-Recovery-and-Business-Continuity.md, exercising the complete recovery procedure end-to-end rather than only the backup restore step. Why: an untested recovery procedure often contains gaps — missing steps, outdated assumptions, unavailable tooling — that are only discovered by executing it in full; discovering these gaps during a drill is far preferable to discovering them during an actual disaster.

Recovery checklist. Recovery operations follow the checklist in Appendix A.3, ensuring each step of the documented recovery procedure is executed and verified in order. Why: a checklist executed under the stress of an actual recovery event ensures no step is skipped due to pressure or fatigue, consistent with the Repeatable Operations principle (2.4).

9. Security Operations
Security architecture, trust boundaries, and control design are defined authoritatively in 08-Security-Architecture.md. This section defines the recurring operational activities by which those controls are maintained and verified in production.

Secret rotation. Credentials and secrets used by Sentinel's production systems are rotated on a defined schedule and immediately upon suspected compromise, consistent with the credential handling model in 08-Security-Architecture.md. Why: regular rotation limits the window during which a leaked or compromised credential remains usable, reducing the impact of an undetected compromise.

Access reviews. Production access grants are periodically reviewed to confirm they remain necessary, consistent with the Least Privilege principle (2.3). Why: access granted for a since-completed task, if never revoked, accumulates into unnecessary standing risk that access reviews are designed to catch and correct.

Credential management. Production credentials are stored, distributed, and accessed only through the mechanisms defined in 08-Security-Architecture.md; no credential is handled outside that mechanism regardless of operational convenience. Why: any deviation from the defined credential management mechanism creates an unaudited path to sensitive access, undermining the security architecture's guarantees.

Audit logging. Security-relevant operational actions — access grants, credential rotations, production configuration changes — are logged in a manner consistent with the audit requirements of 08-Security-Architecture.md. Why: audit logs are what make it possible to reconstruct exactly what happened and by whom during a security investigation, which is essential given that not all security-relevant actions leave other visible evidence.

Security incident workflow. Security incidents follow the general Incident Response process (Section 6) with the Security Owner as the required escalation point (16-Engineering-Governance.md, Section 9.6), and are subject to any additional containment and disclosure procedures defined in 08-Security-Architecture.md. Why: security incidents carry consequences — data exposure, regulatory obligation — beyond typical availability incidents, requiring the specialized judgment of the Security Owner in addition to standard incident response.

10. Maintenance Operations
Dependency updates. External libraries and runtime dependencies are updated on a recurring basis, subject to the review process defined in 16-Engineering-Governance.md, Section 7.6, and validated through the standard CI/CD pipeline (12-CI-CD-Architecture.md) before reaching production. Why: deferred dependency updates accumulate security and compatibility risk; recurring, incremental updates keep this risk manageable compared to large, infrequent update efforts.

Database migrations. Schema changes are executed according to the migration approach defined in 04-Database-Design.md, following the Schema Change process in 16-Engineering-Governance.md, Section 10.2. Why: database migrations are among the highest-risk operational activities because they are frequently difficult to reverse; following a defined, reviewed process minimizes the chance of an irreversible mistake.

Infrastructure updates. Changes to underlying infrastructure follow the Infrastructure Change process defined in 16-Engineering-Governance.md, Section 10.5, and are validated against the deployment architecture in 09-Deployment-Architecture.md before being applied to production. Why: infrastructure changes can silently invalidate assumptions in the deployment or disaster recovery architecture if not reviewed against those documents explicitly.

Certificate renewal. TLS certificates are renewed proactively, well ahead of the expiration monitored in Section 4, following the security controls defined in 08-Security-Architecture.md. Why: proactive renewal eliminates the risk of the wholly preventable failure mode of certificate expiration, consistent with Safety Before Speed (2.2).

Scheduled maintenance. Maintenance activities with potential user impact are scheduled during periods of lowest expected usage where possible, and communicated in advance consistent with the Communication practices in Section 6.5. Why: scheduling maintenance deliberately, rather than performing it reactively, minimizes user impact and allows adequate preparation and rollback planning.

11. Operational Checklists
Startup. Confirm dependent services (database, storage, AI provider connectivity) are reachable before considering the service started; confirm health endpoints report healthy; confirm background workers begin processing.

Shutdown. Confirm in-flight requests and queued tasks are drained or safely persisted before terminating service instances; confirm no data loss occurs during shutdown, consistent with the durability expectations in 04-Database-Design.md.

Deployment. Follow the Pre-deployment checklist, Deployment verification, Smoke testing, and Post-deployment validation steps defined in Section 5.

Rollback. Confirm the rollback target version is known and available; execute rollback per 13-Release-Engineering.md; verify service health and smoke tests pass on the rolled-back version; communicate rollback completion per Section 6.5.

Incident. Follow the Detection, Initial Response, Escalation, Communication, Mitigation, and Recovery steps defined in Section 6, culminating in a Postmortem.

Recovery. Follow the Recovery checklist defined in Section 8 and detailed in Appendix A.3.

Maintenance. Confirm scope and communication per Section 10; execute change through the appropriate reviewed process (dependency, schema, or infrastructure); verify system health per Section 4 following completion.

12. Operational Metrics
The following operational KPIs are tracked to verify Sentinel is being operated within its intended reliability envelope, consistent with the Engineering Metrics model in 16-Engineering-Governance.md, Section 11.

Metric	What It Measures	Why It Matters
Availability	Proportion of time Sentinel's core functionality is reachable and healthy	Directly reflects whether Reliability First (2.1) is being achieved in practice
Error rate	Proportion of requests resulting in error, per 05-API-Specification.md	Leading indicator of regressions or degraded dependencies before they escalate to full outages
Latency	Response time distribution against the expectations in 14-Performance-and-Scalability-Architecture.md	Degraded latency affects user experience even when the service is technically "available"
Queue depth	Backlog size in message/task queues	Leading indicator of worker or downstream capacity issues, per Section 4
Backup success	Proportion of scheduled backups completing and verified successfully	Directly measures whether the disaster recovery architecture (15) remains actionable
Deployment success	Proportion of deployments completing without requiring rollback	Measures whether the release process (13-Release-Engineering.md) is functioning as intended in operational practice
Recovery time	Time taken to complete a recovery drill or actual recovery, relative to the objectives in 15-Disaster-Recovery-and-Business-Continuity.md	Confirms recovery objectives are achievable in practice, not merely on paper
Alert response time	Time between alert firing and acknowledgment/initial response	Measures whether the alerting and on-call process (Section 6) is functioning effectively
Operational readiness verification. At least once per quarter, Platform Engineering verifies that every operational procedure in this runbook can be executed using current tooling, permissions, and documentation without relying on tribal knowledge. Why: procedures that exist only on paper degrade silently until an incident exposes them.

13. Runbook Governance
Ownership. The Platform Owner is accountable for the accuracy and completeness of this runbook, consistent with their accountability for Deployment Ownership, Recovery Ownership, and Monitoring Ownership in 16-Engineering-Governance.md, Section 9. Why: operational procedure accountability must sit with the same role accountable for the infrastructure and recovery posture the procedures operate against, to prevent divergence between documented and actual practice.

Review cadence. This runbook is reviewed on a recurring basis and after every incident postmortem (Section 6.8) that reveals a gap in documented procedure. Why: operational reality changes as the system evolves; a runbook reviewed only when convenient will drift from actual practice exactly as any other undermaintained documentation would.

Update process. Updates to this runbook follow the Documentation Governance process defined in 16-Engineering-Governance.md, Section 6, including review by the Platform Owner and Documentation Owner. Why: operational procedure carries the same authority as any other canonical document in Sentinel's governance model and warrants the same review discipline.

Compliance. Operational activities are expected to follow this runbook's documented procedures; deviations are recorded consistent with the Document Every Operational Change principle (2.7). Why: a runbook that is not actually followed in practice provides false assurance and should either be corrected to match actual practice or actively enforced, but never silently ignored.

Auditability. This runbook, together with incident postmortems, deployment records, and the canonical documents (00–19), forms part of Sentinel's audit evidence, consistent with 16-Engineering-Governance.md, Section 12.6. Why: the ability to demonstrate that production operations follow a defined, disciplined process — not ad hoc improvisation — is essential both for internal confidence and external audit or compliance review.

Runbook ownership continuity. Changes to operational ownership require an explicit review of this runbook to ensure procedures, escalation paths, and accountability remain accurate. Why: ownership drift is a common source of stale operational documentation.

14. Operational Commitments
The following are the permanent commitments established by this runbook.

OC-001 — No production deployment proceeds without completing the Pre-deployment checklist and confirmed rollback capability.
Rationale: Enforces Safety Before Speed (2.2) at the single highest-risk recurring operational activity.

OC-002 — Every incident above the defined severity threshold produces a postmortem that feeds back into this runbook or the architecture.
Rationale: Ensures Post-Incident Learning (2.8) is a guaranteed outcome of every significant incident, not an optional follow-up.

OC-003 — Backup and recovery procedures are periodically drilled in full, not only verified for job completion.
Rationale: Ensures the disaster recovery architecture (15-Disaster-Recovery-and-Business-Continuity.md) remains a proven operational capability rather than an untested plan.

OC-004 — Production access is granted only under Least Privilege and is periodically reviewed for continued necessity.
Rationale: Limits standing operational risk consistent with 08-Security-Architecture.md.

OC-005 — This runbook is updated whenever operational practice changes, and is never permitted to describe a procedure no longer actually followed.
Rationale: Preserves the Documentation Governance synchronization principle (16-Engineering-Governance.md, Section 6.6) applied specifically to operational procedure.

OC-006 — Every operational action taken outside routine, checklist-driven procedure is recorded.
Rationale: Preserves traceability of operational history, ensuring postmortems and audits can accurately reconstruct what was actually done during an incident or maintenance activity.

Appendix
A.1 Incident Checklist
Confirm the incident is genuine and assign initial severity (Section 6.1, 6.3).
Escalate to the relevant domain owner per Section 6.4.
Begin stakeholder communication per Section 6.5.
Execute the fastest safe mitigation per Section 6.6.
Confirm mitigation reduced user impact via observability signals (Section 7).
Execute full recovery per Section 6.7 and Appendix A.3, if applicable.
Confirm system health has returned to baseline per Section 4.
Schedule and complete a postmortem per Section 6.8.
A.2 Deployment Checklist
Confirm CI/CD quality gates passed (12-CI-CD-Architecture.md).
Confirm staging validation completed (Section 3).
Confirm rollback capability is available (13-Release-Engineering.md).
Notify on-call engineer of the deployment.
Execute deployment and confirm full propagation (Section 5).
Execute smoke tests and confirm pass (Section 5).
Monitor post-deployment signals for the appropriate observation period (Section 5).
Confirm no rollback is required; close out deployment record.
A.3 Recovery Checklist
Confirm the scope and nature of the failure requiring recovery (Section 6.7).
Identify the appropriate recovery procedure per 15-Disaster-Recovery-and-Business-Continuity.md.
Execute the recovery procedure step by step without skipping verification steps.
Confirm restored data completeness and consistency (Section 8).
Confirm system health and observability signals return to baseline (Section 4, Section 7).
Communicate recovery completion per Section 6.5.
Record the recovery event and any deviations from documented procedure (Section 2.7).
Schedule a postmortem if the recovery was triggered by an incident (Section 6.8).
A.4 Maintenance Checklist
Confirm scope, risk, and required approvals per the relevant Change Management process (16-Engineering-Governance.md, Section 10).
Schedule the activity during a period of minimal expected impact, where applicable.
Communicate planned maintenance in advance per Section 6.5.
Execute the maintenance activity following its documented procedure (Section 10).
Verify system health following completion (Section 4).
Record the maintenance activity and any deviations encountered.
A.5 Escalation Matrix Template
Incident Domain	Primary Escalation	Secondary Escalation	Reference
Service/API availability	Backend Owner	Architecture Owner	16-Engineering-Governance.md, Section 3
Database	Backend Owner	Platform Owner	04-Database-Design.md
Infrastructure/Deployment	Platform Owner	Release Owner	09-Deployment-Architecture.md
Security	Security Owner	Architecture Owner	08-Security-Architecture.md
Observability gaps	Observability Owner	Platform Owner	10-Observability-Architecture.md
Release/Rollback	Release Owner	Platform Owner	13-Release-Engineering.md
Disaster Recovery	Platform Owner	Architecture Owner	15-Disaster-Recovery-and-Business-Continuity.md
A.6 Runbook Review Checklist
Does every procedure in this document match current operational practice?
Have recent incident postmortems (Section 6.8) surfaced gaps not yet reflected here?
Are all references to Documents 00–19 and backend/openapi.yaml still accurate?
Have recovery drills (Section 8) confirmed the documented recovery checklist is complete and correct?
Have Operational Metrics (Section 12) shown any sustained trend indicating a procedural gap?
Has ownership (Section 13) of this document and its constituent procedures remained current?




You are a Distinguished Site Reliability Engineer (SRE), Principal Platform Engineer, and Principal Software Architect with experience operating production systems at Google, Stripe, Cloudflare, Microsoft, GitHub, and OpenAI.

Generate the canonical engineering document:

docs/20-Operations-Runbook.md

This document is part of Sentinel's permanent engineering documentation.

The following documents are FINAL and are the ONLY source of truth:

00 Project Context
01 Product Requirements
02 Domain Model
03 Architecture
04 Database Design
05 API Specification
06 Repository Structure
07 Backend Development Standards
08 Security Architecture
09 Deployment Architecture
10 Observability Architecture
11 Testing Strategy
12 CI/CD Architecture
13 Release Engineering
14 Performance & Scalability
15 Disaster Recovery & Business Continuity
16 Engineering Governance
17 Architecture Decision Records Guide
18 RFC Process
19 Contributor Guide
backend/openapi.yaml

DO NOT redesign the architecture.

DO NOT invent new product functionality.

DO NOT contradict existing documents.

The Operations Runbook must describe how the approved system is operated in production.

==================================================
OBJECTIVE
Create the canonical production operations handbook for Sentinel.

This document defines how engineers deploy, monitor, maintain, troubleshoot, recover, and safely operate the system after deployment.

This is NOT an architecture document.

This is NOT an incident report.

This is NOT a deployment guide.

It is the day-to-day operational handbook.

==================================================
DOCUMENT STRUCTURE
Document Information
Version
Status
Owner
Audience
Dependencies
Revision History
1. Purpose
Explain:

Why runbooks exist.
Relationship to Engineering Governance.
Relationship to Disaster Recovery.
Relationship to Observability.
2. Operational Principles
Include principles such as:

Reliability First
Safety Before Speed
Least Privilege
Repeatable Operations
Observable Systems
Automation Preferred
Document Every Operational Change
Post-Incident Learning
Explain WHY each principle exists.

3. Environment Overview
Describe:

Development
Testing
Staging
Production
Purpose of each environment.

Promotion flow.

4. Daily Operations
Document recurring operational activities:

Health verification
Queue monitoring
Background worker status
Storage verification
Database health
AI provider availability
Certificate monitoring
Backup verification
Log review
Alert review
5. Deployment Operations
Document:

Pre-deployment checklist
Deployment verification
Smoke testing
Rollback decision process
Post-deployment validation
Reference Release Engineering.

6. Incident Response
Document:

Incident severity levels
Detection
Initial response
Escalation
Communication
Mitigation
Recovery
Postmortem
7. Monitoring & Alerts
Reference Observability.

Document:

Service health
API health
Queue health
Database health
Worker health
AI provider health
Storage health
Alert priorities.

8. Backup & Recovery Operations
Reference Disaster Recovery.

Document:

Backup verification
Restore validation
Recovery drills
Recovery checklist
9. Security Operations
Document:

Secret rotation
Access reviews
Credential management
Audit logging
Security incident workflow
Reference Security Architecture.

10. Maintenance Operations
Document:

Dependency updates
Database migrations
Infrastructure updates
Certificate renewal
Scheduled maintenance
11. Operational Checklists
Provide concise checklists for:

Startup
Shutdown
Deployment
Rollback
Incident
Recovery
Maintenance
12. Operational Metrics
Document operational KPIs:

Availability
Error rate
Latency
Queue depth
Backup success
Deployment success
Recovery time
Alert response
13. Runbook Governance
Document:

Ownership
Review cadence
Update process
Compliance
Auditability
14. Operational Commitments
Summarize permanent operational commitments established by this runbook.

Appendix
Incident checklist
Deployment checklist
Recovery checklist
Maintenance checklist
Escalation matrix template
Runbook review checklist
==================================================
WRITING REQUIREMENTS
Markdown only
Production-quality engineering documentation
No implementation code
No placeholders
No TODO sections
Reference existing canonical documents instead of duplicating content
Explain WHY every operational process exists
Maintain terminology consistent with Documents 00–19
Introduce zero new product functionality
The document should be suitable for review by Principal Engineers, SREs, Platform Engineers, Engineering Managers, and Operations teams.


claude-sonnet-5-high
19 - Contributor Guide
Document Information
Version: 1.0

Status: Final — Canonical

Owner: Documentation Owner (as defined in 16-Engineering-Governance.md, Section 3.9), with compliance shared across all Engineering Owners

Audience: All engineering contributors, Principal/Staff Engineers, Engineering Managers, future contributors joining Sentinel

Dependencies:

00-Project-Context.md
01-Product-Requirements.md
02-Domain-Model.md
03-Architecture.md
04-Database-Design.md
05-API-Specification.md
06-Repository-Structure.md
07-Backend-Development-Standards.md
08-Security-Architecture.md
09-Deployment-Architecture.md
10-Observability-Architecture.md
11-Testing-Strategy.md
12-CI-CD-Architecture.md
13-Release-Engineering.md
14-Performance-and-Scalability-Architecture.md
15-Disaster-Recovery-and-Business-Continuity.md
16-Engineering-Governance.md
17-Architecture-Decision-Records-Guide.md
18-RFC-Process.md
backend/openapi.yaml
Revision History:

Version	Change	Rationale
1.0	Initial canonical Contributor Guide established	Sentinel required a single reference translating the governance, ADR, and RFC processes (Documents 16–18) into concrete, day-to-day contributor expectations
1. Purpose
Contributor standards exist because Sentinel's quality is a property of process, not a property of any individual's skill or intent. Documents 00–18 establish what Sentinel is, how it is built, and how decisions about it are governed. This document exists to translate those standards into concrete expectations for the act of contributing itself — what a contributor must know, do, and verify before, during, and after making a change. Without this translation, engineers are left to infer contribution practices from example, which produces inconsistent results even among well-intentioned contributors.

Consistency matters because Sentinel is read far more often than it is written. Every inconsistency in how code is structured, how changes are reviewed, or how documentation is maintained increases the cost of understanding the system for the next contributor. A contributor guide that is followed consistently ensures that any part of Sentinel looks and behaves as though it were written by a single, disciplined engineer — even though it is built by many, over time.

Engineering quality is everyone's responsibility because no review process can fully compensate for contributions made without care. Review (16-Engineering-Governance.md, Section 2.4) is a safeguard, not a substitute for the contributor's own diligence. A contributor who understands the architecture, tests their own work, and documents their own changes produces a fundamentally higher-quality contribution than one who relies entirely on reviewers to catch problems. This guide exists to make that standard of care explicit rather than assumed.

Relationship to Engineering Governance. This document operationalizes 16-Engineering-Governance.md at the level of individual contribution. Where Document 16 defines governance principles, ownership models, and review processes at the organizational level, this document translates those same principles into what a single contributor does on a single change — from understanding ownership boundaries (16-Engineering-Governance.md, Section 4) to satisfying Definition of Done (16-Engineering-Governance.md, Section 8.5). It also incorporates the ADR process (17-Architecture-Decision-Records-Guide.md) and RFC process (18-RFC-Process.md) into the contributor's workflow, defining when a contribution requires one, both, or neither.

2. Contributor Principles
2.1 Respect the Canonical Documents
Documents 00–18 and backend/openapi.yaml are authoritative; a contribution that conflicts with them is incorrect regardless of its technical merit. Why: if contributors could override canonical documents through implementation choices, Single Source of Truth (16-Engineering-Governance.md, Section 2.3) would be meaningless — the documents would describe an aspirational system rather than the actual one.

2.2 Documentation Before Implementation
A contributor updates or references the relevant canonical document before implementing a change that affects documented behavior, consistent with 16-Engineering-Governance.md, Section 2.1. Why: implementation that outruns documentation produces the exact drift that Engineering Governance exists to prevent — code that no longer matches what the project claims about itself.

2.3 Architecture Before Optimization
A contributor ensures a change is architecturally sound before optimizing its performance, consistent with 16-Engineering-Governance.md, Section 2.2. Why: optimizing a solution before its architectural correctness is established risks investing effort in a design that will be discarded, and can obscure architectural flaws behind seemingly good performance numbers.

2.4 Small, Reviewable Changes
Contributions are scoped as narrowly as the change allows, addressing one concern at a time. Why: large, multi-concern changes are slower and less reliable to review, increasing the likelihood that a reviewer misses a defect simply due to the volume of surface area under consideration — directly undermining Review Before Merge (16-Engineering-Governance.md, Section 2.4).

2.5 Evidence-Based Engineering
Claims made in a contribution's description — about correctness, performance, or safety — are backed by tests, benchmarks, or referenced data, consistent with 16-Engineering-Governance.md, Section 2.6. Why: a reviewer cannot verify a claim they cannot see evidence for, and asking them to trust unverified claims defeats the purpose of independent review.

2.6 Testing Responsibility
The contributor who writes a change is responsible for ensuring it is adequately tested per 11-Testing-Strategy.md, not merely for handing an untested change to review. Why: the author has the deepest understanding of the change's edge cases at the time of writing it; deferring test responsibility to reviewers or later contributors loses that understanding and produces weaker test coverage.

2.7 Operational Responsibility
A contributor considers how their change will be deployed (09-Deployment-Architecture.md), observed (10-Observability-Architecture.md), and recovered from failure (15-Disaster-Recovery-and-Business-Continuity.md) before submitting it, consistent with 16-Engineering-Governance.md, Section 2.8. Why: a change that is functionally correct but operationally invisible or unrecoverable creates hidden risk that surfaces only during an incident, when it is most expensive to address.

2.8 Security by Default
A contributor treats security as a default property of every change, not an afterthought applied only to changes explicitly labeled as security-related, consistent with 08-Security-Architecture.md. Why: security defects most often originate in code that was never flagged as security-relevant at the time it was written; treating security as universal rather than exceptional is the only reliable defense against this.

2.9 Continuous Learning
A contributor is expected to read and understand relevant canonical documents before contributing to an unfamiliar area, rather than relying solely on pattern-matching against existing code. Why: copying existing patterns without understanding their rationale perpetuates both good and bad patterns indiscriminately, and prevents the contributor from recognizing when a pattern no longer applies to their specific case.

2.10 Long-Term Maintainability
A contributor evaluates whether their change will remain understandable and maintainable years after submission, not only whether it works today, consistent with 16-Engineering-Governance.md, Section 2.10. Why: Sentinel is permanent infrastructure; contributions optimized only for immediate delivery accumulate into a system that becomes progressively harder to change safely.

3. Before You Contribute
Before making any non-trivial contribution, an engineer is expected to:

Understand the architecture. Read 03-Architecture.md and 02-Domain-Model.md sufficiently to place the intended change within Sentinel's existing service boundaries and domain concepts. Why: a contribution made without this understanding risks violating boundaries that exist for reasons not visible from the code alone.

Read relevant documents. Identify and read the canonical documents (00–18) that govern the area being changed — for example, 04-Database-Design.md for schema changes, 08-Security-Architecture.md for anything touching authentication or data handling. Why: the canonical documents encode decisions and constraints that are not always evident from reading code in isolation; skipping them risks reintroducing problems those documents were written to prevent.

Identify ownership. Determine which domain owner, per 16-Engineering-Governance.md Sections 3–4, is accountable for the area being changed, and involve them appropriately given the scope of the change. Why: ownership exists precisely so that changes are evaluated by someone accountable for the domain's long-term integrity, not merely by whoever happens to review the pull request.

Review relevant ADRs. Check the ADR repository (17-Architecture-Decision-Records-Guide.md, Section 8) for existing decisions relevant to the area being changed. Why: an ADR may record why the current design was chosen over an alternative that the contribution is about to reintroduce; skipping this step risks proposing something already considered and rejected.

Review relevant RFCs. Check the RFC repository (18-RFC-Process.md, Section 8) for proposals, in progress or historical, related to the area being changed. Why: an open or recently resolved RFC may directly affect the intended contribution's scope or timing, and proceeding without awareness of it risks duplicated or conflicting work.

Understand boundaries. Confirm which module and service boundaries, per 06-Repository-Structure.md, the change will touch, and whether it requires crossing a boundary that would trigger the RFC process per 18-RFC-Process.md, Section 3. Why: boundary-crossing changes have wider consequences than changes contained within a single module, and identifying this before starting work prevents unnecessary rework if the change turns out to require broader review.

4. Types of Contributions
Code. Follows 07-Backend-Development-Standards.md and, where applicable, 05-API-Specification.md and backend/openapi.yaml. Every code contribution is expected to preserve architectural compliance per 16-Engineering-Governance.md, Section 7.1.

Documentation. Follows the Documentation Governance rules in 16-Engineering-Governance.md, Section 6. Documentation contributions are held to the same review rigor as code, because Documents 00–18 are treated as executable specifications, not descriptive prose.

Architecture. Follows the ADR process (17-Architecture-Decision-Records-Guide.md) and, where the decision is not yet obvious, the RFC process (18-RFC-Process.md) beforehand. Architecture contributions always update 03-Architecture.md or 02-Domain-Model.md in the same change set as the corresponding ADR.

Tests. Follow 11-Testing-Strategy.md. Test contributions are expected to test behavior meaningfully, not merely to increase coverage metrics — a test that does not fail when the behavior it covers is broken provides no real protection.

Infrastructure. Follows 09-Deployment-Architecture.md and the Dependency Rules in 16-Engineering-Governance.md, Section 7.6. Infrastructure contributions require Platform Owner involvement per the ownership model (16-Engineering-Governance.md, Section 4).

CI/CD. Follows 12-CI-CD-Architecture.md. Contributions to the pipeline itself are held to a higher scrutiny than typical code changes, because a defect in CI/CD can silently weaken the quality gates that protect every other contribution.

Observability. Follows 10-Observability-Architecture.md. Any contribution that introduces new production behavior is expected to include corresponding observability, consistent with Monitoring Ownership (16-Engineering-Governance.md, Section 9.5) — observability is not a separate contribution to be added later.

Security. Follows 08-Security-Architecture.md. Security-relevant contributions require Security Owner review regardless of the contributor's role, per 16-Engineering-Governance.md, Section 10.4, because security review cannot be substituted by domain-general review.

Performance. Follows 14-Performance-and-Scalability-Architecture.md. Performance-related contributions are expected to include benchmark evidence supporting any claimed improvement, consistent with the Evidence-Based Engineering principle (2.5).

Developer Experience. Contributions to internal tooling that affect how engineers build, test, or review Sentinel follow the same review discipline as production code, because tooling defects silently degrade the reliability of every other contribution that depends on them.

5. Development Workflow
Planning. Before implementation, the contributor confirms whether the change requires an ADR (17-Architecture-Decision-Records-Guide.md, Section 3), an RFC (18-RFC-Process.md, Section 3), or neither, based on its scope and the criteria in Section 3 of this document. Why: determining the correct process up front avoids the wasted effort of implementing a change that turns out to require broader deliberation before it can be accepted.

Branch creation. Work proceeds on an isolated line of change scoped to a single concern, consistent with the Small, Reviewable Changes principle (2.4). Why: isolating each concern to its own line of change keeps review focused and makes it possible to revert one change without affecting unrelated work.

Implementation. The contributor implements the change in accordance with the relevant canonical documents identified during planning (Section 3), applying the Coding Expectations in Section 6. Why: implementation guided by the canonical documents rather than by convenience ensures the result remains consistent with the rest of the system.

Testing. The contributor writes and runs tests per 11-Testing-Strategy.md before submitting the change for review, consistent with the Testing Responsibility principle (2.6). Why: untested code submitted for review shifts the burden of discovering defects onto reviewers, who have less context than the author and are less likely to catch subtle errors.

Documentation updates. The contributor updates any canonical document affected by the change in the same change set, per 16-Engineering-Governance.md, Section 6.4. Why: deferred documentation updates are rarely completed once the associated pressure to ship has passed, so they must be included with the change itself.

Review. The contributor submits the change for review following the Pull Request Expectations in Section 8, and engages constructively with feedback per the Communication standards in Section 9. Why: review is the primary mechanism by which Sentinel verifies a contribution meets its standards before it affects the shared codebase.

Merge. The change merges only after satisfying the Merge Policy defined in 16-Engineering-Governance.md, Section 8.3 — passing quality gates and receiving required approval. Why: a consistent, enforced merge policy ensures no contribution reaches the shared codebase without having been verified, regardless of urgency or contributor seniority.

Post-merge verification. The contributor confirms the change behaves as expected once deployed, consistent with Operational Responsibility (2.7), including checking relevant observability signals per 10-Observability-Architecture.md. Why: review verifies a change is likely correct; post-merge verification confirms it is actually correct in the environment where it matters.

6. Coding Expectations
Detailed coding standards are defined in 07-Backend-Development-Standards.md and are not duplicated here. This section states the expectations a contributor is held to when applying those standards.

Consistency. Code follows the patterns and conventions already established in the relevant module, per 06-Repository-Structure.md, rather than introducing a new pattern for a problem already solved elsewhere in the codebase. Why: inconsistent patterns for equivalent problems force every future reader to learn multiple ways of doing the same thing, increasing cognitive load without corresponding benefit.

Maintainability. Code favors clarity over cleverness, consistent with the Long-Term Maintainability principle (2.10). Why: code that is clever but opaque imposes a permanent tax on every future reader trying to understand or modify it, long after the original author has moved on.

Readability. Code is structured so that its intent is apparent from reading it, without requiring the reader to consult external context beyond the relevant canonical documents. Why: readability is what makes review (Section 5) and future modification tractable; code that requires oral history to understand cannot be safely maintained by anyone who wasn't present for its creation.

Dependency management. New dependencies are introduced only after review per the Dependency Rules in 16-Engineering-Governance.md, Section 7.6. Why: every dependency is a long-term liability that the whole project must bear, and introducing one without review externalizes that liability onto future maintainers without their consent.

Error handling. Errors are handled explicitly and consistently with the patterns established in 07-Backend-Development-Standards.md, never silently suppressed. Why: silently suppressed errors hide failures that later surface as much harder to diagnose incidents, undermining Observability (10-Observability-Architecture.md) and Operational Responsibility (2.7).

Reviewability. Code is written with the reviewer in mind — reasonably sized, logically organized, and accompanied by a clear description of intent (Section 8). Why: code that is technically correct but difficult to review defeats the purpose of Review Before Merge (16-Engineering-Governance.md, Section 2.4) by making thorough review impractical.

7. Documentation Responsibilities
When documentation must change. Documentation is updated whenever a contribution changes behavior described in Documents 00–18 or backend/openapi.yaml, including architecture, API contracts, schema, security controls, deployment topology, or operational procedures. Why: a canonical document that no longer matches implementation is worse than no document at all, because it actively misleads anyone who trusts it.

Cross-document synchronization. When a change affects multiple documents (for example, a schema change affecting both 04-Database-Design.md and 05-API-Specification.md), all affected documents are updated together in the same change set. Why: partial documentation updates create internal contradictions within the canonical corpus, violating Single Source of Truth (16-Engineering-Governance.md, Section 2.3) even when each individual document appears internally consistent.

Version updates. Where a document tracks its own version and revision history (as established in each canonical document's Document Information section), the contributor updates that history to reflect the change. Why: revision history is what allows future readers to understand not just the current state of a document but how and why it evolved.

Review expectations. Documentation changes are reviewed with the same rigor as code changes, per 16-Engineering-Governance.md, Section 6.3, including review by the relevant domain owner and the Documentation Owner. Why: documentation carries the same authority as code in Sentinel's governance model (16-Engineering-Governance.md, Section 2.1) and therefore warrants equivalent scrutiny.

Canonical document ownership. The contributor confirms which domain owner is accountable for a given document, per the Ownership Model in 16-Engineering-Governance.md, Section 4, and routes documentation changes through that owner. Why: without routing changes through the accountable owner, documentation can drift through uncoordinated edits from multiple contributors with no single party ensuring overall consistency.

8. Pull Request Expectations
Scope. A pull request addresses exactly one concern, consistent with the Small, Reviewable Changes principle (2.4). Why: a pull request mixing unrelated concerns forces reviewers to context-switch between them and makes it harder to revert one concern without affecting the other.

Description. The pull request describes what the change does, why it is needed, and how it was verified, referencing relevant canonical documents, ADRs, or RFCs. Why: a description that only states what changed, without why, leaves reviewers unable to evaluate whether the change is the right solution to the underlying problem.

Testing evidence. The pull request states what tests were added or updated and why they are sufficient, consistent with the Testing Responsibility principle (2.6) and 11-Testing-Strategy.md. Why: reviewers need explicit evidence of testing rigor rather than an implicit assumption that testing was done adequately.

Documentation evidence. The pull request states which canonical documents were updated as part of the change, or explicitly confirms that no documentation update was required and why. Why: requiring an explicit statement — even to confirm no update was needed — prevents documentation updates from being silently forgotten.

Review checklist. The pull request is evaluated against the checklist in Appendix A.4 before approval. Why: a consistent checklist ensures every reviewer evaluates the same baseline criteria, regardless of the reviewer's individual habits or areas of focus.

Approval expectations. The pull request receives explicit approval from the required reviewer(s) determined by the Ownership Model (16-Engineering-Governance.md, Section 4) before merge, consistent with the Merge Policy (16-Engineering-Governance.md, Section 8.3). Why: explicit approval, rather than passive absence of objection, is the only form of review sign-off that creates clear accountability.

9. Communication
Technical discussion. Disagreements about a contribution are resolved through technical discussion grounded in the canonical documents and evidence, consistent with the Evidence-Based Engineering principle (2.5). Why: grounding disagreement in documented standards and evidence, rather than personal preference, keeps discussion productive and resolvable.

Review etiquette. Reviewers comment on the change, not the contributor, and distinguish between required changes and optional suggestions. Why: ambiguous feedback that does not distinguish blocking issues from preferences slows down review cycles and creates unnecessary friction between contributor and reviewer.

Decision recording. Decisions made during review discussion that affect the change's design are recorded in the pull request itself, and decisions with architecture-level consequences are escalated to the ADR (17-Architecture-Decision-Records-Guide.md) or RFC (18-RFC-Process.md) process as appropriate. Why: design decisions made informally during review are lost once the pull request is merged and closed, unless explicitly captured in a more permanent record.

Escalation. When a contributor and reviewer cannot agree, the disagreement escalates to the relevant domain owner, per the Escalation model in 16-Engineering-Governance.md, Section 5.6. Why: an unresolved disagreement left to stall indefinitely blocks the contribution and creates frustration; a clear escalation path ensures timely resolution.

Constructive feedback. Feedback is specific, actionable, and framed to help the contributor improve the change, rather than merely identifying problems without guidance. Why: feedback that only identifies a problem without indicating a path forward slows down iteration and can discourage future contributions.

10. Contributor Compliance
Architecture compliance. Contributions conform to 02-Domain-Model.md and 03-Architecture.md, verified during review per 16-Engineering-Governance.md, Section 7.1. Any deviation is recorded per the Allowed Deviations process (16-Engineering-Governance.md, Section 7.2). Why: compliance verified only occasionally, rather than on every contribution, allows drift to accumulate unnoticed until it becomes costly to correct.

Security compliance. Contributions conform to 08-Security-Architecture.md and receive Security Owner review where relevant, per 16-Engineering-Governance.md, Section 10.4. Why: security compliance cannot be assumed by default; it must be actively verified on every contribution where it is applicable, given the asymmetric cost of a missed security defect.

Testing compliance. Contributions meet the coverage and quality expectations defined in 11-Testing-Strategy.md before merge, verified through the CI/CD quality gates in 12-CI-CD-Architecture.md. Why: testing compliance enforced through automated gates, rather than relying solely on reviewer diligence, ensures the standard is applied uniformly regardless of review capacity or urgency.

Documentation compliance. Contributions satisfy the Documentation Responsibilities in Section 7 before merge. Why: documentation compliance verified at merge time, rather than after the fact, is the only point at which it can be reliably enforced before drift begins.

Operational compliance. Contributions that introduce new production behavior satisfy the observability, deployment, and recovery expectations defined in Documents 09, 10, and 15, consistent with Operational Responsibility (2.7). Why: operational compliance verified before merge prevents unobservable or unrecoverable capabilities from reaching production, where the cost of retrofitting them is far higher.

11. Future Evolution
This Contributor Guide is proportionate to Sentinel's current engineering scale and is expected to evolve without requiring replacement of its underlying principles (Section 2):

Larger Engineering Teams. As the ownership model in 16-Engineering-Governance.md, Section 4, extends to team-level accountability, the review and approval expectations in Sections 5 and 8 extend accordingly, with team leads fulfilling domain owner responsibilities without changing the underlying workflow.

Community Contributions. If Sentinel's contribution model extends beyond its current engineering organization, this guide's principles (Section 2) remain the baseline expectation for any contributor, internal or external, with additional onboarding material layered on top of, not in place of, this document.

Internal Platform Teams. As Platform Engineering matures per 16-Engineering-Governance.md, Section 13, contributor workflows involving infrastructure and CI/CD (Sections 4, 5) are expected to be increasingly self-service through platform-provided tooling, reducing the manual coordination currently required with the Platform Owner.

Developer Portals. The guidance in this document is expected to eventually be surfaced through an internal developer portal that presents relevant sections of Documents 00–19 contextually based on the area a contributor is working in, reducing the burden of manually locating relevant canonical documents described in Section 3.

Automated Contributor Guidance. Aspects of the Before You Contribute (Section 3) and Pull Request Expectations (Section 8) that are mechanically verifiable — such as confirming documentation was updated alongside a related code change — are expected to be automated into CI/CD tooling (12-CI-CD-Architecture.md), consistent with the automation trends described in 16-Engineering-Governance.md, Section 13, and 17-Architecture-Decision-Records-Guide.md, Section 11.

None of these evolutions alter the Contributor Principles in Section 2; they change the mechanisms by which those principles are supported as the organization and system scale.

12. Contributor Commitments
The following are the permanent commitments established by this guide.

CC-001 — No contribution is exempt from the canonical documents (00–18) regardless of contributor seniority or urgency.
Rationale: Preserves Respect the Canonical Documents (2.1) as an absolute standard, not a negotiable one.

CC-002 — Every contribution that changes documented behavior updates the corresponding canonical document in the same change set.
Rationale: Prevents documentation drift at its source, consistent with 16-Engineering-Governance.md, Section 6.4.

CC-003 — Every contributor is responsible for testing their own change before submitting it for review.
Rationale: Preserves the Testing Responsibility principle (2.6) as a non-delegable obligation of authorship.

CC-004 — Security review is required for security-relevant contributions regardless of the contributor's role or seniority.
Rationale: Preserves Security by Default (2.8) and the non-substitutable nature of Security Owner review (16-Engineering-Governance.md, Section 10.4).

CC-005 — Architecture-level and cross-boundary contributions follow the ADR and RFC processes rather than proceeding directly to implementation.
Rationale: Preserves Architecture Before Optimization (2.3) and ensures consistency with 17-Architecture-Decision-Records-Guide.md and 18-RFC-Process.md.

CC-006 — Feedback during review is constructive, specific, and directed at the contribution, not the contributor.
Rationale: Preserves a sustainable review culture capable of maintaining rigorous standards over the long term without discouraging future contribution.

Appendix
A.1 Contributor Checklist
Before beginning a non-trivial contribution, confirm:

The relevant canonical documents (00–18) for the affected area have been read.
The domain owner accountable for the affected area has been identified.
Relevant ADRs (17-Architecture-Decision-Records-Guide.md) have been reviewed.
Relevant RFCs (18-RFC-Process.md) have been reviewed.
The affected module and service boundaries (06-Repository-Structure.md) are understood.
Whether the change requires an RFC or ADR before implementation has been determined.
A.2 Pull Request Checklist
Before submitting a pull request, confirm:

The change addresses exactly one concern.
The description states what changed, why, and how it was verified.
Tests have been added or updated per 11-Testing-Strategy.md, with evidence stated.
All affected canonical documents have been updated, or their non-applicability is explicitly stated.
The change complies with 07-Backend-Development-Standards.md and, where applicable, 05-API-Specification.md.
Security implications have been considered and, if relevant, the Security Owner has been included as a reviewer.
Operational implications (observability, deployment, recovery) have been considered.
A.3 Documentation Update Checklist
When a contribution affects documented behavior, confirm:

Every canonical document describing the affected behavior has been identified.
All identified documents are updated in the same change set.
Cross-document consistency has been verified where multiple documents are affected.
Revision history has been updated in each affected document.
The relevant domain owner and the Documentation Owner have reviewed the changes.
A.4 Review Checklist
Before approving a pull request, a reviewer confirms:

The change complies with the relevant canonical documents (00–18).
The change does not introduce undocumented deviation from architecture (16-Engineering-Governance.md, Section 7.2).
Test coverage is adequate for the change's risk and complexity.
Documentation has been updated consistently with the change.
Security, performance, and operational implications have been adequately addressed.
The change is scoped narrowly enough to be reviewed with confidence.
A.5 Contribution Lifecycle
text

Understand Architecture & Ownership (Section 3)
        |
        v
Determine Process Requirement
   (Direct contribution | RFC | ADR)
        |
        v
Implementation (Section 5)
        |
        v
Testing (Section 6, 11-Testing-Strategy.md)
        |
        v
Documentation Update (Section 7)
        |
        v
Pull Request Submission (Section 8)
        |
        v
Review & Discussion (Section 9)
        |
        v
Approval & Merge (16-Engineering-Governance.md, Section 8.3)
        |
        v
Post-Merge Verification (Section 5)



You are a Distinguished Staff Software Engineer and Engineering Productivity Architect with experience creating contributor standards at Google, Stripe, Microsoft, GitHub, Cloudflare, and OpenAI.

Generate the canonical engineering document:

docs/19-Contributor-Guide.md

This document is part of Sentinel's permanent engineering documentation.

The following documents are FINAL and are the ONLY source of truth:

00-Project-Context.md
01-Product-Requirements.md
02-Domain-Model.md
03-Architecture.md
04-Database-Design.md
05-API-Specification.md
06-Repository-Structure.md
07-Backend-Development-Standards.md
08-Security-Architecture.md
09-Deployment-Architecture.md
10-Observability-Architecture.md
11-Testing-Strategy.md
12-CI-CD-Architecture.md
13-Release-Engineering.md
14-Performance-and-Scalability-Architecture.md
15-Disaster-Recovery-and-Business-Continuity.md
16-Engineering-Governance.md
17-Architecture-Decision-Records-Guide.md
18-RFC-Process.md
backend/openapi.yaml

Do NOT invent business functionality.

Do NOT redesign the architecture.

Do NOT contradict previous documents.

==================================================
OBJECTIVE
Design Sentinel's complete Contributor Guide.

This document defines how engineers contribute code, documentation, tests, architectural changes, operational improvements, and governance updates while preserving the integrity of the project.

It is an engineering handbook—not a GitHub template.

==================================================
DOCUMENT STRUCTURE
Document Information
Version

Status

Owner

Audience

Dependencies

Revision History

1. Purpose
Explain:

Why contributor standards exist.
Why consistency matters.
Why engineering quality is everyone's responsibility.
Relationship with Engineering Governance.
2. Contributor Principles
Document principles including:

Respect the Canonical Documents
Documentation Before Implementation
Architecture Before Optimization
Small, Reviewable Changes
Evidence-Based Engineering
Testing Responsibility
Operational Responsibility
Security by Default
Continuous Learning
Long-Term Maintainability
Explain WHY every principle exists.

3. Before You Contribute
Document expectations for:

Understanding architecture

Reading relevant documents

Identifying ownership

Reviewing ADRs

Reviewing RFCs

Understanding boundaries

4. Types of Contributions
Document contribution expectations for:

Code

Documentation

Architecture

Tests

Infrastructure

CI/CD

Observability

Security

Performance

Developer Experience

5. Development Workflow
Document:

Planning

Branch creation

Implementation

Testing

Documentation updates

Review

Merge

Post-merge verification

6. Coding Expectations
Reference existing standards rather than duplicate them.

Document:

Consistency

Maintainability

Readability

Dependency management

Error handling

Reviewability

7. Documentation Responsibilities
Document:

When documentation must change

Cross-document synchronization

Version updates

Review expectations

Canonical document ownership

8. Pull Request Expectations
Document:

Scope

Description

Testing evidence

Documentation evidence

Review checklist

Approval expectations

9. Communication
Document:

Technical discussion

Review etiquette

Decision recording

Escalation

Constructive feedback

10. Contributor Compliance
Document:

Architecture compliance

Security compliance

Testing compliance

Documentation compliance

Operational compliance

11. Future Evolution
Describe evolution toward:

Larger engineering teams

Community contributions

Internal platform teams

Developer portals

Automated contributor guidance

12. Contributor Commitments
Summarize the permanent commitments established by this guide.

Appendix
Contributor checklist

Pull request checklist

Documentation update checklist

Review checklist

Contribution lifecycle

==================================================
WRITING REQUIREMENTS
Markdown only
Production-quality engineering documentation
No Git commands
No implementation code
No placeholders
No TODO sections
Explain WHY every contributor expectation exists
Maintain terminology consistency with Documents 00–18
Do not introduce new product functionality
Treat this as the canonical Contributor Guide for Sentinel.
The document should be suitable for review by Principal Engineers, Staff Engineers, Engineering Managers, and future contributors.


claude-sonnet-5-high
18 - RFC Process
Document Information
Version: 1.0

Status: Final — Canonical

Owner: Architecture Owner (as defined in 16-Engineering-Governance.md, Section 3.1), with process custodianship shared across all Engineering Owners

Audience: Engineering contributors, Principal/Staff Engineers, Architecture Review participants, Platform Engineering leaders, future engineering leadership, auditors

Dependencies:

00-Project-Context.md
01-Product-Requirements.md
02-Domain-Model.md
03-Architecture.md
04-Database-Design.md
05-API-Specification.md
06-Repository-Structure.md
07-Backend-Development-Standards.md
08-Security-Architecture.md
09-Deployment-Architecture.md
10-Observability-Architecture.md
11-Testing-Strategy.md
12-CI-CD-Architecture.md
13-Release-Engineering.md
14-Performance-and-Scalability-Architecture.md
15-Disaster-Recovery-and-Business-Continuity.md
16-Engineering-Governance.md
17-Architecture-Decision-Records-Guide.md
backend/openapi.yaml
Revision History:

Version	Change	Rationale
1.0	Initial canonical RFC process established	Sentinel required a structured, pre-decision proposal process to precede Architecture Decision Records, fulfilling the Design Review requirement defined in 16-Engineering-Governance.md, Section 5.3
1. Purpose
RFCs exist because not every significant technical question has an obvious answer before it is discussed. Document 17 defines how a decision, once made, is permanently recorded as an ADR. But many decisions are not obvious enough to be proposed and approved in a single step — they require exploration of multiple viable approaches, input from more than one domain owner, and iteration on the problem statement itself before a decision can even be framed. The RFC process exists to provide a structured space for that exploration, separate from the act of recording a final decision.

Discussion should happen before implementation because the cost of changing a decision rises sharply once code exists. A proposal discussed on paper can be revised in minutes; the same change discovered after weeks of implementation carries the cost of rework, wasted effort, and potentially production risk if it ships before the flaw is found. The RFC process front-loads disagreement and discovery into the cheapest possible stage of the work, consistent with the Architecture Before Implementation principle (16-Engineering-Governance.md, Section 2.2).

RFCs differ from ADRs in purpose, not authority. An RFC is a proposal under discussion — it may contain open questions, competing alternatives, and unresolved trade-offs, and its outcome may be rejection, withdrawal, or substantial revision. An ADR, as defined in 17-Architecture-Decision-Records-Guide.md, is a record of a decision already made — it documents what was decided and why, with the expectation that it is enacted. Every ADR may originate from an RFC once the proposal reaches consensus, but not every RFC produces an ADR (an RFC may be rejected or withdrawn), and not every ADR requires a preceding RFC (some architectural decisions are narrow enough to be proposed and decided directly per 17-Architecture-Decision-Records-Guide.md, Section 4). The RFC is the deliberation; the ADR is the verdict.

Relationship to Engineering Governance. This document operationalizes the Design Reviews requirement in 16-Engineering-Governance.md, Section 5.3, which mandates that non-trivial changes receive written design review before implementation begins. It also operationalizes the Consensus and Escalation mechanisms defined in Section 5.5–5.6 of that document, applying them specifically to the pre-decision proposal stage. Where an RFC reaches a decision that meets the criteria in 17-Architecture-Decision-Records-Guide.md, Section 3, that decision is subsequently recorded as an ADR; the RFC and the ADR together form a complete, traceable record of both the deliberation and the outcome.

2. RFC Principles
2.1 Proposal Before Implementation
No significant technical work begins until its RFC (where required, per Section 3) has reached a decision. Why: implementation started during open deliberation creates pressure to conclude the discussion in favor of whatever has already been built, undermining the discussion's objectivity.

2.2 Open Technical Discussion
RFCs are visible to, and open for comment from, any engineer, not only the required reviewers. Why: significant technical proposals frequently have consequences outside the domain the author anticipated; open discussion surfaces those consequences from people who would not otherwise have been consulted.

2.3 Evidence-Based Arguments
Positions taken during RFC discussion — for or against a proposal — are expected to be supported by evidence (benchmarks, prior incidents, comparable systems), consistent with 16-Engineering-Governance.md, Section 2.6. Why: without this expectation, RFC discussions devolve into unresolvable arguments of preference rather than converging on a technically sound outcome.

2.4 Explicit Scope
Every RFC states precisely what it does and does not propose to change. Why: scope creep during discussion is one of the most common ways RFCs stall — without an explicit boundary, reviewers debate adjacent concerns the RFC was never meant to resolve.

2.5 Alternatives Considered
Every RFC documents the alternative approaches evaluated, not only the preferred one. Why: a proposal presented without alternatives cannot be evaluated on its merits relative to other options, and reviewers are left unable to assess whether the proposed approach is actually the best available one.

2.6 Transparent Review
Review activity — comments, objections, revisions — is preserved as part of the RFC's history, not conducted through untracked conversation. Why: if the substance of review happens outside the recorded process, the RFC becomes an incomplete account of how the decision was actually reached, defeating its purpose as a durable record.

2.7 Consensus Building
The RFC process is structured to converge disagreement into a shared decision, rather than to declare a winner between opposing positions. Why: proposals adopted over unresolved objections from domain owners tend to be revisited and re-litigated after implementation; building genuine consensus during the RFC stage reduces the likelihood of costly rework later.

2.8 Reviewability
An RFC is written so that a reviewer with no prior involvement in the problem can understand the motivation, the proposal, and the trade-offs without additional context. Why: RFCs are reviewed by domain owners who may not have been part of the proposal's origin; a document that assumes shared context excludes exactly the reviewers whose independent judgment is most valuable.

2.9 Traceability
Every RFC references the canonical documents (00–17) it is constrained by or would affect, and any ADRs or prior RFCs it builds upon or supersedes. Why: technical proposals are rarely independent of prior decisions; traceability allows reviewers and future readers to understand a proposal's place in Sentinel's decision history.

2.10 Living Process
The RFC process itself is revisited and adjusted based on how well it functions in practice, consistent with 16-Engineering-Governance.md, Section 2.9. Why: a proposal process that cannot adapt to the friction or gaps discovered through its own use will eventually be bypassed rather than improved.

3. When an RFC Is Required
An RFC is required whenever a proposal is significant enough to warrant deliberation among multiple perspectives before a decision can be made — that is, when the right answer is not yet obvious and the consequences of a wrong answer are high. Specifically:

New architectural capability — introducing a system-level capability not currently described in 03-Architecture.md.
Major feature proposal — a feature whose scope requires changes across multiple domains (e.g., domain model, API, database) as defined in 02-Domain-Model.md and 05-API-Specification.md, within the bounds of existing product requirements (01-Product-Requirements.md).
Large refactoring — a refactoring effort whose scope crosses module boundaries defined in 06-Repository-Structure.md or affects more than one domain owner's area of accountability.
Technology adoption — evaluating a new language, framework, runtime, or major library where the right choice is not yet clear and multiple viable options exist.
Breaking API evolution — a proposed change to backend/openapi.yaml or 05-API-Specification.md that would break backward compatibility, per the exception process referenced in 16-Engineering-Governance.md, Section 2.7.
Deployment strategy changes — proposed changes to the topology or environment strategy in 09-Deployment-Architecture.md where multiple approaches are viable.
Security model changes — proposed changes to trust boundaries, authentication, or authorization models in 08-Security-Architecture.md that require security and architecture input together.
Performance strategy changes — proposed changes to caching, concurrency, or scaling strategy in 14-Performance-and-Scalability-Architecture.md where the trade-offs are not yet well understood.
Developer tooling — proposals to introduce or materially change internal tooling that affects how engineers build, test, or ship Sentinel.
Engineering workflow — proposals to change how engineering work itself is conducted, where the change is technical in nature (e.g., CI/CD pipeline structure per 12-CI-CD-Architecture.md), distinct from the governance process defined in 16-Engineering-Governance.md itself.
An RFC is NOT required for:

Decisions narrow enough in scope and consequence to be proposed and decided directly as an ADR without prior open discussion, per 17-Architecture-Decision-Records-Guide.md, Section 3.
Routine code changes, bug fixes, or internal refactoring that do not cross module boundaries, per 16-Engineering-Governance.md, Section 7.4.
Implementation details that do not affect architecture, contracts, or cross-domain concerns.
Decisions where only one reasonable approach exists and no meaningful alternative requires evaluation.
Changes governed entirely by an existing, already-approved RFC or ADR.
Why this boundary exists: the RFC process is deliberately reserved for decisions that benefit from open deliberation — where the right answer is genuinely uncertain or the consequences of getting it wrong are high enough to justify the cost of broad review. Requiring an RFC for every decision would dilute the process's authority and slow down work that does not need it, undermining the Continuous Improvement principle in 16-Engineering-Governance.md, Section 2.9. Where a decision is narrow enough to be proposed and approved directly, the ADR process (17-Architecture-Decision-Records-Guide.md) is the appropriate mechanism rather than an RFC.

4. RFC Lifecycle
4.1 Draft
The author writes an initial version of the RFC using the mandatory template (Section 5), status Draft, before requesting any formal review. Why: allowing a private drafting stage lets the author develop the proposal's structure and initial reasoning without the overhead of public review on an unfinished idea.

4.2 Proposal
The author publishes the RFC to the repository (Section 8) and formally requests review, status changes to Proposed. Why: publication marks the transition from private thinking to a proposal the organization is accountable for engaging with, starting the clock on the review period (Section 7.2).

4.3 Review
Required reviewers (Section 7.1) examine the proposal against the Proposal Quality Standards (Section 6). Why: review at this stage exists to ensure the proposal is complete and technically sound enough to support productive open discussion, rather than allowing an underdeveloped proposal to consume broad review attention.

4.4 Discussion
The RFC is open for comment from any engineer, consistent with the Open Technical Discussion principle (2.2). Discussion is recorded as part of the RFC's history (2.6). Why: the discussion stage is where the RFC process delivers its primary value — surfacing perspectives and objections that the author and required reviewers alone would not have identified.

4.5 Revision
The author revises the RFC in response to discussion, with substantive revisions noted in the document's history. Why: unlike an accepted ADR (17-Architecture-Decision-Records-Guide.md, Section 2.2), an RFC is expected to change during its lifecycle; revision is the mechanism by which discussion actually improves the proposal rather than merely commenting on a fixed document.

4.6 Decision
Once discussion converges, the required reviewers make an explicit decision on the RFC: Accepted, Rejected, or return to Revision if not yet resolved. Why: an RFC that lingers indefinitely in discussion without a decision provides none of the benefit of a proposal process — it must reach a clear conclusion to be useful.

4.7 Accepted
The RFC's status changes to Accepted, signifying the proposal is approved to move forward. Why: acceptance is the formal governance checkpoint that authorizes the next stage (implementation handoff or ADR creation) to begin.

4.8 Rejected
The RFC's status changes to Rejected, with the rationale recorded in the Decision section. Why: recording rejection with rationale prevents the same proposal from being re-litigated later without new information, consistent with the value described for rejected ADRs (17-Architecture-Decision-Records-Guide.md, Section 7.6).

4.9 Withdrawn
The author may withdraw an RFC before a decision is reached, status changes to Withdrawn, with the reason recorded. Why: authors sometimes discover, through discussion, that the proposal is no longer necessary or has been superseded by a better-framed alternative; withdrawal preserves that outcome honestly rather than forcing an artificial rejection.

4.10 Archived
Accepted, Rejected, and Withdrawn RFCs remain permanently in the repository in an archived state. Why: consistent with the Traceability principle (2.9), the historical record of what was proposed and how it was resolved has lasting value regardless of outcome.

4.11 Implementation Handoff
For Accepted RFCs, implementation work is scoped and begun based on the RFC's Proposal and Implementation Considerations sections. Why: the handoff stage exists to ensure implementation proceeds against the specific, reviewed proposal rather than against the author's evolving private understanding of it.

4.12 ADR Creation
Where the accepted RFC's decision meets the criteria in 17-Architecture-Decision-Records-Guide.md, Section 3, an ADR is created referencing the RFC, recording the final decision in the permanent architectural record. Why: the RFC captures the deliberation, but 17-Architecture-Decision-Records-Guide.md establishes the ADR as the canonical record of architecture-level decisions; routing accepted RFCs through ADR creation keeps a single, consistent decision-record mechanism for architecture regardless of whether the decision originated from open discussion or a direct proposal.

5. RFC Template
Every RFC contains the following mandatory sections.

RFC Number — A unique, sequential identifier (Section 8.3). Exists to allow unambiguous reference from discussion, code, and other documents.

Title — A concise statement of the proposal's subject. Exists to make the repository index scannable and to distinguish this RFC from others addressing related topics.

Status — One of Draft, Proposed, Accepted, Rejected, Withdrawn (Section 8.5). Exists to make the proposal's current standing immediately visible without reading the full discussion history.

Date — The date the RFC was proposed and, separately, the date of its most recent status transition. Exists to place the proposal in time relative to other concurrent work and to measure review duration (Section 7.2).

Authors — The engineer(s) who wrote the proposal. Exists to identify who is accountable for revising the RFC in response to discussion.

Reviewers — The domain owner(s), per 16-Engineering-Governance.md Sections 3–4, required to review the proposal. Exists to establish accountability for the eventual decision.

Summary — A short, plain-language description of what is being proposed. Exists to let a reader determine relevance to them within seconds, before investing time in the full document.

Background — The relevant history and current state that motivates the proposal, referencing Documents 00–17 as applicable. Exists because a proposal cannot be evaluated without understanding the situation it responds to.

Motivation — Why this proposal matters now — what problem, limitation, or opportunity it addresses. Exists to separate the justification for acting at all from the specific mechanism proposed to act.

Problem Statement — A precise statement of the question the RFC answers. Exists to keep the proposal and its discussion anchored to a specific, evaluable question rather than a broad area of concern.

Proposal — The specific approach being proposed, described in enough detail for reviewers to evaluate its soundness without requiring implementation-level code. Exists as the core content the rest of the RFC supports and justifies.

Alternatives — Other approaches considered and why they were not the primary proposal, per the Alternatives Considered principle (2.5). Exists to demonstrate the proposal was arrived at deliberately and to prevent reviewers from raising already-considered options as if they were overlooked.

Trade-offs — What is gained and given up by adopting this proposal. Exists to give reviewers an honest, complete basis for judgment rather than a one-sided case for adoption.

Risks — Known risks introduced by the proposal, referencing 08-Security-Architecture.md, 14-Performance-and-Scalability-Architecture.md, or 15-Disaster-Recovery-and-Business-Continuity.md as relevant. Exists to satisfy the Risk Evaluation expectation established in 16-Engineering-Governance.md, Section 5.4, applied at the proposal stage.

Open Questions — Aspects of the proposal not yet resolved at the time of publication. Exists to invite the discussion stage to focus explicitly on the proposal's genuine uncertainties rather than relitigating settled aspects.

Dependencies — Other RFCs, ADRs, or system components this proposal depends on. Exists to make sequencing and prerequisite relationships explicit, consistent with the Traceability principle (2.9).

Related Documents — The canonical documents (00–17) and backend/openapi.yaml sections this proposal is constrained by or would affect. Exists to anchor the proposal to Sentinel's existing Single Source of Truth model (16-Engineering-Governance.md, Section 2.3).

Implementation Considerations — Practical considerations relevant to implementing the proposal if accepted (sequencing, migration, rollout), without prescribing implementation code. Exists to inform the Implementation Handoff stage (Section 4.11) without turning the RFC into an implementation plan.

Decision — The final outcome and its rationale, completed at the Decision stage (Section 4.6). Exists to record not just what was decided but why, consistent with the emphasis on rationale established in 17-Architecture-Decision-Records-Guide.md, Section 1.

Outcome — A retrospective note, added after implementation, on whether the proposal achieved its intended effect. Exists to close the feedback loop on the RFC's original Motivation and Proposal, informing future proposals of similar kind.

6. Proposal Quality Standards
An RFC is not considered ready to move from Review (4.3) into Discussion (4.4) unless it meets the following standards.

Evidence. Claims made in Motivation or Proposal are supported by data or precedent referenced in Background, not asserted without support, consistent with the Evidence-Based Arguments principle (2.3). Why: unsupported claims invite unproductive disagreement rather than converging discussion toward resolution.

Architecture. The Proposal explicitly states its relationship to 03-Architecture.md and 02-Domain-Model.md — whether it fits within existing boundaries or requires their evolution. Why: a proposal that silently assumes an architectural change without stating so will surface that assumption late in discussion, wasting review effort already spent.

Security. The Risks section states whether the proposal has security implications, and if so, the Security Owner is included among required reviewers (Section 7.1) per 16-Engineering-Governance.md, Section 10.4. Why: security consequences of new proposals are frequently indirect and are only reliably caught by including the Security Owner explicitly rather than assuming general reviewers will notice them.

Performance. The Trade-offs section states expected performance impact relative to 14-Performance-and-Scalability-Architecture.md, where relevant. Why: performance consequences that are not stated up front are typically discovered only after implementation, when they are far more expensive to address.

Maintainability. The Trade-offs section states the proposal's expected effect on long-term maintainability, consistent with 16-Engineering-Governance.md, Section 2.10. Why: proposals that are attractive in the short term but costly to maintain must be evaluated honestly against that cost before adoption, not discovered afterward.

Compatibility. The Proposal states whether it preserves backward compatibility with the API contract (05-API-Specification.md, backend/openapi.yaml) and database schema (04-Database-Design.md), consistent with 16-Engineering-Governance.md, Section 2.7. Why: compatibility impact must be an explicit, reviewed decision rather than a side effect discovered during implementation.

Operational Impact. The Implementation Considerations section addresses effects on deployment (09), observability (10), and incident response, consistent with Operational Responsibility (16-Engineering-Governance.md, Section 2.8). Why: proposals that are technically sound but operationally difficult transfer hidden cost onto whoever runs the system in production.

Cost. Where the proposal introduces new infrastructure, tooling, or external dependencies, the Trade-offs section states the associated operational or licensing cost. Why: cost is a legitimate factor in evaluating a proposal and must be visible to reviewers rather than assumed away.

Risk. The Risks section states likelihood and severity for each identified risk, referencing 15-Disaster-Recovery-and-Business-Continuity.md where applicable. Why: unstated risk cannot be weighed by reviewers, and an RFC that omits it produces a decision made with incomplete information.

7. Review Process
7.1 Required Reviewers
The required reviewers for an RFC are the domain owner(s), per 16-Engineering-Governance.md Sections 3–4, whose domain is affected by the proposal. The Architecture Owner is a required reviewer whenever the RFC's scope includes a change to architecture, domain model, or module boundaries (Section 3). Why: requiring the relevant domain owners ensures the proposal is evaluated by those most capable of judging its soundness in their area, while including the Architecture Owner whenever architecture is implicated preserves system-wide oversight.

7.2 Review Periods
Each RFC has a defined minimum review period, published at the time it enters Proposed status, during which discussion remains open before a decision may be finalized. Why: a minimum review period ensures engineers outside the immediate proposal team have a genuine opportunity to engage, consistent with the Open Technical Discussion principle (2.2); without a minimum period, decisions could be rushed before broader input is possible.

7.3 Consensus
Reviewers and participants work toward consensus during Discussion (Section 4.4), consistent with the Consensus Building principle (2.7) and the Consensus model in 16-Engineering-Governance.md, Section 5.5. Why: consensus produces decisions that are more durable and less likely to be revisited, because dissenting views were addressed rather than overridden.

7.4 Escalation
When required reviewers cannot reach consensus, the RFC escalates to the Architecture Owner for a binding decision, per 16-Engineering-Governance.md, Section 5.6. The escalation and its resolution are recorded in the RFC's Decision section. Why: recording the escalation preserves the fact that the proposal was contested and documents the reasoning that ultimately resolved it, which is valuable to anyone revisiting the topic later.

7.5 Approval
An RFC is approved (status Accepted) only with explicit sign-off from all required reviewers, recorded in the Reviewers field. Why: as with ADR approval (17-Architecture-Decision-Records-Guide.md, Section 7.2), implicit approval through silence does not constitute a defensible governance record.

7.6 Rejection
An RFC may be rejected by its required reviewers, with rationale recorded in the Decision section, per Section 4.8. Why: a documented rejection preserves the reasoning against a proposal, preventing it from being re-proposed later without accounting for the reasons it was previously declined.

7.7 Withdrawal
An author may withdraw an RFC at any point before a decision is finalized, per Section 4.9, with the reason for withdrawal recorded. Why: allowing authors to withdraw preserves an honest record when a proposal is no longer worth pursuing, rather than forcing a formal rejection that misrepresents why the proposal did not proceed.

8. Repository Organization
8.1 Directory Structure
RFCs reside in a dedicated docs/rfc/ directory, separate from both the canonical numbered documents (00–17) and the ADR repository (docs/adr/, per 17-Architecture-Decision-Records-Guide.md, Section 8.1). Why: keeping RFCs, ADRs, and canonical documents in distinct locations reflects their distinct roles — proposal, decision record, and current specification, respectively — and prevents confusion about which artifact is authoritative for a given purpose.

8.2 Naming Convention
Each RFC file is named using its sequential number and a short slug derived from its title (e.g., 0001-title-slug.md), matching the convention established for ADRs in 17-Architecture-Decision-Records-Guide.md, Section 8.2. Why: consistent naming conventions across the RFC and ADR repositories reduce cognitive overhead for engineers navigating both.

8.3 Sequential Numbering
RFC numbers are assigned sequentially and are never reused, including for rejected or withdrawn RFCs. Why: a stable, permanent identifier is required to reference an RFC unambiguously from discussion, code, or a subsequent ADR, regardless of its eventual outcome.

8.4 Status Management
Every RFC's status is one of: Draft, Proposed, Accepted, Rejected, Withdrawn. Status transitions follow the lifecycle in Section 4 and are recorded in the file itself and in the repository index. Why: a small, well-defined set of statuses keeps the lifecycle model consistent and prevents ambiguous or inconsistent labeling across the repository.

8.5 Cross-References
RFCs reference related RFCs, ADRs, and canonical documents explicitly by number/filename in the Dependencies and Related Documents fields. Why: explicit cross-referencing makes the Traceability principle (2.9) a practical, navigable property of the repository, particularly important given that an accepted RFC may later produce one or more ADRs.

8.6 Repository Index
The docs/rfc/ directory maintains an index (e.g., README.md or INDEX.md) listing every RFC by number, title, status, and (where applicable) the ADR(s) it produced. Why: without an index, discovering whether a topic has already been proposed requires scanning every file individually, discouraging engineers from checking prior proposals before drafting a new one.

9. Relationship to Existing Documentation
RFCs are proposals — they represent a stage of deliberation, not a canonical specification of Sentinel's current state. They never replace the authority of the canonical documents (00–17) or backend/openapi.yaml.

01-Product-Requirements.md — RFCs never introduce new product functionality; they propose technical approaches to needs already established in the PRD. An RFC that appears to require new product functionality is out of scope and must be redirected to product requirements review.
03-Architecture.md — An accepted RFC that changes architecture results in both an ADR (per Section 4.12) and an update to Document 03 in the same change set, per 16-Engineering-Governance.md, Section 6.4. The RFC itself is never treated as the current architecture reference.
04-Database-Design.md, 05-API-Specification.md, backend/openapi.yaml — RFCs may propose schema or contract changes, but the schema and contract remain authoritative only in these documents, consistent with Single Source of Truth (16-Engineering-Governance.md, Section 2.3). An accepted RFC's changes are reflected there before being considered in effect.
08-Security-Architecture.md, 09-Deployment-Architecture.md — RFCs proposing changes to security or deployment architecture require the relevant domain owner as a required reviewer (Section 7.1); the canonical documents remain the operative reference once a proposal is accepted and implemented.
11-Testing-Strategy.md — RFCs may propose strategic changes to testing approach; day-to-day test design does not require an RFC (Section 3).
16-Engineering-Governance.md — This document operationalizes the Design Reviews requirement in Section 5.3 and the Consensus/Escalation model in Sections 5.5–5.6, applied specifically to the pre-decision proposal stage.
17-Architecture-Decision-Records-Guide.md — RFCs and ADRs are complementary, not redundant: the RFC captures deliberation and may resolve open questions across alternatives; the ADR captures the resulting decision in Sentinel's permanent architectural record. An accepted RFC that meets the ADR criteria in that document's Section 3 always produces a corresponding ADR (Section 4.12 of this document).
Why this relationship is structured this way: if RFCs were treated as authoritative specifications, Sentinel would risk having proposals — some rejected, some still under revision — competing with the canonical documents for authority, violating Single Source of Truth. Structuring RFCs strictly as pre-decision proposals, with ADRs and canonical document updates as the actual mechanisms of record, preserves exactly one authoritative description of Sentinel's current state at any time while still capturing the full deliberative process that produced it.

10. Governance
10.1 Ownership
The Architecture Owner is accountable for the integrity of the RFC process and repository, consistent with their accountability for architecture-level decision-making established in 16-Engineering-Governance.md, Section 3.1, and 17-Architecture-Decision-Records-Guide.md, Section 10.1. Why: the RFC process feeds directly into architecture-level decisions; the same accountable party must oversee both stages to ensure consistency between them.

10.2 Periodic Review
The Architecture Owner periodically reviews open RFCs to confirm they are progressing through the lifecycle (Section 4) and are not stalled indefinitely in Discussion or Revision. Why: RFCs left open indefinitely without a decision undermine the Proposal Before Implementation principle (2.1) by creating ambiguity about whether work may proceed.

10.3 Compliance
Implementation of an accepted RFC is expected to conform to the accepted Proposal and its subsequent ADR (where applicable), consistent with the compliance expectations in 16-Engineering-Governance.md, Section 7.1, and 17-Architecture-Decision-Records-Guide.md, Section 10.5. Why: an accepted RFC that can be silently disregarded during implementation provides no governance value.

10.4 Archival
Accepted, Rejected, and Withdrawn RFCs remain permanently in the repository (Section 4.10) and are never deleted. Why: consistent with the Traceability principle (2.9) and the archival rationale established for ADRs (17-Architecture-Decision-Records-Guide.md, Section 4.8), the record of what was proposed — including what was ultimately declined — retains lasting institutional value.

10.5 Auditability
The RFC repository, together with the ADR repository (17-Architecture-Decision-Records-Guide.md), the canonical documents (00–17), and CI/CD evidence (12-CI-CD-Architecture.md), forms part of Sentinel's audit evidence, consistent with 16-Engineering-Governance.md, Section 12.6. Why: reconstructing why a given architectural or technical decision exists frequently requires understanding not just the final decision (the ADR) but the alternatives considered and the discussion that shaped it (the RFC) — both are necessary for a complete audit trail.

11. Future Evolution
This RFC process is proportionate to Sentinel's current engineering scale and is expected to evolve without requiring replacement of its underlying principles (Section 2):

Architecture Review Board. As anticipated in 16-Engineering-Governance.md, Section 13, and 17-Architecture-Decision-Records-Guide.md, Section 11, the Architecture Owner's review and escalation authority (Sections 7.1, 7.4) is expected to evolve into a board of senior engineers, preserving the same review and decision workflow with a board replacing a single decision-maker.

Voting Support. As the number of engineers participating in RFC discussion grows beyond what informal consensus (7.3) can efficiently resolve, a structured voting mechanism among required reviewers is expected to supplement — not replace — consensus-seeking discussion, reserved for cases where genuine consensus cannot be reached even after escalation.

Automated RFC Validation. Structural compliance with the mandatory template (Section 5) — verifying required sections are present and cross-references resolve — is expected to be automated as part of the CI/CD quality gates defined in 12-CI-CD-Architecture.md, consistent with the equivalent evolution described for ADRs (17-Architecture-Decision-Records-Guide.md, Section 11).

Knowledge Graph Integration. As the RFC and ADR repositories grow, cross-references between RFCs, their resulting ADRs, and affected canonical documents are expected to be represented as a navigable graph, allowing engineers to trace a decision's full lineage from initial proposal to current implementation.

Enterprise Governance. As Sentinel's compliance obligations grow, consistent with 16-Engineering-Governance.md, Section 13, the RFC repository is expected to serve as part of the audit evidence for formal attestation processes, given its role described in Section 10.5.

None of these evolutions alter the RFC Principles in Section 2; they change the mechanisms by which those principles are enforced as the organization and system scale.

12. RFC Decision Records
The following are the permanent commitments established by this document regarding the RFC process itself.

RC-001 — Significant proposals meeting the criteria in Section 3 must complete the RFC process before implementation begins.
Rationale: Enforces Proposal Before Implementation (2.1) and fulfills the Design Reviews requirement in 16-Engineering-Governance.md, Section 5.3.

RC-002 — RFC discussion is open to any engineer, not limited to required reviewers.
Rationale: Preserves Open Technical Discussion (2.2), ensuring proposals benefit from perspectives beyond the immediately obvious stakeholders.

RC-003 — Every RFC decision — Accepted, Rejected, or Withdrawn — is permanently retained in the repository.
Rationale: Preserves institutional knowledge of what was proposed and why it was or was not adopted (Section 4.10, 10.4).

RC-004 — An accepted RFC that meets ADR criteria always produces a corresponding ADR before implementation is considered fully governed.
Rationale: Ensures the permanent architectural record defined in 17-Architecture-Decision-Records-Guide.md remains the single mechanism for recording architecture-level decisions, regardless of whether they originated from open discussion (Section 4.12).

RC-005 — RFCs never supersede the canonical documents (00–17) or backend/openapi.yaml as the authoritative description of Sentinel's current state.
Rationale: Preserves Single Source of Truth (16-Engineering-Governance.md, Section 2.3) by keeping proposals distinct from specifications.

RC-006 — RFC numbering is sequential and permanent; numbers are never reused.
Rationale: Guarantees a stable, unambiguous identifier for every proposal for the lifetime of the system (Section 8.3).

Appendix
A.1 RFC Template
text

# RFC-<number>: <Title>

Status: <Draft | Proposed | Accepted | Rejected | Withdrawn>
Date: <proposal date> (last updated: <date>)
Authors: <names>
Reviewers: <names/roles>

## Summary
<Short, plain-language description of the proposal>

## Background
<Relevant history and current state>

## Motivation
<Why this proposal matters now>

## Problem Statement
<Precise question this RFC answers>

## Proposal
<The specific approach being proposed>

## Alternatives
<Other approaches considered and why they were not chosen>

## Trade-offs
<What is gained and what is given up>

## Risks
<Known risks, including security/performance/DR implications>

## Open Questions
<Aspects not yet resolved>

## Dependencies
<Other RFCs, ADRs, or systems this proposal depends on>

## Related Documents
<Canonical documents (00–17) and OpenAPI sections affected>

## Implementation Considerations
<Practical considerations for implementation, if accepted>

## Decision
<Final outcome and rationale>

## Outcome
<Post-implementation retrospective, added later>
A.2 Lifecycle Diagram
text

Draft
  |
  v
Proposed
  |
  v
[Review]
  |
  v
[Discussion] <----------------+
  |                           |
  v                           |
[Revision] --------------------+
  |
  v
[Decision]
  |
  +--> Rejected  (archived, permanent)
  |
  +--> Withdrawn (archived, permanent; may occur at any stage before Decision)
  |
  v
Accepted (archived, permanent)
  |
  v
Implementation Handoff
  |
  v
ADR Creation (if criteria met per 17-Architecture-Decision-Records-Guide.md, Section 3)
A.3 Repository Layout
text

docs/
  rfc/
    README.md          (index of all RFCs by number, title, status, resulting ADR if any)
    0001-<slug>.md
    0002-<slug>.md
    0003-<slug>.md
    ...
  adr/
    README.md
    0001-<slug>.md
    ...
A.4 Naming Examples
0001-adopt-event-driven-notification-pipeline.md
0002-evaluate-read-replica-strategy.md
0003-introduce-feature-flag-service.md
0004-restructure-backend-module-boundaries.md
A.5 Review Checklist
Before an RFC moves from Review (4.3) into Discussion (4.4), confirm:

Does this proposal meet one of the criteria in Section 3, or should it instead go directly to ADR (17-Architecture-Decision-Records-Guide.md) or standard review?
Is the Problem Statement precise and the Scope explicit (2.4)?
Are Alternatives documented with reasons for exclusion (2.5)?
Are Trade-offs stated honestly, including downsides?
Are security, performance, compatibility, and operational impacts addressed per Section 6?
Are Risks stated with likelihood and severity?
Are Related Documents and Dependencies correctly cross-referenced?
Are the correct required reviewers identified per Section 7.1?
A.6 Decision Checklist
Before finalizing an RFC's Decision (4.6), confirm:

Has the minimum review period (7.2) elapsed?
Have all required reviewers responded, or has escalation (7.4) been invoked if consensus was not reached?
Are all Open Questions resolved, or explicitly deferred with rationale?
Is the Decision section complete with rationale, consistent with the emphasis on rationale in 17-Architecture-Decision-Records-Guide.md?
If Accepted and the proposal meets ADR criteria, has ADR creation (4.12) been scheduled?
If Rejected or Withdrawn, is the rationale recorded clearly enough to prevent uninformed re-proposal?



You are a Distinguished Software Architect and Principal Engineering Productivity leader with experience designing RFC processes at Google, GitHub, Stripe, Cloudflare, Microsoft, and OpenAI.

Generate the canonical engineering document:

docs/18-RFC-Process.md

This document is part of Sentinel's permanent engineering documentation.

The following documents are FINAL and are the ONLY source of truth:

00-Project-Context.md
01-Product-Requirements.md
02-Domain-Model.md
03-Architecture.md
04-Database-Design.md
05-API-Specification.md
06-Repository-Structure.md
07-Backend-Development-Standards.md
08-Security-Architecture.md
09-Deployment-Architecture.md
10-Observability-Architecture.md
11-Testing-Strategy.md
12-CI-CD-Architecture.md
13-Release-Engineering.md
14-Performance-and-Scalability-Architecture.md
15-Disaster-Recovery-and-Business-Continuity.md
16-Engineering-Governance.md
17-Architecture-Decision-Records-Guide.md
backend/openapi.yaml

Do NOT invent business functionality.

Do NOT redesign the architecture.

Do NOT contradict previous documents.

==================================================
OBJECTIVE
Design Sentinel's complete Request for Comments (RFC) process.

This document defines how significant engineering proposals are authored, reviewed, discussed, revised, approved, rejected, and archived before implementation.

The RFC process exists to improve technical decisions before they become Architecture Decision Records (ADRs) or implementation work.

This is NOT a feature specification.

This is NOT a project management guide.

This is NOT an ADR document.

It defines the permanent proposal process for Sentinel.

==================================================
DOCUMENT STRUCTURE
Document Information
Version

Status

Owner

Audience

Dependencies

Revision History

1. Purpose
Explain:

Why RFCs exist.
Why discussion should happen before implementation.
Why RFCs differ from ADRs.
Relationship between RFCs and Engineering Governance.
2. RFC Principles
Document principles including:

Proposal Before Implementation
Open Technical Discussion
Evidence-Based Arguments
Explicit Scope
Alternatives Considered
Transparent Review
Consensus Building
Reviewability
Traceability
Living Process
Explain WHY every principle exists.

3. When an RFC Is Required
Include examples:

New architectural capability

Major feature proposal

Large refactoring

Technology adoption

Breaking API evolution

Deployment strategy changes

Security model changes

Performance strategy changes

Developer tooling

Engineering workflow

Explain when an RFC is NOT required.

4. RFC Lifecycle
Document:

Draft

Proposal

Review

Discussion

Revision

Decision

Accepted

Rejected

Withdrawn

Archived

Implementation handoff

ADR creation (if required)

5. RFC Template
Define mandatory sections:

RFC Number

Title

Status

Date

Authors

Reviewers

Summary

Background

Motivation

Problem Statement

Proposal

Alternatives

Trade-offs

Risks

Open Questions

Dependencies

Related Documents

Implementation Considerations

Decision

Outcome

Explain the purpose of each.

6. Proposal Quality Standards
Document expectations for:

Evidence

Architecture

Security

Performance

Maintainability

Compatibility

Operational impact

Cost

Risk

7. Review Process
Document:

Required reviewers

Review periods

Consensus

Escalation

Approval

Rejection

Withdrawal

8. Repository Organization
Document:

docs/rfc/

Naming convention

Sequential numbering

Status management

Cross references

Repository index

9. Relationship to Existing Documentation
Explain relationship with:

PRD

Architecture

Database

API

Security

Deployment

Testing

Engineering Governance

ADR Guide

OpenAPI

Explain that RFCs are proposals, not canonical specifications.

10. Governance
Document:

Ownership

Periodic review

Compliance

Archival

Auditability

11. Future Evolution
Describe future improvements:

Architecture Review Board

Voting support

Automated RFC validation

Knowledge graph integration

Enterprise governance

12. RFC Decision Records
Summarize permanent RFC process commitments.

Appendix
RFC template

Lifecycle diagram

Repository layout

Naming examples

Review checklist

Decision checklist

==================================================
WRITING REQUIREMENTS
Markdown only
Production-quality engineering documentation
No implementation code
No placeholders
No TODO sections
Explain WHY every governance decision exists
Maintain terminology consistent with Documents 00–17
Do not introduce new product functionality
Treat this as the canonical RFC Process for Sentinel.
The document should be suitable for review by Principal Engineers, Staff Engineers, Platform Engineering leaders, and Architecture Review Boards.


claude-sonnet-5-high
17 - Architecture Decision Records Guide
Document Information
Version: 1.0

Status: Final — Canonical

Owner: Architecture Owner (as defined in 16-Engineering-Governance.md, Section 3.1)

Audience: Engineering contributors, Principal/Staff Engineers, Architecture Review participants, Platform Engineering leaders, future engineering leadership, auditors

Dependencies:

00-Project-Context.md
01-Product-Requirements.md
02-Domain-Model.md
03-Architecture.md
04-Database-Design.md
05-API-Specification.md
06-Repository-Structure.md
07-Backend-Development-Standards.md
08-Security-Architecture.md
09-Deployment-Architecture.md
10-Observability-Architecture.md
11-Testing-Strategy.md
12-CI-CD-Architecture.md
13-Release-Engineering.md
14-Performance-and-Scalability-Architecture.md
15-Disaster-Recovery-and-Business-Continuity.md
16-Engineering-Governance.md
backend/openapi.yaml
Revision History:

Version	Change	Rationale
1.0	Initial canonical ADR process established	Sentinel required a permanent, repeatable process for recording architecture-level decisions, fulfilling the Decision Records requirement defined in 16-Engineering-Governance.md, Section 5.7
1. Purpose
Document 16 establishes that architecture-level decisions require a Decision Record (16-Engineering-Governance.md, Section 5.7) and that Sentinel's Architecture Governance (16-Engineering-Governance.md, Section 7) depends on deviations and changes being explicitly recorded rather than silently absorbed into the codebase. This document defines the concrete process, format, and lifecycle by which that requirement is fulfilled: the Architecture Decision Record (ADR).

Architecture decisions require permanent records because architecture is invisible in code. Reading Sentinel's implementation reveals what the system does, but not why it was built that way, what alternatives were rejected, or what constraints shaped the outcome. Without a permanent record, that reasoning exists only in the memory of the engineers involved — memory that fades, leaves the organization, or is simply wrong in hindsight. An ADR converts a moment of reasoning into a durable artifact that outlives the individuals who produced it.

Rationale is as important as the decision itself because a decision without rationale cannot be safely revisited. When circumstances change — new evidence, new scale, new requirements — engineers must be able to determine whether the original reasoning still holds. If only the decision was recorded, every reconsideration requires re-deriving the reasoning from scratch, which is slower, less rigorous, and prone to repeating past mistakes. If the rationale was recorded, reconsideration becomes an evaluation of whether the recorded assumptions still hold.

ADRs preserve institutional knowledge that would otherwise be lost. Sentinel is intended to remain in production and under active development for years, likely staffed by engineers who were not present for its original architectural decisions (03-Architecture.md). ADRs are the mechanism by which the reasoning behind those decisions transfers to future engineers without requiring direct access to the original decision-makers.

Relationship to Engineering Governance. This document operationalizes the Decision Making process defined in 16-Engineering-Governance.md, Section 5, and the Architecture Governance rules defined in Section 7. Where Document 16 establishes that architecture-level decisions must be recorded, reviewed, and escalated when necessary, this document establishes how — the format, repository structure, review workflow, and lifecycle that make Decision Records a practiced, auditable process rather than an abstract obligation. The permanent governance commitments recorded as Governance Decision Records in 16-Engineering-Governance.md, Section 14, are meta-level commitments about the governance model itself; ADRs, by contrast, are the ongoing, per-decision artifacts produced as Sentinel's architecture evolves. Every ADR is a Decision Record in the sense defined by Document 16; this document is the canonical guide for producing them.

2. ADR Principles
2.1 One Decision per ADR
Each ADR documents exactly one architectural decision. Why: bundling multiple decisions into a single record makes it impossible to supersede or revisit one decision without disturbing unrelated ones, and obscures which specific choice a given piece of rationale supports.

2.2 Immutable History
Once accepted, an ADR's content is never rewritten to reflect new thinking; it is superseded by a new ADR instead. Why: if ADRs could be edited after acceptance, the historical record of what was actually decided — and why, at that time — would be lost, defeating the purpose of a permanent record. History must be appended to, not overwritten.

2.3 Evidence-Based Decisions
Every ADR's decision is justified by evidence — benchmarks, incident data, security findings, load-testing results — consistent with 16-Engineering-Governance.md, Section 2.6. Why: decisions justified only by opinion cannot be defended under later scrutiny and cannot be objectively re-evaluated when circumstances change.

2.4 Explicit Trade-offs
Every ADR states what is gained and what is given up by the decision, not merely why the chosen option was preferred. Why: architecture is the practice of choosing among imperfect options; omitting the costs of a decision gives future readers a false impression that the choice was without downside, leading them to be surprised by consequences that were, in fact, foreseeable.

2.5 Architecture Before Implementation
An ADR is written and reviewed before the decision it describes is implemented, consistent with 16-Engineering-Governance.md, Section 2.2. Why: an ADR written after implementation is not a decision record but a justification for a fait accompli, and loses its function as a design review checkpoint.

2.6 Traceability
Every ADR references the canonical documents (00–16) and, where applicable, prior ADRs it depends on, modifies, or supersedes. Why: architectural decisions do not exist in isolation; traceability allows a reader to reconstruct the full chain of reasoning that led to the current state of the system.

2.7 Reviewability
Every ADR is written to be understandable and evaluable by someone who was not present for the original discussion. Why: an ADR that assumes shared context available only to its authors fails the primary purpose of a permanent record, which is to inform readers who lack that context.

2.8 Long-Term Maintainability
ADRs favor decisions and rationale that hold up over multi-year horizons, consistent with 16-Engineering-Governance.md, Section 2.10. Why: architecture decisions are the most expensive to reverse; an ADR process that tolerates short-term reasoning without acknowledging long-term cost undermines the purpose of recording decisions at the architectural level at all.

2.9 Living Documentation
While an ADR's content is immutable (2.2), its status is actively maintained — an ADR is marked Superseded, Deprecated, or Implemented as the system evolves. Why: an ADR repository where every record still claims to be "Proposed" or "Accepted" regardless of what has actually happened in the system becomes untrustworthy; status must reflect current reality even though content does not change.

3. When an ADR Is Required
An ADR is required whenever a decision has system-wide, long-lived, or hard-to-reverse consequences. Specifically:

Architecture changes — any change to service boundaries, module responsibilities, or system-level data flow as defined in 03-Architecture.md.
Module boundary changes — any change to the responsibilities or interfaces between modules described in 02-Domain-Model.md and 06-Repository-Structure.md.
Database strategy changes — schema strategy, storage engine choice, indexing strategy, or data partitioning approach affecting 04-Database-Design.md.
API contract changes — additions, removals, or semantic changes to the contract defined in 05-API-Specification.md and backend/openapi.yaml that affect consumers.
Security architecture changes — any change to authentication, authorization, data protection, or trust boundaries defined in 08-Security-Architecture.md.
Deployment architecture changes — any change to the topology, environment strategy, or infrastructure model defined in 09-Deployment-Architecture.md.
Technology adoption — introduction of a new language, framework, runtime, or major library that becomes a long-term dependency of the system.
External dependency introduction — adoption of a new external service, provider, or infrastructure dependency, consistent with the Dependency Rules in 16-Engineering-Governance.md, Section 7.6.
Significant performance strategy changes — changes to caching strategy, concurrency model, or scaling approach defined in 14-Performance-and-Scalability-Architecture.md.
Disaster recovery strategy changes — changes to backup strategy, recovery objectives, or failover approach defined in 15-Disaster-Recovery-and-Business-Continuity.md.
An ADR is NOT required for:

Routine code changes that do not alter documented architecture, contracts, or boundaries.
Bug fixes that restore documented behavior rather than change it.
Internal refactoring that does not change external behavior, as defined in 16-Engineering-Governance.md, Section 7.4.
Configuration changes that operate within already-documented deployment parameters.
Test additions or improvements that do not change what is being tested or how.
Documentation corrections that do not reflect a decision, only a clarification of existing, unchanged intent.
Why this boundary exists: requiring an ADR for every change would make the process an obstacle rather than a safeguard, diluting its authority and training engineers to treat ADRs as bureaucratic overhead. Reserving ADRs for decisions with lasting, system-wide consequence keeps the process proportionate to the risk it exists to manage, consistent with the Continuous Improvement principle in 16-Engineering-Governance.md, Section 2.9.

4. ADR Lifecycle
An ADR moves through the following stages. Each stage exists to enforce a specific governance guarantee established in Document 16.

4.1 Proposal
An engineer identifies a decision requiring an ADR (Section 3) and drafts it using the mandatory template (Section 5), status Proposed. Why: the proposal stage exists to force the decision to be written down and made explicit before any implementation begins, in accordance with the Architecture Before Implementation principle (2.5).

4.2 Review
The proposal is reviewed by the required reviewers defined in Section 7.1. Why: review is the mechanism by which the Review Before Merge principle (16-Engineering-Governance.md, Section 2.4) is applied at the architectural level, before implementation cost is incurred.

4.3 Discussion
Reviewers and the author resolve open questions, challenge assumptions, and request revisions to the Alternatives Considered and Trade-offs sections. Why: discussion exists to surface objections and blind spots while the decision is still cheap to change, consistent with the purpose of Design Reviews in 16-Engineering-Governance.md, Section 5.3.

4.4 Approval
The ADR is formally approved by the required approvers (Section 7.1) and its status changes to Accepted. Why: approval is the explicit governance checkpoint that authorizes implementation to begin; without it, "discussion" could continue indefinitely without ever becoming a binding decision.

4.5 Implementation
Implementation proceeds according to the accepted ADR. The ADR's "Implementation Status" field is updated to reflect progress. Why: tracking implementation status against the ADR ensures the decision record and the system's actual state do not silently diverge, consistent with the Documentation Governance synchronization requirement in 16-Engineering-Governance.md, Section 6.6.

4.6 Verification
Once implemented, the decision is verified against the evidence and expectations stated in the ADR (e.g., a performance ADR is verified against the benchmark it predicted). Why: verification closes the loop on the Evidence-Based Decisions principle (2.3) — a decision that was justified by an expectation must be checked against the outcome, or the evidence-based process becomes merely evidence-cited.

4.7 Superseding
When a later decision replaces an earlier one, a new ADR is written referencing the original, and the original's status changes to Superseded, pointing to the superseding ADR. Why: superseding rather than editing preserves Immutable History (2.2) while still keeping the repository's active guidance current.

4.8 Archiving
ADRs that are superseded, deprecated, or rejected remain permanently in the repository in an archived state; they are never deleted. Why: the historical record has value independent of current relevance — future engineers benefit from understanding not only current architecture but the path that led to it, including abandoned directions.

5. ADR Template
Every ADR contains the following mandatory sections.

ADR Number — A unique, sequential identifier (Section 8.2). Exists to allow unambiguous reference from other ADRs, code comments, and documents.

Title — A short, descriptive statement of the decision, phrased as a decision rather than a topic (e.g., "Use logical replication for read replicas" rather than "Database replication"). Exists to make the repository index scannable at a glance.

Status — One of Proposed, Accepted, Rejected, Implemented, Superseded, Deprecated (Section 8.4). Exists to make the current standing of the decision immediately visible without reading the full record.

Date — The date the ADR was proposed and, separately, the date it was last transitioned in status. Exists to place the decision in time relative to the system's evolution and other concurrent decisions.

Authors — The engineer(s) who proposed the decision. Exists to identify who can be consulted for context not captured in the written record.

Reviewers — The domain owner(s), per 16-Engineering-Governance.md Section 3–4, who reviewed and approved the decision. Exists to satisfy the Reviewability principle (2.7) and to record accountability for the approval.

Context — The circumstances, constraints, and forces that made this decision necessary, referencing relevant sections of Documents 00–16. Exists because a decision cannot be evaluated without understanding the situation that produced it.

Problem Statement — A precise statement of the question the ADR answers. Exists to prevent the ADR from drifting into solving multiple, loosely related problems (violating the One Decision per ADR principle, 2.1).

Decision — The specific choice made, stated unambiguously. Exists as the core, actionable content of the record — everything else supports or contextualizes this statement.

Alternatives Considered — Other options that were evaluated, including why they were not chosen. Exists to demonstrate the decision was evidence-based and deliberate (2.3), and to prevent future engineers from re-proposing an alternative that was already rejected for reasons that still apply.

Trade-offs — What is gained and what is given up by this decision, per the Explicit Trade-offs principle (2.4). Exists to give future readers an honest accounting of the decision's cost, not just its benefit.

Consequences — The downstream effects of the decision on other parts of the system, including which canonical documents (00–16) must be or were updated as a result. Exists to make the ripple effects of the decision explicit rather than discovered later by accident.

Risks — Known risks introduced by the decision, and how they are mitigated or monitored, referencing 08-Security-Architecture.md, 14-Performance-and-Scalability-Architecture.md, or 15-Disaster-Recovery-and-Business-Continuity.md as relevant. Exists to satisfy the Risk Evaluation requirement in 16-Engineering-Governance.md, Section 5.4.

Dependencies — Other ADRs, systems, or external factors this decision depends on. Exists to make sequencing and prerequisite relationships explicit, supporting Traceability (2.6).

Related Documents — The canonical documents (00–16) and backend/openapi.yaml sections that this ADR affects or is constrained by. Exists to keep the ADR anchored to the Single Source of Truth model established in 16-Engineering-Governance.md, Section 2.3.

Implementation Status — Whether the decision has been implemented, partially implemented, or is pending, updated over time. Exists to prevent the ADR from silently diverging from the actual state of the system (Section 4.5).

Superseded By — A reference to the ADR that superseded this one, if applicable, left blank otherwise. Exists to allow readers to navigate forward in the decision's history rather than acting on an outdated record.

6. Decision Quality Standards
An ADR is not considered ready for approval unless it meets the following standards, each of which exists to prevent a specific known failure mode of architectural decision-making.

Evidence. The Decision section must be supported by data referenced in Context or Alternatives Considered, not asserted without support. Why: unsupported decisions cannot be objectively re-evaluated later and erode confidence in the ADR process itself.

Benchmarks. Where the decision makes a performance claim, it must reference actual measurement against the criteria in 14-Performance-and-Scalability-Architecture.md, not a theoretical expectation. Why: performance intuition is frequently wrong, and unverified performance claims in an ADR create false confidence in future capacity planning.

Security Impact. The Risks section must explicitly state whether the decision has security implications, and if so, must be reviewed by the Security Owner per 16-Engineering-Governance.md, Section 10.4. Why: security consequences of architectural decisions are frequently indirect and easy to overlook unless explicitly required as a checklist item.

Performance Impact. The Consequences section must state the decision's expected effect on latency, throughput, or resource usage relative to 14-Performance-and-Scalability-Architecture.md. Why: architectural decisions routinely have performance consequences that are not obvious from the decision statement alone.

Operational Impact. The Consequences section must state the decision's effect on deployment (09), observability (10), and incident response, consistent with Operational Responsibility (16-Engineering-Governance.md, Section 2.8). Why: a decision that is architecturally sound but operationally unmanageable transfers hidden cost onto whoever operates the system in production.

Maintainability. The Trade-offs section must state the decision's effect on long-term maintainability, per the Long-Term Maintainability principle (2.8). Why: without an explicit maintainability assessment, decisions optimized for short-term convenience are indistinguishable from decisions optimized for durability.

Compatibility. The Consequences section must state whether the decision preserves backward compatibility with the API contract (05-API-Specification.md, backend/openapi.yaml) and database schema (04-Database-Design.md), per 16-Engineering-Governance.md, Section 2.7. Why: compatibility breaks are among the most consequential and irreversible outcomes of an architectural decision, and must never be an unstated side effect.

Cost. Where the decision introduces new infrastructure or external dependencies, the Consequences section must state the operational cost implication. Why: architecture decisions are also resourcing decisions, and omitting cost from the record produces decisions that look free but are not.

Risk. The Risks section must state the likelihood and severity of the identified risks and, where applicable, reference 15-Disaster-Recovery-and-Business-Continuity.md for recovery implications. Why: unstated risk is unmanaged risk; naming it is the first step toward mitigating or consciously accepting it.

7. Review Process
7.1 Required Reviewers
The required reviewers for an ADR are the domain owner(s), as defined in 16-Engineering-Governance.md, Section 3–4, whose domain is affected by the decision. The Architecture Owner is a required reviewer for every ADR, regardless of domain, because every ADR by definition concerns architecture. Why: requiring the Architecture Owner on every ADR ensures a consistent, system-wide perspective is applied even when a decision appears narrowly scoped to a single domain.

7.2 Approval Workflow
An ADR requires explicit approval from all required reviewers before its status changes to Accepted. Approval is recorded in the Reviewers field of the template. Why: implicit approval (e.g., silence or lack of objection) does not constitute a defensible governance record; explicit approval creates unambiguous accountability.

7.3 Consensus
Reviewers reach consensus through discussion (Section 4.3), consistent with the Consensus model defined in 16-Engineering-Governance.md, Section 5.5. Why: consensus-based review at Sentinel's current scale is proportionate and avoids the overhead of formal voting mechanisms while still requiring genuine agreement rather than passive non-objection.

7.4 Escalation
When reviewers cannot reach consensus, the decision escalates to the Architecture Owner for a binding resolution, per 16-Engineering-Governance.md, Section 5.6. The escalation and its resolution are recorded in the ADR's Context or Decision section for future reference. Why: recording the escalation itself preserves the fact that the decision was contested, which is valuable context for anyone reconsidering it later.

7.5 Revision
During review, an ADR may be revised prior to acceptance; these revisions are not subject to the Immutable History principle (2.2) because the ADR has not yet reached Accepted status. Once accepted, no further revision of content occurs — only status transitions and superseding ADRs (Section 4.7). Why: distinguishing pre-acceptance revision from post-acceptance immutability allows the review process to function iteratively while still preserving a stable historical record once a decision is final.

7.6 Rejection
An ADR may be rejected by its required reviewers, in which case its status changes to Rejected and it remains in the repository permanently with its rationale intact. Why: a rejected ADR is still valuable institutional knowledge — it records that an option was considered and why it was not chosen, preventing future engineers from re-proposing the same option without new information.

8. ADR Repository Organization
8.1 Directory Structure
ADRs reside in a dedicated docs/adr/ directory, separate from the canonical numbered documents (00–17). Why: separating ADRs from the canonical document set preserves the distinction established in Section 9 — ADRs supplement the canonical documents but are not themselves canonical architecture specifications.

8.2 Naming Convention and Numbering
Each ADR file is named using its sequential number and a short slug derived from its title (e.g., 0001-title-slug.md). Numbers are assigned sequentially and never reused, including for rejected or superseded ADRs. Why: sequential, non-reused numbering guarantees every ADR has a stable, permanent identifier that can be referenced from other documents and code without ambiguity, consistent with the Immutable History principle (2.2).

8.3 Status Lifecycle
Every ADR's status is one of: Proposed, Accepted, Rejected, Implemented, Superseded, Deprecated. Status transitions follow the lifecycle defined in Section 4 and are recorded in the file itself (Status field) and in the repository index. Why: a single, small set of well-defined statuses keeps the lifecycle model consistent across the entire repository and prevents ad hoc, inconsistent status labeling.

8.4 Cross-References
ADRs reference other ADRs and canonical documents explicitly by number/filename in the Dependencies and Related Documents fields. Why: explicit cross-referencing is what makes Traceability (2.6) a practical, navigable property of the repository rather than an abstract principle.

8.5 Indexing
The docs/adr/ directory maintains an index (e.g., README.md or INDEX.md) listing every ADR by number, title, and current status. Why: without an index, discovering relevant prior decisions requires scanning every file individually, which discourages engineers from checking prior decisions before proposing new ones — undermining the entire purpose of the repository.

9. Relationship to Existing Documentation
ADRs supplement, and never replace, the canonical documents (00–16) and backend/openapi.yaml. The canonical documents describe the current, authoritative state of Sentinel's requirements, architecture, and operational posture. ADRs describe the decisions and reasoning that produced that state and, going forward, the decisions that will change it.

01-Product-Requirements.md — ADRs never introduce new product functionality; they record architectural responses to requirements already established there. Any ADR whose decision appears to require new product functionality is out of scope and must be redirected to product requirements review, not resolved within the ADR process.
03-Architecture.md — Document 03 is the current authoritative architecture description. ADRs record the reasoning behind that architecture and any subsequent changes to it. When an ADR changes the architecture, Document 03 is updated in the same change set, per the Documentation Update Policy (16-Engineering-Governance.md, Section 6.4); the ADR is not a substitute for that update.
04-Database-Design.md, 05-API-Specification.md, backend/openapi.yaml — ADRs record the rationale for schema and contract decisions; the schema and contract themselves remain authoritative only in Document 04, Document 05, and the OpenAPI specification respectively, consistent with Single Source of Truth (16-Engineering-Governance.md, Section 2.3).
08-Security-Architecture.md, 09-Deployment-Architecture.md, 10-Observability-Architecture.md — ADRs record the reasoning behind changes to these architectures; the documents themselves remain the operative reference for current security controls, deployment topology, and observability design.
11-Testing-Strategy.md — ADRs may record decisions that affect testing approach at a strategic level (e.g., adopting a new test category), but day-to-day test design decisions do not require an ADR (Section 3).
16-Engineering-Governance.md — This document operationalizes Document 16's Decision Records requirement (Section 5.7) and Architecture Governance rules (Section 7). ADRs are the artifact type through which those governance requirements are fulfilled for architecture-level decisions specifically.
Why this relationship is structured this way: if ADRs were treated as authoritative in place of the canonical documents, Sentinel would have two competing sources of truth about its own architecture — the numbered documents and the ADR repository — violating Single Source of Truth (16-Engineering-Governance.md, Section 2.3). Structuring ADRs as the historical record of why, while the canonical documents remain the record of what is currently true, preserves a single authoritative description of the system at any point in time while still preserving the reasoning that produced it.

10. Governance
10.1 Ownership
The Architecture Owner is accountable for the integrity of the ADR process and repository, consistent with their accountability for 03-Architecture.md under 16-Engineering-Governance.md, Section 3.1. Why: the same accountability that governs the architecture itself must govern the record of how that architecture came to be, or the two could diverge in authority.

10.2 Periodic Review
The Architecture Owner periodically reviews the ADR repository to confirm that Accepted and Implemented ADRs still accurately reflect the system's current architecture, and flags any that require superseding. Why: without periodic review, ADRs marked as current guidance can silently become stale as the system evolves through changes that were not properly recorded, violating the Living Documentation principle (2.9).

10.3 Deprecation
An ADR is marked Deprecated when its decision is no longer relevant to the system (e.g., the component it concerns was removed) without being formally superseded by a replacement decision. Why: distinguishing deprecation from superseding preserves the accuracy of the historical record — not every ADR that stops applying was replaced by a new decision; some simply became moot.

10.4 Supersession
An ADR is marked Superseded only when a new, formally accepted ADR explicitly replaces its decision, per Section 4.7. Why: requiring a formal replacement (rather than informal abandonment) ensures every architectural change remains fully traceable, with no gap between an old decision losing effect and a new decision taking effect.

10.5 Compliance
Implementation is expected to comply with Accepted and Implemented ADRs in the same manner it complies with the canonical documents, per 16-Engineering-Governance.md, Section 7.1. Deviation from an accepted ADR follows the same Allowed Deviations process defined in 16-Engineering-Governance.md, Section 7.2. Why: an ADR that can be silently ignored during implementation provides no actual governance value; compliance expectations must be identical to those applied to the canonical documents.

10.6 Auditability
The ADR repository, together with the canonical documents (00–16) and CI/CD evidence (12-CI-CD-Architecture.md), forms part of Sentinel's audit evidence per 16-Engineering-Governance.md, Section 12.6. Why: the ability to reconstruct why any architectural property of Sentinel exists is a compliance and operational necessity, not merely a historical curiosity, particularly during incident postmortems or external audits.

11. Future Evolution
This ADR process is proportionate to Sentinel's current engineering scale and is expected to evolve without requiring replacement of its underlying principles (Section 2):

Architecture Review Board. As anticipated in 16-Engineering-Governance.md, Section 13, the single Architecture Owner's review authority (Section 7.1) is expected to evolve into a board of senior engineers who collectively serve as required reviewers, preserving the same approval workflow (Section 7.2) with a board replacing a single reviewer.

Automated ADR Validation. Structural compliance with the mandatory template (Section 5) — such as verifying that all required sections are present, that referenced documents exist, and that cross-references resolve — is expected to be automated as part of the CI/CD quality gates defined in 12-CI-CD-Architecture.md, reducing reliance on manual review for mechanically verifiable completeness.

Knowledge Graph Integration. As the ADR repository grows, cross-references between ADRs and canonical documents (Section 8.4) are expected to be represented as a navigable graph, allowing engineers to trace the full lineage of a given architectural property across multiple superseding decisions.

Decision Analytics. The Engineering Metrics defined in 16-Engineering-Governance.md, Section 11, are expected to extend to ADR-specific metrics — time from proposal to acceptance, frequency of supersession, and rate of decisions that fail verification (Section 4.6) — to measure whether the ADR process itself remains healthy.

Enterprise Governance. As Sentinel's compliance obligations grow, consistent with 16-Engineering-Governance.md, Section 13, the ADR repository is expected to serve as a direct input to formal audit and attestation processes, given its role as part of the audit evidence described in Section 10.6.

None of these evolutions alter the ADR Principles in Section 2; they change the mechanisms by which those principles are enforced as the organization and system scale.

12. ADR Decision Records
The following are the permanent commitments established by this document regarding the ADR process itself.

PC-001 — Every architecture-level decision defined in Section 3 must be recorded as an ADR before implementation begins.
Rationale: Enforces Architecture Before Implementation (2.5) and fulfills the Decision Records requirement in 16-Engineering-Governance.md, Section 5.7.

PC-002 — Accepted ADR content is immutable; changes are made only through superseding ADRs.
Rationale: Preserves the integrity of the historical record (2.2) and ensures the reasoning behind past decisions can never be silently rewritten.

PC-003 — Rejected and superseded ADRs are retained permanently and never deleted.
Rationale: Prevents the loss of institutional knowledge about paths considered and not taken (Section 4.8).

PC-004 — The Architecture Owner is a required reviewer on every ADR regardless of domain.
Rationale: Guarantees a consistent, system-wide perspective is applied to every architectural decision, however narrow it initially appears (Section 7.1).

PC-005 — ADRs supplement but never supersede the canonical documents (00–16) or backend/openapi.yaml as the authoritative description of the current system.
Rationale: Preserves Single Source of Truth (16-Engineering-Governance.md, Section 2.3) by keeping a clear separation between the record of why and the record of what is currently true.

PC-006 — Numbering is sequential and permanent; numbers are never reused.
Rationale: Guarantees every ADR has a stable, unambiguous identifier for the lifetime of the system (Section 8.2).

Appendix
A.1 ADR Template
text

# ADR-<number>: <Title>

Status: <Proposed | Accepted | Rejected | Implemented | Superseded | Deprecated>
Date: <proposal date> (last updated: <date>)
Authors: <names>
Reviewers: <names/roles>

## Context
<Situation, constraints, and forces motivating this decision>

## Problem Statement
<Precise question this ADR answers>

## Decision
<The specific choice made>

## Alternatives Considered
<Other options evaluated and why they were not chosen>

## Trade-offs
<What is gained and what is given up>

## Consequences
<Downstream effects, including canonical documents affected/updated>

## Risks
<Known risks and mitigations, including security/performance/DR implications>

## Dependencies
<Other ADRs or systems this decision depends on>

## Related Documents
<Canonical documents (00–16) and OpenAPI sections affected>

## Implementation Status
<Not started | In progress | Complete>

## Superseded By
<Reference to superseding ADR, if applicable>
A.2 ADR Status Diagram
text

Proposed
   |
   v
[Review + Discussion]
   |
   +--> Rejected (permanent, archived)
   |
   v
Accepted
   |
   v
Implementation
   |
   v
Implemented ----> Verification
   |
   +--> Deprecated (no longer relevant, no replacement)
   |
   +--> Superseded (formally replaced by new ADR)
A.3 Review Workflow
Author drafts ADR using the mandatory template (Appendix A.1), status Proposed.
Required reviewers identified per Section 7.1 (affected domain owner(s) + Architecture Owner).
Review and discussion occur; revisions made as needed (Section 7.5).
Consensus reached, or escalation to Architecture Owner if not (Section 7.4).
Required reviewers formally approve; status changes to Accepted.
Implementation proceeds; Implementation Status field updated.
Upon completion, status changes to Implemented; decision verified against original evidence (Section 4.6).
If later replaced, a new ADR is written referencing this one; this ADR's status changes to Superseded.
A.4 Directory Layout
text

docs/
  adr/
    README.md          (index of all ADRs by number, title, status)
    0001-<slug>.md
    0002-<slug>.md
    0003-<slug>.md
    ...
A.5 Naming Examples
0001-use-logical-replication-for-read-replicas.md
0002-adopt-structured-event-schema-for-audit-log.md
0003-introduce-external-secrets-provider.md
0004-supersede-0001-migrate-to-managed-replication-service.md
A.6 Decision Checklist
Before submitting an ADR for review, confirm:

Does this decision meet one of the criteria in Section 3, or is an ADR unnecessary?
Is exactly one decision being recorded (Section 2.1)?
Is the Decision supported by evidence, not assertion (Section 6)?
Are Alternatives Considered documented with reasons for rejection?
Are Trade-offs stated honestly, including downsides?
Are security, performance, operational, and compatibility impacts addressed (Section 6)?
Are Risks stated with mitigation or monitoring approach?
Are Related Documents and Dependencies correctly cross-referenced?
Has the Architecture Owner been included as a reviewer (Section 7.1)?
If this ADR supersedes a prior one, has the prior ADR's status been updated accordingly (Section 4.7)?



You are a Distinguished Software Architect and Principal Engineer with experience establishing Architecture Decision Record (ADR) processes at companies such as Amazon, Google, Microsoft, Stripe, GitHub, and OpenAI.

Generate the canonical engineering document:

docs/17-Architecture-Decision-Records-Guide.md

This document is part of Sentinel's permanent engineering documentation.

The following documents are FINAL and are the ONLY source of truth:

00-Project-Context.md
01-Product-Requirements.md
02-Domain-Model.md
03-Architecture.md
04-Database-Design.md
05-API-Specification.md
06-Repository-Structure.md
07-Backend-Development-Standards.md
08-Security-Architecture.md
09-Deployment-Architecture.md
10-Observability-Architecture.md
11-Testing-Strategy.md
12-CI-CD-Architecture.md
13-Release-Engineering.md
14-Performance-and-Scalability-Architecture.md
15-Disaster-Recovery-and-Business-Continuity.md
16-Engineering-Governance.md
backend/openapi.yaml

Do NOT invent business functionality.

Do NOT redesign the architecture.

Do NOT contradict previous documents.

==================================================
OBJECTIVE
Design Sentinel's complete Architecture Decision Record (ADR) process.

This document defines how architecture-level decisions are proposed, evaluated, approved, documented, revised, superseded, and archived throughout the lifetime of Sentinel.

This is NOT a collection of ADRs.

This is NOT a design document.

It defines the permanent governance process for future architectural decisions.

==================================================
DOCUMENT STRUCTURE
Document Information
Version

Status

Owner

Audience

Dependencies

Revision History

1. Purpose
Explain:

Why architecture decisions require permanent records.
Why rationale is as important as the decision.
Why ADRs preserve institutional knowledge.
Relationship between ADRs and Engineering Governance.
2. ADR Principles
Document principles including:

One Decision per ADR
Immutable History
Evidence-Based Decisions
Explicit Trade-offs
Architecture Before Implementation
Traceability
Reviewability
Long-Term Maintainability
Living Documentation
Explain WHY each principle exists.

3. When an ADR is Required
Examples include:

Architecture changes
Module boundary changes
Database strategy changes
API contract changes
Security architecture changes
Deployment architecture changes
Technology adoption
External dependency introduction
Significant performance strategy changes
Disaster recovery strategy changes
Also explain when an ADR is NOT required.

4. ADR Lifecycle
Document:

Proposal

Review

Discussion

Approval

Implementation

Verification

Superseding

Archiving

5. ADR Template
Define mandatory sections:

ADR Number
Title
Status
Date
Authors
Reviewers
Context
Problem Statement
Decision
Alternatives Considered
Trade-offs
Consequences
Risks
Dependencies
Related Documents
Implementation Status
Superseded By
Explain the purpose of each field.

6. Decision Quality Standards
Document expectations for:

Evidence

Benchmarks

Security impact

Performance impact

Operational impact

Maintainability

Compatibility

Cost

Risk

7. Review Process
Document:

Required reviewers

Approval workflow

Consensus

Escalation

Revision

Rejection

8. ADR Repository Organization
Document:

Directory structure

Naming convention

Numbering

Status lifecycle

Cross-references

Indexing

9. Relationship to Existing Documentation
Explain how ADRs relate to:

PRD

Architecture

Database

API

Security

Deployment

Observability

Testing

Governance

OpenAPI

Explain that ADRs supplement—not replace—canonical documents.

10. Governance
Document:

Ownership

Periodic review

Deprecation

Supersession

Compliance

Auditability

11. Future Evolution
Describe future evolution toward:

Architecture Review Board

Automated ADR validation

Knowledge graph integration

Decision analytics

Enterprise governance

12. ADR Decision Records
Summarize permanent commitments about the ADR process itself.

Appendix
ADR template

ADR status diagram

Review workflow

Directory layout

Naming examples

Decision checklist

==================================================
WRITING REQUIREMENTS
Markdown only
Production-quality engineering documentation
No example implementation code
No placeholders
No TODO sections
Explain WHY every architectural decision exists
Maintain terminology consistency with Documents 00–16
Do not introduce new product functionality
Treat this as the canonical ADR Guide for Sentinel.
The document should be suitable for review by Principal Engineers, Architecture Review Boards, and Platform Engineering leaders.


claude-sonnet-5-high
16 - Engineering Governance
Document Information
Version: 1.0

Status: Final — Canonical

Owner: Architecture Owner (delegated custodianship to all Engineering Owners defined in Section 3)

Audience: Engineering contributors, Principal/Staff Engineers, Architecture Review participants, Platform Engineering, future engineering leadership, auditors

Dependencies:

00-Project-Context.md
01-Product-Requirements.md
02-Domain-Model.md
03-Architecture.md
04-Database-Design.md
05-API-Specification.md
06-Repository-Structure.md
07-Backend-Development-Standards.md
08-Security-Architecture.md
09-Deployment-Architecture.md
10-Observability-Architecture.md
11-Testing-Strategy.md
12-CI-CD-Architecture.md
13-Release-Engineering.md
14-Performance-and-Scalability-Architecture.md
15-Disaster-Recovery-and-Business-Continuity.md
backend/openapi.yaml
Revision History:

Version	Change	Rationale
1.0	Initial canonical governance model established	Sentinel required a single authoritative reference defining how engineering decisions are made, owned, reviewed, and preserved across its lifecycle
1. Purpose
Sentinel is defined by fifteen prior engineering documents that establish its domain model, architecture, data design, API contract, security posture, deployment topology, observability model, testing strategy, delivery pipeline, release process, performance envelope, and disaster recovery posture. Each of those documents describes what Sentinel is and how it behaves. This document describes how Sentinel is governed — the rules by which those designs remain true, consistent, and enforceable over time.

Governance is an engineering capability, not an administrative overlay. A system's architecture is only as reliable as the process that prevents it from drifting. Without governance, architectural documents become historical artifacts rather than living contracts, code diverges from documented behavior, and operational knowledge becomes tribal rather than institutional. Governance exists to make Sentinel's correctness and consistency a property of the system, not a property of any individual working on it.

Architectural consistency requires governance because architecture decays by default. Every system under continuous change accumulates local optimizations, one-off exceptions, and undocumented assumptions unless a deliberate process resists that decay. Sentinel's architecture (Document 03) is not self-enforcing — it is enforced by review discipline, ownership accountability, and explicit compliance checks defined in this document.

Documentation is part of engineering, not a deliverable adjacent to it. Documents 00–15 are treated as executable specifications: the database design constrains the schema, the API specification constrains the contract, the security architecture constrains what code is permitted to do. Governance exists to guarantee that these documents remain synchronized with the system they describe, because a specification that silently diverges from reality is more dangerous than no specification at all.

Engineering quality cannot depend on individual contributors because individuals rotate, forget, leave, and make mistakes under pressure. Sentinel's reliability, security, and maintainability must be properties of its process — review gates, ownership boundaries, decision records, and compliance checks — so that quality is reproducible regardless of who is doing the work at any given time. Governance is what allows Sentinel to scale from one engineer to many without losing coherence.

2. Governance Principles
Every principle below exists to prevent a specific, previously observed failure mode in software organizations. They are binding for all engineering work on Sentinel.

2.1 Documentation First
Design decisions are written down before they are implemented. Why: implementation without a documented rationale produces systems that cannot be safely modified, because future engineers cannot distinguish intentional design from incidental behavior. Documentation-first ensures every architectural property in Sentinel is traceable to a decision, not to an accident of code.

2.2 Architecture Before Implementation
No feature, service boundary, or data structure is implemented before it is reflected in the relevant architectural document (Domain Model, Architecture, Database Design, or API Specification). Why: implementation-first development produces architecture that is discovered retroactively by reading code, which is slower, error-prone, and unreviewable. Architecture-first ensures design flaws are caught before they are expensive to change.

2.3 Single Source of Truth
For any given concern, exactly one document or artifact is authoritative (e.g., backend/openapi.yaml for the API contract, Document 04 for schema, Document 08 for security controls). Why: duplicated or conflicting sources of truth inevitably diverge, and engineers waste time reconciling contradictions instead of trusting a single reference. Single Source of Truth eliminates ambiguity about what is correct.

2.4 Review Before Merge
No change reaches the main branch without independent review. Why: self-review cannot catch blind spots, and Sentinel's correctness depends on more than one engineer validating that a change is consistent with documented architecture, security posture, and testing strategy (Documents 03, 08, 11). Review is the primary defense against silent architectural drift.

2.5 Explicit Ownership
Every architectural domain, service, and operational responsibility has a named, accountable owner at all times. Why: ambiguous ownership causes decisions to be delayed, duplicated, or made by whoever is available rather than whoever is accountable. Explicit ownership ensures every governance decision has a responsible party who can be consulted, and held accountable, before and after the fact.

2.6 Evidence-Based Decisions
Technical decisions are justified by data — test results, performance benchmarks (Document 14), incident evidence, security findings (Document 08) — rather than by opinion or seniority. Why: decisions made without evidence are not reproducible or defensible under scrutiny, and they erode trust in the governance process itself. Evidence-based decision-making keeps Sentinel's technical direction auditable.

2.7 Backward Compatibility
Changes to the API, database schema, and public contracts preserve backward compatibility unless an explicit, reviewed breaking-change process (Section 10) is followed. Why: Sentinel's API Specification (Document 05) and Database Design (Document 04) are consumed by clients and internal services that cannot be assumed to change in lockstep with the backend. Breaking compatibility without process causes silent outages for consumers who trusted the contract.

2.8 Operational Responsibility
Whoever builds a capability is responsible for its operational behavior in production, including its observability (Document 10), deployment (Document 09), and recovery characteristics (Document 15). Why: separating build responsibility from operational responsibility produces systems that are easy to ship and hard to run, because the incentive to build operable systems disappears when someone else bears the operational cost.

2.9 Continuous Improvement
Governance itself is revisited and improved based on retrospectives, incidents, and audit findings. Why: a governance model that cannot evolve becomes bureaucratic overhead rather than a living safeguard. Continuous improvement ensures governance stays proportionate to Sentinel's actual risk profile as the system grows.

2.10 Long-Term Maintainability
Every governance decision optimizes for the system's maintainability over multi-year horizons, not for short-term delivery speed. Why: Sentinel is permanent infrastructure, not a short-lived project; decisions that trade long-term clarity for short-term velocity compound into unmaintainable systems. Long-term maintainability is the ultimate criterion against which all other principles are balanced.

3. Engineering Roles
The roles below describe responsibilities, not job titles or organizational hierarchy. A single individual may hold multiple responsibilities in Sentinel's current stage; as the engineering organization grows (Section 13), these responsibilities are expected to separate into distinct individuals or groups without changing the governance model itself.

3.1 Architecture Owner
Accountable for the integrity of Document 03 (Architecture) and Document 02 (Domain Model). Approves any change that alters service boundaries, module responsibilities, or system-level data flow. Exists because architectural integrity requires a single accountable authority, otherwise architectural decisions are made piecemeal by whoever touches the code last.

3.2 Backend Owner
Accountable for adherence to Document 07 (Backend Development Standards) and the correctness of backend implementation against Documents 02, 04, and 05. Exists because backend correctness requires continuous, dedicated attention to standards compliance, not just adherence at initial implementation.

3.3 Frontend Owner
Accountable for client-side adherence to the API contract defined in backend/openapi.yaml and Document 05. Exists to ensure the consuming side of the API contract is represented in governance decisions that affect compatibility.

3.4 Security Owner
Accountable for Document 08 (Security Architecture) and for reviewing any change with security-relevant impact (authentication, authorization, data handling, secrets). Exists because security regressions are asymmetric in cost — a single missed review can produce a breach — and therefore require a dedicated, non-negotiable review gate.

3.5 Platform Owner
Accountable for Document 09 (Deployment Architecture) and the infrastructure that hosts Sentinel. Exists because deployment topology and infrastructure configuration require continuity of understanding independent of any single feature team.

3.6 Release Owner
Accountable for Document 13 (Release Engineering) and for the integrity of the release process, including versioning and rollout sequencing. Exists because releases touch every other domain (code, infrastructure, database) and require a single accountable coordinator to prevent uncoordinated changes from colliding in production.

3.7 Observability Owner
Accountable for Document 10 (Observability Architecture), ensuring every system component remains observable as it evolves. Exists because observability degrades silently — a service can lose meaningful telemetry without anyone noticing until an incident occurs.

3.8 Quality Owner
Accountable for Document 11 (Testing Strategy) and the overall health of the test suite. Exists because test coverage and quality degrade under delivery pressure unless someone is explicitly accountable for resisting that pressure.

3.9 Documentation Owner
Accountable for the accuracy, consistency, and lifecycle of Documents 00–16 as a corpus. Exists because documentation entropy — small inconsistencies accumulating across many documents — requires a dedicated custodian, or it will never be anyone's immediate priority.

4. Ownership Model
Ownership defines who is accountable for the correctness of a domain, not who is exclusively permitted to touch it. Any engineer may propose a change to any domain; the owner is accountable for evaluating and approving it against the governing document.

Domain	Owner	Governing Document
Architecture	Architecture Owner	03-Architecture.md
Code (backend)	Backend Owner	07-Backend-Development-Standards.md
Code (frontend/API consumers)	Frontend Owner	backend/openapi.yaml, 05-API-Specification.md
Documentation	Documentation Owner	This document (16)
Infrastructure	Platform Owner	09-Deployment-Architecture.md
Security	Security Owner	08-Security-Architecture.md
CI/CD	Release Owner	12-CI-CD-Architecture.md
Observability	Observability Owner	10-Observability-Architecture.md
Database	Backend Owner (schema), Platform Owner (operational database)	04-Database-Design.md
API Contract	Backend Owner (implementation), Architecture Owner (contract changes)	05-API-Specification.md, backend/openapi.yaml
Performance	Backend Owner, Platform Owner (joint)	14-Performance-and-Scalability-Architecture.md
Disaster Recovery	Platform Owner	15-Disaster-Recovery-and-Business-Continuity.md
Ownership transfer occurs explicitly, never by default or by attrition. When an owner steps back from a domain, the Architecture Owner and Documentation Owner jointly confirm a successor before the transfer is considered complete, and the change is recorded in this document's revision history. Why: undocumented ownership transfer produces periods where a domain is unowned, during which architectural drift and unreviewed decisions are most likely to occur.

5. Decision Making
5.1 Technical Decisions
Day-to-day technical decisions that do not alter architecture, contracts, or security posture are made by the responsible owner without requiring board-level review. Why: requiring heavyweight review for routine decisions would make governance an obstacle rather than a safeguard, undermining its legitimacy.

5.2 Architecture Changes
Any change to service boundaries, domain model, data flow, or module responsibilities requires review by the Architecture Owner and at least one other domain owner affected by the change. Why: architecture changes have system-wide consequences that a single perspective cannot fully evaluate.

5.3 Design Reviews
Non-trivial changes (new domain concepts, new API contracts, schema changes, cross-service dependencies) require a written design review before implementation begins, consistent with the Architecture Before Implementation principle (2.2). Why: reviewing a design document is orders of magnitude cheaper than reviewing and unwinding an implemented but flawed design.

5.4 Risk Evaluation
Every design review and architecture change explicitly states its risk to security, performance, and operational reliability, referencing Documents 08, 14, and 15 respectively. Why: risks that are not explicitly stated are implicitly accepted without anyone consciously deciding to accept them.

5.5 Consensus
Decisions affecting more than one domain require agreement among the affected owners. Consensus is a discussion outcome, not a formal vote — why: Sentinel's engineering organization is small enough that consensus is achievable, and imposing formal voting mechanics adds process weight disproportionate to the current scale (see Section 13 for evolution at larger scale).

5.6 Escalation
When owners cannot reach consensus, the decision escalates to the Architecture Owner, who makes a binding decision informed by the evidence presented (Principle 2.6). Why: unresolved disagreements left to linger are more damaging than a decisively made, well-reasoned decision that can later be revisited.

5.7 Decision Records
Every architecture-level decision produces a Governance Decision Record (Section 14) capturing the decision, its rationale, its rejected alternatives, and its owner. Why: decisions without a recorded rationale are indistinguishable from accidents to future engineers, and will be re-litigated or reversed without understanding why they were made.

6. Documentation Governance
6.1 Documentation Hierarchy
Documents 00–16 form a strict hierarchy: Project Context and Product Requirements (00–01) constrain the Domain Model (02), which constrains Architecture (03), which constrains all subsequent technical documents (04–15). This governance document (16) sits alongside the corpus as the process layer governing how all others are maintained. Why: a hierarchy prevents contradictory documents from being equally authoritative, which would make conflicts unresolvable.

6.2 Version Control
All documents are version-controlled in the same repository as the code they describe, and every code change referencing a documented behavior links to the relevant document. Why: documentation stored outside the codebase's version history desynchronizes from the code silently, and there is no way to reconstruct which version of the documentation applied to which version of the system.

6.3 Review Requirements
Changes to Documents 00–16 require review from the relevant domain owner and the Documentation Owner. Changes to Document 03 (Architecture) additionally require Architecture Owner approval regardless of the initiating owner. Why: documentation carries the same authority as code in Sentinel's governance model, and therefore requires the same review discipline (Principle 2.4).

6.4 Update Policy
A document is updated in the same change set as the implementation it describes, not afterward. Why: deferred documentation updates are frequently never completed, because there is no natural trigger to revisit them once the implementation ships.

6.5 Deprecation
When a documented behavior, endpoint, or component is deprecated, the relevant document is updated to state the deprecation, its reason, and its removal timeline before removal occurs. Why: silent deprecation leaves consumers of the system without warning, violating the Backward Compatibility principle (2.7).

6.6 Synchronization with Implementation
The Documentation Owner periodically audits Documents 00–16 against the current implementation to detect drift, using the compliance mechanisms described in Section 12. Why: even with disciplined update-in-place practices, drift accumulates over time from edge cases and emergency changes; periodic audits are the backstop against Single Source of Truth violations (Principle 2.3).

7. Architecture Governance
7.1 Architecture Compliance
All implementation must conform to the service boundaries, domain model, and data flow defined in Documents 02 and 03. Compliance is verified during code review and, where automatable, through CI/CD checks (Document 12). Why: architecture that is not enforced through review and tooling degrades under delivery pressure regardless of how well it was originally documented.

7.2 Allowed Deviations
Deviations from documented architecture are permitted only when recorded as a Governance Decision Record (Section 14) that explicitly justifies the deviation and defines a remediation plan if the deviation is temporary. Why: undocumented deviations are the mechanism by which architecture silently diverges from its documentation; requiring a record makes every deviation a conscious, reviewable choice rather than an accident.

7.3 Technical Debt
Technical debt is recorded explicitly (in code comments referencing a tracked issue and, where architecturally significant, in a Governance Decision Record) rather than left implicit. Why: undocumented technical debt is indistinguishable from intentional design to future engineers, leading them to build on top of a foundation that was never meant to be permanent.

7.4 Refactoring
Refactoring that does not change external behavior or documented contracts may proceed under normal code review (Section 8). Refactoring that changes documented behavior follows the Change Management process (Section 10). Why: distinguishing internal refactoring from contract-changing refactoring prevents unnecessary process overhead while still protecting consumers from unreviewed breaking changes.

7.5 Boundary Enforcement
Module and service boundaries defined in Documents 02, 03, and 06 (Repository Structure) are enforced through code organization and, where supported by tooling, through automated boundary checks in CI. Why: boundaries that exist only in documentation and not in enforced structure are routinely violated under time pressure, because violating them is easier than respecting them without a technical barrier.

7.6 Dependency Rules
New external dependencies (libraries, services, infrastructure providers) require review by the Architecture Owner and, where security-relevant, the Security Owner, before adoption. Why: every dependency is a long-term maintenance and security liability; introducing one without review externalizes risk that the whole system must eventually bear.

8. Code Governance
8.1 Coding Standards
All backend code conforms to Document 07 (Backend Development Standards); all code touching the API contract conforms to Document 05 and backend/openapi.yaml. Why: consistent standards reduce the cognitive cost of reading unfamiliar code and make review faster and more reliable.

8.2 Review Expectations
Every change is reviewed for correctness, architectural compliance, security implications, test coverage, and documentation impact before approval. Why: review that checks only for correctness misses the majority of the failure modes governance exists to prevent — architectural drift, security regressions, and documentation desynchronization.

8.3 Merge Policy
No change merges to the main branch without passing CI/CD quality gates (Document 12) and at least one independent review approval. Why: this is the mechanical enforcement of Principle 2.4; a policy that exists only as guidance rather than as an enforced gate will eventually be bypassed under pressure.

8.4 Quality Gates
Quality gates include the automated checks defined in Document 12 (CI/CD Architecture) and the test coverage and health criteria defined in Document 11 (Testing Strategy). Why: automated gates catch classes of regression that human review reliably misses, particularly under time pressure or reviewer fatigue.

8.5 Definition of Done
A change is Done when it: implements the reviewed design, includes tests per Document 11, updates affected documentation per Section 6, passes all quality gates, and has been operationally considered (observability, security, performance) per its domain. Why: an explicit Definition of Done prevents "done" from becoming a subjective, individually-defined threshold that varies by contributor.

8.6 Definition of Ready
Work is Ready for implementation when its design has been reviewed per Section 5.3, its architectural impact is understood, and its acceptance criteria are derived from Document 01 (Product Requirements). Why: starting implementation before work is Ready produces designs discovered mid-implementation, violating Architecture Before Implementation (2.2).

9. Operational Governance
9.1 Deployment Ownership
The Platform Owner is accountable for the correctness of every production deployment against Document 09, though the Release Owner coordinates the release process itself (Document 13). Why: separating the coordination role from the infrastructure accountability role ensures deployments are both correctly sequenced and correctly executed.

9.2 Incident Ownership
The owner of the domain in which an incident originates is accountable for its resolution, with the Observability Owner accountable for ensuring the incident was detectable in the first place. Why: assigning incident ownership by domain rather than by availability ensures the most knowledgeable party leads resolution, consistent with Operational Responsibility (2.8).

9.3 Release Ownership
The Release Owner is accountable for adherence to Document 13 for every release, including versioning discipline and rollout verification. Why: without a single accountable party, release discipline erodes under the pressure of shipping quickly.

9.4 Recovery Ownership
The Platform Owner is accountable for the execution and periodic validation of the recovery procedures defined in Document 15. Why: disaster recovery procedures that are not periodically owned and validated are unlikely to work when actually needed.

9.5 Monitoring Ownership
The Observability Owner is accountable for ensuring every production component has monitoring coverage consistent with Document 10 before it is considered production-ready. Why: components shipped without monitoring create blind spots that are typically discovered only during an incident, when it is too late to add them proactively.

9.6 Security Ownership
The Security Owner is accountable for ensuring every production change complies with Document 08, and for leading response to any security-relevant incident. Why: security accountability must be independent of feature delivery accountability, or security review is the first casualty of delivery pressure.

10. Change Management
10.1 Architecture Changes
Require a design review (Section 5.3), Architecture Owner approval, and a Governance Decision Record (Section 14). Why: architecture changes have the widest blast radius of any change category and require the highest level of scrutiny.

10.2 Schema Changes
Require Backend Owner and Platform Owner approval and must comply with the migration and compatibility rules defined in Document 04. Why: schema changes are among the hardest to reverse once deployed, and both the data-model and operational perspectives must agree before they proceed.

10.3 API Changes
Require Backend Owner and Architecture Owner approval, must update backend/openapi.yaml and Document 05 in the same change set, and must comply with the Backward Compatibility principle (2.7) unless a breaking-change record is filed. Why: the API contract is consumed outside the boundary of a single change set's review, so its evolution requires enforcement stricter than internal code changes.

10.4 Security Changes
Require Security Owner approval regardless of which domain owner initiates the change. Why: security changes are the one category of change where the Security Owner's review cannot be substituted by any other owner's judgment, per Principle 2.5's explicit ownership model.

10.5 Infrastructure Changes
Require Platform Owner approval and must comply with Document 09's deployment topology and Document 15's recovery assumptions. Why: infrastructure changes can silently invalidate disaster recovery assumptions if not reviewed against Document 15 explicitly.

10.6 Documentation Updates
Follow the review requirements defined in Section 6.3 and must accompany the code or architecture change that motivates them (Section 6.4). Why: treating documentation updates as a distinct, lower-priority change type is precisely how documentation drift begins.

10.7 Approval Workflow
All changes above the routine code-review threshold (Section 8.2) follow the same sequence: design review → domain owner approval → CI/CD quality gates → merge → documentation confirmation. Why: a single consistent workflow, regardless of change type, makes governance predictable and reduces the chance that a change type is handled inconsistently because its process was ambiguous.

11. Engineering Metrics
Governance is only effective if its outcomes are measurable. The following metrics are tracked to verify governance is functioning, not to evaluate individual contributors.

Metric	What It Measures	Why It Matters
Architecture compliance rate	Proportion of changes that conform to Documents 02/03 without a recorded deviation	Detects architectural drift before it becomes systemic (Section 7.1)
Review turnaround time	Time between change submission and first review response	Slow reviews create pressure to bypass Review Before Merge (2.4); tracking this protects the principle's sustainability
Documentation freshness	Time since a document was last confirmed accurate against implementation	Detects violations of Single Source of Truth (2.3) before they mislead engineers
Technical debt volume	Count and age of recorded technical debt items (Section 7.3)	Unbounded, aging debt is a leading indicator of declining Long-Term Maintainability (2.10)
Test health	Test coverage and flake rate per Document 11	Declining test health is a leading indicator of declining Evidence-Based Decisions (2.6), since untrusted tests stop informing decisions
Operational readiness	Proportion of production components with complete observability, security, and recovery coverage	Directly measures adherence to Operational Responsibility (2.8)
Release quality	Rate of rollbacks or post-release incidents per Document 13	Measures whether Release Ownership (9.3) is functioning as intended
These metrics are reviewed periodically by the relevant owners; a sustained negative trend in any metric triggers a governance retrospective per the Continuous Improvement principle (2.9).

12. Compliance
12.1 Policy Compliance
All engineering work complies with the principles and processes defined in this document. Non-compliance discovered during review is corrected before merge; non-compliance discovered afterward is recorded and remediated. Why: compliance that is only aspirational, without a correction mechanism, is not compliance at all.

12.2 Architecture Compliance
Verified through the review process (Section 7.1) and periodically audited by the Architecture Owner against Documents 02 and 03. Why: architecture compliance cannot be assumed to be self-sustaining; periodic audits catch drift that individual reviews miss cumulatively.

12.3 Documentation Compliance
Verified through the synchronization audits described in Section 6.6. Why: documentation compliance is a precondition for every other form of compliance, since all other compliance checks are evaluated against documented expectations.

12.4 Security Compliance
Verified against Document 08 by the Security Owner as part of every security-relevant change (Section 10.4) and through periodic security review independent of feature delivery. Why: security compliance requires both continuous, change-by-change enforcement and periodic, holistic review, because point-in-time reviews alone miss compounding risk.

12.5 Release Compliance
Verified against Document 13 by the Release Owner for every release. Why: release compliance is the final checkpoint before changes reach production and therefore cannot be skipped regardless of upstream compliance.

12.6 Audit Readiness
Sentinel's documentation corpus (00–16), Governance Decision Records (Section 14), and CI/CD evidence (Document 12) together constitute sufficient audit evidence to reconstruct why any production behavior exists. Why: audit readiness maintained continuously is inexpensive; audit readiness reconstructed retroactively under time pressure is unreliable and expensive.

13. Future Evolution
This governance model is intentionally proportionate to Sentinel's current engineering scale. As the organization grows, the following evolutions are anticipated and are compatible with the principles in Section 2 without requiring their replacement:

Multiple Engineering Teams. As ownership responsibilities in Section 3 separate into distinct teams, the ownership model in Section 4 extends to team-level accountability rather than individual accountability, without changing the underlying principle of Explicit Ownership (2.5).

Architecture Review Board. As architecture-level decisions increase in frequency and complexity, the single Architecture Owner role evolves into a board of senior engineers who collectively fulfill the responsibilities of Section 3.1, preserving the Decision Making process in Section 5 with a board replacing a single decision-maker at the escalation tier (5.6).

Platform Engineering. As infrastructure complexity grows, the Platform Owner responsibility (Section 3.5) evolves into a dedicated function providing infrastructure as a reviewed, versioned capability to other engineering domains, consistent with the existing Infrastructure ownership model (Section 4).

Developer Experience. As the engineering organization grows, tooling that enforces the Code Governance rules in Section 8 (automated boundary checks, quality gate tooling) becomes a dedicated investment area, reducing reliance on manual review for mechanically verifiable compliance.

Internal Tooling. Governance mechanisms currently enforced through documented process (e.g., architecture compliance review) are expected to be progressively automated into CI/CD tooling (Document 12), consistent with the principle that automated enforcement is more durable than manual discipline.

Enterprise Governance. As Sentinel's operational and regulatory obligations grow, the Compliance model in Section 12 extends to include formal audit cycles and external attestation, building on the same documentation corpus and Governance Decision Record trail already established.

None of these evolutions alter the Governance Principles in Section 2; they change the mechanisms by which those principles are enforced as scale increases.

14. Governance Decision Records
The following are the permanent, foundational governance commitments established by this document. Future architecture-level decisions are recorded as additional entries following the same format, maintained alongside this document.

GDR-001 — Documentation is a first-class engineering artifact with equal review rigor to code.
Rationale: Documents 00–16 constrain implementation directly; treating them as secondary artifacts would undermine every downstream architectural guarantee.

GDR-002 — No single individual holds unilateral authority over architecture; escalation requires evidence, not seniority.
Rationale: Prevents architectural decisions from becoming personality-dependent rather than evidence-dependent (Principle 2.6).

GDR-003 — Backward compatibility is the default; breaking changes require an explicit, reviewed exception.
Rationale: Protects consumers of Sentinel's API and schema from silent disruption (Principle 2.7).

GDR-004 — Every production capability must have a named, accountable owner at all times.
Rationale: Eliminates unowned-domain risk windows during ownership transitions (Section 4).

GDR-005 — Deviations from documented architecture are permitted only when explicitly recorded.
Rationale: Converts unavoidable pragmatic exceptions into reviewable, bounded decisions rather than silent drift (Section 7.2).

GDR-006 — Governance itself is subject to periodic review and revision.
Rationale: Prevents governance from calcifying into process that no longer matches Sentinel's actual risk profile (Principle 2.9).

Appendix
A.1 Engineering Ownership Matrix
Domain	Primary Owner	Secondary/Joint Owner
Architecture	Architecture Owner	—
Domain Model	Architecture Owner	Backend Owner
Backend Code	Backend Owner	—
Frontend/API Consumption	Frontend Owner	—
API Contract	Backend Owner	Architecture Owner
Database Schema	Backend Owner	Platform Owner
Infrastructure	Platform Owner	—
Security	Security Owner	—
CI/CD	Release Owner	Platform Owner
Observability	Observability Owner	—
Testing	Quality Owner	Backend Owner
Releases	Release Owner	—
Performance	Backend Owner	Platform Owner
Disaster Recovery	Platform Owner	—
Documentation	Documentation Owner	All Owners (their domain)
A.2 Review Workflow
Design review submitted (for non-routine changes) referencing affected Documents 00–16.
Relevant domain owner(s) review design against governing documents.
Implementation proceeds per approved design.
Code review performed against Section 8.2 criteria.
CI/CD quality gates executed (Document 12).
Documentation updated in the same change set (Section 6.4).
Domain owner approval granted.
Change merged.
A.3 Approval Matrix
Change Type	Required Approvals
Routine code change	1 independent reviewer
Architecture change	Architecture Owner + affected domain owner(s)
Schema change	Backend Owner + Platform Owner
API change	Backend Owner + Architecture Owner
Security change	Security Owner
Infrastructure change	Platform Owner
Release	Release Owner
Documentation change	Relevant domain owner + Documentation Owner
A.4 Documentation Lifecycle
Draft → Design Reviewed → Approved by Domain Owner → Published (merged) → Maintained (synchronized with implementation per Section 6.4) → Deprecated (per Section 6.5) → Superseded/Archived.

A.5 Architecture Review Checklist
Is the change consistent with the Domain Model (Document 02)?
Does the change respect existing service and module boundaries (Documents 03, 06)?
Does the change preserve backward compatibility, or is a breaking-change record filed (Section 10.3)?
Are security implications reviewed against Document 08?
Are performance implications assessed against Document 14?
Is the change observable per Document 10 before it reaches production?
Does the change preserve or improve disaster recovery posture per Document 15?
Is documentation updated in the same change set (Section 6.4)?
Is a Governance Decision Record required (Section 14), and if so, has it been filed?



📌 Sentry Memory Context
──────────────────────
[IMPORTANT INSTRUCTION]: This is a saved context block from a previous session. Do NOT begin solving, generating, or proposing the next steps yet. Output a brief, one-sentence acknowledgment confirming you have absorbed this background context, and explicitly state that you are ready for the user to provide their next input.
──────────────────────
The following is the saved context from a previous AI conversation. Use this as your complete background reference and continue naturally from where we left off — no need to re-explain anything already established.

Goal: Establish the canonical Engineering Governance document for Sentinel, defining rules, ownership, review processes, and architectural compliance to ensure long-term maintainability and professional engineering standards.
Background: This document is part of Sentinel's permanent engineering documentation, distinguishing it from a generic project by establishing a professional engineering organization's governance model.
Constraints:

Markdown only
Production-quality engineering documentation
No implementation code
No management theory
No HR policies
No placeholders
No TODO sections
Explain WHY every governance decision exists
Maintain terminology consistency with Documents 00–15
Do not introduce new product functionality
Key Decisions:
Documentation First
Architecture Before Implementation
Single Source of Truth
Review Before Merge
Explicit Ownership
Evidence-Based Decisions
Backward Compatibility
Operational Responsibility
Continuous Improvement
Long-Term Maintainability
Where we left off: The generation of the canonical engineering document: docs/16-Engineering-Governance.md, which defines how engineering work is governed throughout the product lifecycle, including rules, ownership models, review processes, documentation expectations, architectural compliance, technical decision-making, and long-term maintainability standards.
Continue from: Generate the canonical engineering document: docs/16-Engineering-Governance.md, ensuring it adheres to all specified writing requirements and maintains consistency with the preceding 15 documents.
──────────────────────
You are a Distinguished Software Architect, VP of Engineering, and Principal Engineering Productivity leader with experience establishing engineering governance at Google, Stripe, Microsoft, Cloudflare, GitHub, and OpenAI.

Generate the canonical engineering document:

docs/16-Engineering-Governance.md

This document is part of Sentinel's permanent engineering documentation.

The following documents are FINAL and are the ONLY source of truth:

00-Project-Context.md
01-Product-Requirements.md
02-Domain-Model.md
03-Architecture.md
04-Database-Design.md
05-API-Specification.md
06-Repository-Structure.md
07-Backend-Development-Standards.md
08-Security-Architecture.md
09-Deployment-Architecture.md
10-Observability-Architecture.md
11-Testing-Strategy.md
12-CI-CD-Architecture.md
13-Release-Engineering.md
14-Performance-and-Scalability-Architecture.md
15-Disaster-Recovery-and-Business-Continuity.md
backend/openapi.yaml

Do NOT invent business functionality.

Do NOT redesign the architecture.

Do NOT contradict previous documents.

==================================================
OBJECTIVE
Design Sentinel's complete Engineering Governance architecture.

This document defines how engineering work is governed throughout the product lifecycle.

Engineering Governance establishes the rules, ownership models, review processes, documentation expectations, architectural compliance, technical decision-making, and long-term maintainability standards.

This is NOT a management handbook.

This is NOT an HR document.

This is NOT a project management guide.

It is the permanent engineering governance model for Sentinel.

==================================================
DOCUMENT STRUCTURE
Document Information
Version

Status

Owner

Audience

Dependencies

Revision History

1. Purpose
Explain:

Why governance is an engineering capability.
Why architectural consistency requires governance.
Why documentation is part of engineering.
Why engineering quality cannot depend on individual contributors.
2. Governance Principles
Document principles including:

Documentation First
Architecture Before Implementation
Single Source of Truth
Review Before Merge
Explicit Ownership
Evidence-Based Decisions
Backward Compatibility
Operational Responsibility
Continuous Improvement
Long-Term Maintainability
Explain WHY every principle exists.

3. Engineering Roles
Describe responsibilities for:

Architecture Owner

Backend Owner

Frontend Owner

Security Owner

Platform Owner

Release Owner

Observability Owner

Quality Owner

Documentation Owner

Clarify responsibilities, not job titles.

4. Ownership Model
Document ownership of:

Architecture

Code

Documentation

Infrastructure

Security

CI/CD

Observability

Database

API

Performance

Disaster Recovery

Explain ownership transfer.

5. Decision Making
Document:

Technical decisions

Architecture changes

Design reviews

Risk evaluation

Consensus

Escalation

Decision records

6. Documentation Governance
Document:

Documentation hierarchy

Version control

Review requirements

Update policy

Deprecation

Synchronization with implementation

7. Architecture Governance
Explain:

Architecture compliance

Allowed deviations

Technical debt

Refactoring

Boundary enforcement

Dependency rules

8. Code Governance
Document:

Coding standards

Review expectations

Merge policy

Quality gates

Definition of Done

Definition of Ready

9. Operational Governance
Document:

Deployment ownership

Incident ownership

Release ownership

Recovery ownership

Monitoring ownership

Security ownership

10. Change Management
Document:

Architecture changes

Schema changes

API changes

Security changes

Infrastructure changes

Documentation updates

Approval workflow

11. Engineering Metrics
Document governance metrics such as:

Architecture compliance

Review turnaround

Documentation freshness

Technical debt

Test health

Operational readiness

Release quality

Explain why these metrics matter.

12. Compliance
Document:

Policy compliance

Architecture compliance

Documentation compliance

Security compliance

Release compliance

Audit readiness

13. Future Evolution
Describe evolution toward:

Multiple engineering teams

Architecture Review Board

Platform Engineering

Developer Experience

Internal tooling

Enterprise governance

14. Governance Decision Records
Summarize permanent engineering governance commitments.

Appendix
Engineering ownership matrix

Review workflow

Approval matrix

Documentation lifecycle

Architecture review checklist

==================================================
WRITING REQUIREMENTS
Markdown only
Production-quality engineering documentation
No implementation code
No management theory
No HR policies
No placeholders
No TODO sections
Explain WHY every governance decision exists
Maintain terminology consistency with Documents 00–15
Do not introduce new product functionality
Treat this as the canonical Engineering Governance document for Sentinel.
The document should be suitable for review by Principal Engineers, Staff Engineers, Platform Engineering leaders, and Architecture Review Boards.




---

## ARB Review Notes (Post-Approval)

This document was reviewed after completion of the canonical documentation set.

The review concluded that no architectural or governance changes were required.

Recommended future enhancements (non-blocking):

- Add cloud-provider-specific operational procedures (AWS/Azure/GCP) only after infrastructure is selected.
- Extend AI provider operational procedures if multiple providers or failover strategies are introduced.
- Replace illustrative operational thresholds with production SLO/SLI values once real telemetry is available.
- Keep this runbook synchronized with operational practice whenever deployment, monitoring, recovery, or incident procedures change.

These notes do not modify the approved architecture or governance.
