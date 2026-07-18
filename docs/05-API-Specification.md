# Sentinel --- API Specification

## Document Information

  -----------------------------------------------------------------------
  Field                               Value
  ----------------------------------- -----------------------------------
  **Document**                        05-API-Specification.md

  **Version**                         1.0.2

  **Status**                          Draft --- Pending Architecture
                                      Review Board Sign-off

  **Owner**                           Backend Platform Engineering (API
                                      Guild)

  **Dependencies**                    01-PRD.md, 02-Domain-Model.md,
                                      03-Architecture.md,
                                      04-Database-Design.md

  **Companion Artifact**              `openapi.yaml` (OpenAPI 3.1
                                      machine-readable contract,
                                      generated in lock-step with this
                                      document)
  -----------------------------------------------------------------------

### Revision History

  ------------------------------------------------------------------------
  Version           Date              Author            Summary
  ----------------- ----------------- ----------------- ------------------
  0.1.0             Sprint 3, Week 1  API Guild         Initial skeleton
                                                        derived from
                                                        Domain Model and
                                                        Architecture
                                                        service boundaries

  0.5.0             Sprint 3, Week 2  API Guild         Full endpoint
                                                        drafts for
                                                        Identity, Uploads,
                                                        Assets

  0.8.0             Sprint 3, Week 3  API Guild         Analysis,
                                                        Analyzer,
                                                        Reporting, Audit
                                                        Log endpoints
                                                        added;
                                                        error/pagination
                                                        standardized

  1.0.0             Sprint 3, Week 4  API Guild         Reviewed against
                                                        PRD acceptance
                                                        criteria;
                                                        traceability
                                                        matrix completed;
                                                        approved for
                                                        implementation
                                                        planning
  ------------------------------------------------------------------------

### Assumptions Register (read before implementation)

This specification is written as the single authoritative contract for
Sentinel's public and internal-client-facing REST API. It strictly
reuses the seven business entities already established for the platform
--- **Users, Uploads, Digital Assets, Analyses, Analyzers, Reports,
Audit Logs** --- and introduces no new business entities. Where the
upstream documents did not pin down a specific implementation-level
detail (e.g., exact token lifetimes, exact rate-limit thresholds), this
document states an explicit, reviewable default rather than leaving the
contract ambiguous. These are flagged inline with **\[ASSUMPTION\]** and
are the only areas open for negotiation during architecture review:

-   **\[ASSUMPTION\]** Three platform roles exist: `admin`, `analyst`,
    `viewer`, matching the least-privilege access tiers implied by the
    PRD's "who can see what" requirements (Audit Logs restricted to
    `admin`; Reports/Analyses writable by `analyst` and `admin`;
    `viewer` is read-only).
-   **\[ASSUMPTION\]** Access tokens are short-lived (15 minutes);
    refresh tokens are long-lived (30 days) and rotated on every use.
-   **\[ASSUMPTION\]** Maximum upload size is 500 MB per file, aligned
    with typical digital-asset intelligence workloads (documents,
    images, video, archives); this is configurable per deployment tier.
-   **\[ASSUMPTION\]** Analyzers are a read-only catalog resource in
    this version of the API (managed by platform operators through an
    internal admin process, not through a public write endpoint). No
    public create/update/delete surface is exposed for Analyzers in v1.

Any change to these assumptions must be ratified in the Domain Model and
Architecture documents first; this document will be revised to match,
never the other way around.

------------------------------------------------------------------------

## 1. Purpose

Sentinel is an AI-native Digital Asset Intelligence Platform: users
upload digital assets, the platform runs one or more automated
**Analyzers** against those assets to produce **Analyses**, and the
resulting findings are aggregated into **Reports** for human
consumption. All privileged and security-relevant actions are recorded
in immutable **Audit Logs**.

This document exists to answer one question precisely: **"What does the
Sentinel backend expose over HTTP, and how must every client (web app,
mobile app, internal service, third-party integration, future SDKs)
interact with it?"**

It is deliberately **not** an implementation guide. It does not describe
internal class names, ORM models, queue topologies, or storage engines.
It describes the **contract** --- the stable surface that all consumers
depend on --- so that backend, frontend, mobile, QA, and future SDK
teams can build against a single, unambiguous source of truth without
needing to inspect server code.

### 1.1 Relationship to Prior Documents

  -----------------------------------------------------------------------
  Document                            How this document depends on it
  ----------------------------------- -----------------------------------
  **PRD**                             Every endpoint in Section 6 is
                                      justified by a specific PRD
                                      capability (upload assets, run
                                      analysis, generate reports, manage
                                      account, audit compliance). Section
                                      16 traces each endpoint back to its
                                      PRD requirement.

  **Domain Model**                    Section 5 restates the seven domain
                                      entities exactly as modeled (Users,
                                      Uploads, Digital Assets, Analyses,
                                      Analyzers, Reports, Audit Logs) and
                                      expresses their lifecycle and
                                      relationships as API-visible state
                                      machines. No entity is added,
                                      renamed, or merged.

  **Architecture**                    Each endpoint is routed to exactly
                                      one owning application service
                                      (Identity & Access Service, Upload
                                      Ingestion Service, Asset Registry
                                      Service, Analysis Orchestration
                                      Service, Analyzer Registry Service,
                                      Reporting Service, Audit Service),
                                      matching the service boundaries
                                      defined in the architecture. The
                                      API layer is a thin, stateless HTTP
                                      façade over these services --- it
                                      performs no business logic of its
                                      own beyond validation and
                                      translation.

  **Database Design**                 Section 16 maps every endpoint to
                                      the specific tables it reads or
                                      writes (`users`, `refresh_tokens`,
                                      `uploads`, `digital_assets`,
                                      `analyzers`, `analyses`,
                                      `analysis_findings`, `reports`,
                                      `audit_logs`), confirming no
                                      endpoint requires schema not
                                      already defined.
  -----------------------------------------------------------------------

This document supersedes any verbal or Slack-thread agreement about
endpoint shape. If code and this document disagree, this document is
correct until formally revised.

------------------------------------------------------------------------

## 2. API Philosophy

**Why REST.** Sentinel's domain is naturally resource-oriented ---
Uploads, Assets, Analyses, and Reports are nouns with clear identity,
ownership, and lifecycle. REST's uniform interface (resources + standard
HTTP verbs) gives every client a predictable mental model, is cacheable
at the HTTP layer, and is trivially consumable by browsers, mobile SDKs,
CLIs, and third-party integrators without bespoke tooling.

**Why JSON.** JSON is the universal interchange format for web and
mobile clients, has first-class support in every target platform, is
human-readable for debugging, and integrates directly with our
validation layer (schema-validated request/response bodies).

**Why stateless APIs.** Every request carries all the information
required to process it (bearer token + parameters). No server-side
session state is held between requests. This is required for horizontal
scaling of the API tier behind a load balancer and is a hard
architectural constraint from the Architecture document's
stateless-service tier.

**Why versioned APIs.** Sentinel is expected to be integrated against by
external compliance and security tooling with long upgrade cycles. A
versioned API (`/v1`) lets us evolve the contract without breaking
existing integrations, and gives us a documented, negotiated path to
`/v2` when needed (see Section 15).

**Why predictable, resource-oriented endpoints.** Every endpoint follows
`/{resource}` and `/{resource}/{id}` conventions with standard verbs.
There are no RPC-style action endpoints (e.g., no
`/uploads/processUpload`) except where an operation is not naturally
CRUD (e.g., `/auth/refresh`, `/auth/logout`), which are modeled as
sub-resources of `/auth`, not verbs on business resources.

**Why NOT GraphQL.** Sentinel's clients have well-defined, stable data
needs per screen (asset list, analysis detail, report detail); GraphQL's
flexible querying solves an over-fetching problem we do not have, at the
cost of caching complexity, harder rate-limiting/quota enforcement per
query shape, and a steeper security review surface (arbitrary nested
queries). REST plus purpose-built list/detail endpoints is simpler to
secure, cache, and rate-limit.

