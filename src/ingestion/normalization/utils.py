"""Shared utilities for ingestion normalization.

Contains:
- ISO 8601 duration parser
- Polar sport-label → SportType mapping
- UTC datetime helpers
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

from domain.models.enums import SportType

_DURATION_RE = re.compile(
    r"P"
    r"(?:(\d+)Y)?"
    r"(?:(\d+)M)?"
    r"(?:(\d+)D)?"
    r"(?:T"
    r"(?:(\d+)H)?"
    r"(?:(\d+)M)?"
    r"(?:(\d+(?:\.\d+)?)S)?"
    r")?"
)

# Approximate: Polar durations never use year/month fields for exercise data.
_DAYS_PER_YEAR = 365.25
_DAYS_PER_MONTH = 30.44


def parse_iso_duration(duration: str) -> float:
    """Return total seconds from an ISO 8601 duration string.

    Handles the format used by Polar: ``PT1H15M30.000S``.
    Year and month components use calendar approximations since Polar never
    emits them for exercise/activity durations.

    Raises ``ValueError`` for unrecognisable strings.
    """
    m = _DURATION_RE.fullmatch(duration.strip())
    if not m or not any(m.groups()):
        raise ValueError(f"Cannot parse ISO 8601 duration: {duration!r}")
    years, months, days, hours, minutes, seconds = m.groups()
    total = 0.0
    if years:
        total += float(years) * _DAYS_PER_YEAR * 86_400
    if months:
        total += float(months) * _DAYS_PER_MONTH * 86_400
    if days:
        total += float(days) * 86_400
    if hours:
        total += float(hours) * 3_600
    if minutes:
        total += float(minutes) * 60
    if seconds:
        total += float(seconds)
    return total


# ---------------------------------------------------------------------------
# Sport mapping
# ---------------------------------------------------------------------------

_POLAR_SPORT_MAP: dict[str, SportType] = {
    "RUNNING": SportType.RUNNING,
    "TRAIL_RUNNING": SportType.TRAIL_RUNNING,
    "ROAD_RUNNING": SportType.RUNNING,
    "TREADMILL_RUNNING": SportType.RUNNING,
    "CYCLING": SportType.CYCLING,
    "ROAD_BIKING": SportType.CYCLING,
    "MOUNTAIN_BIKING": SportType.CYCLING,
    "INDOOR_CYCLING": SportType.INDOOR_CYCLING,
    "SPINNING": SportType.INDOOR_CYCLING,
    "SWIMMING": SportType.SWIMMING,
    "OPEN_WATER_SWIMMING": SportType.SWIMMING,
    "POOL_SWIMMING": SportType.SWIMMING,
    "STRENGTH_TRAINING": SportType.STRENGTH_TRAINING,
    "WEIGHT_TRAINING": SportType.STRENGTH_TRAINING,
    "GYM": SportType.STRENGTH_TRAINING,
    "CROSSFIT": SportType.CROSSFIT,
    "HIIT": SportType.HIIT,
    "INTERVAL_TRAINING": SportType.HIIT,
    "YOGA": SportType.YOGA,
    "PILATES": SportType.YOGA,
    "WALKING": SportType.WALKING,
    "HIKING": SportType.HIKING,
    "ROWING": SportType.ROWING,
    "INDOOR_ROWING": SportType.ROWING,
    "SOCCER": SportType.SOCCER,
    "FOOTBALL": SportType.SOCCER,
    "TENNIS": SportType.TENNIS,
    "BASKETBALL": SportType.BASKETBALL,
}


def sport_type_from_polar(polar_sport: str | None) -> SportType:
    """Map a Polar sport label to a canonical ``SportType``.

    Falls back to ``SportType.OTHER`` for unknown labels.
    """
    if not polar_sport:
        return SportType.OTHER
    return _POLAR_SPORT_MAP.get(polar_sport.upper(), SportType.OTHER)


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------


def local_to_utc(local_dt_str: str, utc_offset_minutes: int) -> datetime:
    """Convert a Polar local datetime string to a UTC-aware ``datetime``.

    Args:
        local_dt_str: Local time from Polar API, e.g. ``'2024-05-10T08:00:00'``
                      or ``'2024-05-10T08:00:00.000'``.
        utc_offset_minutes: Offset from UTC in minutes (e.g. 120 for UTC+2).

    Returns:
        UTC-aware ``datetime``.
    """
    local_dt = _parse_polar_datetime(local_dt_str)
    tz = timezone(timedelta(minutes=utc_offset_minutes))
    return local_dt.replace(tzinfo=tz).astimezone(UTC)


def utc_offset_minutes_from(dt_str: str) -> int | None:
    """Return the UTC offset in minutes embedded in a Polar datetime string.

    Returns ``None`` for naive strings (no timezone info), which means the
    offset is unknown and the hour value stored as UTC is the device's local
    clock reading.
    """
    dt = _parse_polar_datetime(dt_str)
    if dt.tzinfo is None:
        return None
    offset = dt.utcoffset()
    if offset is None:
        return None
    return int(offset.total_seconds() / 60)


def parse_as_utc(dt_str: str) -> datetime:
    """Parse a Polar datetime string and return a UTC-aware datetime.

    Handles both naive strings (treated as UTC) and strings with an embedded
    UTC offset (e.g. '2026-04-12T00:03:26+02:00'), converting to UTC.
    """
    dt = _parse_polar_datetime(dt_str)
    if dt.tzinfo is not None:
        return dt.astimezone(UTC)
    return dt.replace(tzinfo=UTC)


def _parse_polar_datetime(dt_str: str) -> datetime:
    """Parse any ISO 8601 datetime variant returned by the Polar API.

    Uses datetime.fromisoformat (Python 3.11+) which handles optional
    milliseconds and UTC offsets (e.g. '+02:00').
    """
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        raise ValueError(f"Cannot parse Polar datetime: {dt_str!r}") from None
