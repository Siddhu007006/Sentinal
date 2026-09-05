"""Pydantic schemas for analyzer API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzerSchema(BaseModel):
    """Schema representing a registered analyzer."""

    key: str = Field(..., description="Unique analyzer identifier")
    version: str = Field(..., description="Analyzer implementation version")
    description: str = Field(..., description="Human-readable analyzer description")


class AnalyzerListResponse(BaseModel):
    """Schema for the list of analyzers response."""

    analyzers: list[AnalyzerSchema] = Field(
        ..., description="List of registered analyzers"
    )
    total: int = Field(..., description="Total number of analyzers")
