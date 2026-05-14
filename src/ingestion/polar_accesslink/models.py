"""Pydantic models for raw Polar AccessLink v3 API responses.

These models are intentionally permissive (all optional fields) to survive
API additions without breaking ingestion. Normalization functions translate
them into strict canonical domain models.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field


class PolarHeartRateZone(BaseModel):
    """Single HR zone entry from an exercise."""

    index: int
    calories: int | None = None
    in_zone: str | None = None  # ISO 8601 duration


class PolarHeartRateSummary(BaseModel):
    """Average and maximum HR from an exercise."""

    average: int | None = None
    maximum: int | None = None


class PolarTrainingLoadPro(BaseModel):
    """Nested Training Load Pro block returned by the Polar exercises API."""

    cardio_load: float | None = Field(
        default=None,
        validation_alias=AliasChoices("cardio_load", "cardio-load"),
    )
    muscle_load: float | None = Field(
        default=None,
        validation_alias=AliasChoices("muscle_load", "muscle-load"),
    )
    model_config = {"populate_by_name": True, "extra": "ignore"}


class PolarExercise(BaseModel):
    """Raw exercise record from an exercise transaction."""

    id: str
    transaction_id: int | None = None
    upload_time: str | None = None
    polar_user: str | None = None
    start_time: str = Field(description="Local start time, e.g. '2024-05-10T08:00:00'")
    start_time_utc_offset: int = Field(
        default=0,
        description="Offset of local time from UTC in minutes (e.g. 120 = UTC+2)",
    )
    duration: str = Field(description="ISO 8601 duration, e.g. 'PT1H15M30.000S'")
    calories: int | None = None
    distance: float | None = None
    heart_rate: PolarHeartRateSummary | None = None
    heart_rate_zones: list[PolarHeartRateZone] = Field(default_factory=list)
    training_load_pro: PolarTrainingLoadPro | None = Field(
        default=None,
        validation_alias=AliasChoices("training_load_pro", "training-load-pro"),
    )
    sport: str | None = None
    detailed_sport_info: str | None = None
    has_route: bool | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}


class PolarExerciseListResponse(BaseModel):
    """List response from GET /v3/exercises — full exercise objects."""

    exercises: list[PolarExercise] = Field(default_factory=list)


class PolarActivitySummary(BaseModel):
    """Raw daily activity summary from GET /v3/users/activities."""

    id: int | None = None
    polar_user: str | None = None
    date: str | None = Field(default=None, description="Calendar date, e.g. '2024-05-10'")
    start_time: str | None = None  # new list endpoint returns start_time instead of date
    created: str | None = None
    calories: int | None = None
    active_calories: int | None = None
    duration: str | None = Field(default=None, description="Total active duration (ISO 8601)")
    active_steps: int | None = None
    distance: float | None = None
    distance_from_steps: float | None = None

    model_config = {"extra": "ignore"}


class PolarActivityListResponse(BaseModel):
    """List response from GET /v3/users/activities — full activity objects.

    The key uses a hyphen which can't be a Python identifier, so we alias it.
    """

    activity_log: list[PolarActivitySummary] = Field(default_factory=list, alias="activity-log")

    model_config = {"populate_by_name": True}


class PolarSleepData(BaseModel):
    """Sleep data for a single night from the Polar sleep endpoint."""

    polar_user: str | None = None
    date: str = Field(description="The morning date, e.g. '2024-05-10'")
    sleep_start_time: str = Field(description="Local datetime, e.g. '2024-05-09T23:45:00.000'")
    sleep_end_time: str = Field(description="Local datetime, e.g. '2024-05-10T07:30:00.000'")
    device_id: str | None = None

    # Continuity
    continuity: float | None = None
    continuity_class: int | None = None

    # Stage durations (seconds)
    light_sleep: int | None = None
    deep_sleep: int | None = None
    rem_sleep: int | None = None
    unrecognized_sleep_stage: int | None = None
    total_interruption_duration: int | None = None
    short_interruption_duration: int | None = None
    long_interruption_duration: int | None = None

    # Scores
    sleep_score: float | None = None
    sleep_charge: int | None = None
    sleep_rating: int | None = None
    sleep_goal_minutes: int | None = None

    # Hypnogram: each character = 5-min interval. '1'=LIGHT '2'=DEEP '3'=REM '4'=UNKNOWN
    hypnogram_5min: str | None = None

    # Heart rate samples keyed by offset from midnight ("HH:MM" -> bpm int)
    heart_rate_samples: dict[str, int] | None = None


class PolarSleepListResponse(BaseModel):
    """List response from GET /v3/users/sleep — contains full sleep objects."""

    nights: list[PolarSleepData] = Field(default_factory=list)


class PolarNightlyRecharge(BaseModel):
    """Nightly recharge (ANS recovery) data for a single night."""

    polar_user: str | None = None
    date: str = Field(description="Calendar date, e.g. '2024-05-10'")

    # ANS charge (0-1 scale; 0 = poor, 1 = excellent)
    ans_charge: float | None = None
    ans_charge_status: int | None = None  # 1-5 classification
    nightly_recharge_status: int | None = None  # 1-5 classification

    # Cardiac metrics
    heart_rate_avg: int | None = None  # mean overnight HR in bpm
    beat_to_beat_avg: int | None = None  # mean PPI in ms
    heart_rate_variability_avg: float | None = Field(
        default=None,
        description="Overnight RMSSD (5-min averages) in milliseconds",
    )

    # Respiratory
    breathing_rate_avg: float | None = None  # breaths per minute

    # 5-minute time series
    hrv_samples: dict[str, int] | None = Field(
        default=None,
        description="5-min RMSSD samples keyed by 'HH:MM' (local time) → ms",
    )
    breathing_samples: dict[str, float] | None = Field(
        default=None,
        description="5-min respiratory rate samples keyed by 'HH:MM' → breaths/min",
    )

    model_config = {"extra": "ignore"}


class PolarNightlyRechargeListResponse(BaseModel):
    """List response from GET /v3/users/nightly-recharge — contains full recharge objects."""

    recharges: list[PolarNightlyRecharge] = Field(default_factory=list)


class PolarHRSample(BaseModel):
    """A single continuous heart rate sample."""

    heart_rate: int = Field(description="Heart rate in beats per minute")
    sample_time: str = Field(description="Local time of the sample, e.g. '23:58:42'")


class PolarContinuousHR(BaseModel):
    """Continuous heart rate data for a single calendar date.

    Returned by GET /v3/users/continuous-heart-rate/{date}.
    Samples are a list of {heart_rate, sample_time} objects where sample_time
    is the local clock time (HH:MM:SS).
    """

    date: str = Field(description="Calendar date, e.g. '2024-05-10'")
    heart_rate_samples: list[PolarHRSample] | None = Field(
        default=None,
        description="HR samples with local timestamp and bpm value",
    )

    model_config = {"extra": "ignore"}


class PolarCardioLoadRecord(BaseModel):
    """Single daily cardio load record from GET /v3/users/cardio-load.

    Fields (from Polar API spec):
      date          — calendar date
      cardio-load   — daily cardio load
      strain        — 7-day rolling cardio load (Polar "acute" load)
      tolerance     — 28-day rolling cardio load (Polar "chronic" load / fitness)
    """

    date: str = Field(description="Calendar date, e.g. '2024-05-10'")
    cardio_load: float | None = Field(
        default=None,
        validation_alias=AliasChoices("cardio_load", "cardio-load"),
        description="Daily cardio load",
    )
    strain: float | None = Field(default=None, description="7-day rolling cardio load")
    tolerance: float | None = Field(default=None, description="28-day rolling cardio load")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class PolarCardioLoadResponse(BaseModel):
    """List response from GET /v3/users/cardio-load."""

    cardio_load: list[PolarCardioLoadRecord] = Field(
        default_factory=list,
        validation_alias=AliasChoices("cardio_load", "cardio-load"),
    )

    model_config = {"populate_by_name": True, "extra": "ignore"}
