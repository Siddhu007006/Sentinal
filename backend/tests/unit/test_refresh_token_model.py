"""
Unit tests for RefreshToken ORM model.

Tests model instantiation, defaults, field types, and __repr__() without
requiring a database connection. These tests validate ORM behavior in memory.

**Validates: Requirement R5 (ORM Model Test Coverage) — Part 1 (Unit Tests)**

Traces to: 22-Engineering-Backlog E3.T9 (Refresh Tokens ORM Model and Migration task)
Traces to: 07-Backend-Development-Standards §8 (ORM model conventions)
Traces to: 11-Testing-Strategy §6 (unit test patterns)
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import inspect

from app.models.refresh_token import RefreshToken


# ===========================================================================
# Test 1: Model Instantiation with Valid Data
# ===========================================================================


def test_instantiate_refresh_token_with_valid_data() -> None:
    """Test: Instantiate RefreshToken with valid data succeeds.

    **Validates: R5 AC #2**

    Verifies that a RefreshToken can be created with all required fields
    populated (no database commit needed, just in-memory object).
    """
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    token_hash = "a" * 64  # 64-char SHA-256 hex
    expires_at = datetime.now(UTC) + timedelta(days=30)

    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    assert token.user_id == user_id
    assert token.token_hash == token_hash
    assert token.expires_at == expires_at


# ===========================================================================
# Test 2: Model Instantiation with Optional Fields
# ===========================================================================


def test_instantiate_refresh_token_with_optional_fields() -> None:
    """Test: Instantiate RefreshToken with optional fields succeeds.

    **Validates: R5 AC #2**

    Verifies that optional fields (user_agent, ip_address) can be set.
    """
    user_id = UUID("87654321-4321-8765-4321-876543218765")
    token_hash = "b" * 64
    expires_at = datetime.now(UTC) + timedelta(days=30)
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    ip_address = "192.0.2.1"

    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    assert token.user_agent == user_agent
    assert token.ip_address == ip_address


# ===========================================================================
# Test 3: Default Values
# ===========================================================================


def test_refresh_token_default_values() -> None:
    """Test: RefreshToken has correct default values.

    **Validates: R5 AC #3**

    Verifies that default values are set when not explicitly provided.
    
    NOTE: SQLAlchemy 2.0 only applies column defaults when adding to session.
    This test verifies the defaults are configured in the schema, not in-memory values.
    Integration tests will verify in-database defaults work correctly.
    """
    from sqlalchemy import inspect
    
    mapper = inspect(RefreshToken)
    columns = {c.name: c for c in mapper.columns}
    
    # Verify column defaults are configured
    assert columns["is_revoked"].default is not None or columns["is_revoked"].server_default is not None
    assert columns["revoked_at"].default is None  # revoked_at should start as None
    assert columns["user_agent"].default is None  # user_agent should start as None
    assert columns["ip_address"].default is None  # ip_address should start as None


# ===========================================================================
# Test 4: __repr__() Does Not Expose Token Hash
# ===========================================================================


def test_refresh_token_repr_does_not_expose_hash() -> None:
    """Test: RefreshToken.__repr__() does NOT expose token_hash.

    **Validates: R5 AC #5**

    Verifies that the string representation omits the sensitive token hash
    for security (never log hashes).
    """
    user_id = UUID("22222222-2222-2222-2222-222222222222")
    token_hash = "d" * 64
    expires_at = datetime.now(UTC) + timedelta(days=30)

    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    repr_str = repr(token)

    # Verify hash is NOT in repr
    assert token_hash not in repr_str
    assert "d" * 64 not in repr_str

    # Verify other fields are present
    assert "RefreshToken" in repr_str
    assert str(token.id) in repr_str


# ===========================================================================
# Test 5: __repr__() Includes Key Fields
# ===========================================================================


def test_refresh_token_repr_includes_key_fields() -> None:
    """Test: RefreshToken.__repr__() includes key identification fields.

    **Validates: R1 AC #5**

    Verifies that the string representation includes id, user_id, revoked
    status, and expiry timestamp for debugging.
    
    NOTE: SQLAlchemy 2.0 doesn't apply defaults to in-memory instances.
    Set id explicitly for this test.
    """
    user_id = UUID("33333333-3333-3333-3333-333333333333")
    token_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    token_hash = "e" * 64
    expires_at = datetime.now(UTC) + timedelta(days=30)

    token = RefreshToken(
        id=token_id,
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    repr_str = repr(token)

    # Verify key fields are present
    assert str(token_id) in repr_str
    assert str(user_id) in repr_str
    # revoked status should show (either explicit False or None depending on SQLAlchemy behavior)
    assert "revoked" in repr_str.lower()


# ===========================================================================
# Test 6: Model Can Be Imported from app.models
# ===========================================================================


def test_refresh_token_import_from_app_models() -> None:
    """Test: RefreshToken can be imported from app.models.

    **Validates: R1 AC #8**

    Verifies that Alembic can discover the model via app.models.
    """
    from app.models import RefreshToken as ImportedRefreshToken

    assert ImportedRefreshToken is RefreshToken


# ===========================================================================
# Test 7: Model Has Correct Table Name
# ===========================================================================


def test_refresh_token_table_name() -> None:
    """Test: RefreshToken has correct table name.

    **Validates: R1 AC #4**

    Verifies that __tablename__ is "user_refresh_tokens".
    """
    assert RefreshToken.__tablename__ == "user_refresh_tokens"


# ===========================================================================
# Test 8: Model Inherits from BaseModel
# ===========================================================================


def test_refresh_token_inherits_from_base_model() -> None:
    """Test: RefreshToken inherits from BaseModel.

    **Validates: R1 AC #2**

    Verifies that RefreshToken has inherited fields (id, created_at, updated_at).
    """
    from app.infrastructure.database.base import BaseModel

    assert issubclass(RefreshToken, BaseModel)


# ===========================================================================
# Test 9: Field Types Are Correct
# ===========================================================================


def test_refresh_token_field_types() -> None:
    """Test: RefreshToken has correct field types.

    **Validates: R5 AC #5**

    Verifies that all fields have correct Python and SQLAlchemy types.
    """
    mapper = inspect(RefreshToken)

    # Verify fields exist
    assert "id" in mapper.columns
    assert "user_id" in mapper.columns
    assert "token_hash" in mapper.columns
    assert "expires_at" in mapper.columns
    assert "is_revoked" in mapper.columns
    assert "user_agent" in mapper.columns
    assert "ip_address" in mapper.columns
    assert "revoked_at" in mapper.columns
    assert "created_at" in mapper.columns
    assert "updated_at" in mapper.columns

    # Verify types by checking column properties
    columns = {c.name: c for c in mapper.columns}

    # id is UUID
    assert str(columns["id"].type) == "UUID"

    # user_id is UUID
    assert str(columns["user_id"].type) == "UUID"

    # token_hash is String
    assert "VARCHAR" in str(columns["token_hash"].type).upper()

    # expires_at is timestamp
    assert "TIMESTAMP" in str(columns["expires_at"].type).upper()

    # is_revoked is boolean
    assert str(columns["is_revoked"].type) == "BOOLEAN"

    # user_agent is String (nullable)
    assert "VARCHAR" in str(columns["user_agent"].type).upper()
    assert columns["user_agent"].nullable is True

    # ip_address is INET (nullable)
    assert columns["ip_address"].nullable is True

    # revoked_at is timestamp (nullable)
    assert "TIMESTAMP" in str(columns["revoked_at"].type).upper()
    assert columns["revoked_at"].nullable is True


# ===========================================================================
# Test 10: Constraints Are Defined
# ===========================================================================


def test_refresh_token_constraints() -> None:
    """Test: RefreshToken has required constraints defined.

    **Validates: R2 AC #1-7**

    Verifies that primary key, foreign key, and unique constraints are present.
    """
    mapper = inspect(RefreshToken)

    # Verify primary key
    pk_columns = [c.name for c in mapper.primary_key]
    assert "id" in pk_columns

    # Verify foreign key exists (check through table args or relationships)
    table = mapper.mapped_table
    fk_found = False
    for constraint in table.foreign_keys:
        if constraint.parent.name == "user_id":
            fk_found = True
            assert constraint.column.table.name == "users"
            break
    assert fk_found, "Foreign key on user_id not found"

    # Verify unique constraint on token_hash
    uq_found = False
    for constraint in table.constraints:
        if hasattr(constraint, "columns"):
            col_names = [c.name for c in constraint.columns]
            if "token_hash" in col_names and "unique" in str(type(constraint)).lower():
                uq_found = True
                break
    assert uq_found, "Unique constraint on token_hash not found"


# ===========================================================================
# Test 11: Can Set Revocation Fields
# ===========================================================================


def test_refresh_token_revocation_fields() -> None:
    """Test: RefreshToken revocation fields can be set.

    **Validates: R1 AC #3**

    Verifies that is_revoked and revoked_at can be set.
    
    NOTE: SQLAlchemy 2.0 doesn't set is_revoked=False in-memory by default.
    Set it explicitly and then verify it can be changed.
    """
    user_id = UUID("44444444-4444-4444-4444-444444444444")
    token_hash = "f" * 64
    expires_at = datetime.now(UTC) + timedelta(days=30)

    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_revoked=False,  # Explicitly set
    )

    # Verify initial state
    assert token.is_revoked is False
    assert token.revoked_at is None

    # Set revocation
    token.is_revoked = True
    token.revoked_at = datetime.now(UTC)

    # Verify revocation
    assert token.is_revoked is True
    assert token.revoked_at is not None


# ===========================================================================
# Test 12: Indexes Are Defined
# ===========================================================================


def test_refresh_token_indexes() -> None:
    """Test: RefreshToken has required indexes defined.

    **Validates: R2 AC #5-7**

    Verifies that indexes for user_id and partial expires_at are present.
    
    NOTE: Integration test verifies indexes exist in actual database.
    This test verifies they're defined in the model schema.
    """
    mapper = inspect(RefreshToken)
    table = mapper.mapped_table

    # Get index names
    index_names = [idx.name for idx in table.indexes]

    # Verify user_id index is defined
    user_id_index_found = any("user_id" in name for name in index_names)
    assert user_id_index_found, f"user_id index not found in {index_names}"

    # Verify expires_at index is defined  
    expires_at_index_found = any("expires_at" in name for name in index_names)
    assert expires_at_index_found, f"expires_at index not found in {index_names}"


# ===========================================================================
# Test 13: Field Comment Documentation
# ===========================================================================


def test_refresh_token_field_comments() -> None:
    """Test: RefreshToken fields have documentation comments.

    **Validates: R1 AC #6**

    Verifies that security-sensitive fields have appropriate comments.
    """
    mapper = inspect(RefreshToken)
    columns = {c.name: c for c in mapper.columns}

    # Verify token_hash has comment about hash security
    token_hash_col = columns["token_hash"]
    assert token_hash_col.comment is not None
    assert "hash" in token_hash_col.comment.lower()

    # Verify user_id has comment about FK
    user_id_col = columns["user_id"]
    assert user_id_col.comment is not None
    assert "fk" in user_id_col.comment.lower() or (
        "foreign" in user_id_col.comment.lower()
    )


# ===========================================================================
# Test 14: Model Docstring Is Comprehensive
# ===========================================================================


def test_refresh_token_docstring() -> None:
    """Test: RefreshToken has comprehensive docstring.

    **Validates: R1 AC #7**

    Verifies that the model has documentation covering token hash security
    and lifecycle.
    """
    docstring = RefreshToken.__doc__
    assert docstring is not None
    assert "token" in docstring.lower()
    assert "hash" in docstring.lower() or "security" in docstring.lower()


# ===========================================================================
# Test 15: Created At Timestamp Fields
# ===========================================================================


def test_refresh_token_has_timestamp_fields() -> None:
    """Test: RefreshToken inherits timestamp fields from BaseModel.

    **Validates: R1 AC #3**

    Verifies that created_at and updated_at are inherited.
    
    NOTE: SQLAlchemy 2.0 only applies defaults when adding to session.
    This test verifies fields exist and are configured with defaults.
    """
    mapper = inspect(RefreshToken)
    
    # Verify timestamp fields exist in the mapper
    assert "created_at" in [c.name for c in mapper.columns]
    assert "updated_at" in [c.name for c in mapper.columns]
    
    # Verify they are timestamp type
    columns = {c.name: c for c in mapper.columns}
    assert "TIMESTAMP" in str(columns["created_at"].type).upper()
    assert "TIMESTAMP" in str(columns["updated_at"].type).upper()


# ===========================================================================
# Test 16: Model Can Handle Maximum Field Values
# ===========================================================================


def test_refresh_token_max_field_values() -> None:
    """Test: RefreshToken can handle maximum field values.

    **Validates: R1 AC #3**

    Verifies that fields can handle typical maximum values without errors.
    """
    user_id = UUID("66666666-6666-6666-6666-666666666666")
    token_hash = "h" * 64  # Exactly 64 chars (SHA-256)
    expires_at = datetime.now(UTC) + timedelta(days=365 * 10)  # 10 years
    user_agent = "A" * 512  # Max user agent length
    ip_address = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"  # IPv6

    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    assert token.token_hash == token_hash
    assert token.user_agent == user_agent
    assert token.ip_address == ip_address
