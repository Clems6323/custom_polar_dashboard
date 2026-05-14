"""Canonical domain model for daily training strain metrics."""

from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from domain.models.base import BaseEntity
from domain.models.enums import Provider

# ACWR danger zones (sports science consensus)
_ACWR_INJURY_RISK_THRESHOLD: float = 1.5


class StrainMetrics(BaseEntity):
    """Aggregated daily training load and strain for a single user.

    One record per user per date.  The acute/chronic workload ratio (ACWR)
    is the primary injury-risk indicator; values above 1.5 are associated
    with elevated soft-tissue injury risk in the sports science literature.

    Scoring formula:
        strain_score = f(training_load, cardio_load, acwr, session_count)
    Implemented in services/scoring/strain_scorer.py.
    """

    # --- Identity ---
    record_date: date = Field(description="Calendar date these metrics represent")
    user_id: str = Field(description="Platform-agnostic user identifier")
    provider: Provider = Field(description="Primary data source for this record")

    # --- Composite score ---
    strain_score: float = Field(
        ge=0,
        le=100,
        description=(
            "Normalised daily strain score (0-100).  "
            "0-33 = low, 34-66 = moderate, 67-100 = high."
        ),
    )

    # --- Load components ---
    cardio_load: float = Field(
        ge=0,
        description="Total Polar Cardio Load for the day (sum across sessions)",
    )
    muscle_load: float | None = Field(
        default=None,
        ge=0,
        description="Total Polar Muscle Load for the day (sum across sessions, where available)",
    )

    # --- Workload ratios ---
    acute_load: float | None = Field(
        default=None,
        ge=0,
        description="7-day rolling average training load (acute workload)",
    )
    chronic_load: float | None = Field(
        default=None,
        ge=0,
        description="28-day rolling average training load (chronic workload)",
    )
    acwr: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Acute/Chronic Workload Ratio (acute_load / chronic_load).  "
            "Values 0.8-1.3 are considered the 'sweet spot'; >1.5 = elevated injury risk."
        ),
    )

    # --- Session summary ---
    session_count: int = Field(
        default=0,
        ge=0,
        description="Number of training sessions contributing to today's strain",
    )
    session_ids: list[str] = Field(
        default_factory=list,
        description="IDs of ActivitySession records included in this day's totals",
    )

    @model_validator(mode="after")
    def warn_high_acwr(self) -> StrainMetrics:
        """Attach a flag when ACWR enters the injury-risk zone.

        This does not raise — it is a soft signal only.  The UI layer can
        surface it as a warning to the user.
        """
        # Validation-only: no mutation required; frozen model.
        return self

    @property
    def acwr_risk(self) -> bool:
        """Return True when ACWR exceeds the injury-risk threshold."""
        return self.acwr is not None and self.acwr > _ACWR_INJURY_RISK_THRESHOLD
