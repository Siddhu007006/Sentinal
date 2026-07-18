# Analyzers Subsystem

## Purpose

Pluggable intelligence units as described in 02-Domain-Model.md.
Each analyzer implements a common interface defined in `base/` and is
registered through `registry/`. Analyzers are structurally isolated
from the pipeline that invokes them.

## Contents

- `base/` — Abstract analyzer interface and shared contracts
- `registry/` — Analyzer discovery and registration mechanism

Analyzer-specific directories (security_analyzer, ocr_analyzer,
metadata_analyzer, ai_document_analyzer, image_analyzer) are created
when their respective implementation Epics are reached.

## Dependency Rules

| May depend on          | Must NOT depend on     |
|------------------------|------------------------|
| `app.domain`           | `app.api`              |
| `app.infrastructure`*  | `app.application`      |
| `app.core`             | `app.schemas`          |
|                        | `app.workers`          |

*AI provider adapters only, through abstraction.

## Key Constraints

- Each analyzer implements the common interface from `base/`
- Analyzers are invoked by Workers, never directly by API routes
- Adding a new analyzer must not require modifying existing analyzers

## Governing Documents

- 02-Domain-Model.md (Analyzer entity, Analysis lifecycle)
- 06-Repository-Structure.md §9
