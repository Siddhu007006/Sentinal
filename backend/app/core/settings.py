"""
Application configuration and settings.

Loads and validates all application configuration from environment variables
and .env files using Pydantic Settings v2. Configuration is hierarchically
organized into logical groups and is immutable once loaded.

Validation is strict — the application will not start if any required
configuration is missing or invalid. This implements the "fail fast"
principle from 07-Backend-Development-Standards §2.

See: 06-Repository-Structure §3 (app/core/ — settings loading)
See: 07-Backend-Development-Standards §2 (fail fast principle)
See: 08-Security-Architecture §9 (secrets sourced from environment)
See: backend/.env.example (all configuration documented)
"""

import json
from enum import StrEnum
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources.base import PydanticBaseSettingsSource
from pydantic_settings.sources.providers.dotenv import DotEnvSettingsSource
from pydantic_settings.sources.providers.env import EnvSettingsSource


# ---------------------------------------------------------------------------
# Custom settings sources — comma-separated list field parsing
# ---------------------------------------------------------------------------
#
# pydantic-settings treats list[str] fields as "complex" and calls
# json.loads() on the raw environment string *before* any field_validator
# can run.  For fields whose canonical env format is comma-separated
# (e.g. CORS_ORIGINS=http://a,http://b) this causes a JSONDecodeError.
#
# The custom sources below intercept those specific fields, parse the
# raw string into a Python list, and return it.  All other fields
# delegate to the default source unchanged.
#
# See: implementation_plan.md — Root Cause Analysis
# ---------------------------------------------------------------------------

# These environment variables intentionally support both:
#
#   VAR=a,b,c            (comma-separated — human-friendly)
#
# and
#
#   VAR=["a","b","c"]    (JSON array — machine-friendly)
#
# The custom settings sources below convert comma-separated values into
# Python lists before Pydantic's default JSON decoding for complex types
# can reject them.  Adding a field here opts it into this behaviour;
# all other fields pass through to the standard source unchanged.
_COMMA_SEPARATED_FIELDS: frozenset[str] = frozenset(
    {
        "allowed_origins",  # CORS_ORIGINS
        "allowed_mime_types",  # UPLOAD_ALLOWED_MIME_TYPES
    }
)


def _parse_comma_separated(value: str) -> list[str]:
    """Parse a comma-separated env string into a list.

    Tries JSON array decoding first (forward-compatible with
    ``'["a","b"]'`` format), then falls back to comma-splitting.
    """
    stripped = value.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except (json.JSONDecodeError, ValueError):
            pass  # Fall through to comma split
    return [item.strip() for item in value.split(",")]


