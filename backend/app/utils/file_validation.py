"""
File validation utilities (E5.T5).

Fail-closed content validation for the upload pipeline, per
08-Security-Architecture §6:

- Declared MIME type is checked against the configured allow-list
  (UploadSettings.allowed_mime_types, the operational contract from
  backend/openapi.yaml) BEFORE any expensive processing or storage
  I/O (reject early — Fail Safe).
- Magic-byte verification: because the client-supplied Content-Type
  header is trivially spoofable, the leading bytes of the actual
  content are independently verified to match the declared and
  allow-listed type. A mismatch is a validation failure, never a
  warning.
- Content failing validation is rejected outright rather than stored
  (no quarantine workflow exists in the product requirements).

Bounded-memory design: validation inspects only the minimum prefix
required for signature detection (<= _SNIFF_BYTES). The stream API
consumes just that prefix and returns a replay iterator yielding the
SAME bytes in the same order — every original byte exactly once — so
the E5.T4 pipeline (hashing tee + multipart storage) continues to run
single-pass with the existing 100 MB bounded-memory contract.

Supported signature mapping (per 22-Engineering-Backlog E5.T5):
PDF, PNG, JPEG, GIF, WebP, ZIP, and the ZIP-container document types
(DOCX/XLSX/PPTX share the ZIP signature; distinguishing them requires
reading archive internals, beyond the minimum-prefix contract — their
signature check is the ZIP signature). The runtime allow-list remains
the gate: a signature being RECOGNIZED does not make its MIME ACCEPTED
unless configured.

text/plain has no magic bytes. Its prefix policy (documented decision):
the sniffed prefix must decode as strict UTF-8 (an empty file is a
valid empty text file). Anything non-decodable fails closed.

Pure stdlib — no FastAPI, SQLAlchemy, aioboto3, or repository imports.
Usable from UploadService and anywhere else that sees a byte stream.

Traces to: 22-Engineering-Backlog E5.T5 (File Validation Utilities)
Traces to: 08-Security-Architecture §6 (upload validation)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

# Bytes needed to decide every supported signature:
#   PNG 8, GIF 6, PDF 5, JPEG 3, ZIP 4, WebP needs offset 8..12.
_SNIFF_BYTES = 16


# ---------------------------------------------------------------------------
# Error model — validation failures, clearly distinct from infrastructure
# (StorageError) failures. Messages carry no internal implementation
# details, only the validation fact.
# ---------------------------------------------------------------------------


class FileValidationError(Exception):
    """Base class for content-validation failures (fail closed)."""


class MimeTypeNotAllowedError(FileValidationError):
    """Declared MIME type is outside the configured allow-list."""

    def __init__(self, content_type: str) -> None:
        self.content_type = content_type
        super().__init__(
            f"Content type {content_type!r} is not allowed for uploads"
        )


class MimeTypeMismatchError(FileValidationError):
    """Content's leading bytes do not match the declared MIME type.

    The client-declared Content-Type was allow-listed, but the actual
    magic bytes belong to a different (or no) known type — treated as
    a validation failure per 08-Security-Architecture §6.
    """

    def __init__(self, declared_content_type: str) -> None:
        self.declared_content_type = declared_content_type
        super().__init__(
            f"File content does not match the declared type "
            f"{declared_content_type!r}"
        )


class TruncatedFileError(FileValidationError):
    """File ended before its type's signature could be present."""

    def __init__(self, declared_content_type: str) -> None:
        self.declared_content_type = declared_content_type
        super().__init__(
            f"File is too short to be a valid "
            f"{declared_content_type!r} document"
        )


class UndecodableContentError(FileValidationError):
    """text/plain content is not decodable text."""


# ---------------------------------------------------------------------------
# Signature table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _MagicPattern:
    """One required byte pattern at a fixed offset."""

    prefix: bytes
    offset: int = 0

    def matches(self, sniffed: bytes) -> bool:
        end = self.offset + len(self.prefix)
        return (
            len(sniffed) >= end
            and sniffed[self.offset : end] == self.prefix
        )