**Why NOT gRPC.** gRPC is excellent for internal service-to-service
calls (and may be used *inside* the architecture's service mesh), but it
requires HTTP/2 binary framing and generated stubs that are a poor fit
for browser clients, third-party webhooks, and ad-hoc integration
testing (curl/Postman). Sentinel's public and partner-facing surface
must be reachable with plain HTTP/JSON tooling.

### 2.1 API Consistency Principles

1.  Resource names are always plural nouns (`/uploads`, not `/upload`).
2.  Nesting is limited to one level and only where ownership is
    exclusive (e.g., an analysis's findings are returned embedded, not
    as `/analyses/{id}/findings` --- see Section 5).
3.  Every list endpoint supports cursor pagination, filtering, and
    sorting using the same query parameter names across resources
    (`cursor`, `limit`, `sort`, `status`, `created_after`,
    `created_before`, `q`).
4.  Every timestamp field is suffixed `_at` and encoded as ISO-8601 UTC.
5.  Every identifier field is suffixed `_id` (except the resource's own
    `id`) and is a UUIDv7.
6.  Every monetary, size, or count field name states its unit explicitly
    (`size_bytes`, not `size`).
7.  HTTP status codes are used per their RFC 9110 semantics only
    (Section 9); we never overload `200` for error conditions.

### 2.2 Backward Compatibility Strategy

Within a major version (`v1`), the following changes are considered
**non-breaking** and may ship at any time without a version bump:

-   Adding a new optional request field.
-   Adding a new field to a response body.
-   Adding a new endpoint.
-   Adding a new enum value to a non-exhaustively-matched field (clients
    are contractually required to treat unknown enum values as
    "unknown/other").
-   Relaxing a validation constraint (e.g., raising a max length).

The following are **breaking** and require a new major version (`v2`)
per Section 15:

-   Removing or renaming a field, endpoint, or query parameter.
-   Changing a field's type or semantic meaning.
-   Changing default sort order or pagination page size.
-   Tightening a validation constraint on an existing field in a way
    that rejects previously-valid input.
-   Changing the meaning of an existing HTTP status code for a given
    endpoint.

------------------------------------------------------------------------

## 3. API Overview

  ---------------------------------------------------------------------------------
  Property                            Value
  ----------------------------------- ---------------------------------------------
  **Base URL (production)**           `https://api.sentinel.io/v1`

  **Base URL (staging)**              `https://api.staging.sentinel.io/v1`

  **Versioning scheme**               URI path versioning: `/v1/...`. The version
                                      denotes the API contract version, independent
                                      of internal service deployment versions.

  **Authentication**                  JWT Bearer tokens
                                      (`Authorization: Bearer <access_token>`)
                                      issued by `POST /v1/auth/login`; see Section
                                      4.

  **Content-Type (JSON bodies)**      `application/json; charset=utf-8`

  **Content-Type (file uploads)**     `multipart/form-data` on `POST /v1/uploads`
                                      only

  **Character Encoding**              UTF-8 everywhere, request and response

  **Time Format**                     ISO-8601, UTC, millisecond precision, `Z`
                                      suffix --- e.g. `2026-03-14T09:41:22.183Z`

  **Identifier Format**               UUIDv7 for all resource IDs ---
                                      e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`

  **Pagination**                      Cursor-based (opaque cursor);
                                      see Section 10

  **Filtering**                       Query-parameter based, resource-specific
                                      allow-list; see Section 11

  **Sorting**                         `sort` query parameter, allow-listed fields,
                                      `-` prefix for descending; see Section 11

  **Error Handling**                  Single standardized error envelope across all
                                      endpoints; see Section 8

  **Idempotency**                     `Idempotency-Key` header supported on all
                                      unsafe (`POST`) mutation endpoints; see
                                      Section 13

  **Rate Limiting**                   Per-account and per-IP token-bucket limits,
                                      surfaced via `X-RateLimit-*` headers; see
                                      Section 12
  ---------------------------------------------------------------------------------

All request and response examples in this document are written in
OpenAPI-style JSON blocks for direct portability into `openapi.yaml`.

------------------------------------------------------------------------

## 4. Authentication

Sentinel uses **JWT-based authentication with a short-lived access token
and a long-lived, rotating refresh token**, matching the Architecture
document's stateless Identity & Access Service.

### 4.1 Tokens

  -------------------------------------------------------------------------------------------
  Token             Lifetime              Transport                         Purpose
  ----------------- --------------------- --------------------------------- -----------------
  **Access Token**  15 minutes            `Authorization: Bearer <token>`   Proves identity +
                    **\[ASSUMPTION\]**    header on every protected request role for a single
                                                                            request; never
                                                                            persisted
                                                                            client-side
                                                                            beyond
                                                                            memory/secure
                                                                            storage.

  **Refresh Token** 30 days               Request body of                   Used solely to
                    **\[ASSUMPTION\]**,   `POST /v1/auth/refresh`; stored   obtain a new
                    rotated on every use  by the client in secure, httpOnly access/refresh
                                          storage                           token pair
                                                                            without
                                                                            re-entering
                                                                            credentials.
  -------------------------------------------------------------------------------------------

Access tokens are signed JWTs (`RS256`; `kid` header required for key rotation) containing `sub` (user id),
`role`, `iat`, `exp`, and `jti`. Clients must treat the token as opaque
and must not parse it for authorization decisions --- the server is
always the source of truth for authorization.

### 4.2 Authorization Header

    Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...

Requests to protected endpoints without a valid, non-expired access
token receive `401 Unauthorized` (Section 8.3). Requests with a valid
token but insufficient role receive `403 Forbidden` (Section 8.4).

### 4.3 Token Refresh

`POST /v1/auth/refresh` exchanges a valid, unexpired, unrevoked refresh
token for a new access/refresh pair. The presented refresh token is
immediately revoked (rotation), so replay of a stolen-but-already-used
refresh token is detected and treated as a security event: the entire
refresh token family is revoked and an entry is written to Audit Logs.

### 4.4 Logout

`POST /v1/auth/logout` revokes the presented refresh token (and,
optionally, all refresh tokens for the user if `all_devices: true` is
passed). Access tokens are not individually revocable (they are
stateless JWTs); they simply expire within 15 minutes, which bounds the
blast radius of a logout race.

### 4.5 Role-Based Authorization

  -----------------------------------------------------------------------
  Role                    Description             Typical capabilities
  ----------------------- ----------------------- -----------------------
  `viewer`                Read-only member of an  List/view Assets,
                          organization            Analyses, Reports they
                                                  have access to

  `analyst`               Operates the platform   All `viewer`
                          day-to-day              capabilities + upload
                                                  assets, trigger
                                                  analyses,
                                                  create/edit/delete
                                                  their own reports

  `admin`                 Organization/platform   All `analyst`
                          administrator           capabilities + manage
                                                  users, view Audit Logs,
                                                  delete any resource
                                                  within their
                                                  organization
  -----------------------------------------------------------------------

Every endpoint in Section 6 states its minimum required role explicitly.

### 4.6 Authentication Flow

    ┌────────┐                          ┌──────────────────────┐                     ┌────────────┐
    │ Client │                          │ Identity & Access Svc │                     │  Database  │
    └───┬────┘                          └──────────┬────────────┘                     └─────┬──────┘
        │  POST /v1/auth/register (email, password) │                                        │
        │────────────────────────────────────────────>                                        │
        │                                            │  hash password, INSERT users            │
        │                                            │────────────────────────────────────────>│
        │            201 Created (user, tokens)      │                                        │
        │<────────────────────────────────────────────                                        │
        │                                            │                                        │
        │  POST /v1/auth/login (email, password)     │                                        │
        │────────────────────────────────────────────>                                        │
        │                                            │  verify hash, issue JWT pair            │
        │                                            │────────────────────────────────────────>│
        │            200 OK (access, refresh)        │                                        │
        │<────────────────────────────────────────────                                        │
        │                                            │                                        │
        │  GET /v1/assets  (Authorization: Bearer)   │                                        │
        │────────────────────────────────────────────>                                        │
        │                                            │  verify JWT signature + exp locally     │
        │                                            │  (no DB round-trip for auth check)      │
        │            200 OK (assets[])               │                                        │
        │<────────────────────────────────────────────                                        │
        │                                            │                                        │
        │  [15 min later] access token expires       │                                        │
        │  POST /v1/auth/refresh (refresh_token)     │                                        │
        │────────────────────────────────────────────>                                        │
        │                                            │  validate + rotate refresh token        │
        │                                            │────────────────────────────────────────>│
        │      200 OK (new access, new refresh)      │                                        │
        │<────────────────────────────────────────────                                        │

------------------------------------------------------------------------

## 5. Resource Definitions

### 5.1 User

-   **Business purpose:** Represents an individual with credentials and
    a role who interacts with Sentinel.
-   **Ownership:** A user owns their own profile. Admins can view/manage
    users within their organization scope.
-   **Lifecycle:** `registered` → `active` → (optionally) `deactivated`.
    Deactivated users cannot authenticate but their historical
    Uploads/Analyses/Reports are retained for audit continuity.
-   **Relationships:** A User creates zero-or-more Uploads, Digital
    Assets, Analyses, and Reports. A User's privileged actions are
    recorded as Audit Log entries.

### 5.2 Upload

-   **Business purpose:** Represents a single raw file transfer into
    Sentinel --- the ingestion event that precedes an asset becoming
    part of the durable catalog.
-   **Ownership:** Owned by the User who performed the upload.
-   **Lifecycle:** `pending` → `uploading` → `stored` → `registered`
    (linked to a Digital Asset) or `failed`/`rejected` (e.g., failed
    validation, virus detected).
-   **Relationships:** An Upload produces exactly one Digital Asset once
    successfully validated and stored. An Upload never exists without a
    User.

### 5.3 Digital Asset

-   **Business purpose:** The durable, catalogued artifact that Sentinel
    tracks and analyzes over time --- the core object of "Digital Asset
    Intelligence."
-   **Ownership:** Owned by the User who registered it (via an Upload);
    visible to other users in the same organization per role.
-   **Lifecycle:** `active` → `archived` → `deleted` (soft delete;
    retained for audit trail, excluded from all default listings).
-   **Relationships:** A Digital Asset originates from exactly one
    Upload. A Digital Asset has zero-or-more Analyses performed against
    it over its lifetime (e.g., re-analysis after an Analyzer is
    updated).

### 5.4 Analyzer

-   **Business purpose:** Represents a distinct AI/ML or rules-based
    analysis capability offered by the platform (e.g., malware/threat
    detection, content classification, metadata extraction,
    deepfake/synthetic-media detection). Analyzers are the
    "intelligence" building blocks orchestrated per Analysis.
-   **Ownership:** Platform-owned, not user-owned. Read-only from the
    public API in v1 (see Assumptions Register).
-   **Lifecycle:** `available` → `deprecated` → `retired`. Only
    `available` Analyzers may be selected for a new Analysis.
-   **Relationships:** An Analyzer is referenced by zero-or-more
    Analyses.

### 5.5 Analysis

-   **Business purpose:** Represents a single execution of one Analyzer
    against one Digital Asset, producing structured findings and a
    risk/classification outcome.
-   **Ownership:** Owned by the User who triggered it; visible per
    organization role.
-   **Lifecycle:** `queued` → `running` → `completed` or `failed`.
    Terminal states are immutable.
-   **Relationships:** An Analysis belongs to exactly one Digital Asset
    and references exactly one Analyzer. An Analysis may be included in
    zero-or-more Reports.

### 5.6 Report

-   **Business purpose:** A human-consumable, curated aggregation of one
    or more Analyses, intended for sharing with stakeholders (internal
    reviewers, compliance, external clients).
-   **Ownership:** Owned by the User who created it; editable by the
    owner and any `admin`.
-   **Lifecycle:** `draft` → `published` → `archived`. Only `draft`
    reports are mutable; `published` reports are append-only (new
    Analyses can be added, prior content is not rewritten) to preserve
    reporting integrity.
-   **Relationships:** A Report references one-or-more Analyses
    (many-to-many). A Report belongs to exactly one owning User.

### 5.7 Audit Log

-   **Business purpose:** An immutable record of security- and
    compliance-relevant actions (authentication events, permission
    changes, deletions, report publication) for forensic and regulatory
    purposes.
-   **Ownership:** Platform-owned. Readable only by `admin` role.
-   **Lifecycle:** Append-only; never updated or deleted via the API.
-   **Relationships:** Each Audit Log entry references the acting User
    and, where applicable, the affected resource (Upload, Digital Asset,
    Analysis, Report, or another User).

------------------------------------------------------------------------

## 6. Endpoint Specifications

Unless otherwise stated: all request/response bodies are
`application/json`; all endpoints require
`Authorization: Bearer <access_token>` except those explicitly marked
**Public**; all list endpoints follow the pagination/filtering/sorting
conventions in Sections 10--11.

### 6.1 `POST /v1/auth/register`

-   **Purpose:** Create a new User account.
-   **Authentication:** Public (none).
-   **Authorization:** None.
-   **Request Headers:** `Content-Type: application/json`
-   **Path Parameters:** none
-   **Query Parameters:** none
-   **Request Body:**

``` json
{
  "email": "jane.doe@sentinel.io",
  "password": "Str0ng!Passw0rd123",
  "full_name": "Jane Doe"
}
```

-   **Validation Rules:**
    -   `email`: required, RFC 5322 format, max 254 chars, unique
        (case-insensitive).
    -   `password`: required, min 12 chars, must contain upper, lower,
        digit, and symbol.
    -   `full_name`: required, 2--120 chars, trimmed, no control
        characters.
-   **Success Response --- `201 Created`:**

``` json
{
  "data": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "jane.doe@sentinel.io",
    "full_name": "Jane Doe",
    "role": "analyst",
    "status": "active",
    "created_at": "2026-03-14T09:41:22.183Z"
  },
  "tokens": {
    "access_token": "eyJhbGciOiJSUzI1NiIs...",
    "refresh_token": "8f1d3c2a-...-rotating-opaque-token",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

-   **Error Responses:** `400` malformed body, `422` validation failure,
    `409` email already registered.
-   **Business Rules:** New self-registered users default to role
    `analyst`; `admin` role can only be granted via
    `PATCH /v1/users/{id}` by an existing `admin` (not exposed publicly
    in this document's endpoint list, tracked as a future admin-console
    capability, not part of v1 self-service surface).
-   **Idempotency:** Not idempotent by default (duplicate calls with
    same email return `409`). Supports `Idempotency-Key` header to
    safely retry on network failure without risk of duplicate side
    effects.
-   **Rate Limiting:** Strict --- 5 requests / hour / IP (Section 12) to
    deter automated account creation.

### 6.2 `POST /v1/auth/login`

-   **Purpose:** Authenticate a user and issue an access/refresh token
    pair.
-   **Authentication:** Public.
-   **Authorization:** None.
-   **Request Body:**

``` json
{ "email": "jane.doe@sentinel.io", "password": "Str0ng!Passw0rd123" }
```

-   **Validation Rules:** `email` required valid format; `password`
    required, non-empty.
-   **Success Response --- `200 OK`:**

``` json
{
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIs...",
    "refresh_token": "8f1d3c2a-...-rotating-opaque-token",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

-   **Error Responses:** `401` invalid credentials, `403` account
    deactivated, `422` malformed body, `429` too many attempts.
-   **Business Rules:** Failed attempts are counted per email + IP; 10
    consecutive failures within 15 minutes locks the account for 15
    minutes and writes an Audit Log entry.
-   **Idempotency:** Naturally idempotent (repeated correct login issues
    new independent token pairs; no state corruption).
-   **Rate Limiting:** 10 requests / minute / IP.

### 6.3 `POST /v1/auth/refresh`

-   **Purpose:** Exchange a valid refresh token for a new token pair.
-   **Authentication:** None (refresh token itself is the credential).
-   **Authorization:** None.
-   **Request Body:**

``` json
{ "refresh_token": "8f1d3c2a-...-rotating-opaque-token" }
```

-   **Validation Rules:** `refresh_token` required, must be a
    well-formed opaque token string.
-   **Success Response --- `200 OK`:** same shape as 6.2.
-   **Error Responses:** `401` invalid/expired/revoked token (also
    triggers full-family revocation + Audit Log entry if reuse of an
    already-rotated token is detected).
-   **Business Rules:** Refresh tokens rotate on every use; the previous
    token is immediately invalidated.
-   **Idempotency:** Explicitly NOT idempotent --- replay of the same
    refresh token is a security signal, not a safe retry (clients must
    retry with the newest issued refresh token, not the original).
-   **Rate Limiting:** 30 requests / minute / user.

### 6.4 `POST /v1/auth/logout`

-   **Purpose:** Revoke the current (or all) refresh token(s) for the
    authenticated user.
-   **Authentication:** Required (access token).
-   **Authorization:** Any authenticated role.
-   **Request Body:**

``` json
{ "refresh_token": "8f1d3c2a-...-rotating-opaque-token", "all_devices": false }
```

-   **Validation Rules:** `refresh_token` required unless
    `all_devices: true`; `all_devices` optional boolean, default
    `false`.
-   **Success Response --- `204 No Content`**
-   **Error Responses:** `401` missing/expired access token.
-   **Business Rules:** `all_devices: true` revokes every refresh token
    issued to the user; requires re-authentication on all other
    sessions.
-   **Idempotency:** Idempotent --- logging out an already-revoked token
    still returns `204`.
-   **Rate Limiting:** 20 requests / minute / user.

### 6.5 `GET /v1/users/me`

-   **Purpose:** Retrieve the authenticated user's own profile.
-   **Authentication:** Required.
-   **Authorization:** Any authenticated role (self only).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "jane.doe@sentinel.io",
    "full_name": "Jane Doe",
    "role": "analyst",
    "status": "active",
    "created_at": "2026-03-14T09:41:22.183Z",
    "updated_at": "2026-03-14T09:41:22.183Z"
  }
}
```

-   **Error Responses:** `401` unauthenticated.
-   **Business Rules:** None beyond identity resolution from the access
    token's `sub` claim.
-   **Idempotency:** Naturally idempotent (read).
-   **Rate Limiting:** 120 requests / minute / user.

### 6.6 `PATCH /v1/users/me`

-   **Purpose:** Update mutable fields of the authenticated user's own
    profile.
-   **Authentication:** Required.
-   **Authorization:** Any authenticated role (self only).
-   **Request Body (all fields optional, at least one required):**

``` json
{ "full_name": "Jane A. Doe", "password": "NewStr0ng!Pass456" }
```

-   **Validation Rules:** `full_name` 2--120 chars if present;
    `password` same policy as 6.1 if present; request rejected with
    `422` if body is empty.
-   **Success Response --- `200 OK`:** returns updated user object, same
    shape as 6.5.
-   **Error Responses:** `400`, `401`, `422`.
-   **Business Rules:** Changing `password` invalidates all existing
    refresh tokens for the user (forces re-login on other devices) and
    writes an Audit Log entry. `email` and `role` are immutable via this
    endpoint.
-   **Idempotency:** Supports `Idempotency-Key` for safe retry of
    network failures.
-   **Rate Limiting:** 30 requests / minute / user.

### 6.7 `POST /v1/uploads`

-   **Purpose:** Ingest a new raw file into Sentinel as the first step
    toward registering a Digital Asset.
-   **Authentication:** Required.
-   **Authorization:** `analyst`, `admin`.
-   **Request Headers:** `Content-Type: multipart/form-data`, optional
    `Idempotency-Key`.
-   **Request Body (multipart fields):**
    -   `file`: binary, required.
    -   `original_filename`: string, required, max 255 chars.
    -   `description`: string, optional, max 1000 chars.
-   **Validation Rules:**
    -   Max size: 500 MB **\[ASSUMPTION\]**; exceeding returns `413`.
    -   Allowed MIME types: allow-list enforced server-side (documents,
        images, video, audio, common archive formats); disallowed type
        returns `415`.
    -   `original_filename`: sanitized (path separators stripped),
        required.
-   **Success Response --- `202 Accepted`** (processing is asynchronous
    --- file is stored and queued for validation/registration):

``` json
{
  "data": {
    "id": "b6f1c2e4-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
    "status": "uploading",
    "original_filename": "quarterly-report.pdf",
    "size_bytes": 2485760,
    "content_type": "application/pdf",
    "owner_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "created_at": "2026-03-14T09:45:10.001Z"
  }
}
```

-   **Error Responses:** `400` missing file, `401`, `403`, `413` too
    large, `415` unsupported type, `422` invalid metadata.
-   **Business Rules:** A successful upload transitions asynchronously
    to `stored` then `registered` (at which point `GET /v1/uploads/{id}`
    exposes a `digital_asset_id` link); failed validation (e.g., malware
    detected by the ingestion Analyzer) transitions to `rejected` and is
    recorded in Audit Logs.
-   **Idempotency:** `Idempotency-Key` header required for safe client
    retry on timeout; identical key + identical file hash within 24
    hours returns the original `202` response rather than creating a
    duplicate Upload.
-   **Rate Limiting:** 20 requests / minute / user; 1000 requests / day
    / organization.

### 6.8 `GET /v1/uploads/{id}`

-   **Purpose:** Retrieve the current status/detail of a specific
    Upload.
-   **Authentication:** Required.
-   **Authorization:** Owner, or `admin`.
-   **Path Parameters:** `id` (UUID, required).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": {
    "id": "b6f1c2e4-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
    "status": "registered",
    "original_filename": "quarterly-report.pdf",
    "size_bytes": 2485760,
    "content_type": "application/pdf",
    "owner_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "digital_asset_id": "9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c",
    "created_at": "2026-03-14T09:45:10.001Z",
    "updated_at": "2026-03-14T09:45:14.552Z"
  }
}
```

-   **Error Responses:** `401`, `403` not owner, `404` not found.
-   **Idempotency:** Naturally idempotent (read).
-   **Rate Limiting:** 120 requests / minute / user.

### 6.9 `GET /v1/uploads`

-   **Purpose:** List the authenticated user's Uploads (or, for `admin`,
    all Uploads in their organization).
-   **Authentication:** Required.
-   **Authorization:** `analyst`, `admin` (viewers do not create Uploads
    and have no listing needs beyond registered Assets).
-   **Query Parameters:** `cursor`, `limit` (default 20, max 100),
    `status` (`pending|uploading|stored|registered|failed|rejected`),
    `created_after`, `created_before`, `sort` (default `-created_at`).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": [
    {
      "id": "b6f1c2e4-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
      "status": "registered",
      "original_filename": "quarterly-report.pdf",
      "size_bytes": 2485760,
      "created_at": "2026-03-14T09:45:10.001Z"
    }
  ],
  "pagination": { "next_cursor": "eyJpZCI6ImI2ZjEuLi4ifQ==", "has_more": true, "limit": 20 }
}
```

