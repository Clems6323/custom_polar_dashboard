"""Normalize raw Polar daily activity summary data.

Polar activity summaries (steps, calories, active duration) are lightweight
records that complement exercise sessions.  They do not carry training load
or HR data so they are stored as metadata for daily totals rather than as
full ``ActivitySession`` objects.
"""

from __future__ import annotations

import contextlib
import datetime

from ingestion.normalization.utils import parse_iso_duration
from ingestion.polar_accesslink.models import PolarActivitySummary


class DailyActivityTotals:
    """Parsed daily totals from a Polar activity summary.

    These are passed to the analytics engine (Phase 5) rather than stored
    as a domain entity -- they augment ``StrainMetrics`` computation.
    """

    __slots__ = ("active_calories", "active_seconds", "active_steps", "calories", "date")

    def __init__(
        self,
        date: datetime.date,
        calories: int | None,
        active_calories: int | None,
        active_seconds: float | None,
        active_steps: int | None,
    ) -> None:
        self.date = date
        self.calories = calories
        self.active_calories = active_calories
        self.active_seconds = active_seconds
        self.active_steps = active_steps

    def __repr__(self) -> str:
        return (
            f"DailyActivityTotals(date={self.date}, "
            f"calories={self.calories}, steps={self.active_steps})"
        )


def normalize_activity_summary(polar: PolarActivitySummary) -> DailyActivityTotals:
    """Translate a ``PolarActivitySummary`` into ``DailyActivityTotals``.

    Duration is parsed from ISO 8601 format if present.
    The new list endpoint returns ``start_time`` instead of ``date``; the date
    component is extracted from whichever field is present.
    """
    date_str = polar.date or (polar.start_time[:10] if polar.start_time else None)
    if not date_str:
        raise ValueError("Activity summary has neither 'date' nor 'start_time'")
    record_date = datetime.date.fromisoformat(date_str)
    active_seconds: float | None = None
    if polar.duration:
        with contextlib.suppress(ValueError):
            active_seconds = parse_iso_duration(polar.duration)

    return DailyActivityTotals(
        date=record_date,
        calories=polar.calories,
        active_calories=polar.active_calories,
        active_seconds=active_seconds,
        active_steps=polar.active_steps,
    )
