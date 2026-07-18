# Sentinel — Implementation Rules

**One page. Very short. Very strict.**

These rules govern every line of code written for Sentinel. They are not guidelines, suggestions, or best practices. They are non-negotiable constraints. Violating any rule is a merge-blocking finding in code review.

---

## Architecture

1. **Never modify openapi.yaml without an ADR.** The API contract is a published agreement, not a living draft. Changing it changes what every consumer depends on.

2. **Never modify Domain Model invariants directly.** The 8 invariants in 02-Domain-Model §"Invariants — consolidated" are the system's correctness guarantees. Weakening one requires an ADR explaining why the guarantee is no longer necessary.

3. **Never introduce undocumented infrastructure.** If it's not in 09-Deployment-Architecture, it doesn't exist yet. Adding a cache, a message broker, a new service, or a new external dependency requires an ADR.

4. **Never import upward.** Domain does not import from Infrastructure. Domain does not import from Application. Application does not import from Presentation. The dependency arrow points inward, always.

5. **Never put business logic in routes.** Route handlers call Application Services. They transform HTTP into function calls and function results into HTTP. Nothing else.

---

## Data

6. **Database schema changes require a migration.** No manual DDL. No `ALTER TABLE` in a console. Every schema change is an Alembic migration, reviewed, tested, and reversible.

7. **Digital Assets are immutable.** If you are writing `UPDATE digital_assets`, something is wrong. A new row, not an edit.

8. **Analyses are append-only.** A completed Analysis is never modified. New information means a new Analysis record.

9. **Audit logs are write-once.** No UPDATE. No DELETE. No exception. If the audit trail can be edited by the system it audits, it provides no accountability.

---

## Security

10. **Hash is always server-computed.** The SHA-256 hash of a Digital Asset is computed server-side from the actual received bytes. Never trust a client-supplied hash. This is non-negotiable.

11. **Passwords never appear outside the password service.** Not in logs. Not in API responses. Not in error messages. Not in audit log details. Nowhere.

12. **Tokens never appear in logs.** JWT access tokens, refresh tokens, and API keys are redacted from all structured log output.

13. **Fail closed.** If a security check cannot be completed with certainty, deny access. A false denial is recoverable. A false allowance is a breach.

---

## Testing

14. **Every endpoint requires tests.** API-level tests validate the HTTP contract against openapi.yaml. No endpoint ships without at least one happy-path and one error-path test.

15. **Every domain invariant requires a test.** An invariant without a test is a documented intention, not an enforced guarantee.

16. **Every database constraint requires a rejection test.** Prove the constraint works by proving it rejects what it should reject. A mock cannot verify this.

17. **Tests verify behavior, not implementation.** If refactoring code without changing behavior breaks a test, the test was wrong, not the refactoring.

---

## Observability

18. **Every feature requires observability.** No feature ships without structured log entries, metrics emission, and trace span instrumentation. Observability is not retrofitted.

19. **Every request is traceable.** `X-Request-ID` propagates from API entry through queue to worker to analyzer. A single user action produces a single traceable chain.

---

## Process

20. **Every milestone must satisfy its Definition of Done.** "It works" is not done. Done means: tests pass, code reviewed, documentation updated, architecture compliance verified, security controls implemented.

21. **Architecture changes require ADR-before-code.** An ADR filed after the code is written is a governance violation, not a documentation success.

22. **Documentation ships with the code it describes.** A feature merged without updating the relevant documentation is incomplete, not "documentation debt to handle later."

---

*This document is not a substitute for the full approved architecture (Documents 00–20). It is the short, strict subset that every developer must internalize before writing their first line of Sentinel code.*

23. No TODOs or placeholder implementations in production code.
Every merged implementation is production-quality. Temporary code, placeholder logic,
mock implementations, and "fix later" comments are merge-blocking unless explicitly
tracked by an approved issue referenced in the code review.

24. Never mark a task complete without objective verification.
Completion requires passing every acceptance criterion, Definition of Done,
required tests, architecture compliance review, and implementation verification.