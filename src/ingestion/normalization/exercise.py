"""Normalize raw Polar exercise data into canonical ``ActivitySession`` models."""

from __future__ import annotations

import logging
from datetime import timedelta

from domain.models import ActivitySession
from domain.models.enums import Provider
from ingestion.normalization.utils import (
    local_to_utc,
    parse_iso_duration,
    sport_type_from_polar,
)
from ingestion.polar_accesslink.models import PolarExercise

logger = logging.getLogger(__name__)


def _parse_hr_zones(zones: list) -> dict[str, float] | None:
    """Convert Polar HR zone list to {zone_index: seconds} dict."""
    if not zones:
        return None
    result: dict[str, float] = {}
    for zone in zones:
        idx = str(zone.index)
        duration_str = zone.in_zone
        if duration_str:
            try:
                result[idx] = parse_iso_duration(duration_str)
            except ValueError:
                logger.warning("Cannot parse HR zone duration %r", duration_str)
    return result if result else None


def normalize_exercise(polar: PolarExercise, user_id: str) -> ActivitySession:
    """Translate a ``PolarExercise`` into a canonical ``ActivitySession``.

    Local time + UTC offset are combined to produce UTC-aware timestamps.
    """
    start_utc = local_to_utc(polar.start_time, polar.start_time_utc_offset)
    duration_seconds = parse_iso_duration(polar.duration)
    end_utc = start_utc + timedelta(seconds=duration_seconds)

    # Prefer detailed_sport_info for more specific mapping
    sport_label = polar.detailed_sport_info or polar.sport
    sport_type = sport_type_from_polar(sport_label)

    hr_zones = _parse_hr_zones(polar.heart_rate_zones)

    avg_hr = (
        float(polar.heart_rate.average)
        if polar.heart_rate and polar.heart_rate.average is not None
        else None
    )
    max_hr = (
        float(polar.heart_rate.maximum)
        if polar.heart_rate and polar.heart_rate.maximum is not None
        else None
    )

    # Training Load Pro — Polar returns -1.0 for unavailable components
    tlp = polar.training_load_pro
    cardio_load: float | None = None
    muscle_load: float | None = None
    if tlp is not None:
        if tlp.cardio_load is not None and tlp.cardio_load >= 0:
            cardio_load = tlp.cardio_load
        if tlp.muscle_load is not None and tlp.muscle_load >= 0:
            muscle_load = tlp.muscle_load

    return ActivitySession(
        id=f"exercise_{user_id}_{polar.id}",
        user_id=user_id,
        provider=Provider.POLAR,
        start_time=start_utc,
        end_time=end_utc,
        duration_seconds=duration_seconds,
        sport_type=sport_type,
        sport_label=polar.sport,
        average_hr_bpm=avg_hr,
        max_hr_bpm=max_hr,
        hr_zone_distribution=hr_zones,
        cardio_load=cardio_load,
        muscle_load=muscle_load,
        calories_kcal=float(polar.calories) if polar.calories is not None else None,
        distance_meters=polar.distance,
    )