-   **Error Responses:** `401`, `422` invalid query parameter.
-   **Rate Limiting:** 120 requests / minute / user.

### 6.10 `POST /v1/assets`

-   **Purpose:** Explicitly register a Digital Asset from a successfully
    stored Upload (used when a client wants synchronous confirmation of
    registration rather than waiting for the asynchronous `202` flow to
    settle, or to attach classification metadata at registration time).
-   **Authentication:** Required.
-   **Authorization:** `analyst`, `admin`.
-   **Request Body:**

``` json
{
  "upload_id": "b6f1c2e4-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
  "name": "Q4 Financial Report",
  "tags": ["finance", "confidential"]
}
```

-   **Validation Rules:** `upload_id` required, must reference an Upload
    owned by the caller with status `stored`; `name` required, 1--200
    chars; `tags` optional, max 10 items, each 1--50 chars.
-   **Success Response --- `201 Created`:**

``` json
{
  "data": {
    "id": "9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c",
    "name": "Q4 Financial Report",
    "tags": ["finance", "confidential"],
    "status": "active",
    "upload_id": "b6f1c2e4-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
    "owner_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "created_at": "2026-03-14T09:46:00.221Z"
  }
}
```

-   **Error Responses:** `400`, `401`, `403` upload not owned by caller,
    `404` upload not found, `409` upload already registered to an asset,
    `422` upload not yet in `stored` state.
