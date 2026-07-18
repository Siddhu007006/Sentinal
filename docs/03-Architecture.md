# 03 --- System Architecture

> **Document Status:** Authoritative\
> **Version:** 1.0.1\
> **Author:** Sentinel Core Team\
> **Last Updated:** 2025\
> **Audience:** Senior Engineers, Platform Reviewers, Technical Hiring
> Evaluators

------------------------------------------------------------------------

## Table of Contents

1.  [Executive Summary](#1-executive-summary)
2.  [Architectural Philosophy](#2-architectural-philosophy)
3.  [System Context Diagram (C4 Level
    1)](#3-system-context-diagram-c4-level-1)
4.  [Container Diagram (C4 Level 2)](#4-container-diagram-c4-level-2)
5.  [Chosen Architecture: Modular
    Monolith](#5-chosen-architecture-modular-monolith)
6.  [Layered Architecture Deep-Dive](#6-layered-architecture-deep-dive)
7.  [Module Boundaries & Dependency
    Rules](#7-module-boundaries--dependency-rules)
8.  [Data Architecture](#8-data-architecture)
9.  [Asynchronous Processing
    Pipeline](#9-asynchronous-processing-pipeline)
10. [AI Orchestration Layer](#10-ai-orchestration-layer)
11. [Authentication & Authorization](#11-authentication--authorization)
12. [API Design Contract](#12-api-design-contract)
13. [Object Storage Strategy](#13-object-storage-strategy)
14. [Observability & Operational
    Readiness](#14-observability--operational-readiness)
15. [Security Architecture](#15-security-architecture)
16. [Deployment Architecture](#16-deployment-architecture)
17. [Decision Log (ADR Summary)](#17-decision-log-adr-summary)
18. [Known Trade-offs & Future Migration
    Paths](#18-known-trade-offs--future-migration-paths)

------------------------------------------------------------------------

## 1. Executive Summary

Sentinel is an **AI-powered Digital Security Reasoning Platform** that
evaluates the trustworthiness of digital assets --- URLs, files,
domains, IP addresses, and composite reports. It accepts submissions
from authenticated users, routes each artifact through an orchestrated
multi-stage AI analysis pipeline, persists structured verdicts, and
surfaces actionable intelligence via a documented REST API.

This document defines the **complete system architecture** of Sentinel
v1. Every technology choice and structural decision made herein is
backed by explicit reasoning against alternatives. The goal is not to
select the most fashionable tool --- it is to select the most
appropriate tool for the stated constraints: a solo developer
maintaining a production-quality, portfolio-grade distributed system
with a clear path to scale.

The architecture is organized around four governing principles:

  -----------------------------------------------------------------------
  Principle                           Manifestation
  ----------------------------------- -----------------------------------
  **Clarity over cleverness**         Flat module structure, explicit
                                      dependency injection, no magic
                                      frameworks

  **Seams over walls**                Modules are boundaries, not silos;
                                      internal APIs are well-typed
                                      contracts

  **Fail loudly in development,       Strict validation at ingress,
  gracefully in production**          structured errors, exhaustive
                                      logging

  **Defer distribution until pain     Monolith now, extraction path
  demands it**                        documented and ready
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 2. Architectural Philosophy

### 2.1 The Core Tension

Every architecture is a negotiation between **correctness** (the system
does what it claims) and **velocity** (the system can be changed safely
and quickly). Microservices optimize for team-scale velocity at the cost
of operational correctness complexity. A big-ball-of-mud monolith
optimizes for initial velocity at the cost of long-term correctness. A
**Modular Monolith** is the correct answer for Sentinel at this stage of
the product lifecycle --- it provides strong intra-module contracts
without the distributed systems tax.

### 2.2 Design Priorities (Ordered)

1.  **Correctness** --- the system must produce valid, repeatable
    verdicts
2.  **Observability** --- every failure path must be traceable without
    attaching a debugger
3.  **Maintainability** --- a single developer must be able to reason
    about the entire system in one sitting
4.  **Performance** --- analysis is async; latency-sensitive paths are
    lightweight REST handlers
5.  **Scalability** --- worker concurrency and horizontal pod scaling
    are the primary levers

### 2.3 What This Architecture Deliberately Avoids

-   **gRPC between internal services** --- unnecessary at single-process
    scale; REST or direct function calls suffice
-   **Event sourcing** --- adds reconstructability complexity without a
    clear audit requirement at v1
-   **CQRS** --- read/write split premature optimization before query
    bottlenecks are observed
-   **GraphQL** --- REST is sufficient for a well-bounded resource
    model; GraphQL's power is in graph traversal, not lists of verdicts
-   **Kubernetes** --- Docker Compose is sufficient for development and
    initial production; K8s added only when horizontal scaling of worker
    pools is required

------------------------------------------------------------------------

### 2.4 Architecture Quality Attributes

The architecture is optimized for the following quality attributes, in
priority order. Each attribute's priority position reflects the failure
mode it prevents and the cost of getting it wrong in a security
intelligence platform.

  -------------------------------------------------------------------------------------
  Priority   Attribute           Rationale                              Detailed In
  ---------- ------------------- -------------------------------------- ---------------
  1          Correctness         A wrong verdict (malicious asset rated  02-Domain-Model
                                 safe) is worse than no verdict. Every  (invariants),
                                 architectural choice defers to         04-Database-Design
                                 correctness when trade-offs arise.     (ACID, §2.2)

  2          Maintainability     A single developer must reason about   This document
                                 the entire system. Complexity that     (§2.2, §5),
                                 exceeds one person's working memory    06-Repository-
                                 blocks all progress.                   Structure

  3          Observability       A system that cannot be observed       10-Observability-
                                 cannot be debugged or trusted.         Architecture
                                 Observability is ranked above
                                 security because security incidents
                                 that cannot be detected are worse
                                 than ones that can.

  4          Security            Sentinel handles untrusted content     08-Security-
                                 by definition. Security failures       Architecture
                                 undermine the platform's reason
                                 for existing.

  5          Reliability         Users must trust that submitted         15-Disaster-
                                 assets are not lost and that           Recovery-and-
                                 completed analyses are durable.        Business-
                                                                        Continuity

  6          Performance         Analysis is asynchronous by design     14-Performance-
                                 (§2.2); latency-sensitive paths are    and-Scalability-
                                 lightweight REST handlers. This        Architecture
                                 ranking reflects that correctness
                                 is never sacrificed for speed.

  7          Scalability         Worker concurrency and horizontal      14-Performance-
                                 scaling are the primary levers.        and-Scalability-
                                 Ranked below performance because       Architecture
                                 premature scaling adds complexity
                                 that violates maintainability (#2).

  8          Testability         Every component must be independently  11-Testing-
                                 testable. Ranked last not because it   Strategy
                                 is unimportant, but because the
                                 architecture's modularity (§5)
                                 provides testability as an emergent
                                 property rather than a bolt-on.
  -------------------------------------------------------------------------------------

These quality attributes serve as the primary criteria for future
architectural decisions. When two attributes conflict, the
higher-priority attribute wins unless an Architecture Decision Record
(17-Architecture-Decision-Records-Guide) explicitly justifies a
deviation.

## 3. System Context Diagram (C4 Level 1)

    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                           SENTINEL SYSTEM BOUNDARY                          │
    │                                                                             │
    │   ┌──────────────┐        REST/HTTPS         ┌─────────────────────────┐   │
    │   │   End User   │ ─────────────────────────► │   Sentinel API Server   │   │
    │   │  (Browser /  │                            │   (FastAPI / Python)    │   │
    │   │  CLI Client) │ ◄───────────────────────── │                         │   │
    │   └──────────────┘   JSON Responses + JWT     └──────────┬──────────────┘   │
    │                                                          │                  │
    │   ┌──────────────┐                            ┌──────────▼──────────────┐   │
    │   │  Threat Intel│ ◄─── Outbound HTTP ──────── │   Background Workers    │   │
    │   │  APIs (VirusTotal,│                        │   (Celery / ARQ)        │   │
    │   │  Shodan, etc)│                             └──────────┬──────────────┘   │
    │   └──────────────┘                                        │                  │
    │                                                           │                  │
    │   ┌──────────────┐        SQL / ORM            ┌──────────▼──────────────┐   │
    │   │  PostgreSQL  │ ◄──────────────────────────  │   Shared Data Layer     │   │
    │   │  Database    │                             │   (SQLAlchemy Async)│   │
    │   └──────────────┘                             └──────────┬──────────────┘   │
    │                                                           │                  │
    │   ┌──────────────┐      S3-Compatible API      ┌──────────▼──────────────┐   │
    │   │ Object Store │ ◄──────────────────────────  │   File Asset Manager    │   │
    │   │(S3/MinIO/R2) │                             └─────────────────────────┘   │
    │   └──────────────┘                                                           │
    │                                                                             │
    │   ┌──────────────┐        AMQP / Redis         ┌─────────────────────────┐   │
    │   │ Message Queue│ ◄──────────────────────────► │   Task Broker           │   │
    │   │(RabbitMQ/Redis│                            └─────────────────────────┘   │
    │   └──────────────┘                                                           │
    └─────────────────────────────────────────────────────────────────────────────┘

      ┌──────────────┐
      │  AI Provider │ ◄──── Outbound HTTPS (API Keys, server-side only)
      │ (OpenAI, etc)│
      └──────────────┘

### External System Responsibilities

  -----------------------------------------------------------------------
  External System         Role                    Coupling Level
  ----------------------- ----------------------- -----------------------
  **PostgreSQL**          Authoritative source of High --- core
                          truth for all           dependency
                          structured data         

  **Object Storage**      Immutable blob store    Medium --- swappable
                          for uploaded files and  via adapter
                          analysis artifacts      

  **Message Queue**       Decouples submission    Medium ---
                          ingestion from analysis broker-agnostic
                          execution               interface

  **AI Provider           Provides reasoning      Low --- abstracted
  (OpenAI)**              capability for          behind `AIProvider`
                          natural-language        interface
                          verdict synthesis       

  **Threat Intel APIs**   Enrichment data sources Low --- optional
                          (VirusTotal, Shodan,    enrichers, fail-open
                          URLScan)                
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 4. Container Diagram (C4 Level 2)

    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                          SENTINEL PROCESS BOUNDARY                          │
    │                                                                             │
    │  ┌────────────────────────────────────────────────────────────────────────┐ │
    │  │                      API SERVER CONTAINER                              │ │
    │  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │ │
    │  │  │  Routers    │  │  Services   │  │  Validators  │  │  Auth Layer │ │ │
    │  │  │(FastAPI)    │─►│(Application │─►│(Pydantic V2) │  │(JWT Bearer) │ │ │
    │  │  │             │  │  Layer)     │  │              │  │             │ │ │
    │  │  └─────────────┘  └──────┬──────┘  └──────────────┘  └─────────────┘ │ │
    │  │                          │                                             │ │
    │  │                  ┌───────▼───────┐                                    │ │
    │  │                  │  Repositories │                                    │ │
    │  │                  │(Domain Layer) │                                    │ │
    │  │                  └───────┬───────┘                                    │ │
    │  └──────────────────────────┼───────────────────────────────────────────┘ │
    │                             │                                               │
    │  ┌──────────────────────────▼───────────────────────────────────────────┐  │
    │  │                     WORKER CONTAINER                                  │  │
    │  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐│  │
    │  │  │Task Consumer│  │  Analyzers  │  │AI Orchestrator│  │  Enrichers  ││  │
    │  │  │(Celery/ARQ) │─►│(Domain Svc) │─►│(Chain Runner) │─►│(VirusTotal, ││  │
    │  │  │             │  │             │  │               │  │ Shodan etc) ││  │
    │  │  └─────────────┘  └──────┬──────┘  └──────────────┘  └─────────────┘│  │
    │  └──────────────────────────┼────────────────────────────────────────────┘  │
    │                             │                                               │
    │            Shared Infra Layer (imported by both containers)                 │
    │  ┌──────────────────────────▼───────────────────────────────────────────┐  │
    │  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐│  │
    │  │  │   Database  │  │Object Store │  │ Queue Client │  │  AI Client  ││  │
    │  │  │  (SQLAlchemy│  │  (boto3 /   │  │ (kombu/redis)│  │  (openai /  ││  │
    │  │  │  Async ORM) │  │   minio)    │  │              │  │  anthropic) ││  │
    │  │  └─────────────┘  └─────────────┘  └──────────────┘  └─────────────┘│  │
    │  └──────────────────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────────────────┘

**Key insight:** Both the API server and workers share the same codebase
and infrastructure layer. They are separate *processes* --- not separate
*repositories* or *deploy units* --- enabling code reuse without the
network-boundary tax of microservices.

------------------------------------------------------------------------

## 5. Chosen Architecture: Modular Monolith

### 5.1 Decision

Sentinel uses a **Modular Monolith** --- a single deployable process
whose internal boundaries are enforced by Python package structure,
explicit dependency injection, and strict import rules rather than by
network calls.

### 5.2 Comparison Against Alternatives

#### Option A: Microservices

  -----------------------------------------------------------------------
  Criteria                Microservices           Verdict
  ----------------------- ----------------------- -----------------------
  Team size fit           Optimal for 5+ teams    ❌ Solo developer ---
                                                  coordination overhead
                                                  is pure waste

  Operational complexity  Requires service mesh,  ❌ Prohibitive without
                          distributed tracing,    a platform team
                          multi-repo CI/CD        

  Data consistency        Requires Saga/2PC       ❌ Sentinel verdicts
                          patterns for            span multiple entities
                          cross-service           --- distributed
                          transactions            transactions are
                                                  dangerous

  Latency                 Network hops between    ❌ Unnecessary when
                          services add \~5--50ms  co-located
                          per call                

  Independent scaling     Each service scales     ✅ Real benefit --- but
                          independently           achievable via worker
                                                  pool scaling in
                                                  monolith

  Technology diversity    Each service can use    ✅ Real benefit --- not
                          optimal                 needed at v1
                          language/framework      
  -----------------------------------------------------------------------

**Verdict:** Microservices impose a distributed systems tax that returns
value only when independent deploy velocity across multiple teams is the
primary bottleneck. It is not the bottleneck here.

#### Option B: Big-Ball-of-Mud Monolith

  -----------------------------------------------------------------------
  Criteria                Unstructured Monolith   Verdict
  ----------------------- ----------------------- -----------------------
  Initial velocity        Fast --- no structure   ✅ Short-term win
                          to maintain             

  Long-term               Poor --- implicit       ❌ Unacceptable for a
  maintainability         dependencies sprawl     portfolio system

  Testability             Difficult --- no clear  ❌ Breaks contract
                          unit boundaries         testing

  Extraction path         Very difficult --- no   ❌ Traps the codebase
                          natural seams           
  -----------------------------------------------------------------------

**Verdict:** Eliminated on first principles.

#### Option C: Modular Monolith ✅ Selected

  -----------------------------------------------------------------------
  Criteria                Modular Monolith        Verdict
  ----------------------- ----------------------- -----------------------
  Team size fit           Optimal for 1--5        ✅ Perfect fit
                          engineers               

  Operational complexity  Single deploy unit,     ✅ Minimal ops burden
                          single CI/CD pipeline   

  Data consistency        ACID transactions       ✅ Correct-by-default
                          within one database     

  Module isolation        Enforced by Python      ✅ Structural
                          package boundaries +    discipline without
                          linting rules           network tax

  Extraction path         Modules become          ✅ Clear upgrade path
                          services; contracts     when needed
                          become APIs             

  Testability             Each module testable in ✅ Clean unit and
                          isolation via DI        integration tests
  -----------------------------------------------------------------------

### 5.3 Extraction Trigger Criteria

The following observable signals would trigger an extraction of a module
into a microservice:

1.  A single module's CPU usage consistently exceeds 70% and cannot be
    resolved by vertical scaling
2.  A team of 3+ engineers needs to deploy the same module independently
    more than 3x per week
3.  A module requires a fundamentally different language runtime (e.g.,
    Rust for binary analysis)
4.  A module's SLA diverges meaningfully from the rest of the system
    (e.g., real-time WebSocket feed)

None of these conditions apply at v1.

------------------------------------------------------------------------

## 6. Layered Architecture Deep-Dive

Sentinel organizes its codebase into five distinct layers.
**Dependencies flow strictly downward.** No lower layer may import from
a higher layer. This is enforced by `import-linter` rules in CI.

    ┌─────────────────────────────────────────────────────────────┐
    │  LAYER 5: PRESENTATION                                       │
    │  FastAPI Routers, Request/Response Schemas (Pydantic)        │
    │  Responsibility: HTTP surface. Validation. Error mapping.    │
    ├─────────────────────────────────────────────────────────────┤
    │  LAYER 4: APPLICATION                                        │
    │  Use Case Services (e.g., SubmitAssetService)               │
    │  Responsibility: Orchestrate domain logic. No business rules.│
    ├─────────────────────────────────────────────────────────────┤
    │  LAYER 3: DOMAIN                                             │
    │  Entities, Value Objects, Domain Services, Repository ABCs   │
    │  Responsibility: Business invariants. Pure Python. No I/O.   │
    ├─────────────────────────────────────────────────────────────┤
    │  LAYER 2: INFRASTRUCTURE                                     │
    │  SQLAlchemy Repositories, S3 Client, Queue Publisher         │
    │  Responsibility: Implement domain abstractions. All I/O here.│
    ├─────────────────────────────────────────────────────────────┤
    │  LAYER 1: WORKERS                                            │
    │  Celery/ARQ Tasks, Analysis Chains, AI Orchestrator          │
    │  Responsibility: Async execution. Consume queue. Write DB.   │
    └─────────────────────────────────────────────────────────────┘

### 6.1 Layer 5 --- Presentation

**What it contains:** - FastAPI `APIRouter` instances, one per module
(e.g., `assets.router`, `reports.router`) - Pydantic v2 `BaseModel`
schemas for request bodies and response envelopes - HTTP exception
handlers (`RequestValidationError` → 422, `DomainError` → 400, etc.) -
Dependency-injection callables (`Depends(get_current_user)`,
`Depends(get_db)`)

**What it must NOT contain:** - Business logic of any kind - Direct
database calls - Any import from the infrastructure layer

**Design rationale:** FastAPI routers are thin translators. They receive
a validated Pydantic model, call exactly one Application Service method,
and return a typed response. If a router function exceeds \~15 lines of
logic, that is a code smell --- the logic belongs in a service.

### 6.2 Layer 4 --- Application

**What it contains:** - Use case services (`SubmitAssetUseCase`,
`GetVerdictUseCase`, `RequestAnalysisUseCase`) - Transaction boundary
ownership --- each use case is one unit of work - Queue publication
(`queue.publish(AnalysisRequestedEvent(...))`) - Orchestration of
multiple domain services within one flow

**What it must NOT contain:** - Business rules (e.g., "a URL is
malicious if its TLD is in this blocklist" --- that belongs in the
Domain layer) - Direct SQL queries - HTTP concerns

**Design rationale:** Application Services are the **single authorized
caller of domain logic**. They ensure that every business operation is
performed as an atomic, traceable unit of work. Testing an Application
Service with a mock repository gives you 100% coverage of the business
flow without a database.

### 6.3 Layer 3 --- Domain

**What it contains:** - **Entities:** `Asset`, `AnalysisJob`, `Verdict`,
`User` --- objects with identity and lifecycle - **Value Objects:**
`Url`, `IpAddress`, `ThreatScore`, `ConfidenceLevel` --- immutable,
validated primitives - **Domain Services:** `ThreatScoringService`,
`VerdictAggregationService` --- stateless logic that spans multiple
entities - **Repository Interfaces (ABCs):** `AssetRepository`,
`VerdictRepository` --- the contract that Infrastructure implements -
**Domain Events:** `AssetSubmitted`, `AnalysisCompleted`, `VerdictReady`

**What it must NOT contain:** - Any import of SQLAlchemy, boto3, redis,
httpx, or any I/O library - Any reference to FastAPI or Pydantic request
schemas

**Design rationale:** The Domain layer is the **heart of the system**.
It must be pure Python --- no framework entanglement. This makes it
trivially testable (`pytest` with no mocks), and ensures that domain
rules survive technology migrations.

``` python
# Example: Value Object with invariant enforcement
@dataclass(frozen=True)
class ThreatScore:
    value: float

    def __post_init__(self):
        if not (0.0 <= self.value <= 1.0):
            raise DomainError(f"ThreatScore must be in [0.0, 1.0], got {self.value}")

    @property
    def severity(self) -> Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        if self.value < 0.25: return "LOW"
        if self.value < 0.50: return "MEDIUM"
        if self.value < 0.75: return "HIGH"
        return "CRITICAL"
```

### 6.4 Layer 2 --- Infrastructure

**What it contains:** - Concrete SQLAlchemy ORM models and async
repository implementations - S3-compatible object storage client
(provider-agnostic via adapter pattern) - Queue publisher and consumer
implementations - HTTP clients for external threat intelligence APIs
(VirusTotal, Shodan, URLScan.io) - AI provider client (OpenAI, Anthropic
--- selected at runtime via config)

**What it must NOT contain:** - Business logic - Presentation concerns

**Design rationale:** Infrastructure is the **dirty layer**. All I/O
lives here. By implementing Repository ABCs from the Domain layer,
Infrastructure code is interchangeable --- swap PostgreSQL for
CockroachDB by writing a new repository implementation, not by touching
the domain.

### 6.5 Layer 1 --- Workers

**What it contains:** - Celery task definitions (`@app.task`) or ARQ
coroutines - Analysis pipeline chains (`analyze_url_chain`,
`analyze_file_chain`) - AI Orchestrator (`ReasoningOrchestrator`) ---
calls AI provider with structured prompts - Enrichment tasks ---
parallel fan-out to threat intel APIs - Result aggregation and `Verdict`
persistence

**What it must NOT contain:** - HTTP request handling - User
authentication logic

**Design rationale:** Workers are the **execution engine**. They consume
tasks from the queue, import Domain and Infrastructure layers directly
(they share the same Python process/image), and write results back to
PostgreSQL. They are stateless and horizontally scalable.

------------------------------------------------------------------------

## 7. Module Boundaries & Dependency Rules

### 7.1 Module Map

    sentinel/
    ├── modules/
    │   ├── auth/            # User identity, JWT issuance, token validation
    │   ├── assets/          # Asset submission, metadata, file upload
    │   ├── analysis/        # Job lifecycle, pipeline orchestration
    │   ├── verdicts/        # Verdict storage, retrieval, aggregation
    │   ├── reports/         # Composite report generation
    │   └── enrichment/      # Threat intel API integrations
    ├── shared/
    │   ├── domain/          # Base entity, value object, repository ABC classes
    │   ├── events/          # Domain event definitions
    │   ├── errors/          # Sentinel exception hierarchy
    │   └── config/          # Settings (Pydantic BaseSettings)
    ├── infra/
    │   ├── db/              # SQLAlchemy engine, session factory, Base model
    │   ├── storage/         # Object storage adapter
    │   ├── queue/           # Broker adapter (Redis/RabbitMQ)
    │   └── ai/              # AI provider abstraction
    └── workers/
        ├── tasks/           # Celery task registrations
        ├── chains/          # Multi-step analysis chains
        └── orchestrator/    # AI reasoning orchestration

### 7.2 Import Dependency Rules (enforced by CI)

    # .importlinter configuration (conceptual)

    [importlinter:contract:no-upward-imports]
    type = layers
    layers =
        sentinel.modules.*.presentation
        sentinel.modules.*.application
        sentinel.modules.*.domain
        sentinel.infra
        sentinel.shared

    [importlinter:contract:no-cross-module-domain-imports]
    type = independence
    modules =
        sentinel.modules.auth
        sentinel.modules.assets
        sentinel.modules.analysis
        sentinel.modules.verdicts
        sentinel.modules.reports
    # Modules communicate only via shared events and application service calls
    # Never: assets.domain.models imports verdicts.domain.models

### 7.3 Inter-Module Communication Patterns

  ----------------------------------------------------------------------------------------------------------
  Pattern                 When to Use             Example
  ----------------------- ----------------------- ----------------------------------------------------------
  **Direct service call** Synchronous reads       `VerdictService.get_by_asset_id(asset_id)`
                          within request          
                          lifecycle               

  **Domain Event**        Notify other modules of `AssetSubmitted` → triggers
                          a state change          `analysis.application.handle_asset_submitted`

  **Queue Task**          Deferred or             `analysis.workers.tasks.run_full_analysis.delay(job_id)`
                          long-running work       

  **Shared repository**   Cross-cutting queries   `ReportRepository.get_with_verdicts(report_id)`
                          (reports module)        
  ----------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

## 8. Data Architecture

### 8.1 Why PostgreSQL

  -----------------------------------------------------------------------
  Requirement       PostgreSQL        Alternative       Decision
  ----------------- ----------------- ----------------- -----------------
  ACID transactions Full ACID,        MongoDB:          ✅ PostgreSQL
                    serializable      document-level    
                    isolation         only              

  JSON storage (AI  Native JSONB with Elasticsearch:    ✅ PostgreSQL
  outputs)          GIN index         overkill          JSONB

  Full-text search  `tsvector` + GIN  Solr/ES: separate ✅ PostgreSQL FTS
  (verdicts)        index             service           

  Relational        Foreign keys,     DynamoDB: no FKs  ✅ PostgreSQL
  integrity         CHECK constraints                   

  Async Python      `asyncpg` driver, MySQL: asyncmy    ✅ PostgreSQL
  support           full async/await  less mature       

  Array columns     Native `ARRAY`    JSON workaround   ✅ PostgreSQL
  (tags, IOCs)      type              in others         
  -----------------------------------------------------------------------

PostgreSQL is not the default choice by habit --- it is the correct
choice because Sentinel's data model is inherently relational (Users →
Assets → AnalysisJobs → Verdicts → Reports), requires ACID guarantees
for verdict integrity, and benefits from JSONB for semi-structured AI
reasoning payloads.

### 8.2 Core Entity-Relationship Model

    ┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
    │    users     │       │     assets       │       │  analysis_jobs   │
    ├──────────────┤       ├──────────────────┤       ├──────────────────┤
    │ id (UUID PK) │──────►│ id (UUID PK)     │──────►│ id (UUID PK)     │
    │ email        │       │ user_id (FK)     │       │ asset_id (FK)    │
    │ password_hash│       │ asset_type       │       │ status           │
    │ role         │       │ raw_value        │       │ started_at       │
    │ created_at   │       │ storage_key      │       │ completed_at     │
    │ is_active    │       │ metadata (JSONB) │       │ error_message    │
    └──────────────┘       │ created_at       │       └────────┬─────────┘
                           └──────────────────┘                │
                                                               │
                           ┌──────────────────┐       ┌────────▼─────────┐
                           │    reports       │       │    verdicts      │
                           ├──────────────────┤       ├──────────────────┤
                           │ id (UUID PK)     │       │ id (UUID PK)     │
                           │ user_id (FK)     │       │ job_id (FK)      │
                           │ title            │       │ threat_score     │
                           │ asset_ids (ARR)  │       │ confidence       │
                           │ summary (TEXT)   │       │ severity         │
                           │ created_at       │       │ reasoning (JSONB)│
                           └──────────────────┘       │ iocs (JSONB)     │
                                                      │ created_at       │
                                                      └──────────────────┘

### 8.3 Indexing Strategy

``` sql
-- Hot query: user's asset list (paginated, sorted by recency)
CREATE INDEX idx_assets_user_created ON assets (user_id, created_at DESC);

-- Hot query: job status lookup by asset
CREATE INDEX idx_jobs_asset_status ON analysis_jobs (asset_id, status);

-- Hot query: verdict by job (1:1 most common)
CREATE UNIQUE INDEX idx_verdicts_job ON verdicts (job_id);

-- Full-text search on verdict reasoning
CREATE INDEX idx_verdicts_fts ON verdicts USING GIN (to_tsvector('english', reasoning->>'summary'));

-- JSONB field access on asset metadata
CREATE INDEX idx_assets_metadata ON assets USING GIN (metadata);
```

### 8.4 Connection Pooling

    Application ──► PgBouncer (transaction mode, pool_size=20) ──► PostgreSQL
    Workers     ──► PgBouncer (session mode, pool_size=10)     ──► PostgreSQL

SQLAlchemy's async engine uses `asyncpg` with an internal pool of
`min=2, max=10` per process. PgBouncer sits in front of PostgreSQL to
prevent connection exhaustion under concurrent worker load.

------------------------------------------------------------------------

## 9. Asynchronous Processing Pipeline

### 9.1 Why Async Analysis

Analysis of a digital asset involves: - Fetching data from 3--5 external
threat intelligence APIs (each: 200ms--5s) - Running AI inference for
reasoning synthesis (1--15s depending on model) - Writing structured
results to the database

Performing this synchronously in an HTTP request would: 1. Hold the
connection open for 10--30 seconds 2. Risk timeout at load balancer
(typically 30--60s) 3. Make the API server non-responsive during
analysis under load

**Solution:** The HTTP handler returns immediately with `202 Accepted`
and a `job_id`. The full analysis runs in a background worker. Clients
poll `GET /api/v1/jobs/{job_id}` or use webhooks for completion
notification.

### 9.2 Pipeline Stages

    Client POST /assets/{id}/analyze
               │
               ▼
       [API Server]
       SubmitAnalysisUseCase
       ─────────────────────
       1. Validate asset exists + belongs to user
       2. Create AnalysisJob (status=PENDING) in DB
       3. Publish AnalysisRequestedEvent to queue
       4. Return 202 { job_id, status: "PENDING" }
               │
               │ (queue message consumed by worker)
               ▼
       [Worker: Stage 1 — Enrichment Fan-out]
       ─────────────────────────────────────
       Parallel HTTP calls (asyncio.gather):
       ├── VirusTotalEnricher.fetch(asset)
       ├── ShodanEnricher.fetch(asset)        [if IP/domain]
       ├── URLScanEnricher.fetch(asset)       [if URL]
       └── WhoisEnricher.fetch(asset)         [if domain]
               │
               ▼
       [Worker: Stage 2 — Feature Extraction]
       ─────────────────────────────────────
       - Normalize enrichment payloads
       - Extract Indicators of Compromise (IOCs)
       - Compute preliminary risk signals
               │
               ▼
       [Worker: Stage 3 — AI Reasoning]
       ─────────────────────────────────
       ReasoningOrchestrator
       - Construct structured prompt with enrichment context
       - Call AI Provider (OpenAI GPT-4o / Anthropic Claude)
       - Parse structured JSON response
       - Validate against VerdictSchema
               │
               ▼
       [Worker: Stage 4 — Verdict Persistence]
       ────────────────────────────────────────
       - Write Verdict entity to PostgreSQL
       - Update AnalysisJob status=COMPLETED
       - Publish VerdictReadyEvent (for webhooks/notifications)
               │
               ▼
       Client GET /jobs/{job_id} → { status: "COMPLETED", verdict_id: "..." }
       Client GET /verdicts/{id} → Full verdict with reasoning

### 9.3 Broker Selection

  -----------------------------------------------------------------------
  Broker            Strengths         Weaknesses        Decision
  ----------------- ----------------- ----------------- -----------------
  **Redis (via      Simple ops,       No message        ✅ Selected for
  Celery/ARQ)**     already a cache,  durability by     v1
                    fast              default, limited  
                                      routing           

  **RabbitMQ**      Durable queues,   Separate service, 🔄 Migration
                    dead-letter       AMQP complexity   target for v2
                    exchange, routing                   

  **Kafka**         Infinite          Overkill,         ❌ Eliminated
                    retention, log    ZooKeeper/KRaft   
                    compaction, event ops complexity    
                    replay                              

  **AWS SQS**       Managed, durable, AWS lock-in, no   ❌ Eliminated
                    at-least-once     local dev         
                    delivery          equivalent        
  -----------------------------------------------------------------------

**Redis** is selected because it collapses the cache and broker into one
service (reducing ops surface), Celery and ARQ both support it natively,
and Sentinel's analysis volume at v1 does not require durable message
replay.

**RabbitMQ migration trigger:** When message durability, dead-letter
queues for failed analysis retries, or topic routing between multiple
worker pools become explicit requirements.

### 9.4 Retry & Failure Policy

``` python
@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,          # 60s base
    retry_backoff=True,              # Exponential: 60s, 120s, 240s
    retry_backoff_max=600,           # Cap at 10 minutes
    acks_late=True,                  # Don't ack until task completes
    reject_on_worker_lost=True,      # Re-queue on hard worker crash
)
def run_full_analysis(self, job_id: str) -> None:
    ...
```

Failed jobs after max retries transition to `FAILED` status and write
the exception traceback to `analysis_jobs.error_message`. An alerting
rule fires when `FAILED` job rate exceeds 5% in a 5-minute window.

------------------------------------------------------------------------

## 10. AI Orchestration Layer

### 10.1 Architecture

The AI layer is a first-class architectural concern, not an
afterthought. It is designed for: - **Determinism:** Structured JSON
output via `response_format={"type": "json_object"}` or tool-calling -
**Auditability:** Full prompt and raw response stored in
`verdicts.reasoning` (JSONB) - **Replaceability:** `AIProvider` ABC
allows swapping OpenAI for Anthropic, a local Ollama instance, or a
fine-tuned model without touching the orchestrator

### 10.2 Prompt Architecture

    System Prompt (static, versioned)
    │
    ├── Role definition: "You are a digital security analyst..."
    ├── Output schema (JSON): { threat_score, confidence, severity, summary, iocs, reasoning_steps }
    ├── Evaluation criteria: reproducibility, evidence-based reasoning, calibrated uncertainty
    └── Constraint: "Never fabricate threat indicators. If uncertain, express it in confidence score."

    User Prompt (dynamic, constructed per analysis)
    │
    ├── Asset context: { type, value, submission_timestamp }
    ├── Enrichment data: { virustotal_result, shodan_result, urlscan_result }
    ├── Historical context (if available): { previous_verdicts_for_domain }
    └── Task: "Synthesize the above data into a structured security verdict."

### 10.3 Output Schema (enforced via Pydantic)

``` python
class AIVerdictOutput(BaseModel):
    threat_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    summary: str = Field(..., max_length=1000)
    iocs: list[IndicatorOfCompromise]
    reasoning_steps: list[str] = Field(..., min_length=1)
    data_gaps: list[str]  # What data was missing/unavailable
    model_version: str    # Which model produced this output
```

### 10.4 Provider Abstraction

``` python
class AIProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[BaseModel],
    ) -> BaseModel:
        ...

class OpenAIProvider(AIProvider):
    async def complete(self, ...) -> BaseModel:
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[{"role": "system", ...}, {"role": "user", ...}],
        )
        return output_schema.model_validate_json(response.choices[0].message.content)
```

------------------------------------------------------------------------

## 11. Authentication & Authorization

### 11.1 Why JWT

  -----------------------------------------------------------------------
  Mechanism         Strengths         Weaknesses        Decision
  ----------------- ----------------- ----------------- -----------------
  **JWT             No session store, Cannot revoke     ✅ Selected
  (stateless)**     horizontally      individual tokens 
                    scalable,         before expiry     
                    self-contained                      
                    claims                              

  **Opaque tokens + Instant           Session store     ❌ Eliminated
  DB session**      revocation, full  becomes a         
                    control           bottleneck, extra 
                                      DB hit per        
                                      request           

  **OAuth2          Delegates auth    Adds third-party  🔄 v2
  (external IdP)**  entirely, best    dependency,       consideration
                    for multi-tenant  complexity for v1 
                    SaaS              solo project      
  -----------------------------------------------------------------------

**JWT** is correct for Sentinel v1 because: 1. The API is stateless by
design --- workers and API servers share no session state 2. Token
lifetime is short (15 minutes access + 7-day refresh) --- the revocation
window is acceptable 3. Scaling API servers horizontally requires no
shared session infrastructure

### 11.2 Token Architecture

    Access Token (JWT, RS256)
    ├── sub: user_id (UUID)
    ├── email: user@example.com
    ├── role: "user" | "analyst" | "admin"
    ├── iat: issued_at (Unix timestamp)
    ├── exp: iat + 900 (15 minutes)
    └── jti: unique token ID (for eventual revocation blocklist)

    Refresh Token (opaque, stored in DB)
    ├── Stored in: users_refresh_tokens table
    ├── Lifetime: 7 days
    ├── Rotation: each use issues a new refresh token (refresh token rotation)
    └── Invalidation: logout, password change, admin action

### 11.3 Authorization Model

Sentinel uses **Role-Based Access Control (RBAC)** with three roles:

  -----------------------------------------------------------------------
  Role                                Permissions
  ----------------------------------- -----------------------------------
  `user`                              Submit assets, view own verdicts,
                                      create own reports

  `analyst`                           All user permissions + view all
                                      verdicts, trigger re-analysis

  `admin`                             All analyst permissions + manage
                                      users, view audit logs, configure
                                      system
  -----------------------------------------------------------------------

Resource ownership is enforced at the application service layer:

``` python
# Every service method validates ownership before proceeding
async def get_verdict(self, verdict_id: UUID, current_user: User) -> Verdict:
    verdict = await self.verdict_repo.get(verdict_id)
    if verdict.job.asset.user_id != current_user.id and current_user.role != "admin":
        raise ForbiddenError("Access denied to this verdict")
    return verdict
```

------------------------------------------------------------------------

## 12. API Design Contract

### 12.1 Design Principles

1.  **Resource-oriented** --- URLs identify resources, HTTP methods
    express intent
2.  **Versioned from day one** --- all routes prefixed `/api/v1/`
3.  **Consistent envelope** --- all responses use a standard shape
4.  **Pagination by default** --- all list endpoints return paginated,
    cursor-based results
5.  **Problem Details (RFC 9457)** --- all errors return structured
    `application/problem+json`

### 12.2 Response Envelope

``` json
// Success (single resource)
{
  "data": { ... },
  "meta": { "request_id": "req_01J..." }
}

// Success (collection)
{
  "data": [ ... ],
  "meta": {
    "request_id": "req_01J...",
    "pagination": {
      "cursor": "eyJpZCI6IjEyMyJ9",
      "has_next": true,
      "count": 25
    }
  }
}

// Error (RFC 9457)
{
  "type": "https://sentinel.dev/errors/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "The 'url' field must be a valid HTTP or HTTPS URL.",
  "instance": "/api/v1/assets",
  "request_id": "req_01J..."
}
```

### 12.3 Core Endpoint Map

  --------------------------------------------------------------------------------------
  Method            Path                             Description       Auth
  ----------------- -------------------------------- ----------------- -----------------
  `POST`            `/api/v1/auth/register`          Create user       None
                                                     account           

  `POST`            `/api/v1/auth/login`             Issue JWT tokens  None

  `POST`            `/api/v1/auth/refresh`           Rotate refresh    Refresh token
                                                     token             

  `DELETE`          `/api/v1/auth/logout`            Revoke refresh    Bearer JWT
                                                     token             

  `GET`             `/api/v1/users/me`               Get current user  Bearer JWT
                                                     profile           

  `POST`            `/api/v1/assets`                 Submit asset for  Bearer JWT
                                                     analysis          

  `GET`             `/api/v1/assets`                 List user's       Bearer JWT
                                                     assets            

  `GET`             `/api/v1/assets/{id}`            Get asset detail  Bearer JWT

  `POST`            `/api/v1/assets/{id}/analyze`    Trigger analysis  Bearer JWT

  `GET`             `/api/v1/jobs/{id}`              Get analysis job  Bearer JWT
                                                     status            

  `GET`             `/api/v1/verdicts/{id}`          Get full verdict  Bearer JWT

  `GET`             `/api/v1/assets/{id}/verdicts`   List verdicts for Bearer JWT
                                                     asset             

  `POST`            `/api/v1/reports`                Create composite  Bearer JWT
                                                     report            

  `GET`             `/api/v1/reports`                List user's       Bearer JWT
                                                     reports           

  `GET`             `/api/v1/reports/{id}`           Get full report   Bearer JWT

  `GET`             `/api/v1/health`                 Health check      None

  `GET`             `/api/v1/health/ready`           Readiness check   None
                                                     (DB + queue)      
  --------------------------------------------------------------------------------------

### 12.4 Why REST over GraphQL

GraphQL excels at client-driven graph traversal where different clients
need different shapes of the same data (e.g., mobile vs. desktop).
Sentinel's API serves a well-defined set of resources with predictable
access patterns. REST with thoughtful resource design is simpler to
implement, cache, document (OpenAPI auto-generated), and reason about
for both the implementer and consumers.

------------------------------------------------------------------------

## 13. Object Storage Strategy

### 13.1 What Gets Stored

  -------------------------------------------------------------------------------------------
  Artifact                Path Pattern                                Retention
  ----------------------- ------------------------------------------- -----------------------
  User-uploaded files     `uploads/{user_id}/{asset_id}/{filename}`   Until asset deleted
  (malware samples, etc.)                                             

  Raw enrichment API      `enrichment/{job_id}/{source}.json`         90 days
  responses                                                           

  Analysis reports (PDF   `reports/{report_id}/report.pdf`            1 year
  export)                                                             

  Prompt/response audit   `audit/{job_id}/ai_exchange.json`           1 year
  logs                                                                
  -------------------------------------------------------------------------------------------

### 13.2 Provider Abstraction

All object storage calls go through a `StorageAdapter` ABC:

``` python
class StorageAdapter(ABC):
    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str) -> str: ...

    @abstractmethod
    async def download(self, key: str) -> bytes: ...

    @abstractmethod
    async def generate_presigned_url(self, key: str, expires_in: int) -> str: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...
```

Implementations: `S3StorageAdapter`, `MinIOStorageAdapter`,
`R2StorageAdapter`. The active adapter is selected via
`STORAGE_PROVIDER` environment variable.

### 13.3 File Upload Flow

    Client ──POST /assets (multipart/form-data)──► API Server
                                                        │
                                                  Validate file
                                                (type, size ≤ 100MB)
                                                        │
                                                Upload to Object Store
                                                (streaming, no temp disk)
                                                        │
                                                Store storage_key in DB
                                                        │
                                                Return { asset_id, status }

Files are **never stored on the API server's local disk** --- they
stream directly to object storage. This ensures stateless API servers
and prevents disk exhaustion under concurrent upload load.

------------------------------------------------------------------------

## 14. Observability & Operational Readiness

### 14.1 Three Pillars

**Logs (Structured JSON)**

``` json
{
  "timestamp": "2025-01-15T14:23:01.452Z",
  "level": "INFO",
  "logger": "sentinel.analysis.worker",
  "message": "Analysis job completed",
  "job_id": "job_01J...",
  "asset_id": "ast_01J...",
  "duration_ms": 4521,
  "threat_score": 0.87,
  "model": "gpt-4o-2024-11-20",
  "trace_id": "trc_01J..."
}
```

Every log line includes: `trace_id` (propagated from HTTP request
headers), `job_id`, `user_id`, and timing information. Logs are written
to stdout and collected by the container runtime.

**Metrics (Prometheus)**

  Metric                                     Type        Labels
  ------------------------------------------ ----------- ---------------------------
  `sentinel_http_requests_total`             Counter     method, path, status_code
  `sentinel_http_request_duration_seconds`   Histogram   method, path
  `sentinel_analysis_jobs_total`             Counter     status (completed/failed)
  `sentinel_analysis_duration_seconds`       Histogram   asset_type
  `sentinel_ai_tokens_used_total`            Counter     provider, model
  `sentinel_queue_depth`                     Gauge       queue_name
  `sentinel_db_pool_connections`             Gauge       state (active/idle)

**Traces (OpenTelemetry)**

All HTTP requests and worker tasks are instrumented with OpenTelemetry
spans. The `trace_id` is propagated from the API server into the queue
message payload so that a single analysis request can be traced
end-to-end across process boundaries.

### 14.2 Health Check Endpoints

    GET /api/v1/health        → { "status": "ok" }               (liveness)
    GET /api/v1/health/ready  → { "status": "ok",                (readiness)
                                   "db": "ok",
                                   "queue": "ok",
                                   "storage": "ok" }

The readiness check is used by the container orchestrator to decide
whether to route traffic to a given instance. It performs lightweight
probes (a `SELECT 1` on the DB, a PING on the queue broker) with a
2-second timeout.

------------------------------------------------------------------------

## 15. Security Architecture

### 15.1 Defense-in-Depth

    ┌──────────────────────────────────────────────────────────────────┐
    │  LAYER 1: Network                                                 │
    │  TLS 1.3 termination at load balancer/reverse proxy (Nginx)      │
    │  No direct database or queue exposure to public internet         │
    ├──────────────────────────────────────────────────────────────────┤
    │  LAYER 2: Application Ingress                                     │
    │  Rate limiting: 100 req/min per IP (slowapi / nginx limit_req)   │
    │  Request size limit: 100MB (file uploads), 1MB (JSON bodies)     │
    │  CORS: explicit allowlist, no wildcard in production             │
    ├──────────────────────────────────────────────────────────────────┤
    │  LAYER 3: Authentication                                          │
    │  JWT RS256 (asymmetric — public key distributable)               │
    │  Refresh token rotation + server-side invalidation               │
    │  bcrypt (cost=12) for password hashing                           │
    ├──────────────────────────────────────────────────────────────────┤
    │  LAYER 4: Authorization                                           │
    │  RBAC enforced at Application Service layer (not router layer)   │
    │  Resource ownership checked before every data access             │
    ├──────────────────────────────────────────────────────────────────┤
    │  LAYER 5: Input Validation                                        │
    │  Pydantic V2 validates all inputs at system boundary             │
    │  File type validation: magic bytes (python-magic), not extension │
    │  SQL injection: SQLAlchemy ORM parameterized queries only        │
    ├──────────────────────────────────────────────────────────────────┤
    │  LAYER 6: Secrets Management                                      │
    │  Zero secrets in source code or Docker images                    │
    │  All secrets via environment variables (production: Vault/SSM)   │
    │  Separate DB credentials for API server vs. workers              │
    └──────────────────────────────────────────────────────────────────┘

### 15.2 File Upload Security

Uploaded files may be malicious --- this is a core use case. Security
measures:

1.  **File type validation:** Magic byte inspection via `python-magic`,
    not file extension
2.  **Sandboxed storage:** Uploaded files are stored in object storage,
    never executed
3.  **Virus scan hook:** `ClamAV` integration point built into the
    analysis pipeline (Stage 0)
4.  **Path traversal prevention:** Storage keys are constructed
    programmatically from `UUID` components, never from user-provided
    filenames
5.  **Content-Disposition on download:** Files served with
    `Content-Disposition: attachment` to prevent browser execution

------------------------------------------------------------------------

## 16. Deployment Architecture

### 16.1 Local Development

``` yaml
# docker-compose.yml (development)
services:
  api:
    build: .
    command: uvicorn sentinel.main:app --reload --host 0.0.0.0 --port 8000
    volumes: ["./:/app"]       # Live reload
    env_file: .env.local

  worker:
    build: .
    command: celery -A sentinel.workers.celery_app worker --loglevel=info
    env_file: .env.local

  postgres:
    image: postgres:16.3
    environment: { POSTGRES_DB: sentinel, POSTGRES_PASSWORD: dev }

  redis:
    image: redis:7.2-alpine

  minio:
    image: minio/minio:RELEASE.2025-02-22T01-52-34Z
    command: server /data --console-address ":9001"
```

### 16.2 Production Topology

                            ┌─────────────────────┐
                            │   Load Balancer      │
                            │  (Nginx / Caddy)     │
                            │  TLS termination     │
                            └──────────┬──────────┘
                                       │
                   ┌───────────────────┼───────────────────┐
                   │                   │                   │
            ┌──────▼──────┐    ┌───────▼─────┐    ┌───────▼─────┐
            │  API Pod 1  │    │  API Pod 2  │    │  API Pod N  │
            │ (Uvicorn)   │    │ (Uvicorn)   │    │ (Uvicorn)   │
            └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
                   └───────────────────┼───────────────────┘
                                       │
                     ┌─────────────────┼─────────────────┐
                     │                 │                 │
              ┌──────▼──────┐  ┌───────▼─────┐  ┌───────▼─────┐
              │ Worker Pod 1│  │Worker Pod 2 │  │Worker Pod N │
              │  (Celery)   │  │  (Celery)   │  │  (Celery)   │
              └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
                     └─────────────────┼─────────────────┘
                                       │
               ┌───────────────────────┼──────────────────────┐
               │                       │                      │
        ┌──────▼──────┐       ┌────────▼────────┐    ┌───────▼────────┐
        │ PostgreSQL  │       │  Redis (Broker) │    │  Object Store  │
        │ (Primary +  │       │  + Cache        │    │  (S3/R2/MinIO) │
        │  Replica)   │       └─────────────────┘    └────────────────┘
        └─────────────┘

### 16.3 Container Design

-   **Single backend container image**, multiple entry points via `CMD` override
    --- no separate Dockerfiles for API vs. workers
-   **Multi-stage build:** `builder` stage installs dependencies;
    `runtime` stage copies only what's needed (no build tools in
    production image)
-   **Non-root user:** Container runs as `uid=1000` --- no root process
    in production
-   **Read-only filesystem:** `/tmp` is the only writable directory in
    the container

------------------------------------------------------------------------

## 17. Decision Log (ADR Summary)

  -------------------------------------------------------------------------
  ID                Decision          Alternatives      Rationale
                                      Considered        
  ----------------- ----------------- ----------------- -------------------
  ADR-001           Modular Monolith  Microservices,    Right-sized for
                                      Serverless        solo dev;
                                                        extraction path
                                                        defined

  ADR-002           FastAPI           Django, Flask,    Async-native,
                                      Litestar          Pydantic V2
                                                        integration,
                                                        OpenAPI auto-gen

  ADR-003           PostgreSQL        MongoDB,          ACID, JSONB,
                                      DynamoDB, SQLite  relational
                                                        integrity, asyncpg

  ADR-004           SQLAlchemy Async  Tortoise ORM,     Mature,
                                      databases         full-featured,
                                                        async support,
                                                        Alembic migrations

  ADR-005           JWT (RS256)       Opaque tokens,    Stateless,
                                      OAuth2            horizontally
                                                        scalable,
                                                        self-contained
                                                        claims

  ADR-006           Redis (Celery)    RabbitMQ, Kafka,  Operational
                                      SQS               simplicity; doubles
                                                        as cache; Celery
                                                        support

  ADR-007           S3-compatible     Local filesystem, Stateless API
                    storage           NFS               servers;
                                                        provider-agnostic
                                                        adapter

  ADR-008           OpenAI GPT-4o     Anthropic Claude, Best JSON
                                      local LLM         structured output;
                                                        provider ABC allows
                                                        swap

  ADR-009           Pydantic V2       Marshmallow,      Native FastAPI
                                      attrs             integration; 5-10x
                                                        faster than V1

  ADR-010           Cursor pagination Offset pagination Stable under
                                                        concurrent inserts;
                                                        no "page drift"

  ADR-011           RFC 9457 error    Custom error      Interoperability
                    format            schema            standard; future
                                                        API consumer
                                                        tooling

  ADR-012           RS256 JWT signing HS256             Asymmetric: public
                                                        key shareable for
                                                        verification
                                                        without secret
                                                        exposure
  -------------------------------------------------------------------------

------------------------------------------------------------------------

## 18. Known Trade-offs & Future Migration Paths

### 18.1 Current Trade-offs

  -----------------------------------------------------------------------
  Trade-off               Impact                  Accepted Because
  ----------------------- ----------------------- -----------------------
  Polling for job         Client must poll        Simpler server
  completion (no          `/jobs/{id}`            implementation; SSE can
  WebSocket)                                      be added in v1.1

  No distributed tracing  Traces logged but not   Jaeger/Tempo added when
  store in v1             queryable in UI         team size justifies ops
                                                  overhead

  Redis without AOF       Queue messages lost on  Acceptable: failed jobs
  persistence             Redis restart           retry; RabbitMQ
                                                  migration documented

  Single PostgreSQL       No read replicas        Sufficient at v1
  primary                                         write/read volume; read
                                                  replica added at 1k DAU

  Celery beat for         Single point for        Sufficient; temporal.io
  scheduled tasks         scheduling              considered for v2
                                                  workflow orchestration
  -----------------------------------------------------------------------

### 18.2 Migration Path to Microservices (If Needed)

When extraction criteria in §5.3 are met, the following
module-to-service mapping applies:

    sentinel.modules.auth       →  auth-service       (Shared nothing; issues JWTs)
    sentinel.modules.assets     →  asset-service      (File management, metadata)
    sentinel.modules.analysis   →  analysis-service   (Job orchestration)
    sentinel.modules.verdicts   →  verdict-service    (Read-heavy; add Redis cache)
    sentinel.modules.enrichment →  enrichment-service (Isolated external API calls)
    sentinel.workers            →  worker-service     (Already process-isolated)

The Repository pattern and Domain Event system mean these extractions
are **seam-guided** --- not big-bang rewrites. Each module already
communicates via well-typed interfaces.

### 18.3 Scalability Ceiling Estimates

  -----------------------------------------------------------------------
  Bottleneck              Estimated Ceiling       Resolution
  ----------------------- ----------------------- -----------------------
  API server (single pod, \~500 RPS               Horizontal pod scaling
  Uvicorn 4 workers)                              

  Worker pool (4 Celery   \~20 concurrent         Add worker pods
  workers)                analyses                

  PostgreSQL (single      \~5,000 connections/sec PgBouncer + read
  primary)                                        replica

  Redis broker            \~50,000 messages/sec   Cluster mode or
                                                  RabbitMQ migration

  OpenAI API              Model-specific rate     Multi-provider load
                          limits                  balancing
  -----------------------------------------------------------------------

Sentinel's design ensures that scaling any one of these bottlenecks is
an **operational change** (add pods, promote read replica), not a **code
change**.

------------------------------------------------------------------------

## Appendix A: Technology Stack Summary

  --------------------------------------------------------------------------
  Component          Technology        Version           Justification
  ------------------ ----------------- ----------------- -------------------
  Language           Python            3.12+             Async support, AI
                                                         ecosystem, type
                                                         hints

  API Framework      FastAPI           0.115+            Async, Pydantic V2,
                                                         OpenAPI

  ORM                SQLAlchemy        2.x (async)       Mature, Alembic,
                                                         full async

  Database           PostgreSQL        16                ACID, JSONB,
                                                         asyncpg

  DB Driver          asyncpg           latest            Fastest async
                                                         PostgreSQL driver

  Migrations         Alembic           latest            SQLAlchemy-native
                                                         migration tool

  Task Queue         Celery + Redis    Celery 5.x        Proven, flexible,
                                                         Redis broker

  Object Storage     boto3 / minio     latest            S3-compatible
                                                         adapter pattern

  Auth               python-jose +     latest            JWT RS256 + bcrypt
                     passlib                             

  Validation         Pydantic V2       2.x               Fast, type-safe,
                                                         FastAPI native

  HTTP Client        httpx             latest            Async, connection
                                                         pooling

  Testing            pytest +          latest            Async test support
                     pytest-asyncio                      

  Containerization   Docker + Compose  latest            Dev/prod parity

  Monitoring         Prometheus +      latest            Metrics +
                     structlog                           structured logs

  Tracing            OpenTelemetry     latest            Vendor-neutral
                                                         trace propagation
  --------------------------------------------------------------------------

------------------------------------------------------------------------

*This document is the authoritative architectural reference for Sentinel
v1. All implementation decisions not explicitly addressed here should be
resolved by applying the principles in §2 and escalating to this
document's owner for any decision that crosses module or layer
boundaries.*

------------------------------------------------------------------------

## Appendix B: Requirements Traceability

  -----------------------------------------------------------------------
  Requirement                         Architectural Decision
  ----------------------------------- -----------------------------------
  Fast upload acknowledgement         Asynchronous queue with background
                                      workers

  Horizontal scalability              Stateless API servers +
                                      independently scalable workers

  Secure asset storage                Object storage abstraction

  AI provider independence            AIProvider abstraction

  Maintainability                     Modular Monolith + layered
                                      architecture
  -----------------------------------------------------------------------
