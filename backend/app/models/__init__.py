"""
ORM models package.

Contains SQLAlchemy ORM models for all domain entities. Each model maps to a
single database table and inherits from BaseModel (UUID PK, timestamps).

Models are organized by domain entity, not by database schema. Each model file
should contain a single model class with its related enums and constraints.

Traces to: 06-Repository-Structure §6 (models directory structure)
Traces to: 07-Backend-Development-Standards §8 (ORM model conventions)
"""

from app.models.user import User, UserRole


__all__ = [
    "User",
    "UserRole",
]
