"""Canonical domain models for daily recovery and readiness metrics."""

from __future__ import annotations

from datetime import date

from pydantic import Field

from domain.models.base import BaseEntity
from domain.models.enums import Provider


class RecoveryContributors(BaseEntity):
    """Signal-level inputs that contribute to the composite recovery score.

    Stored alongside the final score so the dashboard can render a
    contributor breakdown ('what drove today's recovery') without re-running
    the scoring engine.
    """

    hrv_z_score: float | None = Field(
        default=None,
        description=(
            "z-score of overnight RMSSD relative to the rolling 30-day personal baseline. "
            "Positive = HRV higher than usual (good recovery signal)."
        ),
    )
    resting_hr_z_score: float | None = Field(
        default=None,
        description=(
            "z-score of resting heart rate relative to the rolling 30-day baseline. "
            "Negative = HR lower than usual (good recovery signal)."
        ),
    )
    sleep_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Sleep quality score for the preceding night (0-100)",
    )
    previous_strain_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Strain score from the prior day that reduces today's recovery",
    )
    temperature_deviation_celsius: float | None = Field(
        default=None,
        description=(
            "Overnight skin temperature deviation from personal baseline in °C. "
            "Elevation (>0.5 °C) is a stress / illness signal."
        ),
    )
    nightly_recharge_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Provider nightly recharge / ANS charge score (0-100)",
    )
    fitness_load_z_score: float | None = Field(
        default=None,
        description=(
            "z-score of Polar tolerance (28-day rolling cardio load) relative to the "
            "rolling 30-day personal baseline. Positive = higher chronic load than usual "
            "(better aerobic fitness / adaptation)."
        ),
    )


class RecoveryMetrics(BaseEntity):
    """Aggregated daily recovery and readiness metrics.

    One record per user per date.  The scoring engine (services/scoring)
    computes these from raw SleepSession, PPISample, and TemperatureSample
    data and persists the result here for fast retrieval.
    """

    # --- Identity ---
    record_date: date = Field(description="Calendar date these metrics represent")
    user_id: str = Field(description="Platform-agnostic user identifier")
    provider: Provider = Field(description="Primary data source for this record")

    # --- Composite score ---
    recovery_score: float = Field(
        ge=0,
        le=100,
        description=(
            "Composite readiness score (0-100).  "
            "0-33 = poor, 34-66 = moderate, 67-100 = optimal."
        ),
    )

    # --- Raw physiological signals ---
    rmssd_ms: float | None = Field(
        default=None,
        ge=0,
        description="Overnight RMSSD (primary HRV metric) in milliseconds",
    )
    sdnn_ms: float | None = Field(
        default=None,
        ge=0,
        description="Overnight SDNN in milliseconds",
    )
    resting_hr_bpm: float | None = Field(
        default=None,
        ge=20,
        le=250,
        description="Resting heart rate in beats per minute",
    )
    mean_skin_temperature_celsius: float | None = Field(
        default=None,
        ge=20,
        le=42,
        description="Overnight mean wrist skin temperature in °C",
    )

    # --- Baseline context ---
    hrv_baseline_ms: float | None = Field(
        default=None,
        ge=0,
        description="Rolling 30-day RMSSD baseline for this user in milliseconds",
    )
    resting_hr_baseline_bpm: float | None = Field(
        default=None,
        ge=20,
        le=250,
        description="Rolling 30-day resting HR baseline in BPM",
    )

    # --- Score contributors (for UI breakdown) ---
    contributors: RecoveryContributors = Field(
        default_factory=RecoveryContributors,
        description="Per-signal contributions used to explain the composite score",
    )
