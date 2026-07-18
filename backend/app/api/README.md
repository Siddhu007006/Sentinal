# Presentation Layer (API)

## Purpose

The only layer permitted to know about HTTP. Translates HTTP requests into
Application layer calls and Application layer results into HTTP responses.

## Contents

- `v1/routes/` — One module per resource group, mirroring tags in `backend/openapi.yaml`
- `v1/dependencies/` — FastAPI dependency-injection providers (auth, pagination, RBAC)
- `v1/middleware/` — Request-scoped concerns (request ID, logging, rate limiting, CORS)
- `v1/exception_handlers/` — Central translation of Domain/Application exceptions into RFC 7807 error responses

## Dependency Rules

| May depend on        | Must NOT depend on     |
|----------------------|------------------------|
| `app.application`    | `app.domain` (direct)  |
| `app.schemas`        | `app.infrastructure`   |
| `app.core`           | `app.models`           |
|                      | `app.workers`          |
|                      | `app.analyzers`        |

## Key Constraints

- Routes call exactly one Application service or use case
- Response models always come from `app.schemas`, never ad-hoc dictionaries
- No business logic in route handlers
- API is versioned from day one (`v1/`)

## Governing Documents

- 05-API-Specification.md
- 06-Repository-Structure.md §4
- 07-Backend-Development-Standards.md §4
- backend/openapi.yaml
