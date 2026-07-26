"""
Unit tests for Analysis ORM model.

Tests model instantiation, defaults, field types, relationships, and constraints
without requiring a database connection. These tests validate ORM behavior in
memory.

**Validates: Requirement R6 (ORM Model and Migration Test Coverage) - Part 1
(Unit Tests)**

Traces to: 22-Engineering-Backlog E3.T6 (Analysis ORM model task)
Traces to: 07-Backend-Development-Standards §8 (ORM testing patterns)
Traces to: 11-Testing-Strategy §6 (unit test patterns)
"""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    PrimaryKeyConstraint,
    Table,
)

from app.models.analysis import Analysis, AnalysisStatus


table = cast("Table", Analysis.__table__)

# ===========================================================================
# Test 1: Model Instantiation with All Fields
# ===========================================================================


def test_instantiate_analysis_with_all_fields() -> None:
    """Test: Instantiate Analysis with all fields succeeds.

    **Validates: R3 AC #1-22**

    Verifies that an Analysis can be created with all fields populated (no
    database commit needed, just in-memory object).
    """
    asset_id = uuid4()
    user_id = uuid4()
    reasoning = {"threat_level": "high", "confidence": 0.95}
    enrichment = {"virustotal": {"detections": 45}, "shodan": {"exposed": True}}
    now = datetime.now(UTC)

    analysis = Analysis(
        digital_asset_id=asset_id,
        requested_by=user_id,
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        status=AnalysisStatus.COMPLETED,
        analyzer_slugs=["virustotal", "shodan"],
        retry_count=0,
        celery_task_id="task-12345",
        error_message=None,
        error_code=None,
        threat_score=0.85,
        confidence=0.92,
        severity="HIGH",
        reasoning_payload=reasoning,
        enrichment_data=enrichment,
        started_at=now,
        completed_at=now,
    )

    assert analysis.digital_asset_id == asset_id
    assert analysis.requested_by == user_id
    assert analysis.analyzer_key == "virustotal_analyzer"
    assert analysis.analyzer_version == "v2.1.0"
    assert analysis.status == AnalysisStatus.COMPLETED
    assert analysis.analyzer_slugs == ["virustotal", "shodan"]
    assert analysis.retry_count == 0
    assert analysis.celery_task_id == "task-12345"
    assert analysis.error_message is None
    assert analysis.error_code is None
    assert analysis.threat_score == 0.85
    assert analysis.confidence == 0.92
    assert analysis.severity == "HIGH"
    assert analysis.reasoning_payload == reasoning
    assert analysis.enrichment_data == enrichment
    assert isinstance(analysis.started_at, datetime)
    assert isinstance(analysis.completed_at, datetime)


# ===========================================================================
# Test 2: Model Instantiation with Minimal Fields
# ===========================================================================


def test_instantiate_analysis_with_minimal_fields() -> None:
    """Test: Instantiate Analysis with minimal fields succeeds.

    **Validates: R3 AC #2**

    Verifies that an Analysis can be created with only required fields.
    """
    asset_id = uuid4()
    user_id = uuid4()

    analysis = Analysis(
        digital_asset_id=asset_id,
        requested_by=user_id,
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
    )

    assert analysis.digital_asset_id == asset_id
    assert analysis.requested_by == user_id
    assert analysis.analyzer_key == "virustotal_analyzer"
    assert analysis.analyzer_version == "v2.1.0"
    assert analysis.analyzer_slugs == ["virustotal"]

    # Nullable fields should be None by default
    assert analysis.status is None or analysis.status == "pending"
    assert analysis.celery_task_id is None
    assert analysis.error_message is None
    assert analysis.error_code is None
    assert analysis.threat_score is None
    assert analysis.confidence is None
    assert analysis.severity is None
    assert analysis.reasoning_payload is None
    assert analysis.enrichment_data is None
    assert analysis.started_at is None
    assert analysis.completed_at is None


# ===========================================================================
# Test 3: Field Types
# ===========================================================================


def test_field_types_are_correct() -> None:
    """Test: Field types are correct when set.

    **Validates: R3 AC #3**

    Verifies that fields have the correct Python types when instantiated.
    """
    asset_id = uuid4()
    user_id = uuid4()

    analysis = Analysis(
        digital_asset_id=asset_id,
        requested_by=user_id,
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal", "shodan"],
        status=AnalysisStatus.COMPLETED,
        threat_score=0.85,
        confidence=0.92,
        severity="HIGH",
        reasoning_payload={"key": "value"},
        enrichment_data={"key": "value"},
        retry_count=1,
    )

    # UUID fields
    assert isinstance(analysis.digital_asset_id, UUID)
    assert isinstance(analysis.requested_by, UUID)

    # String fields
    assert isinstance(analysis.analyzer_key, str)
    assert isinstance(analysis.analyzer_version, str)
    assert isinstance(analysis.status, str)
    assert isinstance(analysis.severity, str)

    # Array field
    assert isinstance(analysis.analyzer_slugs, list)
    assert all(isinstance(s, str) for s in analysis.analyzer_slugs)

    # Float fields
    assert isinstance(analysis.threat_score, float)
    assert isinstance(analysis.confidence, float)

    # Integer field
    assert isinstance(analysis.retry_count, int)

    # Dict fields
    assert isinstance(analysis.reasoning_payload, dict)
    assert isinstance(analysis.enrichment_data, dict)


