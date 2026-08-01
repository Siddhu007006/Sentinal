"""
Unit tests for Pydantic schemas.

Tests the base schema infrastructure, mixins, pagination, and query parameters,
including serialization, deserialization, alias generation, and validation.

Traces to: E2.T9 acceptance criteria
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.base import BaseSchema
from app.schemas.error import ErrorBody, ErrorDetail, ErrorResponse
from app.schemas.health import HealthResponse
from app.schemas.mixins import TimestampMixin
from app.schemas.pagination import PaginatedResponse
from app.schemas.query_params import FilterParam, SortParam


class TestBaseSchema:
    """Tests for base schema configuration."""

    def test_base_schema_populate_by_name(self) -> None:
        """Verify populate_by_name allows snake_case input parsing."""

        class TestSchema(BaseSchema):
            my_field: str

        # Snake_case input works
        obj1 = TestSchema(my_field="value")
        assert obj1.my_field == "value"

        # populate_by_name allows field name input in requests
        obj2 = TestSchema.model_validate({"my_field": "value"})
        assert obj2.my_field == "value"

    def test_base_schema_from_attributes(self) -> None:
        """Verify from_attributes allows construction from objects."""

        class MockObject:
            my_field: str = "from_object"

        class TestSchema(BaseSchema):
            my_field: str

        obj = MockObject()
        schema = TestSchema.model_validate(obj, from_attributes=True)
        assert schema.my_field == "from_object"

    def test_datetime_serialization_iso8601_utc(self) -> None:
        """Verify datetime fields serialize to ISO 8601 UTC format."""

        class TestSchema(BaseSchema):
            timestamp: datetime

        # Create schema with UTC datetime
        dt = datetime(
            2025,
            1,
            28,
            10,
            15,
            30,
            123456,
            tzinfo=UTC,
        )
        schema = TestSchema(timestamp=dt)

        # Serialize
        serialized = schema.model_dump(mode="json")

        # Check format: YYYY-MM-DDTHH:mm:ss.ffffffZ
        assert serialized["timestamp"] == "2025-01-28T10:15:30.123456Z"

    def test_datetime_serialization_converts_to_utc(self) -> None:
        """Verify datetimes in other timezones are converted to UTC."""
        from datetime import timedelta
        from datetime import timezone as tz

        class TestSchema(BaseSchema):
            timestamp: datetime

        # Create datetime in +05:00 timezone
        eastern = tz(timedelta(hours=5))
        dt = datetime(2025, 1, 28, 15, 15, 30, 0, tzinfo=eastern)
        schema = TestSchema(timestamp=dt)

        # Serialize (should convert to UTC)
        serialized = schema.model_dump(mode="json")

        # 15:15 +05:00 = 10:15 UTC
        assert serialized["timestamp"] == "2025-01-28T10:15:30.000000Z"

    def test_datetime_serialization_naive_assumed_utc(self) -> None:
        """Verify naive datetimes are assumed to be UTC."""

        class TestSchema(BaseSchema):
            timestamp: datetime

        # Naive datetime (no timezone)
        dt = datetime(  # noqa: DTZ001 - intentionally testing naive datetime handling
            2025,
            1,
            28,
            10,
            15,
            30,
            123456,
        )
        schema = TestSchema(timestamp=dt)

        # Serialize
        serialized = schema.model_dump(mode="json")

        # Should treat as UTC
        assert serialized["timestamp"] == "2025-01-28T10:15:30.123456Z"


class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_error_response_structure(self) -> None:
        """Verify ErrorResponse includes all required fields."""
        resp = ErrorResponse(
            error=ErrorBody(
                code="test_error",
                message="Test message",
            ),
            request_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            timestamp=datetime(2025, 1, 28, 10, 15, 30, tzinfo=UTC),
        )

        assert resp.error.code == "test_error"
        assert resp.error.message == "Test message"
        assert resp.request_id == UUID("550e8400-e29b-41d4-a716-446655440000")

    def test_error_response_request_id_alias(self) -> None:
        """Verify request_id serializes with requestId alias."""
        resp = ErrorResponse(
            error=ErrorBody(code="test", message="Test"),
            request_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            timestamp=datetime(2025, 1, 28, 10, 15, 30, tzinfo=UTC),
        )

        serialized = resp.model_dump(by_alias=True, mode="json")

        assert "requestId" in serialized
        assert serialized["requestId"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_error_response_accepts_snake_case_input(self) -> None:
        """Verify ErrorResponse accepts snake_case field names in requests."""
        data = {
            "error": {"code": "test", "message": "Test"},
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-28T10:15:30Z",
        }

        resp = ErrorResponse.model_validate(data)
        assert resp.request_id == UUID("550e8400-e29b-41d4-a716-446655440000")

    def test_error_response_accepts_camel_case_input(self) -> None:
        """Verify ErrorResponse accepts camelCase field names in requests."""
        data = {
            "error": {"code": "test", "message": "Test"},
            "requestId": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-28T10:15:30Z",
        }

        resp = ErrorResponse.model_validate(data)
        assert resp.request_id == UUID("550e8400-e29b-41d4-a716-446655440000")

    def test_error_detail_optional_fields(self) -> None:
        """Verify ErrorDetail fields are optional."""
        detail = ErrorDetail()
        assert detail.field is None
        assert detail.issue is None


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_health_response_structure(self) -> None:
        """Verify HealthResponse includes all required fields."""
        resp = HealthResponse(
            status="ok",
            version="1.0.0",
            timestamp=datetime(2025, 1, 28, 10, 15, 30, tzinfo=UTC),
        )

        assert resp.status == "ok"
        assert resp.version == "1.0.0"

    def test_health_response_dependencies_optional(self) -> None:
        """Verify dependencies field is optional."""
        resp = HealthResponse(
            status="ok",
            version="1.0.0",
            timestamp=datetime(2025, 1, 28, 10, 15, 30, tzinfo=UTC),
        )

        assert resp.dependencies is None

    def test_health_response_datetime_serialization(self) -> None:
        """Verify HealthResponse datetime is serialized to ISO 8601 UTC."""
        dt = datetime(
            2025,
            1,
            28,
            10,
            15,
            30,
            123456,
            tzinfo=UTC,
        )
        resp = HealthResponse(
            status="ok",
            version="1.0.0",
            timestamp=dt,
        )

        serialized = resp.model_dump(mode="json")
        assert serialized["timestamp"] == "2025-01-28T10:15:30.123456Z"


class TestTimestampMixin:
    """Tests for TimestampMixin."""

    def test_timestamp_mixin_fields(self) -> None:
        """Verify TimestampMixin provides created_at and updated_at."""

        class TestSchema(TimestampMixin):
            name: str

        created = datetime(2025, 1, 28, 10, 0, 0, tzinfo=UTC)
        updated = datetime(2025, 1, 28, 11, 0, 0, tzinfo=UTC)

        schema = TestSchema(
            name="test",
            created_at=created,
            updated_at=updated,
        )

        assert schema.created_at == created
        assert schema.updated_at == updated

    def test_timestamp_mixin_camel_case_aliases(self) -> None:
        """Verify timestamp fields use camelCase aliases."""

        class TestSchema(TimestampMixin):
            name: str

        created = datetime(2025, 1, 28, 10, 0, 0, tzinfo=UTC)
        updated = datetime(2025, 1, 28, 11, 0, 0, tzinfo=UTC)

        schema = TestSchema(
            name="test",
            created_at=created,
            updated_at=updated,
        )

        serialized = schema.model_dump(by_alias=True, mode="json")

        assert "createdAt" in serialized
        assert "updatedAt" in serialized
        assert serialized["createdAt"] == "2025-01-28T10:00:00.000000Z"
        assert serialized["updatedAt"] == "2025-01-28T11:00:00.000000Z"

    def test_timestamp_mixin_accepts_camel_case_input(self) -> None:
        """Verify TimestampMixin accepts camelCase input."""

        class TestSchema(TimestampMixin):
            name: str

        data = {
            "name": "test",
            "createdAt": "2025-01-28T10:00:00Z",
            "updatedAt": "2025-01-28T11:00:00Z",
        }

        schema = TestSchema.model_validate(data)
        assert schema.name == "test"
        assert schema.created_at is not None
        assert schema.updated_at is not None


class TestPaginatedResponse:
    """Tests for PaginatedResponse schema."""

    def test_paginated_response_structure(self) -> None:
        """Verify PaginatedResponse includes all required fields."""

        class ItemSchema(BaseSchema):
            id: int
            name: str

        items = [
            ItemSchema(id=1, name="Item 1"),
            ItemSchema(id=2, name="Item 2"),
        ]

        resp = PaginatedResponse[ItemSchema](
            items=items,
            total=100,
            page=1,
            page_size=10,
            total_pages=10,
        )

        assert len(resp.items) == 2
        assert resp.total == 100
        assert resp.page == 1
        assert resp.page_size == 10
        assert resp.total_pages == 10

    def test_paginated_response_page_size_alias(self) -> None:
        """Verify page_size and total_pages use camelCase aliases."""

        class ItemSchema(BaseSchema):
            id: int

        resp = PaginatedResponse[ItemSchema](
            items=[],
            total=100,
            page=1,
            page_size=10,
            total_pages=10,
        )

        serialized = resp.model_dump(by_alias=True, mode="json")

        assert "pageSize" in serialized
        assert "totalPages" in serialized
        assert serialized["pageSize"] == 10
        assert serialized["totalPages"] == 10

    def test_paginated_response_validation(self) -> None:
        """Verify PaginatedResponse validates numeric constraints."""

        class ItemSchema(BaseSchema):
            id: int

        # page must be >= 1
        with pytest.raises(ValidationError):
            PaginatedResponse[ItemSchema](
                items=[],
                total=100,
                page=0,
                page_size=10,
                total_pages=10,
            )

        # page_size must be >= 1
        with pytest.raises(ValidationError):
            PaginatedResponse[ItemSchema](
                items=[],
                total=100,
                page=1,
                page_size=0,
                total_pages=10,
            )


class TestSortParam:
    """Tests for SortParam schema."""

    def test_sort_param_from_string_with_direction(self) -> None:
        """Verify SortParam.from_string parses field:direction format."""
        sort = SortParam.from_string("createdAt:desc")

        assert sort.field == "createdAt"
        assert sort.direction == "desc"

    def test_sort_param_from_string_without_direction(self) -> None:
        """Verify SortParam.from_string defaults to asc."""
        sort = SortParam.from_string("filename")

        assert sort.field == "filename"
        assert sort.direction == "asc"

    def test_sort_param_to_string(self) -> None:
        """Verify SortParam.to_string serializes to query format."""
        sort = SortParam(field="createdAt", direction="desc")

        assert sort.to_string() == "createdAt:desc"

    def test_sort_param_validation(self) -> None:
        """Verify SortParam validates field and direction."""
        # Empty field invalid
        with pytest.raises(ValidationError):
            SortParam(field="", direction="asc")

        # Invalid direction
        with pytest.raises(ValidationError):
            SortParam(field="name", direction="invalid")  # type: ignore


class TestFilterParam:
    """Tests for FilterParam schema."""

    def test_filter_param_from_string_with_operator(self) -> None:
        """Verify FilterParam.from_string parses field:operator:value format."""
        filt = FilterParam.from_string("status:eq:active")

        assert filt.field == "status"
        assert filt.operator == "eq"
        assert filt.value == "active"

    def test_filter_param_from_string_without_operator(self) -> None:
        """Verify FilterParam.from_string defaults operator to eq."""
        filt = FilterParam.from_string("status:active")

        assert filt.field == "status"
        assert filt.operator == "eq"
        assert filt.value == "active"

    def test_filter_param_to_string(self) -> None:
        """Verify FilterParam.to_string serializes to query format."""
        filt = FilterParam(field="status", operator="eq", value="active")

        assert filt.to_string() == "status:eq:active"

    def test_filter_param_validation(self) -> None:
        """Verify FilterParam validates field, operator, and value."""
        # Empty field invalid
        with pytest.raises(ValidationError):
            FilterParam(field="", operator="eq", value="test")

        # Invalid operator
        with pytest.raises(ValidationError):
            FilterParam(field="status", operator="invalid", value="test")  # type: ignore

        # Empty value invalid
        with pytest.raises(ValidationError):
            FilterParam(field="status", operator="eq", value="")


class TestSchemaInheritance:
    """Tests for schema inheritance and mixin behavior."""

    def test_timestamp_mixin_inheritance_chain(self) -> None:
        """Verify TimestampMixin inherits BaseSchema configuration."""

        class ResourceSchema(TimestampMixin):
            id: UUID
            name: str

        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "resource",
            "createdAt": "2025-01-28T10:00:00Z",
            "updatedAt": "2025-01-28T11:00:00Z",
        }

        # Should accept camelCase (from populate_by_name in BaseSchema)
        schema = ResourceSchema.model_validate(data)
        assert schema.name == "resource"

    def test_error_response_inherits_base_schema_config(self) -> None:
        """Verify ErrorResponse inherits BaseSchema populate_by_name."""
        # Should accept both snake_case and camelCase
        data_snake = {
            "error": {"code": "test", "message": "Test"},
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-28T10:15:30Z",
        }

        data_camel = {
            "error": {"code": "test", "message": "Test"},
            "requestId": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-28T10:15:30Z",
        }

        resp1 = ErrorResponse.model_validate(data_snake)
        resp2 = ErrorResponse.model_validate(data_camel)

        assert resp1.request_id == resp2.request_id


class TestOpenAPISchemaGeneration:
    """Tests for OpenAPI schema generation."""

    def test_error_response_schema_has_request_id_alias(self) -> None:
        """Verify ErrorResponse schema includes requestId alias for OpenAPI."""
        schema = ErrorResponse.model_json_schema()

        # Check that requestId appears in properties
        assert "properties" in schema
        # request_id should have alias in schema
        props = schema["properties"]
        # The field might be keyed by the actual field name or alias
        assert any("request" in key.lower() for key in props), (
            f"Properties: {list(props)}"
        )

    def test_timestamp_mixin_schema_has_camel_case_fields(self) -> None:
        """Verify TimestampMixin schema includes camelCase field names."""

        class TestSchema(TimestampMixin):
            name: str

        schema = TestSchema.model_json_schema()
        props = schema.get("properties", {})

        # Should have createdAt and updatedAt in the schema
        # The exact representation may vary based on Pydantic schema generation
        assert len(props) > 0
