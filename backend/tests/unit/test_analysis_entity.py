from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.analysis import (
    CANCELLED,
    COMPLETED,
    FAILED,
    PENDING,
    RUNNING,
    Analysis,
    AnalysisResult,
    AnalysisStateError,
)


def _analysis(**overrides: object) -> Analysis:
    values: dict[str, object] = {
        "id": uuid4(),
        "digital_asset_id": uuid4(),
        "requested_by": uuid4(),
        "analyzer_key": "metadata",
        "analyzer_version": "1.0.0",
    }
    values.update(overrides)
    return Analysis(**values)


def _result(**overrides: object) -> AnalysisResult:
    values: dict[str, object] = {
        "verdict": "informational",
        "evidence": {"file_type": "pdf"},
        "confidence": 1.0,
        "recommendation": "review",
    }
    values.update(overrides)
    return AnalysisResult(**values)


def test_valid_analysis_creation_references_one_asset() -> None:
    analysis = _analysis()

    assert analysis.status == PENDING
    assert analysis.digital_asset_id is not None
    assert analysis.result is None


def test_missing_asset_reference_is_rejected() -> None:
    with pytest.raises(AnalysisStateError, match="digital_asset_id"):
        _analysis(digital_asset_id=None)


def test_valid_lifecycle_transitions() -> None:
    pending = _analysis()
    running = pending.start()
    completed = running.complete(_result())

    assert running.status == RUNNING
    assert completed.status == COMPLETED
    assert completed.result == _result()
    assert completed.completed_at is not None


def test_invalid_lifecycle_transition_is_rejected() -> None:
    with pytest.raises(AnalysisStateError):
        _analysis().complete(_result())

    with pytest.raises(AnalysisStateError):
        _analysis().fail("worker error")

    with pytest.raises(AnalysisStateError):
        _analysis().start().start()


def test_completed_analysis_requires_result() -> None:
    with pytest.raises(AnalysisStateError, match="require a result"):
        _analysis(status=COMPLETED, completed_at=datetime.now(tz=UTC))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("verdict", "", "verdict"),
        ("evidence", None, "evidence"),
        ("confidence", 1.1, "confidence"),
        ("recommendation", "", "recommendation"),
    ],
)
def test_analysis_result_requires_all_components(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(AnalysisStateError, match=message):
        _result(**{field: value})


def test_terminal_completed_analysis_cannot_be_modified() -> None:
    completed = _analysis().start().complete(_result())

    with pytest.raises(AnalysisStateError, match="immutable"):
        completed.result = _result(verdict="changed")
    with pytest.raises(AnalysisStateError, match="immutable"):
        completed.digital_asset_id = uuid4()
    with pytest.raises(AnalysisStateError, match="immutable"):
        completed.status = RUNNING


def test_failed_analysis_is_terminal_and_cannot_restart() -> None:
    failed = _analysis().start().fail("analyzer unavailable", "ANALYZER_DOWN")

    assert failed.status == FAILED
    assert failed.error_message == "analyzer unavailable"
    assert failed.completed_at is not None

    with pytest.raises(AnalysisStateError, match="immutable"):
        failed.error_message = "changed"
    with pytest.raises(AnalysisStateError):
        failed.start()


def test_cancelled_analysis_is_terminal() -> None:
    cancelled = _analysis().cancel()

    assert cancelled.status == CANCELLED
    assert cancelled.completed_at is not None
    with pytest.raises(AnalysisStateError, match="immutable"):
        cancelled.retry_count = 1
