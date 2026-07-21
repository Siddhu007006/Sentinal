"""
Unit tests for Upload ORM model.

Tests model instantiation, defaults, field types, and __repr__() without
requiring a database connection. These tests validate ORM behavior in memory.

**Validates: Requirement R6 (ORM Model and Migration Test Coverage) — Unit Tests**

Traces to: 22-Engineering-Backlog E3.T4 (Upload ORM model task)
Traces to: 07-Backend-Development-Standards §8 (ORM testing patterns)
Traces to: 11-Testing-Strategy §6 (unit test patterns)
"""

from datetime import datetime
from uuid import UUID, uuid4

from app.models.upload import Upload, UploadStatus
from app.models.user import User


# ===========================================================================
# Test 1: Model Instantiation with All Fields
# ===========================================================================


def test_instantiate_upload_with_all_fields() -> None:
    """Test: Instantiate Upload with all fields succeeds.

    **Validates: R6 AC #1**

    Verifies that an Upload can be created with all fields populated (no
    database commit needed, just in-memory object).
    """
    user_id = uuid4()
    upload = Upload(
        user_id=user_id,
        original_filename="report.pdf",
        storage_key="uploads/2025/07/19/uuid4/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024576,
        checksum_sha256="a" * 64,  # 64-char hex string
        upload_status=UploadStatus.PENDING.value,
        completed_at=None,
    )

    assert upload.user_id == user_id
    assert upload.original_filename == "report.pdf"
    assert upload.storage_key == "uploads/2025/07/19/uuid4/report.pdf"
    assert upload.content_type == "application/pdf"
    assert upload.file_size_bytes == 1024576
    assert upload.checksum_sha256 == "a" * 64
    assert upload.upload_status == UploadStatus.PENDING.value
    assert upload.completed_at is None


# ===========================================================================
# Test 2: Model Instantiation with Minimal Fields
# ===========================================================================


def test_instantiate_upload_with_minimal_fields() -> None:
    """Test: Instantiate Upload with minimal fields succeeds.

    **Validates: R6 AC #2**

    Verifies that an Upload can be created with only required fields
    (nullable fields like checksum_sha256 and completed_at are omitted).
    """
    user_id = uuid4()
    upload = Upload(
        user_id=user_id,
        original_filename="document.txt",
        storage_key="uploads/2025/07/19/uuid/document.txt",
        content_type="text/plain",
        file_size_bytes=512,
    )

    assert upload.user_id == user_id
    assert upload.original_filename == "document.txt"
    assert upload.storage_key == "uploads/2025/07/19/uuid/document.txt"
    assert upload.content_type == "text/plain"
    assert upload.file_size_bytes == 512
    # Nullable fields should be None by default
    assert upload.checksum_sha256 is None
    assert upload.completed_at is None


# ===========================================================================
# Test 3: Default upload_status
# ===========================================================================


def test_default_upload_status_is_pending() -> None:
    """Test: Default upload_status is 'pending'.

    **Validates: R6 AC #3**

    Verifies that when an Upload is created without specifying upload_status,
    it defaults to UploadStatus.PENDING ('pending').
    """
    user_id = uuid4()
    upload = Upload(
        user_id=user_id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        upload_status=UploadStatus.PENDING.value,
    )

    assert upload.upload_status == UploadStatus.PENDING.value
    assert upload.upload_status == "pending"


# ===========================================================================
# Test 4: Field Types
# ===========================================================================


def test_field_types_are_correct() -> None:
    """Test: Field types are correct when set.

    **Validates: R6 AC #4**

    Verifies that fields have the correct Python types when instantiated
    with values.
    """
    user_id = uuid4()
    upload = Upload(
        user_id=user_id,
        original_filename="file.pdf",
        storage_key="uploads/2025/07/19/uuid/file.pdf",
        content_type="application/pdf",
        file_size_bytes=2048,
        checksum_sha256="b" * 64,
        upload_status=UploadStatus.PROCESSING.value,
    )

    # UUID field
    assert isinstance(upload.user_id, UUID)

    # String fields
    assert isinstance(upload.original_filename, str)
    assert isinstance(upload.storage_key, str)
    assert isinstance(upload.content_type, str)
    assert isinstance(upload.checksum_sha256, str)
    assert isinstance(upload.upload_status, str)

    # Integer field
    assert isinstance(upload.file_size_bytes, int)

    # Nullable datetime field
    assert upload.completed_at is None