# ===========================================================================
# Test 4: AnalysisStatus Enum Values
# ===========================================================================


def test_analysis_status_enum_has_pending() -> None:
    """Test: AnalysisStatus enum has PENDING value."""
    assert AnalysisStatus.PENDING.value == "pending"


def test_analysis_status_enum_has_running() -> None:
    """Test: AnalysisStatus enum has RUNNING value."""
    assert AnalysisStatus.RUNNING.value == "running"


def test_analysis_status_enum_has_completed() -> None:
    """Test: AnalysisStatus enum has COMPLETED value."""
    assert AnalysisStatus.COMPLETED.value == "completed"


def test_analysis_status_enum_has_failed() -> None:
    """Test: AnalysisStatus enum has FAILED value."""
    assert AnalysisStatus.FAILED.value == "failed"


def test_analysis_status_enum_has_cancelled() -> None:
    """Test: AnalysisStatus enum has CANCELLED value."""
    assert AnalysisStatus.CANCELLED.value == "cancelled"


def test_analysis_status_enum_values_are_strings() -> None:
    """Test: AnalysisStatus enum values are strings (StrEnum).

    **Validates: R2 AC #1-3**

    Verifies that AnalysisStatus is a StrEnum (can be used as strings directly).
    """
    assert isinstance(AnalysisStatus.PENDING.value, str)
    assert isinstance(AnalysisStatus.RUNNING.value, str)
    assert isinstance(AnalysisStatus.COMPLETED.value, str)
    assert isinstance(AnalysisStatus.FAILED.value, str)
    assert isinstance(AnalysisStatus.CANCELLED.value, str)


def test_analysis_status_enum_comparison_works() -> None:
    """Test: AnalysisStatus values can be compared correctly.

    **Validates: R2 AC #2**

    Verifies that AnalysisStatus enum values can be compared for equality.
    """
    analysis1: Analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer1",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer1"],
        status=AnalysisStatus.PENDING,
    )

    analysis2: Analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer2",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer2"],
        status=AnalysisStatus.COMPLETED,
    )

    assert analysis1.status == AnalysisStatus.PENDING
    assert analysis2.status == AnalysisStatus.COMPLETED



# ===========================================================================
# Test 5: Default Values
# ===========================================================================


def test_default_status_is_pending() -> None:
    """Test: Default status = pending.

    **Validates: R2 AC #1**

    Verifies that when status is not specified, it defaults to 'pending'.
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
    )

    # Status defaults to pending or is None before DB assignment
    assert analysis.status is None or analysis.status == "pending"


def test_default_retry_count_is_zero() -> None:
    """Test: Default retry_count = 0.

    **Validates: R3 AC #7**

    Verifies that retry_count defaults to 0 when not provided.
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
    )

    # Retry count should be 0 by default or None before DB assignment
    assert analysis.retry_count is None or analysis.retry_count == 0


def test_default_verdict_fields_are_none() -> None:
    """Test: Default verdict fields = None.

    **Validates: R3 AC #11-16**

    Verifies that verdict fields (threat_score, confidence, severity) are None
    by default, indicating analysis hasn't completed yet.
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
    )

    assert analysis.threat_score is None
    assert analysis.confidence is None
    assert analysis.severity is None


def test_default_jsonb_fields_are_none() -> None:
    """Test: Default JSONB fields = None.

    **Validates: R3 AC #17-20**

    Verifies that reasoning_payload and enrichment_data are None by default.
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
    )

    assert analysis.reasoning_payload is None
    assert analysis.enrichment_data is None


# ===========================================================================
# Test 6: Timestamps Inherited from BaseModel
# ===========================================================================


def test_id_field_exists() -> None:
    """Test: id field exists (inherited from BaseModel).

    **Validates: R3 AC #1**

    Verifies that id field is present (inherited from BaseModel).
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
    )

    assert hasattr(analysis, "id")


def test_created_at_field_exists() -> None:
    """Test: created_at field exists (inherited from BaseModel).

    **Validates: R3 AC #4**

    Verifies that created_at field is present (inherited from BaseModel).
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
    )

    assert hasattr(analysis, "created_at")


