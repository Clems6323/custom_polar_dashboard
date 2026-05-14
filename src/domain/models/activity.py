"""Canonical domain model for a training / exercise session."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from domain.models.base import BaseEntity
from domain.models.enums import Provider, SportType


class ActivitySession(BaseEntity):
    """A single training or exercise session from any provider.

    All provider-specific fields (Polar training load score, Garmin Training
    Stress Score, etc.) are normalised to provider-agnostic fields before
    being stored here.  The ingestion layer is responsible for this mapping.
    """

    # --- Identity ---
    id: str = Field(description="Unique session identifier (provider-scoped)")
    user_id: str = Field(description="Platform-agnostic user identifier")
    provider: Provider = Field(description="Data source")

    # --- Temporal ---
    start_time: datetime = Field(description="UTC-aware session start timestamp")
    end_time: datetime = Field(description="UTC-aware session end timestamp")
    duration_seconds: float = Field(
        ge=0,
        description="Total session duration in seconds",
    )

    # --- Classification ---
    sport_type: SportType = Field(
        default=SportType.OTHER,
        description="Normalised activity category",
    )
    sport_label: str | None = Field(
        default=None,
        description="Original sport label from the provider before normalisation",
    )

    # --- Cardiovascular ---
    average_hr_bpm: float | None = Field(
        default=None,
        ge=20,
        le=250,
        description="Mean heart rate over the session in beats per minute",
    )
    max_hr_bpm: float | None = Field(
        default=None,
        ge=20,
        le=250,
        description="Peak heart rate during the session in beats per minute",
    )
    hr_zone_distribution: dict[str, float] | None = Field(
        default=None,
        description=(
            "Fraction of session time spent in each HR zone "
            "e.g. {'zone_1': 0.3, 'zone_2': 0.5, ...}"
        ),
    )

    # --- Load ---
    cardio_load: float | None = Field(
        default=None,
        ge=0,
        description="Polar Cardio Load from Training Load Pro (arbitrary units)",
    )
    muscle_load: float | None = Field(
        default=None,
        ge=0,
        description="Polar Muscle Load from Training Load Pro (where available)",
    )
    perceived_exertion: float | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Subjective rating of perceived exertion (1-10 Borg RPE)",
    )

    # --- Performance ---
    calories_kcal: float | None = Field(
        default=None,
        ge=0,
        description="Total energy expenditure in kilocalories",
    )
    distance_meters: float | None = Field(
        default=None,
        ge=0,
        description="Total distance covered in metres",
    )
    average_pace_sec_per_km: float | None = Field(
        default=None,
        ge=0,
        description="Average pace in seconds per kilometre (running/walking only)",
    )
    average_power_watts: float | None = Field(
        default=None,
        ge=0,
        description="Mean power output in watts (cycling only)",
    )

    @field_validator("start_time", "end_time")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware")
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> ActivitySession:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self
