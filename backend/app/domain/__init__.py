"""
Domain layer.

Contains business entities, value objects, repository interfaces,
domain services, domain events, and domain exceptions as defined in 02-Domain-Model.md.

This layer must remain independent of infrastructure and frameworks.
It has zero dependencies on FastAPI, SQLAlchemy, Celery, Redis,
S3 clients, or any other framework or infrastructure library.

See: 06-Repository-Structure.md §6.
"""

from app.domain.exceptions import (
    AlreadyExists,
    ConflictError,
    ConstraintViolation,
    NotFound,
    RepositoryException,
)


__all__ = [
    "AlreadyExists",
    "ConflictError",
    "ConstraintViolation",
    "NotFound",
    "RepositoryException",
]