-   **Business Rules:** An Upload can be registered into exactly one
    Digital Asset; a second attempt returns `409`.
-   **Idempotency:** `Idempotency-Key` supported; also naturally
    idempotent via the `upload_id` uniqueness constraint (`409` on
    duplicate is a safe, expected outcome for a retried request).
-   **Rate Limiting:** 60 requests / minute / user.

### 6.11 `GET /v1/assets`

-   **Purpose:** List Digital Assets visible to the authenticated user.
-   **Authentication:** Required.
-   **Authorization:** `viewer`, `analyst`, `admin`.
-   **Query Parameters:** `cursor`, `limit`, `status`
    (`active|archived`), `tag`, `q` (full-text search on `name`),
    `created_after`, `created_before`, `sort` (`created_at`,
    `-created_at`, `name`, `-name`; default `-created_at`).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": [
    {
      "id": "9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c",
      "name": "Q4 Financial Report",
      "tags": ["finance", "confidential"],
      "status": "active",
      "content_type": "application/pdf",
      "size_bytes": 2485760,
      "created_at": "2026-03-14T09:46:00.221Z"
    }
  ],
  "pagination": { "next_cursor": null, "has_more": false, "limit": 20 }
}
```

-   **Error Responses:** `401`, `422` invalid filter/sort value.
-   **Rate Limiting:** 120 requests / minute / user.

### 6.12 `GET /v1/assets/{id}`

-   **Purpose:** Retrieve full detail of a single Digital Asset.
-   **Authentication:** Required.
-   **Authorization:** `viewer`, `analyst`, `admin` (must belong to the
    same organization as the asset owner).
-   **Path Parameters:** `id` (UUID, required).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": {
    "id": "9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c",
    "name": "Q4 Financial Report",
    "tags": ["finance", "confidential"],
    "status": "active",
    "content_type": "application/pdf",
    "size_bytes": 2485760,
    "owner_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "upload_id": "b6f1c2e4-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
    "created_at": "2026-03-14T09:46:00.221Z",
    "updated_at": "2026-03-14T09:46:00.221Z"
  }
}
```

-   **Error Responses:** `401`, `403`, `404`.
-   **Rate Limiting:** 120 requests / minute / user.

### 6.13 `DELETE /v1/assets/{id}`

-   **Purpose:** Soft-delete a Digital Asset, removing it from default
    listings while preserving it for audit purposes.
-   **Authentication:** Required.
-   **Authorization:** Owner (`analyst`), or `admin`.
-   **Path Parameters:** `id` (UUID, required).
-   **Success Response --- `204 No Content`**
-   **Error Responses:** `401`, `403` not owner/admin, `404`, `409`
    asset referenced by a `published` Report cannot be hard-removed
    (soft delete still succeeds; underlying record and its
    Analyses/Report references are retained).
-   **Business Rules:** Deletion is soft (status → `deleted`); the
    record and its historical Analyses remain queryable by `admin` for
    audit continuity and are excluded from all non-admin listings.
    Deletion writes an Audit Log entry.
-   **Idempotency:** Idempotent --- deleting an already-deleted asset
    returns `204`.
-   **Rate Limiting:** 30 requests / minute / user.

### 6.14 `POST /v1/analyses`

-   **Purpose:** Trigger a new Analysis of a Digital Asset using a
    specified Analyzer.
-   **Authentication:** Required.
-   **Authorization:** `analyst`, `admin`.
-   **Request Body:**

``` json
{ "asset_id": "9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c", "analyzer_id": "5b8e1f3a-2c4d-4e6f-9a1b-3c5d7e9f0a1b" }
```

-   **Validation Rules:** `asset_id` required, must reference an
    `active` asset visible to the caller; `analyzer_id` required, must
    reference an `available` Analyzer.
-   **Success Response --- `202 Accepted`** (analysis execution is
    asynchronous):

``` json
{
  "data": {
    "id": "d2e4f6a8-1b3c-4d5e-9f0a-2b4c6d8e0f1a",
    "status": "queued",
    "asset_id": "9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c",
    "analyzer_id": "5b8e1f3a-2c4d-4e6f-9a1b-3c5d7e9f0a1b",
    "triggered_by": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "created_at": "2026-03-14T09:50:00.000Z"
  }
}
```

