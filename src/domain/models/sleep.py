"""Canonical domain models for a sleep session and its stage intervals."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from domain.models.base import BaseEntity
from domain.models.enums import Provider, SleepStage


class SleepStageInterval(BaseEntity):
    """A contiguous interval spent in a single sleep stage.

    Stored as a sequence within SleepSession to allow timeline reconstruction
    and sleep architecture visualisation.
    """

    start_time: datetime = Field(description="UTC-aware start of this stage interval")
    end_time: datetime = Field(description="UTC-aware end of this stage interval")
    stage: SleepStage = Field(description="Sleep stage classification")
    duration_seconds: float = Field(ge=0, description="Interval length in seconds")

    @field_validator("start_time", "end_time")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware")
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> SleepStageInterval:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class SleepSession(BaseEntity):
    """A single night's sleep recording from any provider.

    PPI/HRV fields here are overnight averages.  Individual sample-level data
    lives in PPISample and HeartRateSample.
    """

    # --- Identity ---
    id: str = Field(description="Unique session identifier (provider-scoped)")
    user_id: str = Field(description="Platform-agnostic user identifier")
    provider: Provider = Field(description="Data source")

    # --- Temporal ---
    start_time: datetime = Field(description="UTC-aware time when the user went to bed")
    end_time: datetime = Field(description="UTC-aware time when the user woke up")
    duration_seconds: float = Field(ge=0, description="Total recording duration in seconds")

    # --- Sleep quality ---
    sleep_latency_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Time from lights-out to sleep onset in seconds",
    )
    continuity_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Sleep continuity index scaled to 20-100 (Polar raw: 1.0-5.0 × 20)",
    )
    sleep_efficiency_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Fraction of time in bed actually spent asleep (0-100 %)",
    )

    # --- Architecture (durations in seconds) ---
    light_sleep_seconds: float | None = Field(
        default=None, ge=0, description="Total light sleep in seconds"
    )
    deep_sleep_seconds: float | None = Field(
        default=None, ge=0, description="Total deep (slow-wave) sleep in seconds"
    )
    rem_sleep_seconds: float | None = Field(
        default=None, ge=0, description="Total REM sleep in seconds"
    )
    awake_seconds: float | None = Field(
        default=None, ge=0, description="Total awake time during the recording in seconds"
    )
    interruptions: int | None = Field(
        default=None,
        ge=0,
        description="Number of distinct awakenings during the night",
    )
    short_interruption_duration_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Total duration of short awakenings (< 5 min) during the night in seconds",
    )
    long_interruption_duration_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Total duration of long awakenings (≥ 5 min) during the night in seconds",
    )
    unknown_sleep_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Total duration of epochs with unrecognised stage (e.g. bad skin contact) in seconds",
    )

    # --- Cardiovascular & HRV ---
    average_hr_bpm: float | None = Field(
        default=None,
        ge=20,
        le=250,
        description="Mean overnight heart rate in beats per minute",
    )
    min_hr_bpm: float | None = Field(
        default=None,
        ge=20,
        le=250,
        description="Lowest recorded heart rate during sleep in beats per minute",
    )
    average_ppi_ms: float | None = Field(
        default=None,
        ge=300,
        le=2500,
        description="Mean overnight peak-to-peak (RR) interval in milliseconds",
    )
    rmssd_ms: float | None = Field(
        default=None,
        ge=0,
        description="Root mean square of successive PPI differences (HRV index) in milliseconds",
    )
    sdnn_ms: float | None = Field(
        default=None,
        ge=0,
        description="Standard deviation of PPI intervals (HRV index) in milliseconds",
    )

    # --- Respiratory ---
    breathing_rate_bpm: float | None = Field(
        default=None,
        ge=4,
        le=60,
        description="Average breathing rate in breaths per minute",
    )
    snoring_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Total detected snoring duration in seconds",
    )

    # --- Temperature ---
    mean_skin_temperature_celsius: float | None = Field(
        default=None,
        ge=20,
        le=42,
        description="Mean skin temperature recorded overnight in degrees Celsius",
    )
    temperature_deviation_celsius: float | None = Field(
        default=None,
        description=(
            "Deviation of overnight temperature from the rolling personal baseline "
            "in degrees Celsius (positive = warmer than usual)"
        ),
    )

    # --- Recording timezone ---
    utc_offset_minutes: int | None = Field(
        default=None,
        description=(
            "UTC offset in minutes at the time of recording "
            "(e.g. 120 for UTC+2, -240 for UTC-4). "
            "None means the original timestamp had no timezone info."
        ),
    )

    # --- Stage timeline ---
    stage_intervals: list[SleepStageInterval] = Field(
        default_factory=list,
        description="Ordered sequence of sleep stage intervals for timeline visualisation",
    )

    @field_validator("start_time", "end_time")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware")
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> SleepSession:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self
