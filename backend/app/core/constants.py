"""
Application-wide constants.

Contains immutable, framework-agnostic constant values derived from:
- Backend/openapi.yaml (the canonical API contract)
- Domain Model (02-Domain-Model.md)
- Product Requirements (01-Product-Requirements.md)

These are values that are true regardless of environment or deployment.
Configuration that changes per environment (JWT secrets, database URLs, etc.)
belongs in app/core/settings.py, NOT here.

See: 07-Backend-Development-Standards §3 (constants, no magic numbers).
See: 06-Repository-Structure §11 (shared constants live in app/core/constants.py).
See: backend/openapi.yaml (source of truth for API contract values).
"""

# ===========================================================================
# API
# Source: backend/openapi.yaml
# ===========================================================================

# API version (matches openapi.yaml servers path)
API_VERSION: str = "v1"

# API title and description
API_TITLE: str = "Sentinel"
API_DESCRIPTION: str = (
    "Digital Asset Trust Verification Platform. "
    "Evaluates the trustworthiness of digital assets — URLs, files, "
    "domains, IP addresses — through multi-layered analysis combining "
    "AI reasoning, conventional security scanning, and external "
    "threat intelligence."
)

# OpenAPI documentation URLs (relative to base)
OPENAPI_DOCS_URL: str = "/api/v1/docs"
OPENAPI_REDOC_URL: str = "/api/v1/redoc"
OPENAPI_OPENAPI_JSON_URL: str = "/api/v1/openapi.json"

# ===========================================================================
# HTTP & Requests
# Source: 08-Security-Architecture §7, 07-Backend-Development-Standards §10
# ===========================================================================

# Request ID header for correlation/tracing
REQUEST_ID_HEADER: str = "X-Request-ID"

# Default request timeout (seconds)
DEFAULT_REQUEST_TIMEOUT: int = 30

# ===========================================================================
# Pagination
# Source: 05-API-Specification
# ===========================================================================

# Default page size for list endpoints
DEFAULT_PAGE_SIZE: int = 20

# Maximum page size to prevent excessive queries
MAX_PAGE_SIZE: int = 100

# ===========================================================================
# File Upload
# Source: backend/openapi.yaml §8, 08-Security-Architecture §6
#
# NOTE: Numeric values here MUST match backend/openapi.yaml and
# UPLOAD_MAX_FILE_SIZE / UPLOAD_ALLOWED_MIME_TYPES in settings.py.
# These are documented here as reference constants only.
# ===========================================================================

# Maximum upload file size (100 MB, bytes)
# This is the same as UploadSettings.max_file_size default
MAX_UPLOAD_FILE_SIZE_BYTES: int = 104_857_600

# Default allowed MIME types (matches backend/openapi.yaml)
DEFAULT_ALLOWED_UPLOAD_MIME_TYPES: list[str] = [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "text/plain",
    "application/zip",
]

# ===========================================================================
# Authentication & Security
# Source: 08-Security-Architecture §4, 07-Backend-Development-Standards §11
#
# NOTE: Actual secrets (JWT_SECRET_KEY, etc.) are in settings.py from environment.
# These are only non-secret constants related to auth.
# ===========================================================================

# JWT token types
JWT_TOKEN_TYPE_ACCESS: str = "access"  # noqa: S105
JWT_TOKEN_TYPE_REFRESH: str = "refresh"  # noqa: S105

# HTTP Authorization header scheme
HTTP_BEARER_SCHEME: str = "Bearer"

# ===========================================================================
# Domain Enums & Status Values
# Source: 02-Domain-Model.md, backend/openapi.yaml
# ===========================================================================

# User roles (must match backend/openapi.yaml UserRole enum)
USER_ROLE_ADMIN: str = "admin"
USER_ROLE_ANALYST: str = "analyst"
USER_ROLE_VIEWER: str = "viewer"

# Upload statuses (must match backend/openapi.yaml UploadStatus enum)
UPLOAD_STATUS_PENDING: str = "pending"
UPLOAD_STATUS_PROCESSING: str = "processing"
UPLOAD_STATUS_COMPLETED: str = "completed"
UPLOAD_STATUS_FAILED: str = "failed"

# Analysis statuses (must match backend/openapi.yaml AnalysisStatus enum)
ANALYSIS_STATUS_QUEUED: str = "queued"
ANALYSIS_STATUS_RUNNING: str = "running"
ANALYSIS_STATUS_COMPLETED: str = "completed"
ANALYSIS_STATUS_FAILED: str = "failed"

# Analysis verdicts (must match backend/openapi.yaml AnalysisVerdict enum)
VERDICT_TRUSTED: str = "trusted"
VERDICT_SUSPICIOUS: str = "suspicious"
VERDICT_MALICIOUS: str = "malicious"
VERDICT_UNKNOWN: str = "unknown"

# ===========================================================================
# Error & Validation
# Source: 07-Backend-Development-Standards §9
# ===========================================================================

# Standard error codes for client responses
ERROR_CODE_VALIDATION_ERROR: str = "VALIDATION_ERROR"
ERROR_CODE_NOT_FOUND: str = "NOT_FOUND"
ERROR_CODE_UNAUTHORIZED: str = "UNAUTHORIZED"
ERROR_CODE_FORBIDDEN: str = "FORBIDDEN"
ERROR_CODE_CONFLICT: str = "CONFLICT"
ERROR_CODE_UNPROCESSABLE_ENTITY: str = "UNPROCESSABLE_ENTITY"
ERROR_CODE_INTERNAL_SERVER_ERROR: str = "INTERNAL_SERVER_ERROR"
ERROR_CODE_SERVICE_UNAVAILABLE: str = "SERVICE_UNAVAILABLE"

# ===========================================================================
# Logging & Observability
# Source: 07-Backend-Development-Standards §10, 10-Observability-Architecture
# ===========================================================================

# Structured log field names (common across all loggers)
LOG_FIELD_TIMESTAMP: str = "timestamp"
LOG_FIELD_LEVEL: str = "level"
LOG_FIELD_LOGGER: str = "logger"
LOG_FIELD_REQUEST_ID: str = "request_id"
LOG_FIELD_MESSAGE: str = "message"

# Environment names (must match EnvironmentType enum in settings.py)
ENVIRONMENT_DEVELOPMENT: str = "development"
ENVIRONMENT_STAGING: str = "staging"
ENVIRONMENT_PRODUCTION: str = "production"

# ===========================================================================
# Timing & Delays
# Source: Architecture documents, performance considerations
# ===========================================================================

# Database connection pool acquisition timeout (seconds)
DB_POOL_TIMEOUT_SECONDS: int = 30

# Default retry backoff base (seconds, exponential)
DEFAULT_RETRY_BACKOFF_SECONDS: int = 1

# Maximum retry backoff (seconds)
MAX_RETRY_BACKOFF_SECONDS: int = 300  # 5 minutes

# ===========================================================================
# Service Names & Identifiers
# Source: 10-Observability-Architecture (structured logging)
# ===========================================================================

# Service name for this backend service
SERVICE_NAME: str = "sentinel-backend"

# Worker service name (for logging/metrics)
WORKER_SERVICE_NAME: str = "sentinel-worker"

# Analyzer plugin service name prefix
ANALYZER_SERVICE_NAME_PREFIX: str = "analyzer-"
