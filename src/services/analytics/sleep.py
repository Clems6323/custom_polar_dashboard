"""Sleep quality analytics — score components and consistency.

All functions are pure and deterministic; they accept domain objects or
primitive types and return floats.  No I/O.

Score formula (implemented in ``compute_sleep_score``):
    sleep_score = 0.35 * duration_score
                + 0.35 * efficiency_score
                + 0.20 * architecture_score
                + 0.10 * continuity_score

Stage percentages are expressed as **fraction of time in bed** so that
DEEP + REM + LIGHT + INTERRUPTIONS ≈ 100 %.

Targets (% of time in bed):
    Duration:      7.5 h (Gaussian bell curve, sigma = 1.5 h)
    Efficiency:    ≥ 90 %
    Deep sleep:    ≥ 17 %  (≈ 20 % of ~85 % efficient sleep)
    REM sleep:     ≥ 20 %  (≈ 25 % of ~80 % efficient sleep)
    Continuity:    provider-supplied 0-100 score
    Interruptions: 0 % of time in bed → +100; ≥ 15 % → 0 (blended into architecture)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

from domain.models.sleep import SleepSession

_TARGET_SLEEP_HOURS: float = 7.5
_DURATION_SIGMA: float = 1.5  # hours
_OPTIMAL_EFFICIENCY_PCT: float = 90.0
_OPTIMAL_DEEP_PCT: float = 17.0   # % of time in bed
_OPTIMAL_REM_PCT: float = 20.0    # % of time in bed
_MAX_INTERRUPTION_PCT: float = 15.0  # % of time in bed → architecture sub-score = 0

# Weights must sum to 1.0
_W_DURATION = 0.35
_W_EFFICIENCY = 0.35
_W_ARCHITECTURE = 0.20
_W_CONTINUITY = 0.10


def duration_score(total_sleep_seconds: float) -> float:
    """Score sleep duration 0-100 using a Gaussian centred on 7.5 h.

    Score drops symmetrically away from the target:
      7.5 h -> 100   (peak)
      6.0 h -> 60    (-1 sigma)
      4.5 h -> 13    (-2 sigma)
      9.0 h -> 60    (+1 sigma)
    """
    hours = total_sleep_seconds / 3600.0
    exponent = -((hours - _TARGET_SLEEP_HOURS) ** 2) / (2 * _DURATION_SIGMA**2)
    return 100.0 * math.exp(exponent)


def efficiency_score(efficiency_pct: float | None) -> float:
    """Score sleep efficiency 0-100. Target ≥ 90 %.

    Returns 50 (neutral) when efficiency data is absent.
    Capped at 100 for efficiency above target.
    """
    if efficiency_pct is None:
        return 50.0
    return min(efficiency_pct / _OPTIMAL_EFFICIENCY_PCT * 100.0, 100.0)


def architecture_score(
    deep_pct: float | None,
    rem_pct: float | None,
    interruption_pct: float | None = None,
) -> float:
    """Score sleep stage architecture 0-100.

    All percentages are fractions of **time in bed** (not total sleep).
    Scores each available component against its target and averages.
    Returns 50 (neutral) when no data is available.

    - Deep sleep target:    ≥ 17 % of time in bed
    - REM sleep target:     ≥ 20 % of time in bed
    - Interruption penalty: 0 % → 100, ≥ 15 % → 0
    """
    scores: list[float] = []
    if deep_pct is not None:
        scores.append(min(deep_pct / _OPTIMAL_DEEP_PCT * 100.0, 100.0))
    if rem_pct is not None:
        scores.append(min(rem_pct / _OPTIMAL_REM_PCT * 100.0, 100.0))
    if interruption_pct is not None:
        scores.append(max(0.0, 100.0 - interruption_pct / _MAX_INTERRUPTION_PCT * 100.0))
    if not scores:
        return 50.0
    return sum(scores) / len(scores)


def interruption_score(
    long_interruption_seconds: float | None,
    time_in_bed_seconds: float | None,
) -> float:
    """Score sleep interruption quality 0-100.

    Penalises long awakenings (≥ 5 min) relative to total time in bed.
    0 % long-interruption time → 100 (perfect); ≥ 10 % → 0 (very poor).
    Returns 50 (neutral) when interruption data is absent.
    """
    if (
        long_interruption_seconds is None
        or time_in_bed_seconds is None
        or time_in_bed_seconds <= 0
    ):
        return 50.0
    pct = long_interruption_seconds / time_in_bed_seconds * 100.0
    return max(0.0, 100.0 - pct * 10.0)


def compute_sleep_score(session: SleepSession) -> float:
    """Composite sleep quality score (0-100) for a single night.

    Weights:
      Duration:     35 %
      Efficiency:   35 %
      Architecture: 20 %  (includes deep, REM, and interruption penalty)
      Continuity:   10 %
    """
    total_sleep = (
        (session.light_sleep_seconds or 0.0)
        + (session.deep_sleep_seconds or 0.0)
        + (session.rem_sleep_seconds or 0.0)
    )
    total_for_score = total_sleep if total_sleep > 0 else session.duration_seconds
    time_in_bed = session.duration_seconds

    def _pct_of_bed(seconds: float | None) -> float | None:
        if seconds is None or time_in_bed <= 0:
            return None
        return seconds / time_in_bed * 100.0

    deep_pct = _pct_of_bed(session.deep_sleep_seconds)
    rem_pct = _pct_of_bed(session.rem_sleep_seconds)
    awake_pct = _pct_of_bed(session.awake_seconds)

    dur = duration_score(total_for_score)
    eff = efficiency_score(session.sleep_efficiency_pct)
    arch = architecture_score(deep_pct, rem_pct, awake_pct)
    cont = session.continuity_score if session.continuity_score is not None else 50.0

    return (
        _W_DURATION * dur
        + _W_EFFICIENCY * eff
        + _W_ARCHITECTURE * arch
        + _W_CONTINUITY * cont
    )


def _normalize_bedtime_hour(dt: datetime) -> float:
    """Convert a bedtime to a continuous hour value that handles midnight wrapping.

    Hours 0-5 (early morning) are shifted to 24-29 so that late-evening and
    early-morning bedtimes are numerically adjacent for std-dev computation.
    """
    hour = dt.hour + dt.minute / 60.0
    return hour + 24.0 if hour < 6.0 else hour


def sleep_consistency_score(sessions: Sequence[SleepSession]) -> float | None:
    """Rolling sleep consistency score (0-100) across provided nights.

    Rewards stable bedtimes, wake times, and sleep durations.
    Each dimension contributes equally; 1 h of std deviation costs 25 points.

    Returns ``None`` when fewer than 2 sessions are supplied.
    """
    if len(sessions) < 2:
        return None

    bedtimes = [_normalize_bedtime_hour(s.start_time) for s in sessions]
    waketimes = [s.end_time.hour + s.end_time.minute / 60.0 for s in sessions]
    durations_h = [s.duration_seconds / 3600.0 for s in sessions]

    def _std(vals: list[float]) -> float:
        n = len(vals)
        mean = sum(vals) / n
        return math.sqrt(sum((v - mean) ** 2 for v in vals) / n)

    bed_score = max(0.0, 100.0 - _std(bedtimes) * 25.0)
    wake_score = max(0.0, 100.0 - _std(waketimes) * 25.0)
    dur_score = max(0.0, 100.0 - _std(durations_h) * 25.0)

    return (bed_score + wake_score + dur_score) / 3.0
