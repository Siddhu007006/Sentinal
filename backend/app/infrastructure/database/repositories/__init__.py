"""
Infrastructure database repositories layer.

Concrete repository implementations using SQLAlchemy ORM for PostgreSQL.

This layer implements the repository interfaces defined in the Domain layer,
translating domain operations (create, read, update, delete) into SQLAlchemy
ORM calls and database queries.

Modules:
    Phase A (E3.T7):
        - exceptions: Database exception mapping (SQLAlchemy -> domain exceptions)
        - base: Base PostgreSQL repository implementation (CRUD + helpers)
        - user: User repository implementation
        - upload: Upload repository implementation
        - digital_asset: DigitalAsset repository implementation
        - analysis: Analysis repository implementation

    Phase B (E3.T11):
        - report: Report repository implementation (soft-delete)
        - audit_log: AuditLog repository implementation (immutable)
        - refresh_token: RefreshToken repository implementation (session management)

Database exceptions are mapped to domain exceptions via map_db_exception()
so that the Application layer never sees SQLAlchemy-specific errors.

Transaction lifecycle is managed by the FastAPI dependency system:
- Session created at request start
- All repository operations execute within the transaction
- Commit on success, rollback on exception (handled by dependency)

Lazy loading strategies from E3.T5/E3.T6 are implemented to prevent N+1
queries. By default, relationships are loaded via selectin (separate
SELECT IN query) for efficiency at scale.

Traces to: E3.T7 Specification § Requirement R2 (PostgreSQL Implementations)
Traces to: E3.T11 Specification § Requirement R1-R9 (Phase B Implementations)
Traces to: 03-Architecture §3 (Infrastructure layer)
"""

__all__ = [
    "PostgreSQLAuditLogRepository",
    "PostgreSQLRefreshTokenRepository",
    "map_db_exception",
]

from app.infrastructure.database.repositories.audit_log import (
    PostgreSQLAuditLogRepository,
)
from app.infrastructure.database.repositories.exceptions import map_db_exception
from app.infrastructure.database.repositories.refresh_token import (
    PostgreSQLRefreshTokenRepository,
)