-   **Error Responses:** `400`, `401`, `403` asset not visible to
    caller, `404` asset or analyzer not found, `409` analyzer is
    `deprecated`/`retired`, `422`.
-   **Business Rules:** Multiple Analyses of the same Asset by the same
    Analyzer are permitted (re-analysis is a first-class use case, e.g.,
    after Analyzer model updates); each is a distinct resource.
-   **Idempotency:** `Idempotency-Key` header supported to avoid
    duplicate analysis runs on client retry.
-   **Rate Limiting:** 60 requests / minute / user; analysis execution
    itself is additionally throttled per organization compute quota
    (returns `429` with `Retry-After` if the organization's
    concurrent-analysis quota is exceeded).

### 6.15 `GET /v1/analyses/{id}`

-   **Purpose:** Retrieve the status and, once complete, the findings of
    a specific Analysis.
-   **Authentication:** Required.
-   **Authorization:** `viewer`, `analyst`, `admin` (must have
    visibility of the underlying asset).
-   **Path Parameters:** `id` (UUID, required).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": {
    "id": "d2e4f6a8-1b3c-4d5e-9f0a-2b4c6d8e0f1a",
    "status": "completed",
    "asset_id": "9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c",
    "analyzer_id": "5b8e1f3a-2c4d-4e6f-9a1b-3c5d7e9f0a1b",
    "triggered_by": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "findings": {
      "risk_level": "low",
      "summary": "No malicious content detected; document metadata is consistent with declared authorship.",
      "detail": { "classification": "financial-document", "confidence": 0.94 }
    },
    "created_at": "2026-03-14T09:50:00.000Z",
    "completed_at": "2026-03-14T09:50:47.331Z"
  }
}
```

-   **Error Responses:** `401`, `403`, `404`.
-   **Business Rules:** `findings` is `null` while `status` is `queued`
    or `running`. `findings.detail` schema varies by Analyzer type but
    always includes `classification` and `confidence` as the common
    denominator; Analyzer-specific detail fields are documented
    per-Analyzer in `GET /v1/analyzers`.
-   **Rate Limiting:** 120 requests / minute / user.

### 6.16 `GET /v1/analyses`

-   **Purpose:** List Analyses visible to the authenticated user.
-   **Authentication:** Required.
-   **Authorization:** `viewer`, `analyst`, `admin`.
-   **Query Parameters:** `cursor`, `limit`, `asset_id`, `analyzer_id`,
    `status` (`queued|running|completed|failed`), `risk_level`
    (`low|medium|high|critical`), `created_after`, `created_before`,
    `sort` (default `-created_at`).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": [
    {
      "id": "d2e4f6a8-1b3c-4d5e-9f0a-2b4c6d8e0f1a",
      "status": "completed",
      "asset_id": "9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c",
      "analyzer_id": "5b8e1f3a-2c4d-4e6f-9a1b-3c5d7e9f0a1b",
      "risk_level": "low",
      "created_at": "2026-03-14T09:50:00.000Z"
    }
  ],
  "pagination": { "next_cursor": null, "has_more": false, "limit": 20 }
}
```

-   **Error Responses:** `401`, `422`.
-   **Rate Limiting:** 120 requests / minute / user.

### 6.17 `POST /v1/reports`

-   **Purpose:** Create a new draft Report aggregating one or more
    completed Analyses.
-   **Authentication:** Required.
-   **Authorization:** `analyst`, `admin`.
-   **Request Body:**

``` json
{
  "title": "Q4 Digital Asset Risk Review",
  "analysis_ids": [
    "d2e4f6a8-1b3c-4d5e-9f0a-2b4c6d8e0f1a",
    "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"
  ],
  "notes": "Prepared for the Q4 compliance review committee."
}
```

-   **Validation Rules:** `title` required, 1--200 chars; `analysis_ids`
    required, 1--100 items, each must reference a `completed` Analysis
    visible to the caller; `notes` optional, max 5000 chars.
-   **Success Response --- `201 Created`:**

``` json
{
  "data": {
    "id": "f3a4b5c6-7d8e-49f0-a1b2-c3d4e5f60718",
    "title": "Q4 Digital Asset Risk Review",
    "status": "draft",
    "analysis_ids": ["d2e4f6a8-1b3c-4d5e-9f0a-2b4c6d8e0f1a", "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"],
    "notes": "Prepared for the Q4 compliance review committee.",
    "owner_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "created_at": "2026-03-14T10:00:00.000Z"
  }
}
```

-   **Error Responses:** `400`, `401`, `403` an analysis not visible to
    caller, `404` an analysis id not found, `422` an analysis is not
    `completed`.
-   **Idempotency:** `Idempotency-Key` supported.
-   **Rate Limiting:** 30 requests / minute / user.

### 6.18 `GET /v1/reports`

-   **Purpose:** List Reports visible to the authenticated user.
-   **Authentication:** Required.
-   **Authorization:** `viewer`, `analyst`, `admin`.
-   **Query Parameters:** `cursor`, `limit`, `status`
    (`draft|published|archived`), `owner_id` (admin only), `q` (search
    on `title`), `created_after`, `created_before`, `sort` (default
    `-created_at`).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": [
    {
      "id": "f3a4b5c6-7d8e-49f0-a1b2-c3d4e5f60718",
      "title": "Q4 Digital Asset Risk Review",
      "status": "draft",
      "owner_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "created_at": "2026-03-14T10:00:00.000Z"
    }
  ],
  "pagination": { "next_cursor": null, "has_more": false, "limit": 20 }
}
```

-   **Error Responses:** `401`, `403` non-admin supplying another user's
    `owner_id`, `422`.
-   **Rate Limiting:** 120 requests / minute / user.

### 6.19 `GET /v1/reports/{id}`

-   **Purpose:** Retrieve full detail of a single Report, including
    embedded summaries of its referenced Analyses.
-   **Authentication:** Required.
-   **Authorization:** Owner, any user with visibility per organization
    role, or `admin`.
-   **Path Parameters:** `id` (UUID, required).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": {
    "id": "f3a4b5c6-7d8e-49f0-a1b2-c3d4e5f60718",
    "title": "Q4 Digital Asset Risk Review",
    "status": "draft",
    "notes": "Prepared for the Q4 compliance review committee.",
    "owner_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "analyses": [
      { "id": "d2e4f6a8-1b3c-4d5e-9f0a-2b4c6d8e0f1a", "asset_id": "9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c", "risk_level": "low" }
    ],
    "created_at": "2026-03-14T10:00:00.000Z",
    "updated_at": "2026-03-14T10:00:00.000Z"
  }
}
```

-   **Error Responses:** `401`, `403`, `404`.
-   **Rate Limiting:** 120 requests / minute / user.

### 6.20 `PATCH /v1/reports/{id}`

-   **Purpose:** Update a Report's mutable fields, or transition its
    lifecycle status.
-   **Authentication:** Required.
-   **Authorization:** Owner, or `admin`.
-   **Path Parameters:** `id` (UUID, required).
-   **Request Body (all optional, at least one required):**

``` json
{ "title": "Q4 Digital Asset Risk Review (Final)", "status": "published", "analysis_ids": ["d2e4f6a8-1b3c-4d5e-9f0a-2b4c6d8e0f1a"] }
```

-   **Validation Rules:** `title` 1--200 chars; `status` must be a
    forward-only transition (`draft`→`published`→`archived`; no backward
    transitions); `analysis_ids`, if present while `status` is or
    becomes `published`, may only **add** ids (removal is rejected with
    `409` to preserve published-report integrity).
-   **Success Response --- `200 OK`:** returns updated Report, same
    shape as 6.19.
-   **Error Responses:** `400`, `401`, `403`, `404`, `409` invalid
    status transition or attempted removal from a published report,
    `422`.
-   **Business Rules:** `draft` Reports are fully mutable by the
    owner/admin. `published` Reports are append-only. `archived` Reports
    are fully immutable (only `admin` may archive, and it is terminal).
-   **Idempotency:** `Idempotency-Key` supported; re-applying an
    already-applied status transition is a safe no-op returning `200`
    with the current state.
-   **Rate Limiting:** 30 requests / minute / user.

### 6.21 `DELETE /v1/reports/{id}`

-   **Purpose:** Delete a Report.
-   **Authentication:** Required.
-   **Authorization:** Owner, or `admin`.
-   **Path Parameters:** `id` (UUID, required).
-   **Success Response --- `204 No Content`**
-   **Error Responses:** `401`, `403`, `404`, `409` report is
    `published` (published reports cannot be deleted, only archived, to
    preserve stakeholder-facing integrity --- client must call `PATCH`
    with `status: archived` instead).
-   **Business Rules:** Only `draft` Reports may be hard-deleted.
    Deletion writes an Audit Log entry.
-   **Idempotency:** Idempotent for already-deleted reports (`204`);
    deterministic `409` for published reports on every retry.
-   **Rate Limiting:** 30 requests / minute / user.

### 6.22 `GET /v1/analyzers`

-   **Purpose:** List the catalog of Analyzers available on the
    platform, so clients can present analysis options and interpret
    `findings.detail` schemas.
