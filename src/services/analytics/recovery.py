"""Recovery score computation from physiological signal contributors.

The composite score is a weighted sum of seven signals, each normalised to 0-100.
Missing signals fall back to a neutral 50 so the score degrades gracefully.

Weights (evidence-aligned, tuned for sensitivity):
  Sleep quality:          35 %  — quality of the preceding night
  HRV z-score:            25 %  — ANS recovery (positive = more recovered)
  Resting HR z-score:     20 %  — lower-than-baseline HR = better (inverted)
  Previous strain:        10 %  — recent load burden reduces next-day readiness
  Nightly recharge:        4 %  — provider ANS charge score
  Temperature deviation:   4 %  — elevated skin temp signals stress / illness
  Fitness load z-score:    2 %  — aerobic fitness proxy (Polar 28-day tolerance)

Formula (per contributor):
  z-score signals:  ((clamp(z, -3, 3) + 3) / 6) * 100   [invert for HR]
  strain:           max(0, 100 - previous_strain_score)
  temp_deviation:   clamp(50 - dev_celsius * 50, 0, 100)
  fitness:          same z-score formula (higher tolerance than baseline = better)
"""

from __future__ import annotations

from domain.models.recovery import RecoveryContributors

_WEIGHTS: dict[str, float] = {
    "sleep": 0.35,
    "hrv": 0.25,
    "hr": 0.20,
    "strain": 0.10,
    "recharge": 0.04,
    "temperature": 0.04,
    "fitness": 0.02,
}

_NEUTRAL = 50.0


def _z_to_pct(z: float | None, *, invert: bool = False) -> float:
    """Map a z-score to a 0-100 contributor percentage.

    Clamps to +-3 std so outliers don't dominate.  ``invert=True`` reverses
    direction (used for resting HR where low z-score = good recovery).
    Falls back to neutral (50) on missing data.
    """
    if z is None:
        return _NEUTRAL
    score = (max(-3.0, min(3.0, z)) + 3.0) / 6.0 * 100.0
    return 100.0 - score if invert else score


def recovery_score(contributors: RecoveryContributors) -> float:
    """Composite recovery / readiness score (0-100).

    Each missing contributor defaults to 50 (neutral) so the score
    remains interpretable even with partial data.  Callers should
    track how many contributors were available to assess confidence.
    """
    sleep_c = contributors.sleep_score if contributors.sleep_score is not None else _NEUTRAL
    hrv_c = _z_to_pct(contributors.hrv_z_score)
    hr_c = _z_to_pct(contributors.resting_hr_z_score, invert=True)

    if contributors.previous_strain_score is not None:
        strain_c = max(0.0, 100.0 - contributors.previous_strain_score)
    else:
        strain_c = _NEUTRAL

    recharge_c = (
        contributors.nightly_recharge_score
        if contributors.nightly_recharge_score is not None
        else _NEUTRAL
    )

    if contributors.temperature_deviation_celsius is not None:
        temp_c = max(0.0, min(100.0, 50.0 - contributors.temperature_deviation_celsius * 50.0))
    else:
        temp_c = _NEUTRAL

    fitness_c = _z_to_pct(contributors.fitness_load_z_score)

    return (
        _WEIGHTS["sleep"] * sleep_c
        + _WEIGHTS["hrv"] * hrv_c
        + _WEIGHTS["hr"] * hr_c
        + _WEIGHTS["strain"] * strain_c
        + _WEIGHTS["recharge"] * recharge_c
        + _WEIGHTS["temperature"] * temp_c
        + _WEIGHTS["fitness"] * fitness_c
    )