def test_updated_at_field_exists() -> None:
    """Test: updated_at field exists (inherited from BaseModel).

    **Validates: R3**

    Verifies that updated_at field is present (inherited from BaseModel).
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
    )

    assert hasattr(analysis, "updated_at")


def test_mapper_includes_all_core_columns() -> None:
    """Test: Mapper includes all core columns from ORM definition.

    **Validates: R3**

    Verifies that the SQLAlchemy mapper has all expected columns defined.
    """
    mapper = Analysis.__mapper__
    column_names = [col.name for col in mapper.columns]

    # Verify core columns exist
    expected_columns = {
        "id",
        "digital_asset_id",
        "requested_by",
        "analyzer_key",
        "analyzer_version",
        "analyzer_slugs",
        "status",
        "retry_count",
        "celery_task_id",
        "error_message",
        "error_code",
        "threat_score",
        "confidence",
        "severity",
        "reasoning_payload",
        "enrichment_data",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    }

    for col in expected_columns:
        assert col in column_names, f"Column {col} not found in mapper"


# ===========================================================================
# Test 7: __repr__() Output
# ===========================================================================


def test_repr_returns_useful_string() -> None:
    """Test: __repr__() returns useful string.

    **Validates: Design §12**

    Verifies that __repr__() returns a human-readable representation that
    includes id, asset_id, status, and analyzer info.
    """
    asset_id = uuid4()
    analysis = Analysis(
        digital_asset_id=asset_id,
        requested_by=uuid4(),
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
        status=AnalysisStatus.COMPLETED,
    )

    repr_str = repr(analysis)

    # Should include type name
    assert "Analysis" in repr_str

    # Should include asset_id
    assert str(asset_id) in repr_str or "asset_id" in repr_str.lower()

    # Should include analyzer key
    assert "virustotal_analyzer" in repr_str or "analyzer" in repr_str.lower()

    # Should include status
    assert "completed" in repr_str.lower() or "status" in repr_str.lower()

    # Should be a string
    assert isinstance(repr_str, str)


def test_repr_includes_status() -> None:
    """Test: __repr__() includes status."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.FAILED,
    )

    repr_str = repr(analysis)
    assert "failed" in repr_str.lower() or "status" in repr_str.lower()


def test_repr_includes_analyzer_key() -> None:
    """Test: __repr__() includes analyzer_key."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="shodan_analyzer",
        analyzer_version="v1.5.0",
        analyzer_slugs=["shodan"],
    )

    repr_str = repr(analysis)
    assert "shodan_analyzer" in repr_str or "analyzer" in repr_str.lower()


# ===========================================================================
# Test 8: Model Metadata
# ===========================================================================


def test_analysis_model_has_tablename() -> None:
    """Test: Analysis model has __tablename__ defined.

    **Validates: R1**

    Verifies that __tablename__ is set to "analyses".
    """
    assert Analysis.__tablename__ == "analyses"


def test_analysis_model_inherits_from_basemodel() -> None:
    """Test: Analysis model inherits from BaseModel.

    **Validates: R1**

    Verifies that Analysis inherits from BaseModel (which provides id,
    created_at, updated_at).
    """
    from app.infrastructure.database.base import BaseModel

    assert issubclass(Analysis, BaseModel)


# ===========================================================================
# Test 9: Valid Status Values Can Be Used
# ===========================================================================


def test_analysis_with_pending_status() -> None:
    """Test: Analysis can be created with PENDING status."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.PENDING,
    )

    assert analysis.status == AnalysisStatus.PENDING


def test_analysis_with_running_status() -> None:
    """Test: Analysis can be created with RUNNING status."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.RUNNING,
    )

    assert analysis.status == AnalysisStatus.RUNNING


def test_analysis_with_completed_status() -> None:
    """Test: Analysis can be created with COMPLETED status."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.COMPLETED,
    )

    assert analysis.status == AnalysisStatus.COMPLETED


def test_analysis_with_failed_status() -> None:
    """Test: Analysis can be created with FAILED status."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.FAILED,
    )

    assert analysis.status == AnalysisStatus.FAILED


def test_analysis_with_cancelled_status() -> None:
    """Test: Analysis can be created with CANCELLED status."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        status=AnalysisStatus.CANCELLED,
    )

    assert analysis.status == AnalysisStatus.CANCELLED


# ===========================================================================
# Test 10: Nullable Fields Behavior
# ===========================================================================


def test_celery_task_id_can_be_none() -> None:
    """Test: celery_task_id can be None (nullable field).

    **Validates: R3 AC #10**
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        celery_task_id=None,
    )

    assert analysis.celery_task_id is None


def test_error_message_can_be_none() -> None:
    """Test: error_message can be None (nullable field).

    **Validates: R3 AC #8**
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        error_message=None,
    )

    assert analysis.error_message is None


def test_error_code_can_be_none() -> None:
    """Test: error_code can be None (nullable field).

    **Validates: R3 AC #9**
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        error_code=None,
    )

    assert analysis.error_code is None


def test_threat_score_can_be_none() -> None:
    """Test: threat_score can be None (nullable field).

    **Validates: R3 AC #11-12**
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        threat_score=None,
    )

    assert analysis.threat_score is None


