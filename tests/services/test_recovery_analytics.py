"""Tests for recovery score computation."""

from __future__ import annotations

import pytest

from domain.models.recovery import RecoveryContributors
from services.analytics.recovery import _NEUTRAL, _WEIGHTS, recovery_score


def _contribs(**kwargs) -> RecoveryContributors:  # type: ignore[no-untyped-def]
    return RecoveryContributors(**kwargs)


class TestRecoveryScore:
    def test_all_neutral_returns_50(self) -> None:
        # All signals at neutral (50) → score = 50
        c = _contribs(
            hrv_z_score=0.0,
            resting_hr_z_score=0.0,
            sleep_score=50.0,
            previous_strain_score=50.0,
            nightly_recharge_score=50.0,
            temperature_deviation_celsius=0.0,
            fitness_load_z_score=0.0,
        )
        assert recovery_score(c) == pytest.approx(50.0)

    def test_all_missing_neutral_fallback(self) -> None:
        # No data → all contributors at neutral 50
        c = _contribs()
        assert recovery_score(c) == pytest.approx(50.0)

    def test_excellent_recovery(self) -> None:
        # High HRV, low HR, great sleep, no strain
        c = _contribs(
            hrv_z_score=2.0,        # well above baseline
            resting_hr_z_score=-2.0, # well below baseline (good)
            sleep_score=90.0,
            previous_strain_score=10.0,
            nightly_recharge_score=85.0,
            temperature_deviation_celsius=0.0,
        )
        score = recovery_score(c)
        assert score > 75.0

    def test_poor_recovery(self) -> None:
        # Low HRV, elevated HR, poor sleep, high strain
        c = _contribs(
            hrv_z_score=-2.0,
            resting_hr_z_score=2.0,
            sleep_score=20.0,
            previous_strain_score=90.0,
            nightly_recharge_score=20.0,
            temperature_deviation_celsius=1.0,
        )
        score = recovery_score(c)
        assert score < 35.0

    def test_score_always_in_range(self) -> None:
        # Extreme z-scores
        c = _contribs(hrv_z_score=10.0, resting_hr_z_score=-10.0, sleep_score=100.0)
        score = recovery_score(c)
        assert 0.0 <= score <= 100.0

    def test_z_scores_clamped_at_3(self) -> None:
        c1 = _contribs(hrv_z_score=3.0)
        c2 = _contribs(hrv_z_score=10.0)
        assert recovery_score(c1) == pytest.approx(recovery_score(c2))

    def test_high_temperature_lowers_score(self) -> None:
        base = _contribs(temperature_deviation_celsius=0.0)
        elevated = _contribs(temperature_deviation_celsius=1.0)
        assert recovery_score(elevated) < recovery_score(base)

    def test_high_strain_lowers_score(self) -> None:
        low_strain = _contribs(previous_strain_score=10.0)
        high_strain = _contribs(previous_strain_score=90.0)
        assert recovery_score(high_strain) < recovery_score(low_strain)

    def test_weights_sum_to_one(self) -> None:
        assert sum(_WEIGHTS.values()) == pytest.approx(1.0)

    def test_sleep_most_influential(self) -> None:
        # Sleep has highest weight (35%)
        assert _WEIGHTS["sleep"] >= max(
            w for k, w in _WEIGHTS.items() if k != "sleep"
        )
