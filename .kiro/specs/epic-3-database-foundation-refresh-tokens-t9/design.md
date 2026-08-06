# E3.T9 — Design Document — Refresh Tokens ORM Model and Migration

| Field | Value |
|---|---|
| **Document** | .kiro/specs/epic-3-database-foundation-refresh-tokens-t9/design.md |
| **Feature** | refresh-tokens-orm-model-t9 |
| **Status** | Design |
| **Owner** | Engineering Team |
| **Traces to** | requirements.md (all sections) |

---

## Design Overview

E3.T9 implements the RefreshToken ORM model and Alembic migration to provide server-side session management with per-device revocation support. The design enforces token hash storage (never raw tokens), cascading deletion, and efficient lookup patterns for token validation and session listing.

---

## RefreshToken ORM Model Design

### Model Inheritance and Structure

**Location:** `backend/app/models/refresh_token.py`

**Inheritance:** RefreshToken extends BaseModel (not Base directly)

**Inherited Fields:**
- `id` (UUID PK, auto-generated via uuid.uuid4() and gen_random_uuid())
- `created_at` (UTC timestamp, immutable, set on INSERT)
- `updated_at` (UTC timestamp, auto-updated on every UPDATE via server_onupdate)
- `deleted_at` (UTC timestamp, nullable, unused for refresh tokens)

### Field Definitions

| Field | Type | Constraints | Purpose |
|---|---|---|---|
| `user_id` | UUID (FK) | NOT NULL, ON DELETE CASCADE, indexed | Foreign key to users.id |
| `token_hash` | VARCHAR(64) | NOT NULL, UNIQUE, indexed | SHA-256 hash of token (64 hex chars) |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Absolute UTC expiry timestamp |
| `is_revoked` | BOOLEAN | NOT NULL, default=false | Explicit revocation flag |
| `user_agent` | VARCHAR(512) | Nullable | HTTP User-Agent header (audit context) |
| `ip_address` | INET | Nullable | Client IP (PostgreSQL INET type) |
| `revoked_at` | TIMESTAMPTZ | Nullable | Timestamp when revoked (null if active) |
| `created_at` | TIMESTAMPTZ | NOT NULL, server_default=now() | Token issuance timestamp (inherited) |
| `updated_at` | TIMESTAMPTZ | NOT NULL, server_default=now() | Last modification (inherited) |

### Security Design Decisions

**1. Token Hash (Never Raw Token)**
- Only SHA-256 hash of opaque token is stored in database
- Raw token transmitted only during issuance via HTTPS
- Database breach does not compromise active sessions (attacker sees hashes only)
- Application-layer hash generation in token service (E4.T2)

**2. Foreign Key CASCADE Deletion**
- ON DELETE CASCADE: User deletion automatically removes all refresh tokens
- Prevents orphaned token records in database
- Simplifies data retention and cleanup logic
- Hard delete (not soft delete) because tokens are not audit-critical

**3. Revocation Flag + Timestamp**
- `is_revoked=true` makes token immediately unusable
- `revoked_at` captures timestamp of revocation (for compliance, logs)
- Separate from `expires_at` (expiry vs. explicit revocation)
- Query pattern: `WHERE is_revoked=false AND expires_at > now()` for validation

**4. Session Context Fields**
- `user_agent`: Client device identification (audit trail, not security)
- `ip_address`: Geographic context (abuse detection, not security mechanism)
- Both nullable (some clients may not provide)
- Both stored in audit log for per-device session tracking

### ORM Model Semantics

**Table Name:** `user_refresh_tokens` (follows `user_*` prefix for user-owned resources)

**Primary Key:** `id` (UUID)

**Unique Constraints:**
- `token_hash` (UNIQUE): Prevents duplicate hashes in database

**Foreign Keys:**
- `user_id` → `users.id` (ON DELETE CASCADE)

**Default Values:**
- `is_revoked`: `false` (server_default="false", ORM default=False)
- `created_at`: `now()` (inherited from BaseModel)
- `updated_at`: `now()` (inherited from BaseModel)

