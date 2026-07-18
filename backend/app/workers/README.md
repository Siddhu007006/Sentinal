# Workers Subsystem

## Purpose

Background job consumers that process the asynchronous pipeline defined
in 00-Project-Context.md §5. Workers consume jobs from the queue, execute
logic via the Application/Domain layers, and persist results through
Infrastructure.

## Contents

- `analysis_worker/` — Consumes analysis jobs, resolves analyzers, persists results
- `retry_worker/` — Handles retryable failures with backoff policy
- `scheduled/` — Time-triggered jobs (cleanup, housekeeping)

## Dependency Rules

| May depend on          | Must NOT depend on     |
|------------------------|------------------------|
| `app.application`      | `app.api`              |
| `app.domain` (via app) | `app.schemas`          |
| `app.infrastructure`*  | HTTP concepts          |
| `app.core`             |                        |

*Through Application layer, not directly.

## Key Constraints

- Workers never receive HTTP requests
- Workers never respond directly to a browser
- Job payloads contain identifiers only, never raw file bytes
- Worker lifecycle: Receive → Resolve → Execute → Persist → Acknowledge

## Governing Documents

- 00-Project-Context.md §5 (async pipeline)
- 06-Repository-Structure.md §8
