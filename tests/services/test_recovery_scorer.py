"""Tests for RecoveryScorer — rolling baselines, z-scores, and composite scoring."""

from __future__ import annotations

from datetime import date

import pytest

from domain.models.enums import Provider
from domain.models.recovery import RecoveryContributors, RecoveryMetrics
from domain.models.sleep_metrics import SleepMetrics
from domain.models.strain import StrainMetrics
from services.scoring.recovery_scorer import RecoveryScorer

_UID = "u1"
_DATE = date(2024, 5, 10)
_PROVIDER = Provider.POLAR


def _raw_recovery(**overrides: object) -> RecoveryMetrics:
    base: dict = {
        "user_id": _UID,
        "record_date": _DATE,
        "provider": _PROVIDER,
        "recovery_score": 50.0,
        "contributors": RecoveryContributors(nightly_recharge_score=60.0),
    }
    base.update(overrides)
    return RecoveryMetrics(**base)


def _sleep_metrics(score: float = 75.0) -> SleepMetrics:
    return SleepMetrics(
        user_id=_UID,
        record_date=_DATE,
        provider=_PROVIDER,
        sleep_score=score,
        total_sleep_seconds=27_000.0,
    )


def _strain_metrics(
    strain_score: float = 40.0,
    chronic_load: float | None = None,
) -> StrainMetrics:
    return StrainMetrics(
        user_id=_UID,
        record_date=date(2024, 5, 9),
        provider=_PROVIDER,
        strain_score=strain_score,
        cardio_load=120.0,
        chronic_load=chronic_load,
    )


_SCORER = RecoveryScorer()


class TestRecoveryScorerNoHistory:
    def test_no_history_gives_neutral_score(self) -> None:
        raw = _raw_recovery(rmssd_ms=45.0, resting_hr_bpm=52.0)
        result = _SCORER.score(raw, None, None, [], [])
        # No history → no z-scores; nightly_recharge_score=60 adds ~0.4 above neutral
        assert result.recovery_score == pytest.approx(50.0, abs=0.5)

    def test_no_data_at_all_returns_neutral(self) -> None:
        raw = _raw_recovery()
        result = _SCORER.score(raw, None, None, [], [])
        # nightly_recharge_score=60 in base fixture → score ≈ 50.4
        assert result.recovery_score == pytest.approx(50.0, abs=0.5)

    def test_insufficient_history_no_z_score(self) -> None:
        # Only 1 sample → rolling_std returns empty → z-score not computed
        raw = _raw_recovery(rmssd_ms=45.0)
        result = _SCORER.score(raw, None, None, [40.0], [])
        assert result.contributors.hrv_z_score is None


class TestRecoveryScorerBaselines:
    def _hrv_history(self, n: int = 20, mean: float = 40.0) -> list[float]:
        """Stable HRV history centred on `mean`."""
        return [mean + (i % 3 - 1) for i in range(n)]

    def _hr_history(self, n: int = 20, mean: float = 55.0) -> list[float]:
        return [mean + (i % 3 - 1) for i in range(n)]

    def test_hrv_above_baseline_boosts_score(self) -> None:
        history = self._hrv_history(mean=40.0)
        raw = _raw_recovery(rmssd_ms=60.0)  # well above 40.0 baseline
        result = _SCORER.score(raw, None, None, history, [])
        assert result.recovery_score > 50.0
        assert result.contributors.hrv_z_score is not None
        assert result.contributors.hrv_z_score > 0

    def test_hrv_below_baseline_lowers_score(self) -> None:
        history = self._hrv_history(mean=60.0)
        raw = _raw_recovery(rmssd_ms=30.0)  # well below 60.0 baseline
        result = _SCORER.score(raw, None, None, history, [])
        assert result.recovery_score < 50.0
        assert result.contributors.hrv_z_score is not None
        assert result.contributors.hrv_z_score < 0

    def test_elevated_resting_hr_lowers_score(self) -> None:
        # HR z-score is inverted — elevated HR above baseline → worse recovery
        hr_hist = self._hr_history(mean=52.0)
        raw = _raw_recovery(resting_hr_bpm=65.0)  # elevated vs 52 baseline
        result = _SCORER.score(raw, None, None, [], hr_hist)
        assert result.recovery_score < 50.0
        assert result.contributors.resting_hr_z_score is not None
        assert result.contributors.resting_hr_z_score > 0  # raw z positive

    def test_low_resting_hr_boosts_score(self) -> None:
        hr_hist = self._hr_history(mean=60.0)
        raw = _raw_recovery(resting_hr_bpm=48.0)  # lower than baseline
        result = _SCORER.score(raw, None, None, [], hr_hist)
        assert result.recovery_score > 50.0

    def test_baselines_stored_on_output(self) -> None:
        hrv_hist = self._hrv_history(mean=40.0)
        hr_hist = self._hr_history(mean=55.0)
        raw = _raw_recovery(rmssd_ms=42.0, resting_hr_bpm=56.0)
        result = _SCORER.score(raw, None, None, hrv_hist, hr_hist)
        assert result.hrv_baseline_ms == pytest.approx(40.0, abs=1.0)
        assert result.resting_hr_baseline_bpm == pytest.approx(55.0, abs=1.0)

    def test_baseline_not_set_when_history_empty(self) -> None:
        raw = _raw_recovery(rmssd_ms=42.0)
        result = _SCORER.score(raw, None, None, [], [])
        assert result.hrv_baseline_ms is None
        assert result.resting_hr_baseline_bpm is None