**Not Null Constraints:**
- `user_id` (every token belongs to a user)
- `token_hash` (required for validation)
- `expires_at` (required for token lifecycle)
- `is_revoked` (required state, defaults to false)
- `created_at` (inherited from BaseModel)

**Nullable Fields:**
- `user_agent` (optional, some clients don't send)
- `ip_address` (optional, embedded clients may not have visible IP)
- `revoked_at` (null for active tokens, set on revocation)

### __repr__() Security

**Implementation:**
```python
def __repr__(self) -> str:
    return (
        f"<RefreshToken id={self.id} user_id={self.user_id} "
        f"revoked={self.is_revoked} expires_at={self.expires_at}>"
    )
```

**Security Note:** token_hash is NOT included in __repr__(). Reason:
- Hashes are sensitive information
- Logging __repr__() should never expose hashes (even though they're hashes, not plaintext)
- Prevents accidental information disclosure in error logs

---

## Database Constraints and Indexes

### Constraints

**Primary Key (Automatic):**
```sql
CONSTRAINT pk_user_refresh_tokens PRIMARY KEY (id)
```

**Unique Constraint (on token_hash):**
```sql
CONSTRAINT uq_user_refresh_tokens_token_hash UNIQUE (token_hash)
```

**Foreign Key (with CASCADE):**
```sql
CONSTRAINT fk_user_refresh_tokens_user_id_users FOREIGN KEY (user_id) 
  REFERENCES users(id) ON DELETE CASCADE
```

**Not Null Constraints:**
```sql
NOT NULL: user_id, token_hash, expires_at, is_revoked, created_at
```

### Indexes

**1. User ID Index (Session Listing)**
```sql
CREATE INDEX ix_user_refresh_tokens_user_id ON user_refresh_tokens (user_id)
```
**Purpose:** Efficient lookup of all tokens for a user
**Query Pattern:** `SELECT * FROM user_refresh_tokens WHERE user_id = $1`
**Use Case:** List sessions, revoke all on password change

**2. Token Hash Index (Unique Validation)**
```sql
CREATE UNIQUE INDEX uq_user_refresh_tokens_token_hash ON user_refresh_tokens (token_hash)
```
**Purpose:** O(1) token validation lookup
**Query Pattern:** `SELECT * FROM user_refresh_tokens WHERE token_hash = $1`
**Use Case:** Validate token on every API request

**3. Partial Index (Cleanup Queries)**
```sql
CREATE INDEX ix_user_refresh_tokens_expires_at_active 
  ON user_refresh_tokens (expires_at) 
  WHERE is_revoked = false
```
**Purpose:** Efficient cleanup of expired, non-revoked tokens
**Query Pattern:** `SELECT * FROM user_refresh_tokens WHERE expires_at < now() AND is_revoked = false`
**Use Case:** Background job cleanup (delete expired tokens)
**Optimization:** Partial index reduces size (excludes already-revoked tokens)

---

## Alembic Migration Strategy

### Migration Generation Command

```bash
cd backend
alembic revision --autogenerate -m "Add user_refresh_tokens table"
```

### Expected Migration Output

**File Location:** `backend/migrations/versions/YYYYMMDD_HHMM_<rev>_add_user_refresh_tokens_table.py`

**Migration Structure:**

```python
def upgrade() -> None:
    # Create user_refresh_tokens table with all columns
    op.create_table(
        "user_refresh_tokens",
        # Columns
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("ip_address", INET(), nullable=True),
        sa.Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_user_refresh_tokens_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_user_refresh_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_user_refresh_tokens_token_hash"),
    )
    
    # Create indexes
    op.create_index("ix_user_refresh_tokens_user_id", "user_refresh_tokens", ["user_id"])
    op.create_index(
        "ix_user_refresh_tokens_expires_at_active",
        "user_refresh_tokens",
        ["expires_at"],
        postgresql_where="is_revoked = false",
    )
```

### Migration Validation

**Manual Review Checklist:**
- [ ] Table name is "user_refresh_tokens" (matches __tablename__)
- [ ] All columns present with correct types (UUID, String, TIMESTAMPTZ, Boolean, INET)
- [ ] All column defaults correct (gen_random_uuid(), now(), false)
- [ ] Nullable/not-null flags correct
- [ ] Unique constraint on token_hash present
- [ ] Foreign key on user_id with ON DELETE CASCADE present
- [ ] All indexes present (user_id, token_hash, partial expires_at)
- [ ] downgrade() reverses all changes
- [ ] Migration passes upgrade/downgrade cycle
- [ ] No regressions in prior test suites (E3.T3-E3.T8)

---

## ORM Model Tests

### Test File Location

**File:** `backend/tests/unit/test_refresh_token_model.py`

### Unit Tests

**Test 1: Model Instantiation**
```python
def test_refresh_token_instantiation():
    """RefreshToken can be instantiated with valid data."""
    token = RefreshToken(
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
        token_hash="a" * 64,  # 64-char SHA-256 hex
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    assert token.user_id is not None
    assert token.token_hash == "a" * 64
    assert token.is_revoked is False
    assert token.revoked_at is None
```

**Test 2: Default Values**
```python
def test_refresh_token_defaults():
    """RefreshToken has correct default values."""
    token = RefreshToken(
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
        token_hash="b" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    assert token.is_revoked is False
    assert token.revoked_at is None
    assert token.user_agent is None
    assert token.ip_address is None
```

**Test 3: __repr__ Security**
```python
def test_refresh_token_repr_no_hash():
    """RefreshToken.__repr__() does NOT expose token_hash."""
    token = RefreshToken(
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
        token_hash="c" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    repr_str = repr(token)
    assert "c" * 64 not in repr_str  # Hash should not be exposed
    assert "RefreshToken" in repr_str
    assert str(token.id) in repr_str
```

**Test 4: Model Import**
```python
def test_refresh_token_import():
    """RefreshToken can be imported from app.models."""
    from app.models import RefreshToken
    assert RefreshToken is not None
    assert RefreshToken.__tablename__ == "user_refresh_tokens"
```

**Test 5: Field Types**
```python
def test_refresh_token_field_types():
    """RefreshToken has correct field types."""
    from sqlalchemy import inspect
    mapper = inspect(RefreshToken)
    
    # Verify field existence and type
    assert "user_id" in mapper.columns
    assert "token_hash" in mapper.columns
    assert "expires_at" in mapper.columns
    assert "is_revoked" in mapper.columns
    assert "user_agent" in mapper.columns
    assert "ip_address" in mapper.columns
    assert "revoked_at" in mapper.columns
```

### Integration Tests

**Test 6: Insert Valid Token**
```python
async def test_insert_refresh_token():
    """Insert valid RefreshToken record succeeds."""
    async with get_session() as session:
        token = RefreshToken(
            user_id=user_id,
            token_hash="d" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(token)
        await session.commit()
        
        # Verify record inserted
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.id == token.id)
        )
        assert result.scalar_one_or_none() == token
```

**Test 7: Unique Constraint on token_hash**
```python
async def test_duplicate_token_hash_fails():
    """Insert duplicate token_hash raises unique constraint error."""
    async with get_session() as session:
        token1 = RefreshToken(
            user_id=user_id1,
            token_hash="e" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(token1)
        await session.commit()
        
        # Try to insert duplicate hash for different user
        token2 = RefreshToken(
            user_id=user_id2,
            token_hash="e" * 64,  # Same hash!
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(token2)
        
        with pytest.raises(IntegrityError):
            await session.commit()
```

**Test 8: Cascade Deletion**
```python
async def test_user_deletion_cascades_to_tokens():
    """Deleting user cascades to delete their refresh tokens."""
    async with get_session() as session:
        # Create user
        user = User(
            email="cascade@example.com",
            password_hash="hash",
            full_name="Cascade Test",
        )
        session.add(user)
        await session.commit()
        
        # Create tokens
        token1 = RefreshToken(
            user_id=user.id,
            token_hash="f" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        token2 = RefreshToken(
            user_id=user.id,
            token_hash="g" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add_all([token1, token2])
        await session.commit()
        
        token_ids = [token1.id, token2.id]
        
        # Delete user
        await session.delete(user)
        await session.commit()
        
        # Verify tokens deleted
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.id.in_(token_ids))
        )
        assert result.scalars().all() == []
```

**Test 9: Query by user_id**
```python
async def test_query_tokens_by_user_id():
    """Query all tokens for a user succeeds."""
    async with get_session() as session:
        # Create tokens
        token1 = RefreshToken(
            user_id=user_id,
            token_hash="h" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        token2 = RefreshToken(
            user_id=user_id,
            token_hash="i" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add_all([token1, token2])
        await session.commit()
        
        # Query by user_id
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        tokens = result.scalars().all()
        
        assert len(tokens) == 2
        assert token1 in tokens
        assert token2 in tokens
```

**Test 10: Revocation**
```python
async def test_revoke_token():
    """Update token to set is_revoked=True and revoked_at succeeds."""
    async with get_session() as session:
        token = RefreshToken(
            user_id=user_id,
            token_hash="j" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(token)
        await session.commit()
        
        token_id = token.id
        
        # Revoke token
        token.is_revoked = True
        token.revoked_at = datetime.now(UTC)
        await session.commit()
        
        # Verify revocation
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.id == token_id)
        )
        revoked_token = result.scalar_one()
        
        assert revoked_token.is_revoked is True
        assert revoked_token.revoked_at is not None
```

**Test 11: Query Active Tokens**
```python
async def test_query_active_tokens():
    """Query active tokens (WHERE is_revoked=False) succeeds."""
    async with get_session() as session:
        # Create active token
        active = RefreshToken(
            user_id=user_id,
            token_hash="k" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            is_revoked=False,
        )
        
        # Create revoked token
        revoked = RefreshToken(
            user_id=user_id,
            token_hash="l" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            is_revoked=True,
            revoked_at=datetime.now(UTC),
        )
        
        session.add_all([active, revoked])
        await session.commit()
        
        # Query active tokens
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
            )
        )
        tokens = result.scalars().all()
        
        assert len(tokens) == 1
        assert tokens[0] == active
```

**Test 12: Query Validation (Expiry + Revocation)**
```python
async def test_validation_query():
    """Standard validation query works correctly."""
    async with get_session() as session:
        now_utc = datetime.now(UTC)
        
        # Valid token
        valid = RefreshToken(
            user_id=user_id,
            token_hash="m" * 64,
            expires_at=now_utc + timedelta(days=30),
            is_revoked=False,
        )
        
        # Expired token
        expired = RefreshToken(
            user_id=user_id,
            token_hash="n" * 64,
            expires_at=now_utc - timedelta(days=1),  # Past
            is_revoked=False,
        )
        
        # Revoked token
        revoked = RefreshToken(
            user_id=user_id,
            token_hash="o" * 64,
            expires_at=now_utc + timedelta(days=30),
            is_revoked=True,
        )
        
        session.add_all([valid, expired, revoked])
        await session.commit()
        
        # Validation query
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == "m" * 64,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > now_utc,
            )
        )
        token = result.scalar_one_or_none()
        
        assert token == valid
        
        # Same query with invalid tokens should return None
        for invalid_hash in ["n" * 64, "o" * 64]:
            result = await session.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash == invalid_hash,
                    RefreshToken.is_revoked == False,
                    RefreshToken.expires_at > now_utc,
                )
            )
            assert result.scalar_one_or_none() is None
```

---

## Error Handling and Repository Exceptions

**Out of Scope for This Task:** Repository interface and exceptions are defined in E3.T10+. This design specifies ORM model only.

**However, ORM Model Constraints Enable These Repository Errors:**

1. **DuplicateTokenHashError** (raised by unique constraint on token_hash)
   - Trigger: Attempt to insert token with duplicate hash
   - Database: IntegrityError from unique constraint
   - Repository: Translates to domain exception

2. **TokenNotFoundError** (no constraint, repository logic)
   - Trigger: Query token_hash returns no rows
   - Database: No rows returned
   - Repository: Raises exception if token required

3. **InvalidTokenError** (application logic)
   - Trigger: Token is revoked or expired
   - Check: is_revoked=True OR expires_at < now()
   - Repository: Application-layer validation

4. **UserNotFoundError** (foreign key constraint)
   - Trigger: Attempt to insert token with non-existent user_id
   - Database: Foreign key constraint violation
   - Repository: Translates to domain exception

---

## Migration Validation Checklist

- [ ] RefreshToken model defined in `backend/app/models/refresh_token.py`
- [ ] RefreshToken exported from `backend/app/models/__init__.py`
- [ ] No import errors: `python -c "from app.models import RefreshToken; print(RefreshToken)"`
- [ ] Model syntax valid: `python -m py_compile app/models/refresh_token.py`
- [ ] Alembic migration generated: `alembic revision --autogenerate`
- [ ] Migration file created in `backend/migrations/versions/`
- [ ] Migration reviewed for accuracy:
  - Table name is "user_refresh_tokens"
  - All columns present with correct types
  - Unique constraint on token_hash
  - Foreign key with ON DELETE CASCADE
  - All indexes present
  - downgrade() reverses all changes
- [ ] Unit tests created: `backend/tests/unit/test_refresh_token_model.py`
- [ ] All unit tests pass: `pytest tests/unit/test_refresh_token_model.py -v`
- [ ] All integration tests pass
- [ ] Ruff passes: `ruff check app/models/refresh_token.py` (0 violations)
- [ ] MyPy passes: `mypy app/models/refresh_token.py --strict` (0 errors)
- [ ] No regressions: `pytest tests/ -v` (all E3.T1-E3.T8 tests still pass)

---

## Implementation Notes

### Design Traces

- Traces to: 04-Database-Design §4 (ERD, user_refresh_tokens table)
- Traces to: 04-Database-Design §3.2 (Refresh tokens as server-side session control)
- Traces to: 04-Database-Design §5.2 (RefreshToken schema specification)
- Traces to: 08-Security-Architecture §5 (JWT and refresh token lifecycle)
- Traces to: 07-Backend-Development-Standards §8 (ORM model conventions)
- Traces to: 22-Engineering-Backlog E3.T9 (task definition)

### Follow-Up Tasks

- **E3.T10:** Repository interfaces (RefreshTokenRepository with queries)
- **E3.T11:** Token validation service (hashing, expiry checks)
- **E4.T2:** Token service (generation, issuance, validation)
- **E4.T3:** Authentication service (login, refresh token flow)
- **E4.T4+:** Route handlers (login, refresh, logout endpoints)

### Key Assumptions

1. Token hashing performed by application (not database function)
2. Token generation performed by application (not database function)
3. Session context (user-agent, IP) captured by application and passed to ORM
4. Cleanup job (deleting expired tokens) implemented separately
5. No rate limiting in this model (application layer)

---

## Glossary

| Term | Definition |
|---|---|
| **Refresh Token** | Long-lived token used to obtain new access tokens without re-authentication |
| **Token Hash** | SHA-256 hash of the opaque token value; stored in database (not raw token) |
| **Revocation** | Marking a token as invalid (is_revoked=true) without deleting the record |
| **Session** | Active authenticated user connection; managed by refresh token record |
| **Cascade Deletion** | Database constraint that deletes child records when parent is deleted |
| **Server-Side Default** | Default value applied by database on INSERT if application doesn't provide |
| **Partial Index** | Index with WHERE clause; includes only matching rows (smaller, faster) |