# MIME type -> required magic patterns (ALL must match).
_MIME_SIGNATURES: dict[str, tuple[_MagicPattern, ...]] = {
    "application/pdf": (_MagicPattern(b"%PDF-"),),
    "image/png": (_MagicPattern(b"\x89PNG\r\n\x1a\n"),),
    "image/jpeg": (_MagicPattern(b"\xff\xd8\xff"),),
    "image/gif": (
        _MagicPattern(b"GIF87a"),
        _MagicPattern(b"GIF89a"),
    ),  # either 87a or 89a — see _signature_matches for either-semantics
    "image/webp": (
        _MagicPattern(b"RIFF"),
        _MagicPattern(b"WEBP", offset=8),
    ),
    # ZIP family: local-file-header, empty-archive, and spanned markers.
    "application/zip": (
        _MagicPattern(b"PK\x03\x04"),
        _MagicPattern(b"PK\x05\x06"),
        _MagicPattern(b"PK\x07\x08"),
    ),
    # ZIP-container documents share the ZIP signature.
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        _MagicPattern(b"PK\x03\x04"),
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        _MagicPattern(b"PK\x03\x04"),
    ),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        _MagicPattern(b"PK\x03\x04"),
    ),
}

# Types whose signature list means "ANY of these patterns" (see
# _signature_matches); every other type requires ALL listed patterns.
_ANY_OF_TYPES = frozenset({"image/gif", "application/zip"})

# Types with no binary signature, validated by the text-decodability
# policy instead.
_TEXT_TYPES = frozenset({"text/plain"})


def normalize_content_type(content_type: str) -> str:
    """Normalize a Content-Type value for allow-list comparison.

    Strips parameters (e.g. ``; charset=utf-8``), lowercases, and
    trims surrounding whitespace. Parameters carry no authority for
    type decisions.
    """
    return content_type.split(";", 1)[0].strip().lower()


def validate_declared_mime_type(
    declared_content_type: str,
    allowed_mime_types: Sequence[str],
) -> str:
    """Validate the declared MIME type against the allow-list.

    Args:
        declared_content_type: Client-declared Content-Type (may carry
            parameters; they are ignored)
        allowed_mime_types: Authoritative allow-list

    Returns:
        The normalized MIME type

    Raises:
        MimeTypeNotAllowedError: If the normalized type is not in the
            allow-list
    """
    normalized = normalize_content_type(declared_content_type)
    allowed = {
        normalize_content_type(entry) for entry in allowed_mime_types
    }
    if normalized not in allowed:
        raise MimeTypeNotAllowedError(normalized)
    return normalized


def detect_content_type(sniffed: bytes) -> str | None:
    """Detect the content type from leading bytes, or None if unknown.

    Extension-only or declared-header spoofing cannot pass: the answer
    depends exclusively on the sniffed bytes.
    """
    for mime, patterns in _MIME_SIGNATURES.items():
        if _signature_matches(sniffed, patterns, mime):
            return mime
    if sniffed and _is_decodable_text(sniffed):
        return "text/plain"
    if not sniffed:
        return "text/plain"  # empty stream: see text policy
    return None


