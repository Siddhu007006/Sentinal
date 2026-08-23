"""Unit tests for E5.T5 file validation utilities.

Covers the full supported MIME/signature matrix, fail-closed
mismatches, spoofing resistance, normalization, truncation, and the
bounded-memory replay-stream contract (every original byte yielded
exactly once).

Traces to: 22-Engineering-Backlog E5.T5 (File Validation Utilities)
Traces to: 08-Security-Architecture §6 (magic-byte verification)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.utils.file_validation import (
    FileValidationError,
    MimeTypeMismatchError,
    MimeTypeNotAllowedError,
    TruncatedFileError,
    UndecodableContentError,
    detect_content_type,
    validate_declared_mime_type,
    validate_magic_bytes,
    validate_upload_stream,
)


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

# The operational allow-list (UploadSettings default contract).
ALLOWED: Sequence[str] = (
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "text/plain",
    "application/zip",
)

# Valid content prefixes per supported type (backlog E5.T5 set).
VALID_SAMPLES: dict[str, bytes] = {
    "application/pdf": b"%PDF-1.7\n%\xe2\xe3\xcf\xd3" + b"body" * 8,
    "image/png": b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"x" * 8,
    "image/jpeg": b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 8,
    "image/gif": b"GIF89a" + b"7\x00" + b"body" * 4,
    "image/webp": b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"data" * 2,
    "application/zip": b"PK\x03\x04" + b"\x14\x00\x00\x00\x08\x00" * 2,
    "text/plain": b"ordinary textual content for validation",
}

OFFICE_TYPES = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument."
    "presentationml.presentation",
)


async def _stream_of(data: bytes, chunk_size: int = 4) -> AsyncIterator[bytes]:
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


async def _collect(it: AsyncIterator[bytes]) -> bytes:
    return b"".join([chunk async for chunk in it])


class TestDeclaredMimeValidation:
    def test_allowed_type_passes(self) -> None:
        assert (
            validate_declared_mime_type("application/pdf", ALLOWED)
            == "application/pdf"
        )

    def test_unsupported_type_rejected(self) -> None:
        with pytest.raises(MimeTypeNotAllowedError):
            validate_declared_mime_type("application/x-msdownload", ALLOWED)

    def test_parameters_stripped(self) -> None:
        assert (
            validate_declared_mime_type(
                "text/plain; charset=utf-8", ALLOWED
            )
            == "text/plain"
        )

    def test_case_normalized(self) -> None:
        assert (
            validate_declared_mime_type("Application/PDF", ALLOWED)
            == "application/pdf"
        )

    def test_whitespace_trimmed(self) -> None:
        assert (
            validate_declared_mime_type("  image/png  ", ALLOWED)
            == "image/png"
        )

    def test_allow_list_entries_normalized(self) -> None:
        messy: Sequence[str] = ["Application/PDF; q=1"]
        assert validate_declared_mime_type("application/pdf", messy) == (
            "application/pdf"
        )
        with pytest.raises(MimeTypeNotAllowedError):
            validate_declared_mime_type("image/png", messy)


class TestSignatureMatrix:
    @pytest.mark.parametrize(("mime", "sample"), VALID_SAMPLES.items())
    def test_valid_magic_bytes_accepted(self, mime: str, sample: bytes) -> None:
        """Every supported MIME + its real signature passes."""
        validate_magic_bytes(
            sample[:16],
            declared_content_type=mime,
            stream_exhausted=len(sample) < 16,
        )

    @pytest.mark.parametrize(
        "mime",
        [m for m in VALID_SAMPLES if m != "text/plain"],
    )
    def test_mismatched_magic_fails_closed(self, mime: str) -> None:
        """Valid declared MIME + another type's bytes → mismatch."""
        other = VALID_SAMPLES[
            "image/png" if mime != "image/png" else "application/pdf"
        ]
        with pytest.raises(MimeTypeMismatchError):
            validate_magic_bytes(
                other[:16],
                declared_content_type=mime,
                stream_exhausted=False,
            )

    def test_unknown_signature_fails_closed(self) -> None:
        """Bytes matching NO known signature fail for binary types."""
        with pytest.raises(MimeTypeMismatchError):
            validate_magic_bytes(
                b"\x00\x01\x02\x03\x04nope",
                declared_content_type="application/pdf",
                stream_exhausted=False,
            )

    def test_gif87a_and_89a_both_valid(self) -> None:
        for header in (b"GIF87a", b"GIF89a"):
            validate_magic_bytes(
                header + b"rest-of-file",
                declared_content_type="image/gif",
                stream_exhausted=False,
            )

    def test_zip_family_markers(self) -> None:
        """Local-header, empty-archive, and spanned markers are ZIP."""
        for marker in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
            validate_magic_bytes(
                marker + b"payload-bytes",
                declared_content_type="application/zip",
                stream_exhausted=False,
            )

    @pytest.mark.parametrize("mime", OFFICE_TYPES)
    def test_office_documents_share_zip_signature(self, mime: str) -> None:
        """DOCX/XLSX/PPTX are ZIP containers (documented limitation)."""
        validate_magic_bytes(
            b"PK\x03\x04" + b"zip-body",
            declared_content_type=mime,
            stream_exhausted=False,
        )

    def test_webp_requires_riff_and_webp_offsets(self) -> None:
        validate_magic_bytes(
            b"RIFF\x24\x00\x00\x00WEBPVP8 ",
            declared_content_type="image/webp",
            stream_exhausted=False,
        )
        # RIFF alone (e.g. WAV audio) is NOT WebP
        with pytest.raises(MimeTypeMismatchError):
            validate_magic_bytes(
                b"RIFF\x24\x00\x00\x00WAVEfmt ",
                declared_content_type="image/webp",
                stream_exhausted=False,
            )


