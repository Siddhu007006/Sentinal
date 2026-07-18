# Infrastructure Layer

## Purpose

Concrete implementations of everything external. Every subfolder is an
adapter that translates between the Domain's vocabulary and a specific
external technology.

## Contents

- `database/` — SQLAlchemy engine/session setup, concrete repository implementations
- `storage/` — S3-compatible object storage client and adapter
- `queue/` — Redis/Celery producer adapter for enqueuing analysis jobs
- `ai_providers/` — Adapters wrapping external AI provider SDKs/APIs
- `email/` — Transactional email delivery adapter
- `logging/` — Structured logging configuration and emission helpers
- `config/` — Environment-variable loading and validated settings objects

## Dependency Rules

| May depend on        | Must NOT depend on     |
|----------------------|------------------------|
| `app.domain`         | `app.api`              |
| `app.models`         | `app.application`      |
| `app.core`           | `app.schemas`          |
| External libraries   | `app.workers`          |
|                      | `app.analyzers`        |

## Key Constraints

- Every adapter's job is translation and error mapping
- Infrastructure exceptions are converted to Domain-meaningful errors
- No adapter contains business rules
- Adapters fulfill contracts defined by Domain repository interfaces
- Schema shape is governed entirely by 04-Database-Design.md

## Governing Documents

- 04-Database-Design.md (persistence schema)
- 06-Repository-Structure.md §7
- 08-Security-Architecture.md (credential handling, encryption)
- 09-Deployment-Architecture.md (infrastructure dependencies)
- 10-Observability-Architecture.md (logging, metrics)