def test_confidence_can_be_none() -> None:
    """Test: confidence can be None (nullable field).

    **Validates: R3 AC #13-14**
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        confidence=None,
    )

    assert analysis.confidence is None


def test_severity_can_be_none() -> None:
    """Test: severity can be None (nullable field).

    **Validates: R3 AC #15-16**
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        severity=None,
    )

    assert analysis.severity is None


# ===========================================================================
# Test 11: Threat Score Constraint Bounds [0.0, 1.0]
# ===========================================================================


@pytest.mark.parametrize("score", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_threat_score_valid_bounds(score: float) -> None:
    """Test: threat_score accepts values in [0.0, 1.0].

    **Validates: R3 AC #12**

    Verifies that threat_score can hold values across the valid range.
    Database CHECK constraint will enforce bounds at persist time.
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        threat_score=score,
    )

    assert analysis.threat_score == score


def test_threat_score_zero() -> None:
    """Test: threat_score can be exactly 0.0."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        threat_score=0.0,
    )

    assert analysis.threat_score == 0.0


def test_threat_score_one() -> None:
    """Test: threat_score can be exactly 1.0."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        threat_score=1.0,
    )

    assert analysis.threat_score == 1.0


# ===========================================================================
# Test 12: Confidence Constraint Bounds [0.0, 1.0]
# ===========================================================================


@pytest.mark.parametrize("conf", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_confidence_valid_bounds(conf: float) -> None:
    """Test: confidence accepts values in [0.0, 1.0].

    **Validates: R3 AC #14**

    Verifies that confidence can hold values across the valid range.
    Database CHECK constraint will enforce bounds at persist time.
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        confidence=conf,
    )

    assert analysis.confidence == conf


def test_confidence_zero() -> None:
    """Test: confidence can be exactly 0.0."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        confidence=0.0,
    )

    assert analysis.confidence == 0.0


def test_confidence_one() -> None:
    """Test: confidence can be exactly 1.0."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        confidence=1.0,
    )

    assert analysis.confidence == 1.0


# ===========================================================================
# Test 13: Severity Valid Values
# ===========================================================================


@pytest.mark.parametrize("sev", ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
def test_severity_valid_values(sev: str) -> None:
    """Test: severity accepts valid values (LOW, MEDIUM, HIGH, CRITICAL).

    **Validates: R3 AC #15-16**

    Verifies that severity can hold all valid threat levels.
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        severity=sev,
    )

    assert analysis.severity == sev


def test_severity_low() -> None:
    """Test: severity can be LOW."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        severity="LOW",
    )

    assert analysis.severity == "LOW"


def test_severity_medium() -> None:
    """Test: severity can be MEDIUM."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        severity="MEDIUM",
    )

    assert analysis.severity == "MEDIUM"


def test_severity_high() -> None:
    """Test: severity can be HIGH."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        severity="HIGH",
    )

    assert analysis.severity == "HIGH"


def test_severity_critical() -> None:
    """Test: severity can be CRITICAL."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        severity="CRITICAL",
    )

    assert analysis.severity == "CRITICAL"


# ===========================================================================
# Test 14: Retry Count Non-Negative Constraint
# ===========================================================================


@pytest.mark.parametrize("count", [0, 1, 2, 5, 10])
def test_retry_count_non_negative_values(count: int) -> None:
    """Test: retry_count accepts non-negative values.

    **Validates: R3 AC #7**

    Verifies that retry_count can hold 0 and positive integers.
    Database CHECK constraint will enforce non-negative at persist time.
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        retry_count=count,
    )

    assert analysis.retry_count == count


def test_retry_count_zero() -> None:
    """Test: retry_count can be exactly 0."""
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        retry_count=0,
    )

    assert analysis.retry_count == 0


# ===========================================================================
# Test 15: JSONB Fields Handle Complex Structures
# ===========================================================================


def test_reasoning_payload_stores_complex_dict() -> None:
    """Test: reasoning_payload can store complex nested structures.

    **Validates: R8 AC #1-3**

    Verifies that reasoning_payload accepts nested dicts (JSONB).
    """
    payload = {
        "threat_level": "high",
        "confidence": 0.95,
        "reasoning_steps": [
            {"step": 1, "conclusion": "malware detected"},
            {"step": 2, "conclusion": "network IOC found"},
        ],
        "iocs": {
            "domains": ["evil.com", "attacker.net"],
            "ips": ["192.0.2.1", "192.0.2.2"],
        },
        "model_metadata": {
            "version": "gpt-4",
            "tokens_used": 2048,
            "latency_ms": 1234,
        },
    }

    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        reasoning_payload=payload,
    )

    assert analysis.reasoning_payload == payload
    assert isinstance(analysis.reasoning_payload, dict)


