"""Normalize raw Polar sleep data into canonical domain models."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta

from domain.models import SleepMetrics, SleepSession
from domain.models.enums import Provider, SleepStage
from domain.models.sleep import SleepStageInterval
from ingestion.normalization.utils import parse_as_utc, utc_offset_minutes_from
from ingestion.polar_accesslink.models import PolarSleepData

logger = logging.getLogger(__name__)

# Polar AccessLink v3 hypnogram_5min encoding (5-minute epochs):
#   0 = WAKE          1 = REM
#   2 = LIGHTER NREM  3 = LIGHT NREM  (both mapped to LIGHT)
#   4 = DEEP NREM     5 = UNKNOWN (bad skin contact, etc.)
_HYPNOGRAM_STAGE_MAP: dict[str, SleepStage] = {
    "0": SleepStage.AWAKE,
    "1": SleepStage.REM,
    "2": SleepStage.LIGHT,
    "3": SleepStage.LIGHT,
    "4": SleepStage.DEEP,
    "5": SleepStage.UNKNOWN,
}

_5MIN_SECONDS = 300.0


def _parse_hypnogram(
    raw: str,
    sleep_start: object,  # UTC-aware datetime
    session_id: str,
) -> list[SleepStageInterval]:
    """Convert a Polar 5-min hypnogram string into ``SleepStageInterval`` objects.

    Each character represents 5 minutes.  Consecutive identical stages are
    merged into a single interval to reduce storage.
    """
    from datetime import datetime as _datetime

    if not isinstance(sleep_start, _datetime):
        raise TypeError("sleep_start must be a datetime")

    intervals: list[SleepStageInterval] = []
    if not raw:
        return intervals

    # Merge consecutive identical stages
    current_stage_char = raw[0]
    current_start = sleep_start
    count = 1

    def _flush(stage_char: str, start: _datetime, n: int) -> None:
        stage = _HYPNOGRAM_STAGE_MAP.get(stage_char, SleepStage.UNKNOWN)
        end = start + timedelta(seconds=_5MIN_SECONDS * n)
        duration = _5MIN_SECONDS * n
        intervals.append(
            SleepStageInterval(
                start_time=start,
                end_time=end,
                stage=stage,
                duration_seconds=duration,
            )
        )

    for char in raw[1:]:
        if char == current_stage_char:
            count += 1
        else:
            _flush(current_stage_char, current_start, count)
            current_start = current_start + timedelta(seconds=_5MIN_SECONDS * count)
            current_stage_char = char
            count = 1

    _flush(current_stage_char, current_start, count)
    return intervals


def _stage_stats_from_hypnogram(raw: str) -> dict[str, float] | None:
    """Count 5-min hypnogram epochs and return exact stage durations + percentages.

    All five percentages (DEEP + REM + LIGHT + WAKE + UNKNOWN) sum to exactly
    100 % because the denominator is the total number of epochs.

    Encoding: 0=WAKE 1=REM 2=LIGHTER_NREM 3=LIGHT_NREM 4=DEEP 5=UNKNOWN.
    Stages 2 and 3 are both classified as LIGHT.

    Returns ``None`` if the string is empty.
    """
    if not raw:
        return None
    counts = Counter(raw)
    total_n = len(raw)

    wake_n = counts.get("0", 0)
    rem_n = counts.get("1", 0)
    light_n = counts.get("2", 0) + counts.get("3", 0)
    deep_n = counts.get("4", 0)
    unknown_n = counts.get("5", 0)

    def _pct(n: int) -> float:
        return round(n / total_n * 100.0, 1)

    return {
        "deep_s":    deep_n    * _5MIN_SECONDS,
        "rem_s":     rem_n     * _5MIN_SECONDS,
        "light_s":   light_n   * _5MIN_SECONDS,
        "awake_s":   wake_n    * _5MIN_SECONDS,
        "unknown_s": unknown_n * _5MIN_SECONDS,
        "deep_pct":    _pct(deep_n),
        "rem_pct":     _pct(rem_n),
        "light_pct":   _pct(light_n),
        "awake_pct":   _pct(wake_n),
        "unknown_pct": _pct(unknown_n),
    }


def normalize_sleep(
    polar: PolarSleepData, user_id: str
) -> tuple[SleepSession, SleepMetrics]:
    """Translate a ``PolarSleepData`` into a ``(SleepSession, SleepMetrics)`` pair.

    Sleep timestamps from the Polar API are in local time without timezone info.
    We store them as UTC per the project's documented assumption.
    """
    start_utc = parse_as_utc(polar.sleep_start_time)
    end_utc = parse_as_utc(polar.sleep_end_time)
    utc_offset = utc_offset_minutes_from(polar.sleep_start_time)
    session_id = f"sleep_{user_id}_{polar.date}"
    time_in_bed = (end_utc - start_utc).total_seconds()

    short_interruption = float(polar.short_interruption_duration) if polar.short_interruption_duration else None
    long_interruption = float(polar.long_interruption_duration) if polar.long_interruption_duration else None

    # --- Stage intervals + percentages ---------------------------------
    # Primary source: API duration fields normalised against their own sum.
    # Fallback: hypnogram epoch counts (exact 100 % decomposition).
    # Stage intervals for the hypnogram are always parsed when available.
    intervals: list = []
    hypno_stats: dict[str, float] | None = None

    if polar.hypnogram_5min:
        try:
            intervals = _parse_hypnogram(polar.hypnogram_5min, start_utc, session_id)
            hypno_stats = _stage_stats_from_hypnogram(polar.hypnogram_5min)
        except Exception:
            logger.warning("Failed to parse hypnogram for %s", session_id, exc_info=True)

    # API duration fields — normalise against their own sum so percentages add up to 100 %.
    api_deep    = float(polar.deep_sleep or 0)
    api_rem     = float(polar.rem_sleep or 0)
    api_light   = float(polar.light_sleep or 0)
    api_awake   = float(polar.total_interruption_duration or 0)
    api_unknown = float(polar.unrecognized_sleep_stage or 0)
    api_total   = api_deep + api_rem + api_light + api_awake + api_unknown

    if api_total > 0:
        deep    = api_deep
        rem     = api_rem
        light   = api_light
        awake   = api_awake
        unknown = api_unknown
        deep_pct    = round(deep    / api_total * 100, 1)
        rem_pct     = round(rem     / api_total * 100, 1)
        light_pct   = round(light   / api_total * 100, 1)
        awake_pct   = round(awake   / api_total * 100, 1)
        unknown_pct = round(unknown / api_total * 100, 1)
    elif hypno_stats:
        deep        = hypno_stats["deep_s"]
        rem         = hypno_stats["rem_s"]
        light       = hypno_stats["light_s"]
        awake       = hypno_stats["awake_s"]
        unknown     = hypno_stats["unknown_s"]
        deep_pct    = hypno_stats["deep_pct"]
        rem_pct     = hypno_stats["rem_pct"]
        light_pct   = hypno_stats["light_pct"]
        awake_pct   = hypno_stats["awake_pct"]
        unknown_pct = hypno_stats["unknown_pct"]
    else:
        deep = rem = light = awake = unknown = 0.0
        deep_pct = rem_pct = light_pct = awake_pct = unknown_pct = None

    total_sleep = deep + rem + light  # excludes WAKE and UNKNOWN epochs
    efficiency = round(total_sleep / time_in_bed * 100, 1) if time_in_bed > 0 else None

    # Continuity score: Polar provides 1.0–5.0; scale to 20–100 for our model
    continuity_raw = polar.continuity
    continuity_scaled = round(continuity_raw * 20, 1) if continuity_raw is not None else None

    session = SleepSession(
        id=session_id,
        user_id=user_id,
        provider=Provider.POLAR,
        start_time=start_utc,
        end_time=end_utc,
        utc_offset_minutes=utc_offset,
        duration_seconds=time_in_bed,
        continuity_score=continuity_scaled,
        sleep_efficiency_pct=efficiency,
        light_sleep_seconds=light if light > 0 else None,
        deep_sleep_seconds=deep if deep > 0 else None,
        rem_sleep_seconds=rem if rem > 0 else None,
        awake_seconds=awake if awake > 0 else None,
        unknown_sleep_seconds=unknown if unknown > 0 else None,
        short_interruption_duration_seconds=short_interruption,
        long_interruption_duration_seconds=long_interruption,
        stage_intervals=intervals,
    )

    sleep_score = float(polar.sleep_score) if polar.sleep_score is not None else 50.0

    metrics = SleepMetrics(
        record_date=end_utc.date(),
        user_id=user_id,
        provider=Provider.POLAR,
        sleep_session_id=session_id,
        sleep_score=sleep_score,
        total_sleep_seconds=total_sleep,
        time_in_bed_seconds=time_in_bed,
        sleep_efficiency_pct=efficiency,
        deep_sleep_pct=deep_pct,
        rem_sleep_pct=rem_pct,
        light_sleep_pct=light_pct,
        awake_pct=awake_pct,
        unknown_sleep_pct=unknown_pct,
        short_interruption_duration_seconds=short_interruption,
        long_interruption_duration_seconds=long_interruption,
    )

    return session, metrics