class _CommaSplitEnvSource(EnvSettingsSource):
    """EnvSettingsSource that pre-parses comma-separated list fields.

    For fields registered in ``_COMMA_SEPARATED_FIELDS``, the raw
    environment string is converted to a Python list *before*
    pydantic-settings can attempt ``json.loads`` on it.

    All other fields delegate to the default ``EnvSettingsSource``.
    """

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,  # noqa: ANN401  — must match parent signature
        value_is_complex: bool,
    ) -> Any:  # noqa: ANN401  — must match parent signature
        if field_name in _COMMA_SEPARATED_FIELDS and isinstance(value, str):
            return _parse_comma_separated(value)
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class _CommaSplitDotEnvSource(DotEnvSettingsSource):
    """DotEnvSettingsSource counterpart of ``_CommaSplitEnvSource``.

    Identical logic, applied to ``.env`` file sources.
    """

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,  # noqa: ANN401  — must match parent signature
        value_is_complex: bool,
    ) -> Any:  # noqa: ANN401  — must match parent signature
        if field_name in _COMMA_SEPARATED_FIELDS and isinstance(value, str):
            return _parse_comma_separated(value)
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class EnvironmentType(StrEnum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class AIProviderType(StrEnum):
    """Supported AI providers."""

    MOCK = "mock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class DatabaseSettings(BaseSettings):
    """Database configuration group.

    Traces to: 04-Database-Design, 07-Backend-Development-Standards §8.
    """

    url: str = Field(
        ...,
        alias="DATABASE_URL",
        description="Async PostgreSQL connection string (postgresql+asyncpg://...)",
    )
    migration_url: str = Field(
        ...,
        alias="DATABASE_MIGRATION_URL",
        description="Migration connection string (DDL privileges)",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_default=True,
        extra="ignore",
    )


class StorageSettings(BaseSettings):
    """Object storage (S3-compatible) configuration group.

    Traces to: 03-Architecture §4, 08-Security-Architecture §6.
    """

    endpoint_url: str = Field(
        ...,
        alias="S3_ENDPOINT_URL",
        description="S3-compatible endpoint (MinIO, AWS, Cloudflare R2, etc.)",
    )
    bucket_name: str = Field(
        ...,
        alias="S3_BUCKET_NAME",
        description="Bucket name for digital asset storage",
    )
    access_key_id: SecretStr = Field(
        ...,
        alias="S3_ACCESS_KEY",
        description="S3 access key (secret)",
    )
    secret_access_key: SecretStr = Field(
        ...,
        alias="S3_SECRET_KEY",
        description="S3 secret key (secret)",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_default=True,
        extra="ignore",
    )


class QueueSettings(BaseSettings):
    """Task queue (Celery/Redis) configuration group.

    Traces to: 03-Architecture §4, 00-Project-Context §5.
    """

    broker_url: str = Field(
        ...,
        alias="REDIS_URL",
        description="Redis connection URL for Celery broker",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_default=True,
        extra="ignore",
    )


class SecuritySettings(BaseSettings):
    """Authentication and security configuration group.

    Traces to: 08-Security-Architecture §4, 07-Backend-Development-Standards §11.
    """

    jwt_secret_key: SecretStr = Field(
        ...,
        alias="JWT_SECRET_KEY",
        description="JWT signing secret (use: python -c "
        "'import secrets; print(secrets.token_urlsafe(64))')",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        alias="JWT_ALGORITHM",
        description="JWT signing algorithm (HS256 or RS256)",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=15,
        alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        description="Access token lifetime in minutes (default: 15 minutes)",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS",
        description="Refresh token lifetime in days (default: 7 days)",
    )
    password_hashing_algorithm: str = Field(
        default="argon2id",
        alias="PASSWORD_HASHING_ALGORITHM",
        description="Password hashing algorithm (argon2id or bcrypt)",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_default=True,
        extra="ignore",
    )

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        """Ensure JWT algorithm is one of the supported options."""
        if v not in ("HS256", "RS256"):
            raise ValueError(f"jwt_algorithm must be HS256 or RS256, got {v}")
        return v

    @field_validator("password_hashing_algorithm")
    @classmethod
    def validate_password_hashing_algorithm(cls, v: str) -> str:
        """Ensure password hashing algorithm is one of the supported options."""
        if v not in ("argon2id", "bcrypt"):
            raise ValueError(
                f"password_hashing_algorithm must be argon2id or bcrypt, got {v}"
            )
        return v


class CORSSettings(BaseSettings):
    """CORS configuration group.

    Traces to: 08-Security-Architecture §7 (explicit allow-list, never wildcard).
    """

    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        alias="CORS_ORIGINS",
        description="CORS allowed origins (comma-separated string or list)",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        """Parse CORS_ORIGINS from comma-separated string to list.

        Defence-in-depth: the custom EnvSettingsSource handles env/dotenv
        parsing, but this validator catches programmatic construction.
        """
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        if isinstance(v, list):
            return v
        return ["http://localhost:3000"]  # Default fallback

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Replace default env/dotenv sources with comma-split variants."""
        return (
            init_settings,
            _CommaSplitEnvSource(settings_cls),
            _CommaSplitDotEnvSource(settings_cls),
            file_secret_settings,
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_default=True,
        extra="ignore",
    )


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration group.

    Traces to: 08-Security-Architecture §7.
    """

    authenticated_requests_per_minute: int = Field(
        default=60,
        alias="RATE_LIMIT_AUTHENTICATED",
        description="Requests per minute for authenticated users",
    )
    unauthenticated_requests_per_minute: int = Field(
        default=10,
        alias="RATE_LIMIT_UNAUTHENTICATED",
        description="Requests per minute for unauthenticated endpoints",
    )

    model_config = SettingsConfigDict(validate_default=True)


class OpenAISettings(BaseSettings):
    """OpenAI provider configuration."""

    api_key: SecretStr | None = Field(
        default=None,
        alias="OPENAI_API_KEY",
        description="OpenAI API key (secret)",
    )
    model: str = Field(
        default="gpt-4o",
        alias="OPENAI_MODEL",
        description="OpenAI model identifier",
    )
    timeout_seconds: int = Field(
        default=30,
        alias="OPENAI_TIMEOUT_SECONDS",
        description="Request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        alias="OPENAI_MAX_RETRIES",
        description="Maximum retries for transient failures",
    )

    model_config = SettingsConfigDict(validate_default=True)


class AnthropicSettings(BaseSettings):
    """Anthropic (Claude) provider configuration."""

    api_key: SecretStr | None = Field(
        default=None,
        alias="ANTHROPIC_API_KEY",
        description="Anthropic API key (secret)",
    )
    model: str = Field(
        default="claude-sonnet-4-20250514",
        alias="ANTHROPIC_MODEL",
        description="Anthropic model identifier",
    )
    timeout_seconds: int = Field(
        default=30,
        alias="ANTHROPIC_TIMEOUT_SECONDS",
        description="Request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        alias="ANTHROPIC_MAX_RETRIES",
        description="Maximum retries for transient failures",
    )

    model_config = SettingsConfigDict(validate_default=True)


class GoogleAISettings(BaseSettings):
    """Google AI provider configuration."""

    api_key: SecretStr | None = Field(
        default=None,
        alias="GOOGLE_AI_API_KEY",
        description="Google AI API key (secret)",
    )
    model: str = Field(
        default="gemini-2.0-flash",
        alias="GOOGLE_AI_MODEL",
        description="Google AI model identifier",
    )
    timeout_seconds: int = Field(
        default=30,
        alias="GOOGLE_AI_TIMEOUT_SECONDS",
        description="Request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        alias="GOOGLE_AI_MAX_RETRIES",
        description="Maximum retries for transient failures",
    )

    model_config = SettingsConfigDict(validate_default=True)


class AIProviderSettings(BaseSettings):
    """AI provider configuration group.

    Traces to: 03-Architecture §4, 08-Security-Architecture §8.
    """

    provider: AIProviderType = Field(
        default=AIProviderType.MOCK,
        alias="AI_PROVIDER",
        description="Active AI provider (mock | openai | anthropic | google)",
    )
    openai: OpenAISettings = Field(
        default_factory=OpenAISettings,
        description="OpenAI-specific configuration",
    )
    anthropic: AnthropicSettings = Field(
        default_factory=AnthropicSettings,
        description="Anthropic-specific configuration",
    )
    google: GoogleAISettings = Field(
        default_factory=GoogleAISettings,
        description="Google AI-specific configuration",
    )

    model_config = SettingsConfigDict(validate_default=True)

    @field_validator("provider", mode="before")
    @classmethod
    def parse_provider(cls, v: object) -> AIProviderType:
        """Parse provider string to enum."""
        if isinstance(v, str):
            return AIProviderType(v)
        return v  # type: ignore[return-value]


class LoggingSettings(BaseSettings):
    """Logging configuration group.

    Traces to: 07-Backend-Development-Standards §10, 10-Observability-Architecture §4.
    """

    level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Log level (DEBUG | INFO | WARNING | ERROR | CRITICAL)",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_default=True,
        extra="ignore",
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}, got {v}")
        return v.upper()