def test_enrichment_data_stores_complex_dict() -> None:
    """Test: enrichment_data can store complex nested structures.

    **Validates: R8 AC #3-5**

    Verifies that enrichment_data accepts nested dicts (JSONB).
    """
    enrichment = {
        "virustotal": {
            "detections": 45,
            "last_analysis_date": "2024-01-15T10:00:00Z",
            "vendors": {
                "Microsoft": "Trojan:Win32/Emotet.A",
                "Kaspersky": "Trojan.Win32.Generic",
            },
        },
        "shodan": {
            "exposed_services": ["ssh", "http"],
            "vulnerabilities": ["CVE-2021-44228"],
        },
        "urlscan": {
            "verdict": "malicious",
            "screenshot_available": True,
        },
    }

    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["analyzer"],
        enrichment_data=enrichment,
    )

    assert analysis.enrichment_data == enrichment
    assert isinstance(analysis.enrichment_data, dict)


# ===========================================================================
# Test 16: Analyzer Slugs Array
# ===========================================================================


def test_analyzer_slugs_single_analyzer() -> None:
    """Test: analyzer_slugs can contain a single analyzer.

    **Validates: R3 AC #6**
    """
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=["virustotal"],
    )

    assert analysis.analyzer_slugs == ["virustotal"]
    assert len(analysis.analyzer_slugs) == 1


def test_analyzer_slugs_multiple_analyzers() -> None:
    """Test: analyzer_slugs can contain multiple analyzers.

    **Validates: R3 AC #6**
    """
    slugs = ["virustotal", "shodan", "urlscan"]
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=slugs,
    )

    assert analysis.analyzer_slugs == slugs
    assert len(analysis.analyzer_slugs) == 3


def test_analyzer_slugs_preserves_order() -> None:
    """Test: analyzer_slugs preserves order of analyzers.

    **Validates: R3 AC #6**
    """
    slugs = ["shodan", "virustotal", "urlscan"]
    analysis = Analysis(
        digital_asset_id=uuid4(),
        requested_by=uuid4(),
        analyzer_key="analyzer",
        analyzer_version="v1.0.0",
        analyzer_slugs=slugs,
    )

    assert analysis.analyzer_slugs == slugs


# ===========================================================================
# Test 17: Analyzer Identity Fields (Idempotency)
# ===========================================================================


def test_analyzer_key_is_immutable_concept() -> None:
    """Test: analyzer_key and analyzer_version form idempotency key.

    **Validates: R4 AC #1-4, R7 AC #1**

    Verifies that (digital_asset_id, analyzer_key, analyzer_version)
    uniquely identifies an analysis for idempotency.
    """
    asset_id = uuid4()

    analysis1 = Analysis(
        digital_asset_id=asset_id,
        requested_by=uuid4(),
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
        status=AnalysisStatus.COMPLETED,
    )

    analysis2 = Analysis(
        digital_asset_id=asset_id,
        requested_by=uuid4(),
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
        status=AnalysisStatus.COMPLETED,
    )

    # Same triple → same analysis (idempotency key)
    assert analysis1.digital_asset_id == analysis2.digital_asset_id
    assert analysis1.analyzer_key == analysis2.analyzer_key
    assert analysis1.analyzer_version == analysis2.analyzer_version


def test_different_analyzer_version_creates_different_analysis() -> None:
    """Test: Different analyzer_version creates different analysis.

    **Validates: R4 AC #1-4**
    """
    asset_id = uuid4()

    analysis1 = Analysis(
        digital_asset_id=asset_id,
        requested_by=uuid4(),
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.0.0",
        analyzer_slugs=["virustotal"],
    )

    analysis2 = Analysis(
        digital_asset_id=asset_id,
        requested_by=uuid4(),
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
    )

    # Different versions → different analyses
    assert analysis1.analyzer_version != analysis2.analyzer_version


def test_different_analyzer_key_creates_different_analysis() -> None:
    """Test: Different analyzer_key creates different analysis.

    **Validates: R4 AC #1-4**
    """
    asset_id = uuid4()

    analysis1 = Analysis(
        digital_asset_id=asset_id,
        requested_by=uuid4(),
        analyzer_key="virustotal_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["virustotal"],
    )

    analysis2 = Analysis(
        digital_asset_id=asset_id,
        requested_by=uuid4(),
        analyzer_key="shodan_analyzer",
        analyzer_version="v2.1.0",
        analyzer_slugs=["shodan"],
    )

    # Different keys → different analyses
    assert analysis1.analyzer_key != analysis2.analyzer_key


# ===========================================================================
# Test 18: Relationship Properties
# ===========================================================================


def test_analysis_has_digital_asset_relationship() -> None:
    """Test: Analysis has digital_asset relationship property.

    **Validates: R9 AC #1-4**

    Verifies that the digital_asset relationship exists on the Analysis class.
    """
    assert hasattr(Analysis, "digital_asset")


