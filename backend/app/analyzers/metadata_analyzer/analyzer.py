"""Deterministic local metadata analyzer."""

from __future__ import annotations

import hashlib
import re
import struct
from typing import TYPE_CHECKING

from app.analyzers.base.analyzer import Analyzer
from app.domain.entities.analysis import AnalysisResult


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.domain.entities.digital_asset import DigitalAsset


class MetadataAnalyzer(Analyzer):
    """Extract file metadata without external services or database access."""

    @property
    def key(self) -> str:
        return "metadata"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def analyze(
        self,
        asset: DigitalAsset,
        content_stream: AsyncIterator[bytes],
    ) -> AnalysisResult:
        """Return deterministic metadata or a controlled failed result."""
        content = bytearray()
        async for chunk in content_stream:
            content.extend(chunk)

        try:
            evidence = self._extract(asset, bytes(content))
        except ValueError as exc:
            return AnalysisResult(
                verdict="failed",
                evidence={"error": str(exc)},
                confidence=0.0,
                recommendation="Unable to extract metadata; review the input",
            )

        return AnalysisResult(
            verdict="informational",
            evidence=evidence,
            confidence=1.0,
            recommendation="Informational metadata only; no security judgment",
        )

    @staticmethod
    def _extract(asset: DigitalAsset, content: bytes) -> dict[str, object]:
        if asset.asset_type != "file":
            raise ValueError("metadata analyzer requires a file asset")
        if not content:
            raise ValueError("content stream is empty")
        if not asset.mime_type:
            raise ValueError("file asset MIME type is required")
        if not asset.sha256_hash:
            raise ValueError("file asset SHA-256 identity is required")

        evidence: dict[str, object] = {
            "file_type": MetadataAnalyzer._file_type(asset.mime_type),
            "mime_type": asset.mime_type,
            "size_bytes": len(content),
            "sha256_hash": asset.sha256_hash,
        }
        if asset.size_bytes is not None and asset.size_bytes != len(content):
            raise ValueError("content size does not match asset metadata")

        detected_hash = hashlib.sha256(content).hexdigest()
        if detected_hash != asset.sha256_hash:
            raise ValueError("content hash does not match asset identity")

        if asset.mime_type == "application/pdf":
            evidence["page_count"] = MetadataAnalyzer._pdf_page_count(content)
        elif asset.mime_type == "image/png":
            evidence.update(MetadataAnalyzer._png_dimensions(content))
        elif asset.mime_type == "image/jpeg":
            evidence.update(MetadataAnalyzer._jpeg_dimensions(content))
        else:
            raise ValueError(f"unsupported metadata MIME type: {asset.mime_type}")
        return evidence

    @staticmethod
    def _file_type(mime_type: str) -> str:
        return {
            "application/pdf": "pdf",
            "image/png": "png",
            "image/jpeg": "jpeg",
        }.get(mime_type, mime_type)

    @staticmethod
    def _pdf_page_count(content: bytes) -> int:
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content:
            raise ValueError("content is not a valid PDF")
        count = len(re.findall(rb"/Type\s+/Page\b", content))
        if count == 0:
            raise ValueError("PDF contains no pages")
        return count

    @staticmethod
    def _png_dimensions(content: bytes) -> dict[str, int]:
        if len(content) < 24 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("content is not a valid PNG")
        if content[12:16] != b"IHDR":
            raise ValueError("PNG IHDR chunk is missing")
        width, height = struct.unpack(">II", content[16:24])
        if width == 0 or height == 0:
            raise ValueError("PNG dimensions are invalid")
        return {"width": width, "height": height}

    @staticmethod
    def _jpeg_dimensions(content: bytes) -> dict[str, int]:
        if len(content) < 4 or content[:2] != b"\xff\xd8":
            raise ValueError("content is not a valid JPEG")
        position = 2
        while position + 3 < len(content):
            if content[position] != 0xFF:
                position += 1
                continue
            marker = content[position + 1]
            position += 2
            if marker in (0xD8, 0xD9):
                continue
            if position + 2 > len(content):
                break
            segment_length = struct.unpack(">H", content[position : position + 2])[0]
            if segment_length < 2 or position + segment_length > len(content):
                break
            if marker in range(0xC0, 0xC4) or marker in range(0xC5, 0xC8):
                if segment_length < 7:
                    break
                height, width = struct.unpack(
                    ">HH", content[position + 3 : position + 7]
                )
                if width == 0 or height == 0:
                    break
                return {"width": width, "height": height}
            position += segment_length
        raise ValueError("JPEG dimensions could not be read")
