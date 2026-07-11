# Sentinel

A platform for uploading digital assets and running them through pluggable analyzers — security, media, and document intelligence — producing durable, versioned analysis reports.

Built as a first-principles engineering exercise: every architecture and technology decision is documented, with alternatives considered, before it's implemented.

## Status

**Sprint 0** — repository scaffolding and engineering documentation. No application code yet.

## Start here

[`docs/01-Product-Requirements.md`](docs/01-Product-Requirements.md)

| Doc | Purpose | Status |
|---|---|---|
| `01-Product-Requirements.md` | What we're building, for whom, and why | Draft |
| `02-Domain-Model.md` | Core entities, relationships, invariants | Next |
| `03-Architecture.md` | System design and tech stack rationale | Planned |
| `04-API-Design.md` | API surface | Planned |
| `05-Database-Design.md` | Schema, indexing, migrations | Planned |
| `06-Repository-Structure.md` | This layout, explained | Planned |
| `adr/` | Architecture Decision Records | Planned |

## Layout

```
Sentinel/
├── docs/          engineering documentation, ADRs
├── backend/       FastAPI application
├── frontend/      client application
├── workers/       background task / queue consumers
├── deployment/    infra, containers, CI/CD
├── tests/         test suites
└── scripts/       one-off / dev tooling
```

## Stack

FastAPI · PostgreSQL · object storage · background queue. Rationale for each choice lands in `docs/03-Architecture.md`.
