"""
Database exception mapping.

Converts SQLAlchemy and database exceptions to domain exceptions.

When the Infrastructure layer executes database operations (INSERT, UPDATE,
DELETE), the database may raise various exceptions:
- NoResultFound: Query returned no results
- IntegrityError: Constraint violated (UNIQUE, FK, CHECK)
- DatabaseError: Other database-level errors

This module provides map_db_exception() which catches these database exceptions
and converts them to domain exceptions (NotFound, AlreadyExists, etc.) so that
the Application and Domain layers never see database-specific exceptions.

The conversion strategy:
1. Inspect the exception type and message
2. Match to the most likely domain-level intent
3. Raise the corresponding domain exception with a domain-focused message

Example:
    ```python
    from sqlalchemy.exc import IntegrityError, NoResultFound
    from app.domain.exceptions import NotFound, AlreadyExists

    try:
        user = await session.get(UserORM, user_id)
        if not user:
            raise NoResultFound()
    except NoResultFound:
        raise map_db_exception(NoResultFound())  # -> NotFound
    except IntegrityError as e:
        if "UNIQUE" in str(e):
            raise map_db_exception(e)  # -> AlreadyExists
        raise map_db_exception(e)  # -> ConstraintViolation or ConflictError
    ```

Traces to: E3.T7 Specification § Requirement R8 (Error Handling)
Traces to: E3.T7 Design § Section 4.2 (Error Mapping)
"""

from __future__ import annotations

from sqlalchemy.exc import (
    DatabaseError,
    IntegrityError,
    InvalidRequestError,
    NoResultFound,
    OperationalError,
)

from app.domain.exceptions import (
    AlreadyExists,
    ConflictError,
    ConstraintViolation,
    NotFound,
    RepositoryException,
)


def map_db_exception(exc: Exception) -> RepositoryException:
    """
    Convert a SQLAlchemy or database exception to a domain exception.

    Maps database-level exceptions to domain-level exceptions so that the
    Application and Domain layers can handle errors using domain terminology
    rather than database-specific errors.

    Mapping strategy:
    1. NoResultFound -> NotFound (entity not found by query)
    2. IntegrityError with "UNIQUE" -> AlreadyExists (duplicate key)
    3. IntegrityError with "FOREIGN KEY" -> ConstraintViolation (invalid reference)
    4. IntegrityError with "CHECK" -> ConstraintViolation (invalid value)
    5. IntegrityError (other) -> ConflictError (data integrity issue)
    6. Other -> ConflictError (unexpected database error)

    Args:
        exc: The SQLAlchemy or database exception to convert

    Returns:
        A domain exception (NotFound, AlreadyExists, ConstraintViolation,
        or ConflictError) that represents the domain-level intent

    Example:
        >>> from sqlalchemy.exc import NoResultFound
        >>> try:
        ...     result = await session.scalar(select(User).where(...))
        ...     if not result:
        ...         raise NoResultFound()
        ... except NoResultFound as e:
        ...     raise map_db_exception(e)
        NotFound: Entity not found

        >>> from sqlalchemy.exc import IntegrityError
        >>> try:
        ...     await session.execute(insert(User).values(...))
        ... except IntegrityError as e:
        ...     raise map_db_exception(e)  # -> AlreadyExists or ConstraintViolation
    """
    exc_str = str(exc).upper()

    # Handle NoResultFound: entity not found in query
    if isinstance(exc, NoResultFound):
        return NotFound("Entity not found")

    # Handle IntegrityError: constraint violations
    if isinstance(exc, IntegrityError):
        # UNIQUE constraint violation: entity with this value already exists
        # Examples: duplicate email, duplicate hash, etc.
        if "UNIQUE" in exc_str or "unique constraint" in exc_str.lower():
            msg = "Entity with this value already exists"
            if hasattr(exc, "orig") and exc.orig:
                msg = str(exc.orig)
            return AlreadyExists(msg)

        # FOREIGN KEY constraint violation: invalid reference to related entity
        # Example: asset references non-existent user
        if (
            "FOREIGN KEY" in exc_str
            or "foreign key" in exc_str.lower()
            or "fk_" in exc_str.lower()
        ):
            msg = "Invalid reference to related entity"
            if hasattr(exc, "orig") and exc.orig:
                msg = str(exc.orig)
            return ConstraintViolation(msg)

        # CHECK constraint violation: value violates business rule
        # Example: status must be one of (pending, running, completed)
        if "CHECK" in exc_str or "check constraint" in exc_str.lower():
            msg = "Value violates database constraint"
            if hasattr(exc, "orig") and exc.orig:
                msg = str(exc.orig)
            return ConstraintViolation(msg)

        # Other IntegrityError: catch-all for data integrity violations
        msg = "Data integrity violation"
        if hasattr(exc, "orig") and exc.orig:
            msg = str(exc.orig)
        return ConflictError(msg)

    # Handle InvalidRequestError: SQLAlchemy usage error (unexpected in production)
    if isinstance(exc, InvalidRequestError):
        return ConflictError(f"Invalid database request: {exc}")

    # Handle OperationalError: connection, environment, or permission issues
    # These are typically transient (connection lost, database restarts)
    if isinstance(exc, OperationalError):
        return ConflictError(f"Database operation failed: {exc}")

    # Handle DatabaseError: catch-all for database-level errors
    if isinstance(exc, DatabaseError):
        return ConflictError(f"Database error: {exc}")

    # Fallback: unknown exception type, re-raise as ConflictError
    return ConflictError(f"Unexpected database error: {exc}")
