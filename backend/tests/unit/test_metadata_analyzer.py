from __future__ import annotations

import hashlib
import struct
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.analyzers.metadata_analyzer.analyzer import MetadataAnalyzer
from app.analyzers.registry.registry import AnalyzerRegistry
from app.domain.entities.analysis import AnalysisResult
from app.domain.entities.digital_asset import DigitalAsset


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable


def _asset(content: bytes, mime_type: str) -> DigitalAsset:
    digest = hashlib.sha256(content).hexdigest()
    return DigitalAsset.create_file(
        user_id=uuid4(),
        sha256_hash=digest,
        mime_type=mime_type,
        size_bytes=len(content),
        raw_value="fixture",
        id=uuid4(),
    )


async def _stream(content: bytes) -> AsyncIterator[bytes]:
    for start in range(0, len(content), 5):
        yield content[start : start + 5]


def _pdf() -> bytes:
    return (
        b"%PDF-1.7\n"
        b"1 0 obj << /Type /Pages /Count 2 >> endobj\n"
        b"2 0 obj << /Type /Page /Parent 1 0 R >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 1 0 R >> endobj\n"
        b"%%EOF"
    )


def _png() -> bytes:
    header = b"\x89PNG\r\n\x1a\n"
    return header + struct.pack(">I4sIIBBBBB", 13, b"IHDR", 640, 480, 8, 2, 0, 0, 0)


def _jpeg() -> bytes:
    sof = b"\xff\xc0\x00\x0b\x08\x00\x20\x00\x30\x03\x01\x11\x00"
    return b"\xff\xd8" + sof + b"\xff\xd9"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content_factory", "mime_type", "expected"),
    [
        (_pdf, "application/pdf", {"file_type": "pdf", "page_count": 2}),
        (_jpeg, "image/jpeg", {"file_type": "jpeg", "width": 48, "height": 32}),
        (_png, "image/png", {"file_type": "png", "width": 640, "height": 480}),
    ],
)
async def test_metadata_analyzer_extracts_file_metadata(
    content_factory: Callable[[], bytes],
    mime_type: str,
    expected: dict[str, object],
) -> None:
    content = content_factory()
    asset = _asset(content, mime_type)

    result = await MetadataAnalyzer().analyze(asset, _stream(content))

    assert isinstance(result, AnalysisResult)
    assert result.verdict == "informational"
    assert result.confidence == 1.0
    assert result.evidence["mime_type"] == mime_type
    assert result.evidence["size_bytes"] == len(content)
    assert result.evidence["sha256_hash"] == asset.sha256_hash
    for key, value in expected.items():
        assert result.evidence[key] == value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "mime_type"),
    [
        (b"", "application/pdf"),
        (b"not a pdf", "application/pdf"),
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"plain text", "application/octet-stream"),
    ],
)
async def test_malformed_or_unsupported_content_returns_failed_result(
    content: bytes,
    mime_type: str,
) -> None:
    asset = _asset(content or b"placeholder", mime_type)

    result = await MetadataAnalyzer().analyze(asset, _stream(content))

    assert result.verdict == "failed"
    assert result.confidence == 0.0
    assert result.evidence["error"]


def test_metadata_analyzer_identity_and_registry_discovery() -> None:
    analyzer = MetadataAnalyzer()
    registry = AnalyzerRegistry([analyzer])

    assert analyzer.key == "metadata"
    assert analyzer.version == "1.0.0"
    assert registry.get("metadata") is analyzer
