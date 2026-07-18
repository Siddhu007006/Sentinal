"""
Logger factory and core logging utilities.

Provides centralized logger creation with consistent formatting,
level configuration, and context integration. All application code
obtains loggers through get_logger(), ensuring a single point of
configuration and behavior.

See: 10-Observability-Architecture §4 (structured logging).
See: 07-Backend-Development-Standards §10 (logging standards).
See: 08-Security-Architecture §10 (sensitive data handling).
"""

import logging
import sys

from app.core.settings import Settings
from app.infrastructure.logging.filters import ContextFilter, SensitiveDataFilter
from app.infrastructure.logging.formatters import SentinelJSONFormatter


# Cache of loggers by name to avoid recreating them
_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str, settings: Settings | None = None) -> logging.Logger:
    """Get or create a logger with the given name.

    Loggers are cached by name to ensure that multiple calls for the same
    logger name return the same instance, consistent with Python's standard
    logging module behavior.

    Each logger is configured with:
    - Sentinel's custom JSON formatter for structured output
    - Console handler (stdout)
    - Filters for context injection and sensitive data redaction
    - Log level from settings (or configured default)

    Args:
        name: Logger name, typically __name__ from the calling module.
        settings: Application settings. If not provided, uses defaults.
            In later Epics, settings will be injected via dependency.

    Returns:
        A configured logger instance, ready to use.

    Example:
        logger = get_logger(__name__)
        logger.info("upload_created", extra={"fields": {"upload_id": upload.id}})

    See: 10-Observability-Architecture §4 (centralized logging).
    See: 07-Backend-Development-Standards §10 (logger factory).
    """
    # Return cached logger if it already exists
    if name in _loggers:
        return _loggers[name]

    # Create new logger
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if get_logger is called multiple times
    if logger.handlers:
        return logger

    # Determine log level
    if settings is None:
        # Development default
        log_level = logging.INFO
    else:
        # Get level from settings
        level_name = settings.logging.level.upper()
        log_level = getattr(logging, level_name)

    logger.setLevel(log_level)

    # Create and configure handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # Apply formatter (SentinelJSONFormatter always outputs JSON)
    formatter = SentinelJSONFormatter()
    handler.setFormatter(formatter)

    # Add filters for context and sensitive data
    handler.addFilter(ContextFilter())
    handler.addFilter(SensitiveDataFilter())

    # Add handler to logger
    logger.addHandler(handler)

    # Prevent propagation to avoid duplicate logs
    logger.propagate = False

    # Cache the logger
    _loggers[name] = logger

    return logger


def configure_logging(settings: Settings) -> None:
    """Configure the logging system based on application settings.

    This function is called once at application startup to initialize
    the logging system. It sets the root logger's level and configures
    all loggers to use consistent formatting. It also suppresses uvicorn's
    default access logs in favor of structured middleware logging.

    Args:
        settings: Application settings containing log configuration.

    See: 10-Observability-Architecture §4.
    See: E2.T3 (suppress uvicorn access logs).
    """
    root_logger = logging.getLogger()
    level_name = settings.logging.level.upper()
    log_level = getattr(logging, level_name)
    root_logger.setLevel(log_level)

    # Suppress uvicorn access logs (we log requests in RequestIdMiddleware)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").propagate = False

    # Ensure all subsequent loggers use our factory
    logging.setLoggerClass(logging.Logger)
