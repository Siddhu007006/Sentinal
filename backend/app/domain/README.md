# Domain Layer

## Purpose

The pure business core implementing the entities and rules from
02-Domain-Model.md. This layer defines what Sentinel *is* — its
invariants, its vocabulary, its business rules.

## Contents

- `entities/` — User, Upload, DigitalAsset, Analyzer, Analysis, Report, AuditLog
- `value_objects/` — Immutable types with no identity (Sha256Hash, ConfidenceScore, Verdict)
- `repositories/` — Abstract interfaces only (concrete implementations in `app.infrastructure.database`)
- `services/` — Business rules that don't belong to a single entity (e.g., duplicate detection)
- `events/` — Domain events representing meaningful state transitions (UploadCompleted, AnalysisFinished)

## Dependency Rules

| May depend on | Must NOT depend on       |
|---------------|--------------------------|
| Nothing       | `app.application`        |
|               | `app.api`                |
|               | `app.infrastructure`     |
|               | `app.models`             |
|               | `app.schemas`            |
|               | `app.workers`            |
|               | `app.analyzers`          |
|               | FastAPI                  |
|               | SQLAlchemy               |
|               | Celery / Redis           |
|               | boto3 / S3 clients       |
|               | Any AI provider SDK      |
|               | Pydantic (API schemas)   |

## Key Constraints

- Zero framework dependencies
- Entities use plain dataclasses, not Pydantic
- Repository interfaces define *what*, not *how*
- Domain events decouple from what happens as a result of state transitions
- All 8 invariants from 02-Domain-Model must be enforced here

## Governing Documents

- 02-Domain-Model.md (entities, invariants, lifecycle rules)
- 06-Repository-Structure.md §6
- 07-Backend-Development-Standards.md §2 (business rules live here, nowhere else)
