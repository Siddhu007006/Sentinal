"""
Logging formatters for structured JSON output.

Provides the SentinelJSONFormatter which formats log records as JSON objects
with consistent field names, UTC timestamps, and support for structured
extra fields passed via the standard logging 'extra' dict.

See: 10-Observability-Architecture §4 (log format, structured logging).
See: 07-Backend-Development-Standards §10 (structured output).
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.constants import (
    LOG_FIELD_LEVEL,
    LOG_FIELD_LOGGER,
    LOG_FIELD_MESSAGE,
    LOG_FIELD_REQUEST_ID,
    LOG_FIELD_TIMESTAMP,
)
from app.core.dependencies import get_settings


class SentinelJSONFormatter(logging.Formatter):
    """Custom logging formatter that outputs JSON-structured log entries.

    Every log entry is formatted as a JSON object with consistent fields:
    - timestamp: ISO-8601 UTC datetime
    - level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - logger: Logger name (module path)
    - message: Log message
    - request_id: X-Request-ID correlation ID (if available via context)
    - ... any additional fields passed via extra dict

    Timestamps are always UTC to ensure consistency across all environments
    and support for cross-timezone analysis.

    See: 10-Observability-Architecture §4 (log format).
    See: 07-Backend-Development-Standards §3 (UTC timestamps).
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON object.

        Args:
            record: The log record to format.

        Returns:
            A JSON string suitable for output to a log aggregation system.
        """
        # Build the base log object with required fields
        log_obj: dict[str, Any] = {
            LOG_FIELD_TIMESTAMP: self._get_utc_timestamp(),
            LOG_FIELD_LEVEL: record.levelname,
            LOG_FIELD_LOGGER: record.name,
            LOG_FIELD_MESSAGE: record.getMessage(),
        }

        # Add environment from settings
        try:
            settings = get_settings()
            log_obj["environment"] = settings.environment.value
        except Exception:  # noqa: S110
            # If settings not available (e.g., during import), skip environment
            pass

        # Add request ID if available in context
        request_id = self._extract_request_id(record)
        if request_id:
            log_obj[LOG_FIELD_REQUEST_ID] = request_id

        # Add any structured fields passed via extra dict
        if hasattr(record, "fields") and isinstance(record.fields, dict):
            log_obj.update(record.fields)

        # Add exception info if this is an error log with exception
        if record.exc_info and record.exc_text:
            log_obj["exception"] = record.exc_text

        # Serialize to JSON and return
        try:
            return str(json.dumps(log_obj, default=str))
        except (TypeError, ValueError):
            # Fallback if JSON serialization fails (shouldn't happen normally)
            log_obj["message"] = f"{log_obj['message']} (JSON serialization error)"
            return str(json.dumps(log_obj, default=str))

    def _get_utc_timestamp(self) -> str:
        """Get current UTC timestamp in ISO-8601 format.

        Returns:
            Timestamp string like "2025-01-15T10:30:45.123456Z".

        See: 07-Backend-Development-Standards §3 (UTC timestamps).
        """
        now = datetime.now(UTC)
        return now.isoformat()

    def _extract_request_id(self, record: logging.LogRecord) -> str | None:
        """Extract request ID from log record's extra fields if present.

        In later Epics, request IDs will be set via contextvars; for now,
        they can be passed manually via extra dict or as a field.

        Args:
            record: The log record.

        Returns:
            The request ID if available, None otherwise.
        """
        # Check if request_id was passed in extra fields
        if hasattr(record, LOG_FIELD_REQUEST_ID):
            val = getattr(record, LOG_FIELD_REQUEST_ID, None)
            if isinstance(val, str):
                return val

        # Check in fields dict if present
        if hasattr(record, "fields") and isinstance(record.fields, dict):
            rid = record.fields.get(LOG_FIELD_REQUEST_ID)
            if isinstance(rid, str):
                return rid

        return None


class SentinelPlainFormatter(logging.Formatter):
    """Plain text formatter for development use.

    Used when JSON formatting is disabled (e.g., in development for
    easier console reading). Still includes all structured fields but
    in a human-readable format.

    See: 10-Observability-Architecture §4 (configurable output).
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as plain text.

        Args:
            record: The log record to format.

        Returns:
            A plain text log line.
        """
        # Build timestamp
        timestamp = datetime.now(UTC).isoformat()

        # Extract request ID if available
        request_id = ""
        if hasattr(record, LOG_FIELD_REQUEST_ID):
            request_id = f" [{getattr(record, LOG_FIELD_REQUEST_ID)}]"
        elif hasattr(record, "fields") and isinstance(record.fields, dict):
            rid = record.fields.get(LOG_FIELD_REQUEST_ID)
            if rid:
                request_id = f" [{rid}]"

        # Get message
        message = record.getMessage()

        # Add extra fields if present
        extra_fields = ""
        if hasattr(record, "fields") and isinstance(record.fields, dict):
            fields = {
                k: v for k, v in record.fields.items() if k != LOG_FIELD_REQUEST_ID
            }
            if fields:
                extra_fields = " " + " ".join(f"{k}={v}" for k, v in fields.items())

        # Format: timestamp [level] logger: message [request_id] extra_fields
        return (
            f"{timestamp} [{record.levelname}] {record.name}: "
            f"{message}{request_id}{extra_fields}"
        )