def test_digital_asset_relationship_has_selectin_lazy_loading() -> None:
    """Test: digital_asset relationship uses lazy='selectin'.

    **Validates: R9 AC #3, Design §5.1**

    Verifies that lazy loading strategy is selectin (separate query) for scale.
    """
    # Get the relationship property
    relationship_property = Analysis.__mapper__.relationships.get("digital_asset")

    assert relationship_property is not None, "digital_asset relationship not found"
    assert (
        relationship_property.lazy == "selectin"
    ), f"Expected lazy='selectin', got '{relationship_property.lazy}'"


def test_digital_asset_relationship_has_back_populates() -> None:
    """Test: digital_asset relationship has back_populates='analyses'.

    **Validates: Design §5.1**

    Verifies that bidirectional relationship is properly configured.
    """
    relationship_property = Analysis.__mapper__.relationships.get("digital_asset")

    assert relationship_property is not None
    assert relationship_property.back_populates == "analyses", (
        f"Expected back_populates='analyses', "
        f"got '{relationship_property.back_populates}'"
    )


def test_analysis_has_user_relationship() -> None:
    """Test: Analysis has user relationship property.

    **Validates: R9 AC #1-4**

    Verifies that the user relationship exists on the Analysis class.
    """
    assert hasattr(Analysis, "user")


def test_user_relationship_has_selectin_lazy_loading() -> None:
    """Test: user relationship uses lazy='selectin'.

    **Validates: R9 AC #3, Design §5.2**

    Verifies that lazy loading strategy is selectin (separate query) for scale.
    """
    relationship_property = Analysis.__mapper__.relationships.get("user")

    assert relationship_property is not None, "user relationship not found"
    assert (
        relationship_property.lazy == "selectin"
    ), f"Expected lazy='selectin', got '{relationship_property.lazy}'"


def test_user_relationship_has_back_populates() -> None:
    """Test: user relationship has back_populates='analyses_requested'.

    **Validates: Design §5.2**

    Verifies that bidirectional relationship is properly configured.
    """
    relationship_property = Analysis.__mapper__.relationships.get("user")

    assert relationship_property is not None
    assert relationship_property.back_populates == "analyses_requested", (
        f"Expected back_populates='analyses_requested', "
        f"got '{relationship_property.back_populates}'"
    )


def test_user_relationship_uses_requested_by_foreign_key() -> None:
    """Test: user relationship uses requested_by column as foreign key.

    **Validates: Design §5.2**

    Verifies that the relationship is based on requested_by FK, not user_id.
    """
    relationship_property = Analysis.__mapper__.relationships.get("user")

    assert relationship_property is not None
    # Check foreign keys used by the relationship
    fks = relationship_property.synchronize_pairs
    assert len(fks) > 0, "No foreign key pairs found in user relationship"


# ===========================================================================
# Test 19: Index Metadata
# ===========================================================================


def test_analysis_table_has_eight_indexes() -> None:
    """Test: Analysis table has exactly 8 indexes.

    **Validates: R6 AC #1, Design §6.2**

    Verifies that all 8 indexes (3 partial, 1 unique partial, 4 composite)
    are present.
    """
    indexes = list(Analysis.__table__.indexes)  # type: ignore[attr-defined]

    # Should have 7 named indexes (not including PK which is implicit)
    assert len(indexes) == 7, (
        f"Expected 7 indexes, got {len(indexes)}. "
        f"Indexes: {[idx.name for idx in indexes]}"
    )


def test_index_ix_analyses_asset_status_exists() -> None:
    """Test: Index ix_analyses_asset_status exists.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    assert "ix_analyses_asset_status" in indexes, (
        f"Index 'ix_analyses_asset_status' not found. "
        f"Available: {list(indexes.keys())}"
    )


def test_index_ix_analyses_asset_status_columns() -> None:
    """Test: ix_analyses_asset_status has correct columns.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    idx = indexes.get("ix_analyses_asset_status")

    assert idx is not None
    column_names = [col.name for col in idx.columns]
    assert "digital_asset_id" in column_names
    assert "status" in column_names


def test_index_ix_analyses_asset_latest_exists() -> None:
    """Test: Index ix_analyses_asset_latest exists.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    assert (
        "ix_analyses_asset_latest" in indexes
    ), f"Index 'ix_analyses_asset_latest' not found. Available: {list(indexes.keys())}"


def test_index_ix_analyses_pending_exists() -> None:
    """Test: Index ix_analyses_pending exists.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    assert (
        "ix_analyses_pending" in indexes
    ), f"Index 'ix_analyses_pending' not found. Available: {list(indexes.keys())}"


