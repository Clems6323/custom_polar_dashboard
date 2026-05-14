"""Strain analytics — training load estimation, ACWR, daily strain scoring.

All functions are pure and deterministic; no I/O.

Load estimation priority:
  1. Provider training_load (Polar supplies this directly)
  2. Intensity * duration fallback (when provider load is absent)
  3. Duration-only floor (minimal estimate, 1 unit/minute)

Strain score formula:
    base = 100 * tanh(training_load / 200)
    strain_score = clamp(base + acwr_modifier, 0, 100)

ACWR reference: Gabbett TJ (2016) Br J Sports Med 50:273-280.
  Sweet spot: 0.8-1.3  |  Elevated risk: > 1.5
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from domain.models.activity import ActivitySession

# tanh reference load: 200 units → ~76/100; 400 units → ~96/100.
# Calibrated so a typical hard training day (~150-250 Polar units) scores 60-80.
_LOAD_REFERENCE: float = 200.0

# ACWR thresholds
_ACWR_SWEET_SPOT_LOW: float = 0.8
_ACWR_SWEET_SPOT_HIGH: float = 1.3
_ACWR_RISK_THRESHOLD: float = 1.5


def estimate_session_load(session: ActivitySession) -> float:
    """Estimate training load for a single session (arbitrary units).

    Uses Polar Cardio Load when available, otherwise derives a
    TRIMP-inspired estimate from duration and relative HR intensity.

    Units are consistent with the Polar Cardio Load scale.
    """
    if session.cardio_load is not None:
        return session.cardio_load

    minutes = session.duration_seconds / 60.0

    if (
        session.average_hr_bpm is not None
        and session.max_hr_bpm is not None
        and session.max_hr_bpm > 0
    ):
        # Relative intensity: avg HR as fraction of session peak HR
        intensity = session.average_hr_bpm / session.max_hr_bpm
        # Scale factor 2 so 60 min at 80 % intensity ≈ 96 units
        return minutes * intensity * 2.0

    return minutes  # floor: 1 unit/minute, no HR context


def daily_training_load(sessions: Sequence[ActivitySession]) -> float:
    """Sum of estimated training loads across all sessions on a given day."""
    return sum(estimate_session_load(s) for s in sessions)


def acwr(
    daily_loads: Sequence[float | None],
    *,
    acute_window: int = 7,
    chronic_window: int = 28,
) -> float | None:
    """Acute / Chronic Workload Ratio from a time-ordered load history.

    Args:
        daily_loads:    Daily load values, oldest first. ``None`` = rest day.
        acute_window:   Trailing days for acute (short-term) load.
        chronic_window: Trailing days for chronic (long-term) load.

    Returns:
        ACWR float, or ``None`` when history is insufficient or chronic load
        is effectively zero (avoids division by near-zero).

    Interpretation:
        < 0.8   Under-training relative to chronic load
        0.8-1.3 Sweet spot
        > 1.5   Elevated soft-tissue injury risk (Gabbett 2016)
    """
    vals = list(daily_loads)
    if len(vals) < chronic_window:
        return None

    acute_vals = [v for v in vals[-acute_window:] if v is not None]
    chronic_vals = [v for v in vals[-chronic_window:] if v is not None]

    if not acute_vals or not chronic_vals:
        return None

    acute = sum(acute_vals) / len(acute_vals)
    chronic = sum(chronic_vals) / len(chronic_vals)

    if chronic < 0.1:
        return None

    return acute / chronic


def strain_score(
    training_load: float,
    acwr_value: float | None = None,
) -> float:
    """Map daily training load to a 0-100 strain score.

    Base score uses tanh normalization with a 200-unit reference.
    An ACWR modifier (±10 pts) reflects acute load spikes or under-training.

    Args:
        training_load: Total daily load (sum over all sessions).
        acwr_value:    Current ACWR; ``None`` skips the modifier.
    """
    base = 100.0 * math.tanh(training_load / _LOAD_REFERENCE)

    if acwr_value is None:
        return min(base, 100.0)

    # Boost score when load spike exceeds the risk threshold
    if acwr_value > _ACWR_RISK_THRESHOLD:
        modifier = min((acwr_value - _ACWR_RISK_THRESHOLD) * 10.0, 10.0)
    else:
        modifier = 0.0

    return max(0.0, min(base + modifier, 100.0))
