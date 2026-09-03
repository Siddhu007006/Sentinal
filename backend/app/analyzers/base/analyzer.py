"""Infrastructure-independent analyzer contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.domain.entities.analysis import AnalysisResult
    from app.domain.entities.digital_asset import DigitalAsset


class Analyzer(ABC):
    """Base interface implemented by every analysis provider."""

    @property
    @abstractmethod
    def key(self) -> str:
        """Stable analyzer identity used for analysis idempotency."""
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        """Analyzer implementation version used for idempotency."""
        raise NotImplementedError

    @abstractmethod
    async def analyze(
        self,
        asset: DigitalAsset,
        content_stream: AsyncIterator[bytes],
    ) -> AnalysisResult:
        """Analyze an asset and return the canonical domain result."""
        raise NotImplementedError
