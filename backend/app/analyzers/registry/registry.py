"""Analyzer registration and lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.analyzers.base.analyzer import Analyzer


class AnalyzerRegistryError(ValueError):
    """Raised when analyzer registration or lookup is invalid."""


class AnalyzerRegistry:
    """Registry of analyzers keyed by their stable implementation identity."""

    def __init__(self, analyzers: Iterable[Analyzer] = ()) -> None:
        self._analyzers: dict[str, Analyzer] = {}
        for analyzer in analyzers:
            self.register(analyzer)

    def register(self, analyzer: Analyzer) -> None:
        """Register an analyzer, rejecting duplicate keys."""
        if not analyzer.key:
            raise AnalyzerRegistryError("analyzer key is required")
        if not analyzer.version:
            raise AnalyzerRegistryError("analyzer version is required")
        if analyzer.key in self._analyzers:
            raise AnalyzerRegistryError(
                f"Analyzer key {analyzer.key!r} is already registered"
            )
        self._analyzers[analyzer.key] = analyzer

    def get(self, key: str) -> Analyzer:
        """Return the analyzer registered under key."""
        try:
            return self._analyzers[key]
        except KeyError as exc:
            raise AnalyzerRegistryError(
                f"Analyzer key {key!r} is not registered"
            ) from exc

    def list(self) -> list[Analyzer]:
        """Return registered analyzers in registration order."""
        return list(self._analyzers.values())