class ObservabilitySettings(BaseSettings):
    """Observability (metrics, tracing) configuration group.

    Traces to: 10-Observability-Architecture §5-§6.
    """

    metrics_enabled: bool = Field(
        default=False,
        alias="METRICS_ENABLED",
        description="Enable metrics collection",
    )
    metrics_export_endpoint: str | None = Field(
        default=None,
        alias="METRICS_EXPORT_ENDPOINT",
        description="Prometheus scrape endpoint or OTLP endpoint",
    )
    tracing_enabled: bool = Field(
        default=False,
        alias="TRACING_ENABLED",
        description="Enable distributed tracing",
    )
    tracing_otlp_endpoint: str | None = Field(
        default=None,
        alias="TRACING_OTLP_ENDPOINT",
        description="OTLP tracing endpoint",
    )
    tracing_sample_rate: float = Field(
        default=1.0,
        alias="TRACING_SAMPLE_RATE",
        description="Tracing sample rate (0.0 to 1.0)",
    )

    model_config = SettingsConfigDict(validate_default=True)

    @field_validator("tracing_sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: float) -> float:
        """Ensure tracing sample rate is between 0.0 and 1.0."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"tracing_sample_rate must be 0.0-1.0, got {v}")
        return v


class ThreatIntelSettings(BaseSettings):
    """External threat intelligence API configuration.

    Traces to: 03-Architecture §4, optional enrichment module.
    """

    virustotal_api_key: SecretStr | None = Field(
        default=None,
        alias="VIRUSTOTAL_API_KEY",
        description="VirusTotal API key (optional, secret)",
    )
    urlscan_api_key: SecretStr | None = Field(
        default=None,
        alias="URLSCAN_API_KEY",
        description="URLScan.io API key (optional, secret)",
    )

    model_config = SettingsConfigDict(validate_default=True)


class EmailSettings(BaseSettings):
    """Email (SMTP) configuration group.

    Traces to: 03-Architecture §4, 06-Repository-Structure §7.
    """

    host: str | None = Field(
        default=None,
        alias="SMTP_HOST",
        description="SMTP server hostname",
    )
    port: int = Field(
        default=587,
        alias="SMTP_PORT",
        description="SMTP server port",
    )
    username: str | None = Field(
        default=None,
        alias="SMTP_USERNAME",
        description="SMTP authentication username",
    )
    password: SecretStr | None = Field(
        default=None,
        alias="SMTP_PASSWORD",
        description="SMTP authentication password (secret)",
    )
    use_tls: bool = Field(
        default=True,
        alias="SMTP_USE_TLS",
        description="Use TLS for SMTP",
    )
    from_email: str | None = Field(
        default=None,
        alias="SMTP_FROM_EMAIL",
        description="Sender email address",
    )

    model_config = SettingsConfigDict(validate_default=True)


class UploadSettings(BaseSettings):
    """File upload constraints configuration group.

    Traces to: backend/openapi.yaml, 08-Security-Architecture §6.

    NOTE: These values MUST match backend/openapi.yaml exactly.
    """

    max_file_size: int = Field(
        default=104857600,  # 100 MB
        alias="UPLOAD_MAX_FILE_SIZE",
        description="Maximum upload file size in bytes (default: 100 MB)",
    )
    allowed_mime_types: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/gif",
            "text/plain",
            "application/zip",
        ],
        alias="UPLOAD_ALLOWED_MIME_TYPES",
        description="Allowed MIME types (comma-separated string or list)",
    )

    @field_validator("allowed_mime_types", mode="before")
    @classmethod
    def parse_mime_types(cls, v: object) -> list[str]:
        """Parse UPLOAD_ALLOWED_MIME_TYPES from comma-separated string to list.

        Defence-in-depth: the custom EnvSettingsSource handles env/dotenv
        parsing, but this validator catches programmatic construction.
        """
        if isinstance(v, str):
            return [mime.strip() for mime in v.split(",")]
        if isinstance(v, list):
            return v
        return [
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/gif",
            "text/plain",
            "application/zip",
        ]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Replace default env/dotenv sources with comma-split variants."""
        return (
            init_settings,
            _CommaSplitEnvSource(settings_cls),
            _CommaSplitDotEnvSource(settings_cls),
            file_secret_settings,
        )

    model_config = SettingsConfigDict(validate_default=True)

    @field_validator("max_file_size")
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        """Ensure max file size is positive."""
        if v <= 0:
            raise ValueError(f"max_file_size must be > 0, got {v}")
        return v


class Settings(BaseSettings):
    """Root settings object — all application configuration.

    Loads from environment variables and .env file (via pydantic-settings).
    All nested settings are validated on instantiation.

    Configuration is immutable and cached after first load.
    See: get_settings() in app/core/dependencies.py for usage.

    Traces to: 06-Repository-Structure §3 (app/core/ — settings).
    Traces to: 07-Backend-Development-Standards §2 (fail fast).
    """

    # --- Application ---
    environment: EnvironmentType = Field(
        default=EnvironmentType.DEVELOPMENT,
        alias="ENVIRONMENT",
        description="Application environment (development | staging | production)",
    )

    # --- Nested Settings Groups ---
    database: DatabaseSettings = Field(
        default=None,  # type: ignore[assignment]
        description="Database configuration",
    )
    storage: StorageSettings = Field(
        default=None,  # type: ignore[assignment]
        description="Object storage configuration",
    )
    queue: QueueSettings = Field(
        default=None,  # type: ignore[assignment]
        description="Task queue configuration",
    )
    security: SecuritySettings = Field(
        default=None,  # type: ignore[assignment]
        description="Security configuration",
    )
    cors: CORSSettings = Field(
        default=None,  # type: ignore[assignment]
        description="CORS configuration",
    )
    rate_limit: RateLimitSettings = Field(
        default=None,  # type: ignore[assignment]
        description="Rate limiting configuration",
    )
    logging: LoggingSettings = Field(
        default=None,  # type: ignore[assignment]
        description="Logging configuration",
    )

    def __init__(self, **data: object) -> None:
        """Initialize Settings with nested BaseSettings auto-instantiation."""
        # Pydantic v2 nested BaseSettings need explicit instantiation
        if "database" not in data or data["database"] is None:
            data["database"] = DatabaseSettings()
        if "storage" not in data or data["storage"] is None:
            data["storage"] = StorageSettings()
        if "queue" not in data or data["queue"] is None:
            data["queue"] = QueueSettings()
        if "security" not in data or data["security"] is None:
            data["security"] = SecuritySettings()
        if "cors" not in data or data["cors"] is None:
            data["cors"] = CORSSettings()
        if "rate_limit" not in data or data["rate_limit"] is None:
            data["rate_limit"] = RateLimitSettings()
        if "logging" not in data or data["logging"] is None:
            data["logging"] = LoggingSettings()
        super().__init__(**data)  # type: ignore[arg-type]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        validate_default=True,
        extra="ignore",  # Ignore unknown environment variables
        frozen=True,  # Enforce immutability per E2.T1 acceptance criteria
    )
