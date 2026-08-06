"""
Domain layer repository interfaces.

Abstract repository interfaces for CRUD and domain-specific queries.

This layer defines the contract that all repository implementations must follow.
These interfaces have no SQLAlchemy imports and are pure Python, allowing the
Domain and Application layers to depend on abstractions rather than concrete
implementations.

Modules:
    Phase A (E3.T7):
        - base: BaseRepository ABC (CRUD interface for all entities)
        - user: UserRepository ABC (user-specific queries)
        - upload: UploadRepository ABC (upload-specific queries)
        - digital_asset: DigitalAssetRepository ABC (asset-specific queries)
        - analysis: AnalysisRepository ABC (analysis-specific queries)

    Phase B (E3.T10-E3.T11):
        - report: ReportRepository ABC (report-specific queries, soft-delete)
        - audit_log: AuditLogRepository ABC (audit-specific queries, immutable)
        - refresh_token: RefreshTokenRepository ABC (token lifecycle, immutable)

The Application layer depends on these interfaces. The Infrastructure layer
provides concrete implementations (PostgreSQL repositories).

Scope (E3.T7, E3.T10-E3.T11):
    - User: Soft-delete support, email lookup, active user listing
    - Upload: Immutable after creation, storage key lookup, status filtering
    - DigitalAsset: Soft-delete support, hash lookup, deduplication
    - Analysis: Job queue management, N+1 prevention, completion tracking
    - Report: Soft-delete support, asset listing, status filtering
    - AuditLog: Immutable, actor/resource/date-range queries
    - RefreshToken: Immutable (except revocation), token validation, session listing

Traces to: E3.T7 Specification § Requirement R1 (Domain Interfaces)
Traces to: E3.T10 Specification § Requirement R1 (Domain Interfaces - Phase B)
Traces to: 03-Architecture §4 (Domain layer)
"""

__all__ = [
    "AnalysisRepository",
    "AuditLogRepository",
    "BaseRepository",
    "DigitalAssetRepository",
    "RefreshTokenRepository",
    "ReportRepository",
    "UploadRepository",
    "UserRepository",
]

from app.domain.repositories.analysis import AnalysisRepository
from app.domain.repositories.audit_log import AuditLogRepository
from app.domain.repositories.base import BaseRepository
from app.domain.repositories.digital_asset import DigitalAssetRepository
from app.domain.repositories.refresh_token import RefreshTokenRepository
from app.domain.repositories.report import ReportRepository
from app.domain.repositories.upload import UploadRepository
from app.domain.repositories.user import UserRepository