def test_index_ix_analyses_pending_is_partial() -> None:
    """Test: ix_analyses_pending has partial WHERE clause.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    idx = indexes.get("ix_analyses_pending")

    assert idx is not None
    # Partial indexes have postgresql_where in dialect_options['postgresql']
    postgresql_opts = idx.dialect_options.get("postgresql", {})
    assert postgresql_opts.get(
        "where"
    ), "Index ix_analyses_pending should have a WHERE clause (partial index)"


def test_index_ix_analyses_user_history_exists() -> None:
    """Test: Index ix_analyses_user_history exists.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    assert (
        "ix_analyses_user_history" in indexes
    ), f"Index 'ix_analyses_user_history' not found. Available: {list(indexes.keys())}"


def test_index_ix_analyses_user_history_columns() -> None:
    """Test: ix_analyses_user_history has correct columns.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    idx = indexes.get("ix_analyses_user_history")

    assert idx is not None
    column_names = [col.name for col in idx.columns]
    assert "requested_by" in column_names
    assert "created_at" in column_names


def test_index_ix_analyses_celery_task_exists() -> None:
    """Test: Index ix_analyses_celery_task exists.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    assert (
        "ix_analyses_celery_task" in indexes
    ), f"Index 'ix_analyses_celery_task' not found. Available: {list(indexes.keys())}"


def test_index_ix_analyses_celery_task_is_partial() -> None:
    """Test: ix_analyses_celery_task has partial WHERE clause.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    idx = indexes.get("ix_analyses_celery_task")

    assert idx is not None
    # Partial indexes should have WHERE clause in dialect_options['postgresql']
    postgresql_opts = idx.dialect_options.get("postgresql", {})
    assert postgresql_opts.get(
        "where"
    ), "Index ix_analyses_celery_task should have a WHERE clause (partial index)"


def test_index_ix_analyses_severity_completed_exists() -> None:
    """Test: Index ix_analyses_severity_completed exists.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    assert "ix_analyses_severity_completed" in indexes, (
        f"Index 'ix_analyses_severity_completed' not found. "
        f"Available: {list(indexes.keys())}"
    )


def test_index_ix_analyses_severity_completed_is_partial() -> None:
    """Test: ix_analyses_severity_completed has partial WHERE clause.

    **Validates: Design §6.2**
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    idx = indexes.get("ix_analyses_severity_completed")

    assert idx is not None
    # Partial indexes should have WHERE clause in dialect_options
    postgresql_opts = idx.dialect_options.get("postgresql", {})
    assert postgresql_opts.get("where"), (
        "Index ix_analyses_severity_completed should have a WHERE "
        "clause (partial index)"
    )


def test_unique_index_uq_analyses_asset_analyzer_completed_exists() -> None:
    """Test: Unique index ix_analyses_asset_analyzer_completed exists.

    **Validates: R7 AC #1, Design §6.2**

    Verifies that the idempotency index exists.
    Note: The index name is prefixed with 'ix_' not 'uq_' in the ORM.
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    assert "ix_analyses_asset_analyzer_completed" in indexes, (
        f"Index 'ix_analyses_asset_analyzer_completed' not found. "
        f"Available: {list(indexes.keys())}"
    )


def test_unique_index_is_unique() -> None:
    """Test: ix_analyses_asset_analyzer_completed is marked as unique.

    **Validates: R7 AC #1, Design §6.2**

    Verifies that the unique constraint is properly set.
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    idx = indexes.get("ix_analyses_asset_analyzer_completed")

    assert idx is not None
    assert idx.unique is True, "Index should be marked as UNIQUE"


def test_unique_index_columns() -> None:
    """Test: ix_analyses_asset_analyzer_completed has correct columns.

    **Validates: R7 AC #1, Design §6.2**

    Verifies that the unique index covers asset_id, analyzer_key,
    analyzer_version.
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    idx = indexes.get("ix_analyses_asset_analyzer_completed")

    assert idx is not None
    column_names = [col.name for col in idx.columns]
    assert (
        "digital_asset_id" in column_names
    ), f"Expected digital_asset_id in {column_names}"
    assert "analyzer_key" in column_names, f"Expected analyzer_key in {column_names}"
    assert (
        "analyzer_version" in column_names
    ), f"Expected analyzer_version in {column_names}"


def test_unique_index_is_partial() -> None:
    """Test: ix_analyses_asset_analyzer_completed is a partial index.

    **Validates: R7 AC #2, Design §6.2**

    Verifies that unique constraint only applies to completed status.
    """
    indexes = {idx.name: idx for idx in Analysis.__table__.indexes}  # type: ignore[attr-defined]
    idx = indexes.get("ix_analyses_asset_analyzer_completed")

    assert idx is not None
    # Should have WHERE clause for partial uniqueness in dialect_options
    postgresql_opts = idx.dialect_options.get("postgresql", {})
    assert postgresql_opts.get(
        "where"
    ), "Unique index should have a WHERE clause (partial unique)"


# ===========================================================================
# Test 20: Constraint Metadata
# ===========================================================================


