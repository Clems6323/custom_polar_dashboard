"""Normalize raw Polar nightly recharge data into ``RecoveryMetrics``."""

from __future__ import annotations

import datetime
import logging

from domain.models import RecoveryMetrics
from domain.models.enums import Provider
from domain.models.recovery import RecoveryContributors
from ingestion.polar_accesslink.models import PolarNightlyRecharge

logger = logging.getLogger(__name__)


# ans_charge_status is a 1-5 Polar classification; map to our 0-100 score.
# 1=very low, 2=low, 3=moderate, 4=high, 5=very high ANS recovery.
_ANS_STATUS_TO_SCORE: dict[int, float] = {1: 10.0, 2: 30.0, 3: 50.0, 4: 70.0, 5: 90.0}


def normalize_nightly_recharge(
    polar: PolarNightlyRecharge, user_id: str
) -> RecoveryMetrics:
    """Translate a ``PolarNightlyRecharge`` into a canonical ``RecoveryMetrics``.

    Mapping decisions:
    - ``ans_charge_status`` (1-5) maps to ``recovery_score`` via _ANS_STATUS_TO_SCORE.
      Falls back to 50.0 when unavailable.
    - ``ans_charge`` (deviation from personal baseline, ~-10 to +10) is stored as
      ``nightly_recharge_score`` in contributors for use by the composite scorer.
    - ``heart_rate_variability_avg`` (ms) is actual overnight RMSSD from the device.
    - ``heart_rate_avg`` maps to ``resting_hr_bpm``; falls back to deriving from
      ``beat_to_beat_avg`` (60_000 / PPI_ms) when unavailable.
    - Baselines and z-scores are NOT set here; the analytics pipeline (RecoveryScorer)
      computes them from the rolling 30-day window.
    """
    record_date = datetime.date.fromisoformat(polar.date)

    recovery_score = _ANS_STATUS_TO_SCORE.get(
        polar.ans_charge_status or 0, 50.0  # type: ignore[arg-type]
    )

    # Use direct mean HR when available; derive from beat-to-beat as fallback
    resting_hr: float | None
    if polar.heart_rate_avg is not None:
        resting_hr = float(polar.heart_rate_avg)
    elif polar.beat_to_beat_avg and polar.beat_to_beat_avg > 0:
        resting_hr = round(60_000 / polar.beat_to_beat_avg, 1)
    else:
        resting_hr = None

    # Normalise ans_charge (deviation ~-10..+10) to 0-100 for the contributor field.
    # Clamp to [0, 100] so downstream validators don't reject extreme nights.
    nightly_score: float | None = None
    if polar.ans_charge is not None:
        nightly_score = max(0.0, min(100.0, (polar.ans_charge + 10.0) * 5.0))

    contributors = RecoveryContributors(nightly_recharge_score=nightly_score)

    return RecoveryMetrics(
        record_date=record_date,
        user_id=user_id,
        provider=Provider.POLAR,
        recovery_score=recovery_score,
        rmssd_ms=polar.heart_rate_variability_avg,
        resting_hr_bpm=resting_hr,
        contributors=contributors,
    )