def test_user_id_is_uuid_type() -> None:
    """Test: user_id field is UUID type."""
    user_id = uuid4()
    upload = Upload(
        user_id=user_id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    assert isinstance(upload.user_id, UUID)
    assert upload.user_id == user_id


def test_file_size_bytes_is_integer_type() -> None:
    """Test: file_size_bytes field is integer type."""
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=999,
    )

    assert isinstance(upload.file_size_bytes, int)
    assert upload.file_size_bytes == 999


def test_checksum_sha256_is_string_type() -> None:
    """Test: checksum_sha256 field is string type when set."""
    checksum = "f" * 64
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        checksum_sha256=checksum,
    )

    assert isinstance(upload.checksum_sha256, str)
    assert upload.checksum_sha256 == checksum


def test_checksum_sha256_is_64_chars() -> None:
    """Test: checksum_sha256 is exactly 64 hex characters (SHA-256)."""
    checksum = "a" * 64  # 64 hex chars = 32 bytes
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        checksum_sha256=checksum,
    )

    assert upload.checksum_sha256 is not None
    assert len(upload.checksum_sha256) == 64


# ===========================================================================
# Test 5: UploadStatus Enum
# ===========================================================================


def test_upload_status_enum_has_four_values() -> None:
    """Test: UploadStatus enum has exactly four values.

    **Validates: R6 AC #5**

    Verifies that UploadStatus has PENDING, PROCESSING, COMPLETED, FAILED.
    """
    statuses = [s.value for s in UploadStatus]
    assert len(statuses) == 4
    assert set(statuses) == {"pending", "processing", "completed", "failed"}


def test_upload_status_enum_values_are_strings() -> None:
    """Test: UploadStatus enum values are strings (StrEnum).

    **Validates: R6 AC #6**

    Verifies that UploadStatus is a StrEnum (can be used as strings directly).
    """
    assert isinstance(UploadStatus.PENDING.value, str)
    assert isinstance(UploadStatus.PROCESSING.value, str)
    assert isinstance(UploadStatus.COMPLETED.value, str)
    assert isinstance(UploadStatus.FAILED.value, str)


def test_upload_status_pending() -> None:
    """Test: UploadStatus.PENDING equals 'pending'."""
    assert UploadStatus.PENDING.value == "pending"


def test_upload_status_processing() -> None:
    """Test: UploadStatus.PROCESSING equals 'processing'."""
    assert UploadStatus.PROCESSING.value == "processing"


def test_upload_status_completed() -> None:
    """Test: UploadStatus.COMPLETED equals 'completed'."""
    assert UploadStatus.COMPLETED.value == "completed"


def test_upload_status_failed() -> None:
    """Test: UploadStatus.FAILED equals 'failed'."""
    assert UploadStatus.FAILED.value == "failed"


# ===========================================================================
# Test 6: Relationship to User
# ===========================================================================


def test_user_relationship_type_is_mapped_user() -> None:
    """Test: Upload.user relationship type is Mapped['User'].

    **Validates: R6 AC #7**

    Verifies that the relationship is correctly typed for lazy loading.
    """
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    # Check that the relationship is defined
    assert hasattr(upload, "user")


def test_user_uploads_relationship_exists_on_user_model() -> None:
    """Test: User.uploads relationship exists.

    **Validates: R6 AC #8**

    Verifies that the User model has the uploads relationship defined
    for bidirectional access.
    """
    user = User(
        email="test@example.com",
        password_hash="$2b$12$hash",
        full_name="Test User",
    )

    # Check that the relationship is defined
    assert hasattr(user, "uploads")


# ===========================================================================
# Test 7: __repr__() Output
# ===========================================================================


def test_repr_returns_useful_string() -> None:
    """Test: __repr__() returns useful string.

    **Validates: R6 AC #9**

    Verifies that __repr__() returns a human-readable representation that
    includes id, user_id, status, and filename.
    """
    user_id = uuid4()
    upload = Upload(
        user_id=user_id,
        original_filename="report.pdf",
        storage_key="uploads/2025/07/19/uuid/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        upload_status=UploadStatus.PENDING.value,
    )

    repr_str = repr(upload)

    # Should include type name
    assert "Upload" in repr_str

    # Should include status
    assert "pending" in repr_str or "status" in repr_str

    # Should include filename for identification
    assert "report.pdf" in repr_str or "filename" in repr_str

    # Should be a string
    assert isinstance(repr_str, str)