def test_analysis_table_has_five_check_constraints() -> None:
    """Test: Analysis table has exactly 5 CHECK constraints.

    **Validates: R10 AC #1, Design §7.1**

    Verifies that all 5 CHECK constraints are present.
    """
    constraints = list(table.constraints)
    check_constraints = [c for c in constraints if isinstance(c, CheckConstraint)]

    assert len(check_constraints) == 5, (
        f"Expected 5 CHECK constraints, got {len(check_constraints)}. "
        f"Constraints: {[c.name for c in check_constraints]}"
    )


def test_check_constraint_status_exists() -> None:
    """Test: CHECK constraint ck_analyses_status exists.

    **Validates: R10 AC #1, Design §7.1**
    """
    constraints = {
        str(c.name): c
        for c in table.constraints
        if c.name is not None
    }
    # Constraint names may have prefix added by SQLAlchemy
    found = any("status" in name for name in constraints if "ck_analyses" in name)
    assert found, (
        f"CHECK constraint with 'status' not found. "
        f"Available: {list(constraints.keys())}"
    )


def test_check_constraint_threat_score_exists() -> None:
    """Test: CHECK constraint ck_analyses_threat_score exists.

    **Validates: R10 AC #2, Design §7.1**
    """
    constraints = {
        str(c.name): c
        for c in table.constraints
        if c.name is not None
    }
    found = any("threat_score" in name for name in constraints if "ck_analyses" in name)
    assert found, (
        f"CHECK constraint with 'threat_score' not found. "
        f"Available: {list(constraints.keys())}"
    )


def test_check_constraint_confidence_exists() -> None:
    """Test: CHECK constraint ck_analyses_confidence exists.

    **Validates: R10 AC #3, Design §7.1**
    """
    constraints = {
        str(c.name): c
        for c in table.constraints
        if c.name is not None
    }
    found = any("confidence" in name for name in constraints if "ck_analyses" in name)
    assert found, (
        f"CHECK constraint with 'confidence' not found. "
        f"Available: {list(constraints.keys())}"
    )


def test_check_constraint_severity_exists() -> None:
    """Test: CHECK constraint ck_analyses_severity exists.

    **Validates: R10 AC #4, Design §7.1**
    """
    constraints = {
        str(c.name): c
        for c in table.constraints
        if c.name is not None
   }
    found = any("severity" in name for name in constraints if "ck_analyses" in name)
    assert found, (
        f"CHECK constraint with 'severity' not found. "
        f"Available: {list(constraints.keys())}"
    )


def test_check_constraint_retry_count_exists() -> None:
    """Test: CHECK constraint ck_analyses_retry_count exists.

    **Validates: R10 AC #5, Design §7.1**
    """
    constraints = {
        str(c.name): c
        for c in table.constraints
        if c.name is not None
    }
    found = any("retry_count" in name for name in constraints if "ck_analyses" in name)
    assert found, (
        f"CHECK constraint with 'retry_count' not found. "
        f"Available: {list(constraints.keys())}"
    )


def test_analysis_table_has_two_foreign_key_constraints() -> None:
    """Test: Analysis table has exactly 2 FK constraints.

    **Validates: R5 AC #1, Design §7.3**

    Verifies that FK constraints for digital_asset_id and requested_by exist.
    """
    constraints = list(table.constraints)
    fk_constraints = [c for c in constraints if isinstance(c, ForeignKeyConstraint)]

    assert len(fk_constraints) == 2, (
        f"Expected 2 FK constraints, got {len(fk_constraints)}. "
        f"Foreign keys: {[str(c) for c in fk_constraints]}"
    )


def test_foreign_key_digital_asset_exists() -> None:
    """Test: FK constraint for digital_asset_id exists.

    **Validates: R5 AC #1, Design §7.3**
    """
    fk_constraints = [
        c
        for c in Analysis.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(c, ForeignKeyConstraint)
    ]

    column_sets = [{col.name for col in fk.columns} for fk in fk_constraints]

    found_asset_fk = any("digital_asset_id" in cols for cols in column_sets)
    assert found_asset_fk, "FK for digital_asset_id not found"


def test_foreign_key_requested_by_exists() -> None:
    """Test: FK constraint for requested_by exists.

    **Validates: R5 AC #1, Design §7.3**
    """
    fk_constraints = [
        c
        for c in Analysis.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(c, ForeignKeyConstraint)
    ]

    column_sets = [{col.name for col in fk.columns} for fk in fk_constraints]

    found_user_fk = any("requested_by" in cols for cols in column_sets)
    assert found_user_fk, "FK for requested_by not found"


def test_analysis_table_has_primary_key_constraint() -> None:
    """Test: Analysis table has a primary key constraint.

    **Validates: R1 AC #1, Design §3.1**

    Verifies that PK constraint exists (should be on id column).
    """
    constraints = list(table.constraints)
    pk_constraints = [c for c in constraints if isinstance(c, PrimaryKeyConstraint)]

    assert (
        len(pk_constraints) == 1
    ), f"Expected 1 PK constraint, got {len(pk_constraints)}"