class TestTruncationAndEmpty:
    @pytest.mark.parametrize(
        ("mime", "signature"),
        [
            ("application/pdf", b"%PDF-"),
            ("image/png", b"\x89PNG\r\n\x1a\n"),
            ("image/gif", b"GIF89a"),
        ],
    )
    def test_truncated_header_rejected(
        self, mime: str, signature: bytes
    ) -> None:
        with pytest.raises(TruncatedFileError):
            validate_magic_bytes(
                signature[: len(signature) - 1],
                declared_content_type=mime,
                stream_exhausted=True,
            )

    def test_empty_stream_is_invalid_pdf(self) -> None:
        with pytest.raises(TruncatedFileError):
            validate_magic_bytes(
                b"",
                declared_content_type="application/pdf",
                stream_exhausted=True,
            )

    def test_empty_stream_is_valid_text(self) -> None:
        """An empty file is a valid (empty) text file — documented
        decision in the module."""
        validate_magic_bytes(
            b"",
            declared_content_type="text/plain",
            stream_exhausted=True,
        )


class TestTextPolicy:
    def test_valid_utf8_text_accepted(self) -> None:
        validate_magic_bytes(
            "héllo wörld —validated".encode(),
            declared_content_type="text/plain",
            stream_exhausted=False,
        )

    def test_undecodable_bytes_rejected_as_text(self) -> None:
        with pytest.raises(UndecodableContentError):
            validate_magic_bytes(
                b"\xff\xfe\xfa binary \x00stuff",
                declared_content_type="text/plain",
                stream_exhausted=False,
            )

    def test_control_characters_rejected_as_text(self) -> None:
        """NUL/control bytes mark binary content even though they are
        technically valid UTF-8."""
        with pytest.raises(UndecodableContentError):
            validate_magic_bytes(
                b"\x00\x01\x02\x03\x04binary-junk",
                declared_content_type="text/plain",
                stream_exhausted=False,
            )

    def test_tab_lf_cr_allowed_in_text(self) -> None:
        validate_magic_bytes(
            b"line1\nline2\ttabbed\r\nend",
            declared_content_type="text/plain",
            stream_exhausted=False,
        )


class TestSpoofingResistance:
    def test_extension_spoofing_fails(self) -> None:
        """PE executable bytes declared as PDF (report.exe.pdf style)
        cannot pass: the bytes decide, not the name or header."""
        pe_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff"
        with pytest.raises(MimeTypeMismatchError):
            validate_magic_bytes(
                pe_bytes,
                declared_content_type="application/pdf",
                stream_exhausted=False,
            )

    def test_detect_ignores_declared_header(self) -> None:
        """detect_content_type depends exclusively on the bytes."""
        assert detect_content_type(b"%PDF-") == "application/pdf"
        assert detect_content_type(b"MZ\x90\x00") is None
        assert detect_content_type(b"") == "text/plain"


