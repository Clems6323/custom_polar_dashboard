"""Base Pydantic models shared by all domain entities."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BaseEntity(BaseModel):
    """Root base for all domain entities.

    Frozen (immutable) by default — mutations produce new instances.
    """

    model_config = ConfigDict(frozen=True)


class BaseTimeSeriesSample(BaseEntity):
    """Common fields for physiological time-series data points.

    Shared by HeartRateSample, PPISample, and TemperatureSample to avoid
    field repetition and enable generic processing in analytics pipelines.
    """

    session_id: str | None = Field(
        default=None,
        description="Session this sample belongs to, or None for continuous background samples",
    )
    user_id: str = Field(description="Platform-agnostic user identifier")
    timestamp: datetime = Field(description="UTC-aware timestamp of the measurement")
    provider: str = Field(description="Data source, e.g. 'polar', 'garmin', 'demo'")
