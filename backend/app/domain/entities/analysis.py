"""Pure domain model for an analysis job and its result."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar


if TYPE_CHECKING:
    from uuid import UUID


PENDING = "pending"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"
VALID_STATUSES = (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
TERMINAL_STATUSES = (COMPLETED, FAILED, CANCELLED)


class AnalysisStateError(ValueError):
    """Raised when an analysis violates lifecycle or result invariants."""


@dataclass(frozen=True)
class AnalysisResult:
    """Validated result returned by an analyzer."""

    verdict: str
    evidence: Any
    confidence: float
    recommendation: str

    def __post_init__(self) -> None:
        if not self.verdict or not isinstance(self.verdict, str):
            raise AnalysisStateError("result.verdict is required")
        if self.evidence is None:
            raise AnalysisStateError("result.evidence is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise AnalysisStateError("result.confidence must be between 0 and 1")
        if not self.recommendation or not isinstance(self.recommendation, str):
            raise AnalysisStateError("result.recommendation is required")


@dataclass
class Analysis:
    """An analysis tied to exactly one digital asset."""

    id: UUID
    digital_asset_id: UUID
    requested_by: UUID
    analyzer_key: str
    analyzer_version: str
    status: str = PENDING
    result: AnalysisResult | None = None
    threat_score: float | None = None
    error_message: str | None = None
    error_code: str | None = None
    analyzer_slugs: str | None = None
    retry_count: int = 0
    celery_task_id: str | None = None
    confidence: float | None = None
    severity: str | None = None
    reasoning_payload: str | None = None
    enrichment_data: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime | None = None
    _initialized: bool = field(default=False, init=False, repr=False)
    _terminal_statuses: ClassVar[tuple[str, ...]] = TERMINAL_STATUSES

    def __post_init__(self) -> None:
        self.validate()
        super().__setattr__("_initialized", True)

    def __setattr__(self, name: str, value: object) -> None:
        if (
            self.__dict__.get("_initialized")
            and self.__dict__.get("status") in self._terminal_statuses
        ):
            raise AnalysisStateError(
                "Terminal analyses are immutable; create a new analysis to re-run"
            )
        super().__setattr__(name, value)

    def validate(self) -> None:
        """Validate identity, lifecycle, and completed-result invariants."""
        if self.digital_asset_id is None:
            raise AnalysisStateError("digital_asset_id is required")
        if self.status not in VALID_STATUSES:
            raise AnalysisStateError(
                f"Invalid status {self.status!r}; expected one of {VALID_STATUSES}"
            )
        if not self.analyzer_key or not self.analyzer_version:
            raise AnalysisStateError("analyzer_key and analyzer_version are required")
        if self.retry_count < 0:
            raise AnalysisStateError("retry_count must be non-negative")
        if self.status == COMPLETED and self.result is None:
            raise AnalysisStateError("completed analyses require a result")
        if self.status == FAILED and not self.error_message:
            raise AnalysisStateError("failed analyses require an error_message")
        if self.status in TERMINAL_STATUSES and self.completed_at is None:
            raise AnalysisStateError("terminal analyses require completed_at")
        if self.status not in TERMINAL_STATUSES and self.completed_at is not None:
            raise AnalysisStateError("non-terminal analyses cannot have completed_at")

    def start(self) -> Analysis:
        """Transition pending -> running."""
        self._require_status(PENDING, "start")
        now = datetime.now(tz=UTC)
        return replace(self, status=RUNNING, started_at=now, updated_at=now)

    def complete(self, result: AnalysisResult) -> Analysis:
        """Transition running -> completed with a validated result."""
        self._require_status(RUNNING, "complete")
        now = datetime.now(tz=UTC)
        return replace(
            self, status=COMPLETED, result=result, completed_at=now, updated_at=now
        )

    def fail(self, error_message: str, error_code: str | None = None) -> Analysis:
        """Transition running -> failed with an actionable error."""
        self._require_status(RUNNING, "fail")
        if not error_message:
            raise AnalysisStateError("error_message is required")
        now = datetime.now(tz=UTC)
        return replace(
            self,
            status=FAILED,
            error_message=error_message,
            error_code=error_code,
            completed_at=now,
            updated_at=now,
        )

    def cancel(self) -> Analysis:
        """Transition pending or running -> cancelled."""
        if self.status not in (PENDING, RUNNING):
            raise AnalysisStateError(
                f"Cannot cancel analysis from status {self.status!r}"
            )
        now = datetime.now(tz=UTC)
        return replace(self, status=CANCELLED, completed_at=now, updated_at=now)

    def _require_status(self, expected: str, operation: str) -> None:
        if self.status != expected:
            raise AnalysisStateError(
                f"Cannot {operation} analysis from status {self.status!r}; "
                f"expected {expected!r}"
            )
