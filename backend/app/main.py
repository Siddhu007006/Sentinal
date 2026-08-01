"""
Sentinel application factory and entrypoint.

Creates and configures the FastAPI application using the factory
pattern. The application is never instantiated as a module-level
global — it is always created through create_app().

See: 06-Repository-Structure §3 (app/main.py — FastAPI app factory).
See: 07-Backend-Development-Standards §4 (FastAPI standards).
See: 03-Architecture §4 (Presentation layer — FastAPI).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.exception_handlers.handlers import register_exception_handlers
from app.api.v1.middleware.rate_limit import RateLimitMiddleware
from app.api.v1.middleware.request_id import RequestIdMiddleware
from app.api.v1.router import api_v1_router
from app.core.dependencies import get_logger, get_settings
from app.core.settings import EnvironmentType
from app.infrastructure.cache.redis_client import close_redis_client
from app.infrastructure.database.session import get_engine
from app.infrastructure.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan context manager.

    Handles startup and shutdown lifecycle events. Resources acquired
    during startup (dependency injection setup, logging, database pools,
    Redis connections, queue clients) are released during shutdown.

    Startup hooks:
    1. Initialize logging (configured with settings)
    2. Initialize dependency providers (via provider registry)
    3. Database/Redis/storage/queue connections (future Epics)

    Shutdown hooks:
    1. Clean up infrastructure providers (teardown hooks)
    2. Close database pools, Redis connections, etc. (future Epics)
    3. Graceful shutdown

    See: 07-Backend-Development-Standards §3 (application factory).
    See: 10-Observability-Architecture §2 (logging initialization).
    See: 09-Deployment-Architecture §3 (graceful shutdown).
    """
    # --- Startup ---
    # Configure logging system with settings
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)

    # Future Epics will add:
    #   - Explicit database connection pool initialization
    #   - Redis connection
    #   - Object storage client
    #   - Provider registry setup hooks
    yield
    # --- Shutdown ---
    # Close Redis client
    close_redis_client()

    # Dispose database connection pool
    engine = get_engine(settings)

    if engine is not None:
        try:
            await engine.dispose()
            logger.info("Database connection pool disposed")
        except Exception as e:
            logger.error(f"Failed to dispose database pool: {e}")
            # Error logged but does not prevent termination

    # Future Epics will add:
    #   - Provider registry teardown hooks (if implemented)
    #   - Redis connection close
    #   - Graceful queue drain
    #   - Logging flush


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    This is the application factory. It:
    1. Loads configuration via Settings (singleton, cached)
    2. Instantiates FastAPI with OpenAPI metadata from settings
    3. Registers the lifespan context manager
    4. Initializes dependency injection infrastructure
    5. Registers middleware (outermost first)
    6. Registers centralized exception handlers
    7. Includes API routers

    The factory pattern is used because:
    - Tests can create isolated app instances with different configs
    - No global mutable state at module level
    - Multiple app configurations (test, dev, prod) without conditionals

    Dependency Injection:
    - Settings are loaded once via get_settings() (cached singleton)
    - Request context is created per-request via get_request_context()
    - Loggers are acquired via get_logger(name)
    - Future infrastructure providers (DB, Redis, Storage) will be
      initialized in the lifespan startup hook

    See: 06-Repository-Structure §3 (app factory / entrypoint).
    See: 07-Backend-Development-Standards §3 (dependency injection).
    See: 10-Observability-Architecture §2 (request context propagation).
    """
    # Load settings (cached singleton)
    settings = get_settings()

    application = FastAPI(
        title="Sentinel",
        description=(
            "Digital Asset Trust Verification Platform. "
            "Evaluates the trustworthiness of digital assets — URLs, files, "
            "domains, IP addresses — through multi-layered analysis combining "
            "AI reasoning, conventional security scanning, and external "
            "threat intelligence."
        ),
        version="1.0.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # --- Middleware ---
    # Registration order matters: middleware executes in REVERSE order
    # of registration (last registered = outermost = executes first).
    #
    # Execution order for an inbound request:
    #   1. CORS (outermost — must run first for CORS headers)
    #   2. RequestIdMiddleware (sets request ID for all downstream)
    #   3. RateLimitMiddleware (uses request ID for correlation) — SKIP IN TEST
    #
    # To achieve this execution order, register in REVERSE:
    #   - Register RateLimitMiddleware first → executes last (innermost)
    #   - Register RequestIdMiddleware second → executes middle
    #   - Register CORS last → executes first (outermost)
    #
    # This ensures:
    # - CORS runs first (allows preflight requests through)
    # - RequestIdMiddleware sets request.state.request_id
    # - RateLimitMiddleware can access request.state.request_id
    #
    # See: 07-Backend-Development-Standards §4 (middleware).
    # See: 08-Security-Architecture §7 (CORS and rate limiting).

    # Skip rate limiting during tests (no Redis required for unit tests)
    # Tests that explicitly need rate limiting can use integration tests with Redis
    if settings.environment != EnvironmentType.TEST:
        application.add_middleware(
            RateLimitMiddleware,
            settings=settings.rate_limit,
            redis_url=settings.queue.broker_url,
        )

    application.add_middleware(RequestIdMiddleware)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Exception Handlers ---
    # Centralized error translation: Domain/Application exceptions → Error envelope.
    # See: 07-Backend-Development-Standards §9.
    register_exception_handlers(application)

    # --- Routers ---
    # All v1 routes are mounted under /api/v1.
    # See: 07-Backend-Development-Standards §4 (versioning).
    # See: backend/openapi.yaml servers (localhost:8000/api/v1).
    application.include_router(api_v1_router, prefix="/api/v1")

    return application


# ---------------------------------------------------------------------------
# Application instance for uvicorn
# ---------------------------------------------------------------------------
# uvicorn expects a module-level callable or instance.
# The Dockerfile CMD uses: uvicorn app.main:app
# This is the ONLY place a module-level app variable exists.
# ---------------------------------------------------------------------------
app = create_app()
