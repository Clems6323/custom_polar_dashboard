"""Canonical domain model for a single heart-rate measurement."""

from __future__ import annotations

from pydantic import Field, field_validator

from domain.models.base import BaseTimeSeriesSample


class HeartRateSample(BaseTimeSeriesSample):
    """A single instantaneous heart rate data point.

    Used for both intra-session HR curves and overnight resting HR streams.
    Individual samples feed into rolling HR statistics and zone calculations
    in the analytics layer.
    """

    hr_bpm: float = Field(
        ge=20,
        le=250,
        description="Instantaneous heart rate in beats per minute",
    )
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Measurement confidence reported by the device (0 = unreliable, 1 = high). "
            "Samples with low confidence may be excluded from aggregations."
        ),
    )

    @field_validator("timestamp")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:  # noqa: F821
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v