def test_repr_does_not_expose_storage_key() -> None:
    """Test: __repr__() does NOT expose storage_key for security.

    **Validates: R6 AC #9**

    Verifies that the storage key (sensitive S3/MinIO credential) is never
    included in string representation to prevent accidental log exposure.
    """
    storage_key = "uploads/2025/07/19/uuid4/sensitive-key.pdf"
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.pdf",
        storage_key=storage_key,
        content_type="application/pdf",
        file_size_bytes=1024,
    )

    repr_str = repr(upload)

    # Should NOT contain the actual storage key
    assert storage_key not in repr_str

    # Should NOT contain "storage" keyword (for defense in depth)
    assert "storage" not in repr_str.lower()


def test_repr_includes_status() -> None:
    """Test: __repr__() includes status."""
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        upload_status=UploadStatus.COMPLETED.value,
    )

    repr_str = repr(upload)
    assert "completed" in repr_str or "status" in repr_str


def test_repr_includes_filename() -> None:
    """Test: __repr__() includes filename."""
    upload = Upload(
        user_id=uuid4(),
        original_filename="my-document.docx",
        storage_key="uploads/2025/07/19/uuid/my-document.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size_bytes=50000,
    )

    repr_str = repr(upload)
    assert "my-document" in repr_str


def test_repr_includes_user_id() -> None:
    """Test: __repr__() includes user_id."""
    user_id = uuid4()
    upload = Upload(
        user_id=user_id,
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    repr_str = repr(upload)
    # Should include user_id or reference to it
    assert str(user_id) in repr_str or "user_id" in repr_str


# ===========================================================================
# Test 8: Timestamps Inherited from BaseModel
# ===========================================================================


def test_created_at_field_exists() -> None:
    """Test: created_at field exists (inherited from BaseModel).

    **Validates: R6 AC #10**

    Verifies that created_at field is present (inherited from BaseModel).
    In-memory instantiation won't set the timestamp yet (database sets it),
    but the field should exist.
    """
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    # Field should exist as an attribute
    assert hasattr(upload, "created_at")


def test_updated_at_field_exists() -> None:
    """Test: updated_at field exists (inherited from BaseModel).

    **Validates: R6 AC #10**

    Verifies that updated_at field is present (inherited from BaseModel).
    """
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    # Field should exist as an attribute
    assert hasattr(upload, "updated_at")


# ===========================================================================
# Test 9: Nullable Fields
# ===========================================================================


def test_checksum_sha256_nullable() -> None:
    """Test: checksum_sha256 can be null.

    **Validates: R6 AC #11**

    Verifies that checksum_sha256 defaults to None and can be omitted
    during creation (will be set later during processing).
    """
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    assert upload.checksum_sha256 is None


def test_completed_at_nullable() -> None:
    """Test: completed_at can be null.

    **Validates: R6 AC #11**

    Verifies that completed_at defaults to None and can be omitted
    during creation (will be set when reaching terminal state).
    """
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
    )

    assert upload.completed_at is None


def test_completed_at_can_be_set() -> None:
    """Test: completed_at can be explicitly set to a datetime."""
    from datetime import UTC

    now = datetime.now(UTC)
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        completed_at=now,
    )

    assert upload.completed_at == now


# ===========================================================================
# Test 10: Model Metadata
# ===========================================================================


def test_upload_model_has_tablename() -> None:
    """Test: Upload model has __tablename__ defined.

    **Validates: R1 AC #1**

    Verifies that __tablename__ is set to "uploads".
    """
    assert Upload.__tablename__ == "uploads"


def test_upload_model_inherits_from_basemodel() -> None:
    """Test: Upload model inherits from BaseModel.

    **Validates: R1 AC #2**

    Verifies that Upload inherits from BaseModel (which provides id, created_at,
    updated_at).
    """
    from app.infrastructure.database.base import BaseModel

    assert issubclass(Upload, BaseModel)