class TestRecoveryScorerContributors:
    def test_sleep_score_used_as_contributor(self) -> None:
        raw = _raw_recovery()
        high_sleep = _SCORER.score(raw, _sleep_metrics(score=95.0), None, [], [])
        low_sleep = _SCORER.score(raw, _sleep_metrics(score=20.0), None, [], [])
        assert high_sleep.recovery_score > low_sleep.recovery_score

    def test_high_prev_strain_lowers_score(self) -> None:
        raw = _raw_recovery()
        low_strain = _SCORER.score(raw, None, _strain_metrics(strain_score=10.0), [], [])
        high_strain = _SCORER.score(raw, None, _strain_metrics(strain_score=90.0), [], [])
        assert high_strain.recovery_score < low_strain.recovery_score

    def test_no_prev_strain_neutral_contributor(self) -> None:
        raw = _raw_recovery()
        result = _SCORER.score(raw, None, None, [], [])
        assert result.contributors.previous_strain_score is None
        # Score is still computable (neutral fallback used)
        assert 0 < result.recovery_score < 100

    def test_nightly_recharge_propagated(self) -> None:
        raw = _raw_recovery(
            contributors=RecoveryContributors(nightly_recharge_score=90.0)
        )
        result = _SCORER.score(raw, None, None, [], [])
        assert result.contributors.nightly_recharge_score == pytest.approx(90.0)

    def test_temperature_deviation_propagated(self) -> None:
        raw = _raw_recovery(
            contributors=RecoveryContributors(temperature_deviation_celsius=0.8)
        )
        result = _SCORER.score(raw, None, None, [], [])
        assert result.contributors.temperature_deviation_celsius == pytest.approx(0.8)


class TestRecoveryScorerFitnessZScore:
    def _tol_history(self, n: int = 20, mean: float = 100.0) -> list[float]:
        return [mean + (i % 5 - 2) for i in range(n)]

    def test_fitness_z_computed_from_tolerance_history(self) -> None:
        tol_hist = self._tol_history(mean=100.0)
        # current chronic_load (today's tolerance) well above history mean
        prev = _strain_metrics(chronic_load=140.0)
        raw = _raw_recovery()
        result = _SCORER.score(raw, None, prev, [], [], tol_hist)
        assert result.contributors.fitness_load_z_score is not None
        assert result.contributors.fitness_load_z_score > 0  # above baseline

    def test_fitness_z_none_when_no_chronic_load(self) -> None:
        tol_hist = self._tol_history()
        prev = _strain_metrics(chronic_load=None)
        raw = _raw_recovery()
        result = _SCORER.score(raw, None, prev, [], [], tol_hist)
        assert result.contributors.fitness_load_z_score is None

    def test_fitness_z_none_when_no_tolerance_history(self) -> None:
        prev = _strain_metrics(chronic_load=110.0)
        raw = _raw_recovery()
        result = _SCORER.score(raw, None, prev, [], [], [])
        assert result.contributors.fitness_load_z_score is None

    def test_rising_fitness_boosts_recovery(self) -> None:
        tol_hist = self._tol_history(mean=80.0)
        high_fitness = _SCORER.score(
            _raw_recovery(), None, _strain_metrics(chronic_load=120.0), [], [], tol_hist
        )
        low_fitness = _SCORER.score(
            _raw_recovery(), None, _strain_metrics(chronic_load=50.0), [], [], tol_hist
        )
        assert high_fitness.recovery_score > low_fitness.recovery_score


class TestRecoveryScorerScoreRange:
    def test_score_always_in_0_100(self) -> None:
        hrv_hist = [30.0 + i for i in range(25)]
        hr_hist = [55.0 - i * 0.1 for i in range(25)]
        raw = _raw_recovery(
            rmssd_ms=80.0,
            resting_hr_bpm=40.0,
            contributors=RecoveryContributors(nightly_recharge_score=100.0),
        )
        result = _SCORER.score(raw, _sleep_metrics(95.0), _strain_metrics(5.0), hrv_hist, hr_hist)
        assert 0.0 <= result.recovery_score <= 100.0

    def test_excellent_signals_above_67(self) -> None:
        hrv_hist = [40.0] * 25
        hr_hist = [58.0] * 25
        raw = _raw_recovery(
            rmssd_ms=65.0,  # above 40 baseline
            resting_hr_bpm=48.0,  # below 58 baseline
            contributors=RecoveryContributors(nightly_recharge_score=90.0),
        )
        result = _SCORER.score(raw, _sleep_metrics(90.0), _strain_metrics(5.0), hrv_hist, hr_hist)
        assert result.recovery_score > 67.0

    def test_poor_signals_below_34(self) -> None:
        hrv_hist = [60.0] * 25
        hr_hist = [50.0] * 25
        raw = _raw_recovery(
            rmssd_ms=25.0,  # well below 60 baseline
            resting_hr_bpm=72.0,  # well above 50 baseline
            contributors=RecoveryContributors(nightly_recharge_score=10.0, temperature_deviation_celsius=1.5),
        )
        result = _SCORER.score(raw, _sleep_metrics(15.0), _strain_metrics(95.0), hrv_hist, hr_hist)
        assert result.recovery_score < 34.0
