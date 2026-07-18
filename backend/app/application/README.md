# Application Layer

## Purpose

Orchestrates use cases described in 01-Product-Requirements.md and
05-API-Specification.md by coordinating Domain entities and Infrastructure
adapters. Contains workflow logic, not business rules.

## Contents

- `services/` — Coordinating objects grouped by capability (upload, analysis, report, auth)
- `use_cases/` — Complex workflows warranting their own object (e.g., CreateUploadUseCase)
- `commands/` — Input data structures representing intent to change state
- `queries/` — Input data structures representing read requests with filtering/pagination

## Dependency Rules

| May depend on          | Must NOT depend on     |
|------------------------|------------------------|
| `app.domain`           | `app.api`              |
| `app.infrastructure`*  | `app.schemas`          |
| `app.core`             | `app.models` (direct)  |
|                        | HTTP concepts           |
|                        | Database/ORM concepts   |

*Through Domain-defined repository interfaces only (dependency inversion).

## Key Constraints

- No HTTP or database awareness
- Must remain a thin coordinator
- Any rule that would be true regardless of framework/database belongs in Domain instead
- Commands and queries decouple from API request schemas

## Governing Documents

- 01-Product-Requirements.md §6 (Core Use Cases)
- 05-API-Specification.md
- 06-Repository-Structure.md §5
