"""Shared MCP output schema types used across all tools."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ToolMeta(BaseModel):
    """Metadata attached to every tool response.

    Callers can use ``confidence`` to decide how much weight to give the result
    (e.g. 0.5 = half of optional signals were missing, fall-back to neutral used).
    ``missing_signals`` lists the specific fields that were absent.
    """

    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when this response was generated",
    )
    data_available: bool = Field(
        description="False when no record exists for the requested date/user"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of optional signals available (0 = no data, 1 = all fields present)",
    )
    missing_signals: list[str] = Field(
        default_factory=list,
        description="Names of optional fields that were absent (fell back to neutral)",
    )


class NotFoundOutput(BaseModel):
    """Returned by any tool when no record exists for the given parameters."""

    error: str = Field(default="not_found")
    message: str
    metadata: ToolMeta