-   **Authentication:** Required.
-   **Authorization:** `viewer`, `analyst`, `admin`.
-   **Query Parameters:** `cursor`, `limit`, `status`
    (`available|deprecated|retired`; default filters to `available` when
    omitted), `category` (e.g. `threat-detection`,
    `content-classification`, `metadata-extraction`), `sort` (default
    `name`).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": [
    {
      "id": "5b8e1f3a-2c4d-4e6f-9a1b-3c5d7e9f0a1b",
      "name": "Threat & Malware Scanner",
      "category": "threat-detection",
      "status": "available",
      "version": "3.2.0",
      "description": "Static and behavioral analysis for malicious content embedded in digital assets."
    }
  ],
  "pagination": { "next_cursor": null, "has_more": false, "limit": 20 }
}
```

-   **Error Responses:** `401`, `422`.
-   **Business Rules:** This is a platform-managed, read-only catalog in
    v1 (see Assumptions Register); no write endpoints are exposed
    publicly.
-   **Rate Limiting:** 120 requests / minute / user.

### 6.23 `GET /v1/audit-logs`

-   **Purpose:** Retrieve the immutable audit trail of security- and
    compliance-relevant platform actions.
-   **Authentication:** Required.
-   **Authorization:** `admin` only.
-   **Query Parameters:** `cursor`, `limit`, `actor_id`, `action`
    (e.g. `user.login`, `user.password_changed`, `asset.deleted`,
    `report.published`, `refresh_token.reuse_detected`), `resource_type`
    (`user|upload|asset|analysis|report`), `resource_id`,
    `created_after`, `created_before`, `sort` (fixed `-created_at`,
    non-configurable --- audit logs are always returned newest-first).
-   **Success Response --- `200 OK`:**

``` json
{
  "data": [
    {
      "id": "1a2b3c4d-5e6f-4708-9a0b-c1d2e3f40516",
      "actor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "action": "asset.deleted",
      "resource_type": "asset",
      "resource_id": "9c4e2a1b-3d5f-4e6a-8b7c-1d2e3f4a5b6c",
      "metadata": { "reason": "user-initiated" },
      "ip_address": "203.0.113.42",
      "created_at": "2026-03-14T10:05:00.000Z"
    }
  ],
  "pagination": { "next_cursor": "eyJpZCI6IjFhMmIuLi4ifQ==", "has_more": true, "limit": 20 }
}
```

-   **Error Responses:** `401`, `403` non-admin caller, `422` invalid
    filter.
-   **Business Rules:** Entries are write-once, created exclusively by
    internal services in reaction to state-changing events; there is no
    public write endpoint. Retention follows the platform's compliance
    policy (append-only; no API-driven deletion).
-   **Idempotency:** Naturally idempotent (read-only).
-   **Rate Limiting:** 60 requests / minute / user.

------------------------------------------------------------------------

## 7. Request Validation

All request bodies are validated server-side against a strict schema
before any business logic executes, following a fail-closed model:
unrecognized fields are rejected (`422`), not silently ignored, to catch
client/contract drift early.

-   **Schema validation (Pydantic-equivalent):** Every endpoint's
    request body is validated against a declarative schema (type,
    required/optional, min/max length, numeric bounds, regex patterns)
    before reaching the owning application service. Validation failures
    short-circuit before any database access.
-   **File validation:** `POST /v1/uploads` validates, in order:
    presence of `file` part → size ≤ 500 MB → MIME type against an
    allow-list (checked via magic-byte sniffing, not just the
    client-supplied `Content-Type`, to prevent extension/type spoofing)
    → filename sanitization (strips path separators and control
    characters). Files are additionally scanned asynchronously by the
    Threat & Malware Scanner Analyzer before an Upload reaches `stored`.
-   **UUID validation:** All path and body identifier fields are
    validated as RFC 4122 UUIDv7; malformed values return `422` (not
    `404`, to distinguish "badly formed request" from "well-formed but
    absent resource").
-   **Enum validation:** Fields with a fixed set of values (`status`,
    `role`, `risk_level`, `action`, etc.) are validated against an
    explicit allow-list on write; on read, clients must tolerate unknown
    future values per Section 2.2.
-   **Size limits:** String fields enforce explicit max lengths
    (documented per-field above); array fields enforce explicit max item
    counts; request bodies overall are capped at 1 MB for JSON endpoints
    (file bytes on `POST /v1/uploads` are handled via streamed multipart
    parsing, not loaded into the JSON body limit).
-   **Content-Type validation:** JSON endpoints reject requests without
    `Content-Type: application/json` with `415`; the upload endpoint
    requires `multipart/form-data` with `415` otherwise.
-   **Input sanitization:** All free-text fields (`full_name`, `name`,
    `title`, `notes`, `description`) are trimmed, stripped of control
    characters, and stored as opaque text --- never interpreted as
    markup or executed. Output encoding at the client layer is the
    consuming application's responsibility (Section 14).

------------------------------------------------------------------------

## 8. Error Handling

### 8.1 Standard Error Schema

Every error response, regardless of endpoint, uses this envelope:

``` json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be processed due to invalid input.",
    "details": [
      { "field": "email", "issue": "must be a valid email address" }
    ],
    "request_id": "req_9f2c1d4e6b8a"
  }
}
```

-   `code`: a stable, machine-readable string in `SCREAMING_SNAKE_CASE`
    (see Section 17.6 for the naming convention). Clients should branch
    on `code`, never on `message`.
-   `message`: a human-readable summary safe to display or log; never
    contains stack traces or internal identifiers.
-   `details`: optional array, present for validation and business-rule
    errors, giving per-field or per-condition context.
-   `request_id`: correlates the response with server-side logs/traces
    for support and debugging.

### 8.2 Validation Errors --- `422 Unprocessable Content`

``` json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be processed due to invalid input.",
    "details": [
      { "field": "password", "issue": "must be at least 12 characters" },
      { "field": "analysis_ids", "issue": "must contain at least 1 item" }
    ],
    "request_id": "req_9f2c1d4e6b8a"
  }
}
```

### 8.3 Authentication Errors --- `401 Unauthorized`

``` json
{
  "error": {
    "code": "AUTHENTICATION_REQUIRED",
    "message": "A valid access token is required to access this resource.",
    "request_id": "req_2a4b6c8d0e1f"
  }
}
```

Other codes in this family: `INVALID_CREDENTIALS`, `TOKEN_EXPIRED`,
`REFRESH_TOKEN_INVALID`.

### 8.4 Authorization Errors --- `403 Forbidden`

``` json
{
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "Your role does not permit this action.",
    "request_id": "req_3b5c7d9e1f20"
  }
}
```

### 8.5 Business Rule Violations --- `409 Conflict` or `422 Unprocessable Content`

``` json
{
  "error": {
    "code": "INVALID_STATE_TRANSITION",
    "message": "A published report cannot have analyses removed.",
    "request_id": "req_4c6d8e0f1a2b"
  }
}
```

### 8.6 Conflict Errors --- `409 Conflict`

``` json
{
  "error": {
    "code": "RESOURCE_ALREADY_EXISTS",
    "message": "An account with this email already exists.",
    "request_id": "req_5d7e9f0a1b2c"
  }
}
```

### 8.7 Internal Errors --- `500 Internal Server Error`

``` json
{
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "An unexpected error occurred. Our team has been notified.",
    "request_id": "req_6e8f0a1b2c3d"
  }
}
```

No internal detail (stack trace, SQL, file path) is ever included in the
response body; full detail is available server-side via `request_id`
correlation.

### 8.8 Retryable Errors

`429 Too Many Requests`, `503 Service Unavailable`, and
`500 Internal Server Error` are considered retryable. These responses
include a `Retry-After` header (seconds), and clients are expected to
implement exponential backoff with jitter. `400`, `401`, `403`, `404`,
`409`, `413`, `415`, and `422` are never retryable without changing the
request.

------------------------------------------------------------------------

## 9. Status Codes

  -----------------------------------------------------------------------
  Code                    Meaning                 Used when
  ----------------------- ----------------------- -----------------------
  **200 OK**              Success, response body  Successful `GET`,
                          present                 `PATCH`, and
                                                  synchronous `POST`
                                                  operations (e.g.,
                                                  login, refresh)

  **201 Created**         Success, new resource   `POST` endpoints that
                          created                 synchronously create a
                                                  resource (`register`,
                                                  `assets`, `reports`)

  **202 Accepted**        Request accepted,       `POST /uploads`,
                          processing continues    `POST /analyses` ---
                          asynchronously          the resource is created
                                                  in a non-terminal state
                                                  and progresses via
                                                  background processing

  **204 No Content**      Success, no response    `logout`, `DELETE`
                          body                    endpoints

  **400 Bad Request**     Malformed request that  Structural request
                          could not be parsed at  errors, distinct from
                          all (e.g., invalid      field-level validation
                          JSON, missing required  
                          multipart part)         

  **401 Unauthorized**    Missing, invalid, or    No/expired/invalid
                          expired credentials     access token; invalid
                                                  login credentials

  **403 Forbidden**       Authenticated but not   Role/ownership check
                          permitted               fails

  **404 Not Found**       Resource does not exist Unknown or inaccessible
                          or caller has no        resource ID (never
                          visibility of it        distinguishes "doesn't
                                                  exist" from "not yours"
                                                  to avoid leaking
                                                  existence)

  **409 Conflict**        Request conflicts with  Duplicate registration,
                          current resource state  invalid lifecycle
                                                  transition, deletion of
                                                  a published report

  **413 Payload Too       Request body/file       Upload exceeding 500
  Large**                 exceeds size limit      MB, JSON body exceeding
                                                  1 MB

  **415 Unsupported Media Wrong `Content-Type` or Non-JSON body on a JSON
  Type**                  disallowed file type    endpoint; disallowed
                                                  file MIME type on
                                                  upload

  **422 Unprocessable     Well-formed request,    Field-level validation
  Content**               but semantically        failures, business-rule
                          invalid field values    preconditions not met

  **429 Too Many          Rate limit exceeded     Section 12 thresholds
  Requests**                                      exceeded

  **500 Internal Server   Unhandled server-side   Bugs, unexpected
  Error**                 failure                 downstream failures

  **503 Service           A dependent service     Planned maintenance,
  Unavailable**           (e.g., an Analyzer      downstream outage;
                          execution backend) is   always paired with
                          temporarily unavailable `Retry-After`
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 10. Pagination

**Chosen strategy: cursor-based pagination**, used uniformly across
every list endpoint (`/uploads`, `/assets`, `/analyses`, `/reports`,
`/analyzers`, `/audit-logs`).

**Cursor vs. offset:** Offset-based pagination (`?page=3&size=20`)
degrades under concurrent writes (items shift between pages, causing
skipped or duplicated rows) and performs poorly on large tables
(`OFFSET` requires scanning and discarding all prior rows). Sentinel's
tables (especially `audit_logs` and `analyses`) are high-write and
expected to grow large, so cursor pagination --- anchored on a stable,
indexed `(created_at, id)` tuple --- is required for consistent,
performant results.

**Response format:**

``` json
{
  "data": [ { "...": "resource" } ],
  "pagination": {
    "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0wMy0xNFQxMDowMDowMFoiLCJpZCI6ImYzYTQuLi4ifQ==",
    "has_more": true,
    "limit": 20
  }
}
```

-   `cursor` (request, optional): an opaque, base64-encoded token from a
    prior response's `next_cursor`; omit for the first page.
-   `limit` (request, optional): page size, default `20`, max `100`;
    values outside range return `422`.
-   `next_cursor` (response): pass verbatim as `cursor` to fetch the
    next page; `null` when no further pages exist.
-   `has_more` (response): boolean convenience flag equivalent to
    `next_cursor !== null`.

**Example:**

    GET /v1/assets?limit=2
    200 OK
    {
      "data": [ {"id": "..."}, {"id": "..."} ],
      "pagination": { "next_cursor": "eyJjcm...", "has_more": true, "limit": 2 }
    }

    GET /v1/assets?limit=2&cursor=eyJjcm...
    200 OK
    {
      "data": [ {"id": "..."} ],
      "pagination": { "next_cursor": null, "has_more": false, "limit": 2 }
    }

Cursors are opaque and must not be constructed or decoded by clients;
their internal encoding may change without notice (non-breaking under
Section 2.2).

------------------------------------------------------------------------

## 11. Filtering

Filtering uses standard query parameters with a resource-specific
allow-list; unrecognized filter parameters return `422` (fail closed, to
surface client typos rather than silently ignoring them).

  -----------------------------------------------------------------------
  Resource                            Supported filters
  ----------------------------------- -----------------------------------
  Uploads                             `status`, `created_after`,
                                      `created_before`

  Assets                              `status`, `tag`, `q` (search),
                                      `created_after`, `created_before`

  Analyses                            `asset_id`, `analyzer_id`,
                                      `status`, `risk_level`,
                                      `created_after`, `created_before`

  Reports                             `status`, `owner_id` (admin only),
                                      `q` (search), `created_after`,
                                      `created_before`

  Analyzers                           `status`, `category`

  Audit Logs                          `actor_id`, `action`,
                                      `resource_type`, `resource_id`,
                                      `created_after`, `created_before`
  -----------------------------------------------------------------------

**Searching:** `q` performs a case-insensitive substring/full-text match
against the resource's primary name/title field only (`name` for Assets,
`title` for Reports); it does not search nested or related fields.

**Sorting:** `sort` accepts a resource-specific allow-listed field,
optionally prefixed with `-` for descending order (e.g.,
`sort=-created_at`, `sort=name`). Default sort is `-created_at` for all
resources except Analyzers (`name`, ascending) and Audit Logs (fixed
`-created_at`).

**Date filtering:** `created_after` / `created_before` accept ISO-8601
timestamps and are inclusive/exclusive respectively
(`created_after ≤ x < created_before`).

**Status filtering:** `status` accepts a single value from the
resource's enum; repeating the parameter
(`status=draft&status=published`) is supported and is interpreted as a
logical OR.

**Example:**

    GET /v1/analyses?status=completed&risk_level=high&created_after=2026-01-01T00:00:00Z&sort=-created_at&limit=50

------------------------------------------------------------------------

## 12. Rate Limiting

Rate limits are enforced per authenticated user (and, prior to
authentication, per source IP) using a token-bucket algorithm at the API
gateway tier, ahead of the application services.

  -----------------------------------------------------------------------
  Endpoint group                      Limit
  ----------------------------------- -----------------------------------
  `POST /v1/auth/register`            5 / hour / IP

  `POST /v1/auth/login`               10 / minute / IP

  `POST /v1/auth/refresh`             30 / minute / user

  `POST /v1/auth/logout`              20 / minute / user

  `POST /v1/uploads`                  20 / minute / user, 1000 / day /
                                      organization

  `POST /v1/analyses`                 60 / minute / user, subject to
                                      organization concurrent-analysis
                                      compute quota

  `POST/PATCH/DELETE /v1/reports*`    30 / minute / user

  All other authenticated `GET`       120 / minute / user
  endpoints                           
  -----------------------------------------------------------------------

**Headers returned on every request:**

    X-RateLimit-Limit: 120
    X-RateLimit-Remaining: 117
    X-RateLimit-Reset: 1770998400

**On limit exceeded --- `429 Too Many Requests`:**

    HTTP/1.1 429 Too Many Requests
    Retry-After: 42
    Content-Type: application/json

    {
      "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "You have exceeded the request limit for this endpoint. Please retry after the indicated time.",
        "request_id": "req_7f9a1b2c3d4e"
      }
    }

`Retry-After` is expressed in seconds and reflects the time until the
token bucket next has capacity; clients must not retry before this
interval elapses.

------------------------------------------------------------------------

## 13. Idempotency

Sentinel supports the `Idempotency-Key` request header on all unsafe
mutation endpoints (`POST /v1/auth/register`, `POST /v1/users/me`
updates via `PATCH`, `POST /v1/uploads`, `POST /v1/assets`,
`POST /v1/analyses`, `POST /v1/reports`, `PATCH /v1/reports/{id}`).

-   **Duplicate uploads:** Because network interruptions during large
    file transfers are common, `POST /v1/uploads` combines two
    safeguards: (1) an `Idempotency-Key` header --- replaying the same
    key within 24 hours returns the original `202` response without
    re-processing the file; (2) a content-hash check --- if a
    byte-identical file is uploaded twice by the same user without an
    idempotency key, the second call returns the existing Upload's
    representation rather than creating a duplicate.
-   **Retrying requests:** A client that does not receive a response
    (timeout, connection drop) should retry the exact same request with
    the same `Idempotency-Key`. The server guarantees that the side
    effect (resource creation) happens at most once per key, and returns
    the original response (same status code and body) for any repeat
    within a 24-hour idempotency window.
-   **Idempotency keys:** Client-generated UUIDs, scoped per user and
    per endpoint. Reusing a key with a *different* request body on the
    same endpoint returns `409 Conflict` with code
    `IDEMPOTENCY_KEY_REUSED`, protecting against accidental key
    collisions masking distinct requests.
-   **Safe retries without a key:** All `GET`, `PATCH`
    (full-resource-state), and `DELETE` endpoints are naturally
    idempotent per Section 6's per-endpoint notes and may be retried
    freely without an `Idempotency-Key`.

------------------------------------------------------------------------

## 14. Security

-   **Authentication:** Every non-public endpoint requires a valid,
    signed, unexpired JWT access token (Section 4). Passwords are never
    stored or logged in plaintext; hashing uses a modern, salted,
    memory-hard algorithm at the persistence layer (Database Design
    document).
-   **Authorization:** Enforced at the application-service layer on
    every request using role checks (Section 4.5) plus ownership checks
    (a user may act on their own Uploads/Assets/Reports; cross-user
    access requires `admin`). Authorization failures never leak whether
    a resource exists (`404`, not `403`, for resources outside the
    caller's visibility --- except where the caller is authenticated but
    the wrong role entirely, e.g. non-admin calling `/audit-logs`, which
    correctly returns `403` since the endpoint's existence is not
    sensitive).
-   **Least privilege:** `viewer` cannot create/modify/delete any
    resource. `analyst` is scoped to resources they own (plus
    organization-visible reads). Only `admin` can read Audit Logs or act
    on another user's resources.
-   **HTTPS:** All traffic is served exclusively over TLS 1.2+; plain
    HTTP requests are redirected/rejected at the edge. HSTS is enabled.
-   **Input validation:** Enforced per Section 7 on every request before
    business logic executes.
-   **Output encoding:** API responses are always `application/json`;
    free-text fields are returned as raw JSON string values and must be
    encoded/escaped appropriately by the consuming client's rendering
    layer (e.g., HTML-escaped before DOM insertion) --- the API itself
    performs no HTML rendering and is not a source of injected markup.
-   **Sensitive fields:** `password` is write-only --- accepted on
    request bodies, never present on any response body. Refresh tokens
    are returned once at issuance and never retrievable thereafter.
    Internal fields (e.g., password hashes, internal service
    identifiers, storage paths) are never serialized into any API
    response.
-   **File upload security:** Files are validated by size, MIME
    allow-list, and magic-byte sniffing (Section 7); every uploaded file
    is scanned by the Threat & Malware Scanner Analyzer before being
    marked `stored`; files failing the scan are marked `rejected` and
    never promoted to a Digital Asset. Uploaded content is stored in
    isolated object storage, never on an application server's local
    filesystem, and is served back to clients only via short-lived,
    scoped download references (not modeled as a public endpoint in this
    version --- asset content retrieval is out of scope for v1's read
    API, which returns metadata only).

------------------------------------------------------------------------

## 15. API Versioning

-   **Current version:** `v1`, expressed via the URI path prefix
    (`/v1/...`).
-   **Future compatibility:** Non-breaking changes (Section 2.2) are
    added continuously to `v1` without a new prefix. A new major prefix
    (`/v2`) is introduced only for breaking changes, and `v1` continues
    to be served, unmodified, for the duration of its deprecation
    window.
-   **Deprecation strategy:** When `v2` is introduced, `v1` is marked
    deprecated via a `Deprecation` and `Sunset` HTTP header (RFC 8594)
    on every `v1` response, with a minimum 12-month sunset window from
    the deprecation announcement. Deprecation is also announced through
    the developer changelog and, for authenticated integrators, via an
    in-app/email notice.
-   **Breaking change policy:** No breaking change (Section 2.2) is ever
    introduced into an existing, non-deprecated major version. All
    breaking changes are batched into the next major version, documented
    in a migration guide, and given the full sunset window before the
    prior version is retired.

------------------------------------------------------------------------

## 16. Architecture Traceability

  ----------------------------------------------------------------------------------------------------------
  Endpoint                    PRD Requirement           Domain Entity  Application     Database Tables
                                                                       Service         
  --------------------------- ------------------------- -------------- --------------- ---------------------
  `POST /v1/auth/register`    User account creation /   User           Identity &      `users`,
                              onboarding                               Access Service  `refresh_tokens`

  `POST /v1/auth/login`       User authentication       User           Identity &      `users`,
                                                                       Access Service  `refresh_tokens`

  `POST /v1/auth/refresh`     Persistent, secure        User           Identity &      `refresh_tokens`
                              sessions                                 Access Service  

  `POST /v1/auth/logout`      Session termination /     User           Identity &      `refresh_tokens`
                              security control                         Access Service  

  `GET /v1/users/me`          Account/profile           User           Identity &      `users`
                              management                               Access Service  

  `PATCH /v1/users/me`        Account/profile           User           Identity &      `users`,
                              management                               Access Service  `refresh_tokens`

  `POST /v1/uploads`          Ingest digital assets     Upload         Upload          `uploads`
                              into the platform                        Ingestion       
                                                                       Service         

  `GET /v1/uploads/{id}`      Track ingestion status    Upload         Upload          `uploads`
                                                                       Ingestion       
                                                                       Service         

  `GET /v1/uploads`           Manage/review submitted   Upload         Upload          `uploads`
                              uploads                                  Ingestion       
                                                                       Service         

  `POST /v1/assets`           Register/catalog digital  Digital Asset  Asset Registry  `digital_assets`,
                              assets                                   Service         `uploads`

  `GET /v1/assets`            Browse the digital asset  Digital Asset  Asset Registry  `digital_assets`
                              catalog                                  Service         

  `GET /v1/assets/{id}`       View asset                Digital Asset  Asset Registry  `digital_assets`
                              detail/intelligence                      Service         
                              context                                                  

  `DELETE /v1/assets/{id}`    Asset lifecycle /         Digital Asset  Asset Registry  `digital_assets`
                              retention management                     Service         

  `POST /v1/analyses`         Run AI-driven analysis on Analysis,      Analysis        `analyses`,
                              an asset                  Analyzer,      Orchestration   `digital_assets`,
                                                        Digital Asset  Service         `analyzers`

  `GET /v1/analyses/{id}`     Review analysis findings  Analysis       Analysis        `analyses`,
                                                                       Orchestration   `analysis_findings`
                                                                       Service         

  `GET /v1/analyses`          Browse historical         Analysis       Analysis        `analyses`
                              analyses                                 Orchestration   
                                                                       Service         

  `POST /v1/reports`          Compile intelligence into Report,        Reporting       `reports`, `analyses`
                              a shareable report        Analysis       Service         

  `GET /v1/reports`           Browse generated reports  Report         Reporting       `reports`
                                                                       Service         

  `GET /v1/reports/{id}`      Review a compiled report  Report,        Reporting       `reports`, `analyses`
                                                        Analysis       Service         

  `PATCH /v1/reports/{id}`    Manage report lifecycle   Report         Reporting       `reports`
                              (draft/publish/archive)                  Service         

  `DELETE /v1/reports/{id}`   Report lifecycle /        Report         Reporting       `reports`
                              cleanup                                  Service         

  `GET /v1/analyzers`         Discover available        Analyzer       Analyzer        `analyzers`
                              analysis capabilities                    Registry        
                                                                       Service         

  `GET /v1/audit-logs`        Compliance / security     Audit Log      Audit Service   `audit_logs`
                              audit trail                                              
  ----------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

## 17. Appendix

### 17.1 Naming Conventions

-   Resources: plural, lowercase, hyphenated for multi-word nouns
    (`audit-logs`, not `auditLogs` or `audit_logs`).
-   Path parameters: singular, lowercase (`{id}`).
-   Query parameters: `snake_case` (`created_after`, `analyzer_id`).
-   JSON body fields: `snake_case`, matching query parameter casing for
    consistency across the whole contract.

### 17.2 URL Conventions

-   All endpoints are rooted at `/v1`.
-   Collection endpoints: `/v1/{resources}`.
-   Item endpoints: `/v1/{resources}/{id}`.
-   No verbs in resource URLs; the only non-resource paths are the
    `/v1/auth/*` sub-resources, which model authentication actions as a
    dedicated resource family rather than verbs on `/users`.
-   Trailing slashes are not significant; `/v1/assets/` and `/v1/assets`
    are equivalent and canonicalize to the latter in all documentation
    and examples.

### 17.3 JSON Conventions

-   All successful responses wrap their payload in a top-level `data`
    key (`{ "data": {...} }` or `{ "data": [...] }`), with list
    endpoints additionally including a sibling `pagination` key.
-   All error responses wrap their payload in a top-level `error` key
    (Section 8.1).
-   `null` is used for "explicitly absent" values (e.g.,
    `findings: null` while an Analysis is running); omitted keys are
    never used to signal absence.
-   Booleans are always `true`/`false`, never `0`/`1` or string
    equivalents.

### 17.4 Timestamp Conventions

-   Every timestamp is ISO-8601, UTC, millisecond precision,
    `Z`-suffixed: `2026-03-14T09:41:22.183Z`.
-   Every persisted resource carries `created_at`; mutable resources
    additionally carry `updated_at`; resources with a defined completion
    event carry an explicit `*_at` field for that event (e.g.,
    `completed_at` on Analyses).

### 17.5 Field Naming

-   Identifier fields: the resource's own key is always `id`; references
    to other resources are `{resource}_id` (`asset_id`, `analyzer_id`,
    `owner_id`).
-   Enumerated state fields are always named `status`.
-   Size fields state their unit: `size_bytes`.
-   Boolean fields are prefixed with a verb or `has_`/`is_` where
    applicable (`has_more`).

### 17.6 Error Code Naming

-   Error `code` values are `SCREAMING_SNAKE_CASE`, verb-free, and
    describe the *condition*, not the *endpoint* (`VALIDATION_ERROR`,
    not `REGISTER_FAILED`), so the same code can be reused consistently
    across every endpoint that can produce it.
-   Codes are stable identifiers and are never repurposed for a
    different meaning once shipped; a new condition always gets a new
    code, per the backward-compatibility strategy in Section 2.2.

------------------------------------------------------------------------

## Architecture Review Notes (v1.0.1)

This review intentionally preserves the published REST contract.

-   Maintain a canonical registry of machine-readable `error.code`
    values.
-   Require or generate an `X-Request-ID` for every request to improve
    traceability.
-   Continue supporting `Idempotency-Key` on unsafe POST endpoints; keep
    retention policy in implementation documentation.
-   Keep `openapi.yaml` generated and validated alongside this
    specification to prevent documentation drift.

These are operational recommendations only and do not change endpoint
behavior.
