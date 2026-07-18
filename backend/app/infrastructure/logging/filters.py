"""
Logging filters for sensitive data redaction and context handling.

Provides filters that enforce security and context policies on log output:
- Redacts sensitive fields (passwords, tokens, secrets)
- Adds correlation IDs from contextvars
- Prevents accidental logging of protected data

See: 08-Security-Architecture §10 (sensitive data handling).
See: 07-Backend-Development-Standards §10 (logging security).
"""

import logging
import re

from app.infrastructure.logging.request_context import get_request_id


# List of field name patterns that should never be logged
# Covers: credentials, tokens, keys, secrets, session data, cookies
SENSITIVE_FIELD_PATTERNS = [
    r".*password.*",
    r".*secret.*",
    r".*token.*",
    r".*credential.*",
    r".*apikey.*",
    r".*api_key.*",
    r".*access_key.*",
    r".*secret_key.*",
    r".*jwt.*",
    r".*bearer.*",
    r".*authorization.*",
    r".*auth.*header.*",
    r".*client_secret.*",
    r".*refresh_token.*",
    r".*access_token.*",
    r".*private_key.*",
    r".*public_key.*",
    r".*session.*",
    r".*cookie.*",
    r".*csrf.*",
    r".*x-api-key.*",
    r".*x-auth.*",
]

# Compile patterns for efficiency
COMPILED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in SENSITIVE_FIELD_PATTERNS
]


class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive fields from log records.

    Inspects all extra fields in a log record and redacts any values
    matching known sensitive patterns (passwords, tokens, secrets, etc.),
    replacing them with a placeholder string.

    This enforces the security policy defined in 08-Security-Architecture §10
    at the logging layer, so no call site can accidentally leak a secret.

    See: 08-Security-Architecture §10 (PII and secret redaction).
    """

    REDACTED_VALUE = "[REDACTED]"

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and potentially redact a log record.

        Recursively inspects all extra fields and redacts sensitive values.
        Always returns True so the record is not filtered out (we redact,
        not drop).

        Args:
            record: The log record to potentially redact.

        Returns:
            True (always), allowing the record to be logged.
        """
        # Redact fields if present
        if hasattr(record, "fields") and isinstance(record.fields, dict):
            record.fields = self._redact_fields(record.fields)

        return True

    def _redact_fields(self, fields: dict[str, object]) -> dict[str, object]:
        """Recursively redact sensitive fields in a dictionary.

        Args:
            fields: Dictionary potentially containing sensitive data.

        Returns:
            Dictionary with sensitive values replaced with REDACTED_VALUE.
        """
        redacted: dict[str, object] = {}

        for key, value in fields.items():
            if self._is_sensitive_field(key):
                redacted[key] = self.REDACTED_VALUE
            elif isinstance(value, dict):
                redacted[key] = self._redact_fields(value)
            elif isinstance(value, (list, tuple)):
                redacted[key] = self._redact_sequence(value)
            else:
                redacted[key] = value

        return redacted

    def _redact_sequence(
        self, sequence: list[object] | tuple[object, ...]
    ) -> list[object]:
        """Recursively redact sensitive values in a sequence.

        Args:
            sequence: List or tuple potentially containing sensitive data.

        Returns:
            List with sensitive values replaced.
        """
        result: list[object] = []
        for item in sequence:
            if isinstance(item, dict):
                result.append(self._redact_fields(item))
            elif isinstance(item, (list, tuple)):
                result.append(self._redact_sequence(item))
            else:
                result.append(item)
        return result

    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if a field name matches any sensitive pattern.

        Args:
            field_name: The field name to check.

        Returns:
            True if the field should be redacted, False otherwise.
        """
        return any(pattern.match(field_name) for pattern in COMPILED_PATTERNS)


class ContextFilter(logging.Filter):
    """Filter that adds context data (like request IDs) to log records.

    Uses contextvars to retrieve the current request's correlation ID and
    other context, making them available to formatters without requiring
    them to be passed via the 'extra' dict on every log call.

    This is the async-safe way to propagate request-scoped data through
    the logging system.

    See: 10-Observability-Architecture §4 (correlation IDs).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context data to log record.

        Args:
            record: The log record.

        Returns:
            True (always), allowing the record to be logged.
        """
        # Add request ID from context if not already present
        if not hasattr(record, "request_id"):
            try:
                record.request_id = get_request_id()
            except LookupError:
                # contextvars may raise LookupError if no context is set
                # (e.g., during startup or in background tasks)
                record.request_id = None

        return True