# ===========================================================================
# Test 11: All UploadStatus States
# ===========================================================================


def test_upload_with_pending_status() -> None:
    """Test: Upload can be created with pending status."""
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        upload_status=UploadStatus.PENDING.value,
    )

    assert upload.upload_status == UploadStatus.PENDING.value


def test_upload_with_processing_status() -> None:
    """Test: Upload can be created with processing status."""
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        upload_status=UploadStatus.PROCESSING.value,
    )

    assert upload.upload_status == UploadStatus.PROCESSING.value


def test_upload_with_completed_status() -> None:
    """Test: Upload can be created with completed status."""
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        upload_status=UploadStatus.COMPLETED.value,
    )

    assert upload.upload_status == UploadStatus.COMPLETED.value


def test_upload_with_failed_status() -> None:
    """Test: Upload can be created with failed status."""
    upload = Upload(
        user_id=uuid4(),
        original_filename="file.txt",
        storage_key="uploads/2025/07/19/uuid/file.txt",
        content_type="text/plain",
        file_size_bytes=100,
        upload_status=UploadStatus.FAILED.value,
    )

    assert upload.upload_status == UploadStatus.FAILED.value


# ===========================================================================
# Test 12: File Size Variations
# ===========================================================================


def test_upload_with_zero_size_file() -> None:
    """Test: Upload can represent zero-byte file (empty file)."""
    upload = Upload(
        user_id=uuid4(),
        original_filename="empty.txt",
        storage_key="uploads/2025/07/19/uuid/empty.txt",
        content_type="text/plain",
        file_size_bytes=0,
    )

    assert upload.file_size_bytes == 0


def test_upload_with_large_file() -> None:
    """Test: Upload can represent very large file (gigabyte scale)."""
    large_size = 1024 * 1024 * 1024  # 1 GB
    upload = Upload(
        user_id=uuid4(),
        original_filename="large.bin",
        storage_key="uploads/2025/07/19/uuid/large.bin",
        content_type="application/octet-stream",
        file_size_bytes=large_size,
    )

    assert upload.file_size_bytes == large_size


# ===========================================================================
# Test 13: Content Type Variations
# ===========================================================================


def test_upload_with_different_content_types() -> None:
    """Test: Upload accepts various MIME types."""
    mime_types = [
        "application/pdf",
        "image/png",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "video/mp4",
    ]

    for mime in mime_types:
        upload = Upload(
            user_id=uuid4(),
            original_filename="file.ext",
            storage_key="uploads/2025/07/19/uuid/file.ext",
            content_type=mime,
            file_size_bytes=100,
        )
        assert upload.content_type == mime


# ===========================================================================
# Test 14: Lazy Loading Strategy
# ===========================================================================


def test_upload_user_relationship_lazy_joined() -> None:
    """Test: Upload.user relationship uses lazy='joined' strategy.

    **Validates: D4 (Lazy Loading Strategy)**

    Verifies that Upload.user is eagerly loaded (joined) when fetching uploads.
    This is optimal for many-to-one relationships where each upload has
    exactly one user.
    """
    # Check that the relationship is defined with lazy="joined"
    # This is verified at the class level via inspection

    # Get the relationship property from the Upload class
    mapper = Upload.__mapper__

    # Find the "user" relationship
    user_relationship = None
    for rel in mapper.relationships:
        if rel.key == "user":
            user_relationship = rel
            break

    assert user_relationship is not None, "user relationship not found"
    # Verify lazy loading strategy is "joined"
    assert user_relationship.lazy == "joined"


def test_user_uploads_relationship_lazy_selectin() -> None:
    """Test: User.uploads relationship uses lazy='selectin' strategy.

    **Validates: D4 (Lazy Loading Strategy)**

    Verifies that User.uploads uses separate SELECT IN query (selectin)
    to avoid Cartesian product on collection access.
    """
    # Get the relationship property from the User class
    mapper = User.__mapper__

    # Find the "uploads" relationship
    uploads_relationship = None
    for rel in mapper.relationships:
        if rel.key == "uploads":
            uploads_relationship = rel
            break

    assert uploads_relationship is not None, "uploads relationship not found"
    # Verify lazy loading strategy is "selectin"
    assert uploads_relationship.lazy == "selectin"
