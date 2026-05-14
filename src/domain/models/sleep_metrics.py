"""Canonical domain model for aggregated daily sleep quality metrics."""

from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from domain.models.base import BaseEntity
from domain.models.enums import Provider


class SleepMetrics(BaseEntity):
    """Aggregated sleep quality metrics derived from a SleepSession.

    One record per user per date.  Separating SleepMetrics from SleepSession
    keeps raw session data clean while allowing the scoring engine to attach
    computed quality scores without mutating the original record.

    Sleep score formula:
        score = w_efficiency * efficiency
               + w_duration * duration_score
               + w_architecture * architecture_score
               + w_hrv * hrv_score
    Implemented in services/scoring/sleep_scorer.py.
    """

    # --- Identity ---
    record_date: date = Field(description="Calendar date (night) these metrics represent")
    user_id: str = Field(description="Platform-agnostic user identifier")
    provider: Provider = Field(description="Primary data source for this record")
    sleep_session_id: str | None = Field(
        default=None,
        description="ID of the SleepSession this record was derived from",
    )

    # --- Composite score ---
    sleep_score: float = Field(
        ge=0,
        le=100,
        description=(
            "Composite sleep quality score (0-100).  "
            "0-33 = poor, 34-66 = fair, 67-100 = good."
        ),
    )

    # --- Duration ---
    total_sleep_seconds: float = Field(
        ge=0,
        description="Total time actually asleep (excluding awake time) in seconds",
    )
    time_in_bed_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Total recording window duration in seconds",
    )

    # --- Efficiency ---
    sleep_efficiency_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="total_sleep_seconds / time_in_bed_seconds x 100",
    )
    sleep_latency_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Time from bed to sleep onset in seconds (lower = better)",
    )

    # --- Architecture percentages (all as fraction of TIME IN BED) ---
    # DEEP + REM + LIGHT + WAKE + UNKNOWN = 100 % (derived from hypnogram epochs)
    deep_sleep_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Fraction of time in bed spent in deep (slow-wave) sleep (0-100 %)",
    )
    rem_sleep_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Fraction of time in bed spent in REM (0-100 %)",
    )
    light_sleep_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Fraction of time in bed spent in light NREM (0-100 %)",
    )
    awake_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Fraction of time in bed spent awake / interrupted (0-100 %)",
    )
    unknown_sleep_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Fraction of time in bed with unrecognised sleep stage "
            "(e.g. bad skin contact) (0-100 %)"
        ),
    )
    short_interruption_duration_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Total duration of short awakenings (< 5 min) in seconds",
    )
    long_interruption_duration_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Total duration of long awakenings (≥ 5 min) in seconds",
    )

    # --- HRV & cardiovascular ---
    rmssd_ms: float | None = Field(
        default=None,
        ge=0,
        description="Overnight mean RMSSD in milliseconds",
    )
    average_hr_bpm: float | None = Field(
        default=None,
        ge=20,
        le=250,
        description="Overnight mean heart rate in BPM",
    )

    # --- Consistency (cross-night) ---
    sleep_consistency_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Rolling 7-night sleep consistency score (0-100).  "
            "Rewards regular sleep/wake times and stable duration."
        ),
    )

    @model_validator(mode="after")
    def architecture_within_bounds(self) -> SleepMetrics:
        """Validate that the five time-in-bed components don't wildly exceed 100 %.

        DEEP + REM + LIGHT + WAKE + UNKNOWN are all fractions of time in bed
        and should sum to ≤ 102 % (allowing for per-value rounding errors).
        """
        parts = [
            self.deep_sleep_pct,
            self.rem_sleep_pct,
            self.light_sleep_pct,
            self.awake_pct,
            self.unknown_sleep_pct,
        ]
        non_null = [p for p in parts if p is not None]
        if non_null:
            total = sum(non_null)
            if total > 102.0:
                raise ValueError(
                    f"Sleep stage percentages sum to {total:.1f}% (> 102%); "
                    "all values must be fractions of time in bed"
                )
        return self
