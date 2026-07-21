# Sentinel — Threat Intelligence & Digital Asset Analysis Platform

A comprehensive threat intelligence platform for analyzing, enriching, and managing digital assets with multi-vendor threat intelligence integration.

## Project Overview

**Sentinel** is built as a scalable, microservices-ready architecture with:
- RESTful API backend (Python/FastAPI)
- PostgreSQL database with comprehensive schema
- Real-time threat intelligence enrichment
- Multi-vendor OSINT integration
- Comprehensive audit logging and compliance tracking

## Epic 3: Database Foundation (Current Focus)

This epic implements the complete database schema and ORM layer for threat intelligence analysis:

| Task | Status | Description |
|---|---|---|
| **E3.T1** | ✅ Complete | User ORM model with authentication |
| **E3.T2** | ✅ Complete | Alembic migration framework setup |
| **E3.T3** | ✅ Complete | User table and FK constraints |
| **E3.T4** | ✅ Complete | Upload model and file handling |
| **E3.T5** | ✅ Complete | DigitalAsset ORM model and indexing |
| **E3.T6** | ✅ Complete | **Analysis ORM model** (20 fields, 8 indexes, full tests) |

## Key Features

### E3.T6 — Analysis ORM Model

The Analysis model represents threat intelligence analysis results:

- **20 ORM Fields** (18 explicit + 2 inherited from BaseModel)
- **5 Lifecycle States**: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
- **2 FK Relationships**: DigitalAsset and User with selectin lazy loading
- **5 CHECK Constraints**: Status validation, score ranges, severity levels
- **8 Database Indexes**: Query optimization for common access patterns
- **Idempotency Guarantee**: Partial unique index enforces single completed result per analyzer

### Analysis Fields

| Category | Fields |
|---|---|
| **Identifiers** | id (UUID), digital_asset_id (FK), requested_by (FK) |
| **Analyzer Info** | analyzer_key, analyzer_version, analyzer_slugs |
| **Lifecycle** | status, started_at, completed_at |
| **Results** | threat_score, confidence, severity |
| **Data** | reasoning_payload (JSONB), enrichment_data (JSONB) |
| **Retry** | retry_count, celery_task_id |
| **Errors** | error_message, error_code |
| **Timestamps** | created_at (inherited), updated_at (inherited) |

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Docker & Docker Compose (recommended)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Siddhu007006/sentinal.git
   cd sentinal
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Initialize database:**
   ```bash
   docker-compose up -d postgres
   cd backend
   alembic upgrade head
   ```

5. **Run tests:**
   ```bash
   pytest backend/tests/unit/test_analysis_model.py -v
   ```

## Architecture

### Database Schema

**Core Entities:**
- `users` — User accounts with roles (ADMIN, ANALYST, VIEWER)
- `digital_assets` — Domain names, IP addresses, URLs, file hashes, etc.
- `analyses` — Threat intelligence analysis results (E3.T6)
- `uploads` — File uploads for batch processing
- `audit_logs` — Comprehensive audit trail

### ORM Layer

Built with SQLAlchemy 2.0+:
- Declarative models with type hints
- Relationships with eager/lazy loading strategies
- Database constraints enforced at schema level
- Migrations managed via Alembic

### API Design

FastAPI-based REST API:
- Request/response validation (Pydantic)
- Role-based access control (RBAC)
- Comprehensive error handling
- API documentation (Swagger/OpenAPI)

## Testing Strategy

### Unit Tests (E3.T6)

**Coverage: 100% on analysis.py**

- ORM model instantiation and field validation
- Relationship navigation (digital_asset, user)
- Enum validation (AnalysisStatus)
- Server defaults and nullable constraints
- Repr and string representation

**Run:**
```bash
pytest backend/tests/unit/test_analysis_model.py -v --cov=app.models.analysis
```

### Integration Tests (E3.T6)

**Requires PostgreSQL with DATABASE_MIGRATION_URL configured**

- Migration upgrade/downgrade idempotence
- FK constraint enforcement (ON DELETE RESTRICT)
- CHECK constraint validation (status, scores, severity)
- Partial unique index (idempotency guarantee)
- Index usage and query performance

**Run:**
```bash
export DATABASE_MIGRATION_URL="postgresql://user:pass@localhost/sentinal_test"
pytest backend/tests/integration/test_analysis_*.py -v
```

## Quality Assurance

### Code Quality

- **Linting:** Ruff (0 issues)
- **Type Checking:** MyPy (0 errors)
- **Test Coverage:** 100% for E3.T6 ORM model

### Pre-Commit Checks

```bash
cd backend
ruff check app/models/analysis.py
mypy app/models/analysis.py
pytest backend/tests/unit/test_analysis_model.py
```

## Project Structure

```
sentinal/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── analysis.py         (E3.T6 — ORM model)
│   │   │   ├── digital_asset.py    (E3.T5)
│   │   │   ├── upload.py           (E3.T4)
│   │   │   └── user.py             (E3.T1)
│   │   └── ...
│   ├── migrations/
│   │   └── versions/
│   │       └── 20260721_1416_*.py  (E3.T6 migration)
│   ├── tests/
│   │   ├── unit/
│   │   │   └── test_analysis_model.py  (103 tests, 100% coverage)
│   │   └── integration/
│   │       ├── test_analysis_migration.py
│   │       ├── test_analysis_constraints.py
│   │       └── test_analysis_performance.py
│   ├── ALEMBIC_SETUP.md
│   ├── README.md
│   └── pyproject.toml
├── .kiro/
│   └── specs/
│       └── epic-3-database-foundation-analyses-t6/
│           ├── requirements.md
│           ├── design.md
│           └── tasks.md
├── .github/
│   ├── E3-T6-FINAL-AUDIT.md
│   ├── E3-T6-MIGRATION-REVIEW.md
│   └── workflows/
│       └── ci.yml
└── docs/
    ├── 00-Project-Context.md
    └── 22-Engineering-Backlog.md
```

## Documentation

- **Requirements:** `.kiro/specs/epic-3-database-foundation-analyses-t6/requirements.md`
- **Design:** `.kiro/specs/epic-3-database-foundation-analyses-t6/design.md`
- **Tasks:** `.kiro/specs/epic-3-database-foundation-analyses-t6/tasks.md`
- **Migration Review:** `.github/E3-T6-MIGRATION-REVIEW.md` (24 checkpoints)
- **Audit:** `.github/E3-T6-FINAL-AUDIT.md`

## Contributing

1. Create a feature branch from `main`
2. Implement changes with full test coverage
3. Ensure all tests pass and linting is clean
4. Create a pull request with detailed description
5. Code review and merge to main

## Next Steps

- **E3.T7:** Query layer and repository pattern
- **E3.T8:** API endpoints for analysis endpoints
- **E4:** Event-driven enrichment pipeline

## License

Proprietary — All rights reserved.

## Contact

**Maintainer:** Siddharth Reddy (Siddhu007006)

---

**Status:** E3.T6 Complete ✅ — Ready for production  
**Last Updated:** July 21, 2026