class TestValidationVsInfrastructureErrors:
    def test_validation_errors_distinct(self) -> None:
        """All validation failures share the FileValidationError family —
        distinguishable from StorageError (infrastructure) at the call
        site."""
        for exc in (
            MimeTypeNotAllowedError("application/evil"),
            MimeTypeMismatchError("application/pdf"),
            TruncatedFileError("application/pdf"),
            UndecodableContentError("not text"),
        ):
            assert isinstance(exc, FileValidationError)


class TestStreamValidation:
    @pytest.mark.asyncio
    async def test_replay_yields_every_byte_exactly_once(self) -> None:
        """The replay stream reproduces the input byte-for-byte."""
        payload = VALID_SAMPLES["application/pdf"]
        replay = await validate_upload_stream(
            _stream_of(payload, chunk_size=3),
            declared_content_type="application/pdf",
            allowed_mime_types=ALLOWED,
        )
        assert await _collect(replay) == payload

    @pytest.mark.asyncio
    async def test_replay_preserves_chunk_crossing_window(self) -> None:
        """A chunk crossing the sniff window is fully preserved."""
        payload = VALID_SAMPLES["image/png"] + b"trailing-data" * 5
        replay = await validate_upload_stream(
            _stream_of(payload, chunk_size=32),  # chunks cross the window
            declared_content_type="image/png",
            allowed_mime_types=ALLOWED,
        )
        assert await _collect(replay) == payload

    @pytest.mark.asyncio
    async def test_stream_validation_accepts_valid_content(self) -> None:
        replay = await validate_upload_stream(
            _stream_of(VALID_SAMPLES["image/gif"]),
            declared_content_type="image/gif",
            allowed_mime_types=ALLOWED,
        )
        assert (await _collect(replay)).startswith(b"GIF89a")

    @pytest.mark.asyncio
    async def test_stream_validation_rejects_mismatch(self) -> None:
        with pytest.raises(MimeTypeMismatchError):
            await validate_upload_stream(
                _stream_of(b"MZ\x90\x00\x03 executable bytes"),
                declared_content_type="application/pdf",
                allowed_mime_types=ALLOWED,
            )

    @pytest.mark.asyncio
    async def test_stream_validation_rejects_unsupported_declared(
        self,
    ) -> None:
        with pytest.raises(MimeTypeNotAllowedError):
            await validate_upload_stream(
                _stream_of(b"%PDF-1.7 valid-looking"),
                declared_content_type="application/x-msdownload",
                allowed_mime_types=ALLOWED,
            )

    @pytest.mark.asyncio
    async def test_stream_validation_truncated(self) -> None:
        with pytest.raises(TruncatedFileError):
            await validate_upload_stream(
                _stream_of(b"%PD"),
                declared_content_type="application/pdf",
                allowed_mime_types=ALLOWED,
            )

    @pytest.mark.asyncio
    async def test_sniff_consumes_at_most_window(self) -> None:
        """Bounded memory: validation pulls only the sniff window from a
        large stream (the rest stays untouched for the replay)."""
        pulled: list[int] = []

        async def big_stream() -> AsyncIterator[bytes]:
            # First chunk carries a valid signature; later chunks would
            # blow the window if validation were unbounded. Record the
            # size BEFORE yielding (the generator only resumes when the
            # consumer pulls the next chunk).
            pulled.append(32)
            yield VALID_SAMPLES["application/pdf"][:32]
            for _ in range(10):
                pulled.append(4096)
                yield b"x" * 4096

        replay = await validate_upload_stream(
            big_stream(),
            declared_content_type="application/pdf",
            allowed_mime_types=ALLOWED,
        )
        # Validation itself pulled only the first chunk
        assert sum(pulled) == 32
        # The replay still delivers everything
        assert len(await _collect(replay)) == 32 + 10 * 4096
