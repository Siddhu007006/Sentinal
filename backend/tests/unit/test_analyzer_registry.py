from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.analyzers.base.analyzer import Analyzer
from app.analyzers.registry.registry import AnalyzerRegistry, AnalyzerRegistryError
from app.domain.entities.analysis import AnalysisResult
from app.domain.entities.digital_asset import DigitalAsset


if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class ExampleAnalyzer(Analyzer):
    @property
    def key(self) -> str:
        return "example"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def analyze(
        self,
        asset: DigitalAsset,
        content_stream: AsyncIterator[bytes],
    ) -> AnalysisResult:
        del asset, content_stream
        return AnalysisResult(
            verdict="informational",
            evidence={"source": "test"},
            confidence=1.0,
            recommendation="review",
        )


class DuplicateAnalyzer(ExampleAnalyzer):
    @property
    def key(self) -> str:
        return "example"


class MissingKeyAnalyzer(Analyzer):
    @property
    def key(self) -> str:
        return ""

    @property
    def version(self) -> str:
        return "1.0.0"

    async def analyze(
        self,
        asset: DigitalAsset,
        content_stream: AsyncIterator[bytes],
    ) -> AnalysisResult:
        del asset, content_stream
        raise NotImplementedError


class IncompleteAnalyzer(Analyzer):
    pass


def test_incomplete_analyzer_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        IncompleteAnalyzer()


def test_concrete_analyzer_satisfies_contract() -> None:
    analyzer = ExampleAnalyzer()
    result = analyzer.analyze

    assert analyzer.key == "example"
    assert analyzer.version == "1.0.0"
    assert result.__annotations__["return"] == "AnalysisResult"


@pytest.mark.asyncio
async def test_concrete_analyzer_returns_canonical_analysis_result() -> None:
    analyzer = ExampleAnalyzer()
    asset = DigitalAsset.create_ioc(
        user_id=uuid4(),
        asset_type="domain",
        raw_value="example.com",
        normalized_value="example.com",
        id=uuid4(),
    )

    result = await analyzer.analyze(asset, iter(()))

    assert isinstance(result, AnalysisResult)
    assert result.verdict == "informational"


def test_analysis_result_validation_is_canonical() -> None:
    valid = AnalysisResult("safe", {"signal": "none"}, 0.9, "monitor")

    assert valid.confidence == 0.9
    with pytest.raises(ValueError, match="verdict"):
        AnalysisResult("", {}, 0.9, "monitor")
    with pytest.raises(ValueError, match="evidence"):
        AnalysisResult("safe", None, 0.9, "monitor")
    with pytest.raises(ValueError, match="confidence"):
        AnalysisResult("safe", {}, 1.1, "monitor")
    with pytest.raises(ValueError, match="recommendation"):
        AnalysisResult("safe", {}, 0.9, "")


def test_registry_registers_retrieves_and_lists_analyzers() -> None:
    analyzer = ExampleAnalyzer()
    registry = AnalyzerRegistry()

    registry.register(analyzer)

    assert registry.get("example") is analyzer
    assert registry.list() == [analyzer]


def test_registry_rejects_unknown_key() -> None:
    with pytest.raises(AnalyzerRegistryError, match="not registered"):
        AnalyzerRegistry().get("missing")


def test_registry_rejects_duplicate_key() -> None:
    registry = AnalyzerRegistry([ExampleAnalyzer()])

    with pytest.raises(AnalyzerRegistryError, match="already registered"):
        registry.register(DuplicateAnalyzer())


def test_registry_rejects_missing_analyzer_key() -> None:
    with pytest.raises(AnalyzerRegistryError, match="key is required"):
        AnalyzerRegistry().register(MissingKeyAnalyzer())