def validate_magic_bytes(
    sniffed: bytes,
    *,
    declared_content_type: str,
    stream_exhausted: bool,
) -> None:
    """Verify leading bytes against the declared (allow-listed) type.

    Args:
        sniffed: The first bytes of the content (up to _SNIFF_BYTES)
        declared_content_type: Normalized declared MIME type
        stream_exhausted: Whether the stream ended within the sniff
            window (prefix shorter than the signature requirement)

    Raises:
        TruncatedFileError: Stream ended before the signature could
            possibly be present
        MimeTypeMismatchError: Bytes do not match the declared type
            (unknown signature, or a different known type)
        UndecodableContentError: text/plain content is not text
    """
    expected = normalize_content_type(declared_content_type)

    if expected in _TEXT_TYPES:
        if sniffed and not _is_decodable_text(sniffed):
            raise UndecodableContentError(
                "Declared text/plain but the content is not decodable text"
            )
        return

    patterns = _MIME_SIGNATURES.get(expected)
    if patterns is None:  # pragma: no cover - unreachable via pipeline
        # Unknown signature table entry: fail closed rather than guess.
        raise MimeTypeMismatchError(expected)

    required = max(
        p.offset + len(p.prefix) for p in patterns
    )
    if stream_exhausted and len(sniffed) < required:
        raise TruncatedFileError(expected)

    if not _signature_matches(sniffed, patterns, expected):
        raise MimeTypeMismatchError(expected)


def _signature_matches(
    sniffed: bytes,
    patterns: tuple[_MagicPattern, ...],
    mime: str,
) -> bool:
    """ALL patterns must match, except _ANY_OF_TYPES (any one suffices)."""
    if mime in _ANY_OF_TYPES:
        return any(p.matches(sniffed) for p in patterns)
    return all(p.matches(sniffed) for p in patterns)


def _is_decodable_text(prefix: bytes) -> bool:
    """Text policy: strict UTF-8 decodable with no binary control bytes.

    C0 control characters (other than TAB/LF/CR) and DEL mark the
    content as binary — plain UTF-8 decoding alone accepts them, which
    would let arbitrary binary junk pass as text/plain.
    """
    try:
        prefix.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    allowed_control = {0x09, 0x0A, 0x0D}  # TAB, LF, CR
    for byte in prefix:
        if (byte < 0x20 and byte not in allowed_control) or byte == 0x7F:
            return False
    return True


# ---------------------------------------------------------------------------
# Stream validation — bounded-memory single-pass API
# ---------------------------------------------------------------------------


async def validate_upload_stream(
    stream: AsyncIterator[bytes],
    *,
    declared_content_type: str,
    allowed_mime_types: Sequence[str],
) -> AsyncIterator[bytes]:
    """Validate a byte stream and return a replay of the SAME bytes.

    Consumes only the sniff window (<= _SNIFF_BYTES) from the input,
    runs declared-MIME and magic-byte validation (fail closed), and
    returns an iterator that replays the sniffed prefix followed by
    the remainder of the original stream — every byte exactly once —
    so the caller's downstream processing (hashing, storage) needs no
    buffering of the complete file.

    Args:
        stream: Async iterator of the file's bytes
        declared_content_type: Client-declared Content-Type
        allowed_mime_types: Authoritative allow-list

    Returns:
        Async iterator yielding the same bytes as `stream`

    Raises:
        MimeTypeNotAllowedError: Declared type outside the allow-list
        TruncatedFileError: Stream too short for the declared type
        MimeTypeMismatchError: Magic bytes do not match the declared
            type
        UndecodableContentError: text/plain content is not text
    """
    # Declared-MIME gate first: reject before touching the stream.
    expected = validate_declared_mime_type(
        declared_content_type, allowed_mime_types
    )

    # Sniff only the minimum prefix. If a chunk crosses the window
    # boundary, keep its tail locally — the replay iterator yields it
    # before continuing the original stream.
    window = bytearray()
    overflow = b""
    exhausted = False
    async for chunk in stream:
        window.extend(chunk)
        if len(window) >= _SNIFF_BYTES:
            overflow = bytes(window[_SNIFF_BYTES:])
            del window[_SNIFF_BYTES:]
            break
    else:
        exhausted = True

    validate_magic_bytes(
        bytes(window),
        declared_content_type=expected,
        stream_exhausted=exhausted,
    )

    sniffed = bytes(window)

    async def replay() -> AsyncIterator[bytes]:
        if sniffed:
            yield sniffed
        if overflow:
            yield overflow
        async for chunk in stream:
            yield chunk

    return replay()
