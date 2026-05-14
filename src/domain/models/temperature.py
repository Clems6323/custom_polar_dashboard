"""Canonical domain model for skin temperature measurements."""

from __future__ import annotations

from pydantic import Field, field_validator

from domain.models.base import BaseTimeSeriesSample

# Wrist skin temperature in healthy adults: ~28-36 degrees C during sleep
_SKIN_TEMP_MIN_C: float = 20.0
_SKIN_TEMP_MAX_C: float = 42.0


class TemperatureSample(BaseTimeSeriesSample):
    """A single skin (wrist) temperature reading.

    Temperature data feeds into recovery and illness detection.  A rolling
    personal baseline is computed in the analytics layer; deviation from that
    baseline is the clinically meaningful signal (not the absolute value).
    """

    skin_temperature_celsius: float = Field(
        ge=_SKIN_TEMP_MIN_C,
        le=_SKIN_TEMP_MAX_C,
        description="Wrist skin temperature in degrees Celsius",
    )
    ambient_temperature_celsius: float | None = Field(
        default=None,
        ge=-30,
        le=60,
        description=(
            "Ambient (room) temperature in degrees Celsius at measurement time, "
            "if provided by the device.  Used to contextualise skin readings."
        ),
    )

    @field_validator("timestamp")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:  # noqa: F821
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v
