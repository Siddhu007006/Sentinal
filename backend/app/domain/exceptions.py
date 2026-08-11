"""
Domain layer exceptions.

Defines exception types used by repositories and domain services to signal
errors in domain language. These exceptions form the contract between the
Domain/Application layers and the Infrastructure layer.

Database exceptions (SQLAlchemy IntegrityError, NoResultFound, etc.) are
caught by the Infrastructure layer and converted to these domain exceptions.
The Application and Domain layers never import or see database-specific
exceptions.

See: E3.T7 Specification § Requirement R8 (Error Handling)
See: 07-Backend-Development-Standards § Error Handling
See: 08-Security-Architecture § Error Message Security
"""


class RepositoryException(Exception):  # noqa: N818
    """Base exception for repository operations.

    All repository-related exceptions inherit from this base class.
    This allows Application layer to catch all repository errors with
    a single except clause if needed.

    Usage:
        try:
            user = await user_repo.get_by_id(user_id)
        except RepositoryException as e:
            # Handle any repository error
            log.error(f"Repository error: {e}")
    """

    pass


class NotFound(RepositoryException):
    """Entity not found in repository.

    Raised when a get_by_id() or similar lookup query returns no result.

    This is distinct from an empty list returned by list() — a NotFound
    exception signals that a specific requested entity does not exist,
    and the Application layer should typically treat this as an error
    (return 404 Not Found to client, log as warning, etc.).

    Usage:
        >>> user = await user_repo.get_by_id(user_id)
        NotFound: User with id 5b6c7d8e-9f01-4a2b-8c3d-4e5f60718293 not found
    """

    pass


class AlreadyExists(RepositoryException):
    """Entity already exists (unique constraint violation).

    Raised when create() or similar insert operation violates a UNIQUE
    constraint in the database.

    Common cases:
    - User with email already exists
    - Asset with normalized_value + asset_type already exists
    - Analysis for (asset, analyzer_key, analyzer_version) already completed

    Usage:
        >>> user = await user_repo.create(user)
        AlreadyExists: User with email jane@example.com already exists
    """

    pass


class ConstraintViolation(RepositoryException):
    """Database constraint violated (FK or CHECK constraint).

    Raised when create() or update() operation violates a FOREIGN KEY or
    CHECK constraint in the database.

    Common cases:
    - Attempting to create an entity with a non-existent foreign key reference
    - Attempting to create an entity that violates a CHECK constraint
    - Attempting to delete a user that has associated assets (FK RESTRICT)

    Usage:
        >>> asset = await asset_repo.create(asset)
        ConstraintViolation: Cannot insert asset: user_id references non-existent user
    """

    pass


class ConflictError(RepositoryException):
    """Data integrity violation (other than unique/FK/CHECK constraints).

    Raised when create() or update() operation violates database integrity
    rules that don't fit the categories of AlreadyExists, ConstraintViolation,
    or other specific constraint violations.

    This is a catch-all for database integrity errors that should be rare
    in production if the Application layer is working correctly.

    Usage:
        >>> result = await repo.create(entity)
        ConflictError: Data integrity violation: [database error details]
    """

    pass


class TokenAlreadyRotatedError(Exception):
    """Raised when a token has been concurrently rotated (race condition handled).

    Occurs when two requests attempt to refresh the same refresh token
    simultaneously. The database-level atomic UPDATE ensures exactly one
    succeeds. The other request gets this exception, indicating the token
    was already revoked by a concurrent request.

    This is a normal, expected condition in concurrent scenarios and should
    result in HTTP 409 Conflict to the client. The client can retry with
    the new tokens from the successful concurrent request (if available).

    Usage:
        >>> await auth_service.refresh(refresh_token)
        TokenAlreadyRotatedException: Token was concurrently rotated by another request

    Lifecycle:
        1. Request A: decode token → atomic_revoke_by_jti() → SUCCESS (True)
        2. Request B: decode token → atomic_revoke_by_jti() → FAIL (False, raise this)
        3. Request A: create new tokens → return to client
        4. Request B: raise this exception → handler returns 409 → client sees
           token was rotated
    """

    pass
