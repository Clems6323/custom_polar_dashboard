"""Unit tests for all canonical domain models.

Focus: validation correctness, boundary conditions, immutability.
All fixtures are deterministic — no randomness, no external dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from domain.models import (
    ActivitySession,
    HeartRateSample,
    PPISample,
    RecoveryContributors,
    RecoveryMetrics,
    SleepMetrics,
    SleepSession,
    SleepStage,
    SleepStageInterval,
    StrainMetrics,
    TemperatureSample,
)
from domain.models.enums import Provider, SportType

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_UID = "user-001"
_PROVIDER = Provider.POLAR

_T0 = datetime(2024, 5, 10, 22, 0, 0, tzinfo=UTC)
_T1 = datetime(2024, 5, 11, 6, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# ActivitySession
# ---------------------------------------------------------------------------


class TestActivitySession:
    def _valid(self, **overrides: object) -> dict:
        base: dict = {
            "id": "act-001",
            "user_id": _UID,
            "provider": _PROVIDER,
            "start_time": _T0,
            "end_time": _T1,
            "duration_seconds": 3600.0,
            "sport_type": SportType.RUNNING,
        }
        base.update(overrides)
        return base

    def test_valid_session(self) -> None:
        s = ActivitySession(**self._valid())
        assert s.sport_type == SportType.RUNNING
        assert s.duration_seconds == 3600.0

    def test_end_before_start_raises(self) -> None:
        with pytest.raises(ValidationError, match="end_time must be after start_time"):
            ActivitySession(**self._valid(end_time=_T0, start_time=_T1))

    def test_naive_timestamp_raises(self) -> None:
        naive = datetime(2024, 5, 10, 22, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            ActivitySession(**self._valid(start_time=naive))

    def test_hr_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            ActivitySession(**self._valid(average_hr_bpm=300.0))

    def test_immutable(self) -> None:
        s = ActivitySession(**self._valid())
        with pytest.raises(ValidationError):
            s.duration_seconds = 9999  # type: ignore[misc]

    def test_optional_fields_default_none(self) -> None:
        s = ActivitySession(**self._valid())
        assert s.cardio_load is None
        assert s.distance_meters is None


# ---------------------------------------------------------------------------
# SleepSession
# ---------------------------------------------------------------------------


class TestSleepSession:
    def _valid(self, **overrides: object) -> dict:
        base: dict = {
            "id": "sleep-001",
            "user_id": _UID,
            "provider": _PROVIDER,
            "start_time": _T0,
            "end_time": _T1,
            "duration_seconds": 28_800.0,
        }
        base.update(overrides)
        return base

    def test_valid_session(self) -> None:
        s = SleepSession(**self._valid())
        assert s.duration_seconds == 28_800.0

    def test_stage_intervals_default_empty(self) -> None:
        s = SleepSession(**self._valid())
        assert s.stage_intervals == []

    def test_with_stage_intervals(self) -> None:
        interval = SleepStageInterval(
            start_time=_T0,
            end_time=datetime(2024, 5, 10, 23, 0, 0, tzinfo=UTC),
            stage=SleepStage.LIGHT,
            duration_seconds=3600.0,
        )
        s = SleepSession(**self._valid(stage_intervals=[interval]))
        assert len(s.stage_intervals) == 1
        assert s.stage_intervals[0].stage == SleepStage.LIGHT

    def test_ppi_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            SleepSession(**self._valid(average_ppi_ms=200))  # below 300 ms minimum

    def test_naive_timestamp_raises(self) -> None:
        # Line 177 in sleep.py: must_be_timezone_aware validator
        naive = datetime(2024, 5, 10, 22, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            SleepSession(**self._valid(start_time=naive))

    def test_end_before_start_raises(self) -> None:
        # Line 183 in sleep.py: end_after_start validator
        with pytest.raises(ValidationError, match="end_time must be after start_time"):
            SleepSession(**self._valid(start_time=_T1, end_time=_T0))


# ---------------------------------------------------------------------------
# SleepStageInterval
# ---------------------------------------------------------------------------


class TestSleepStageInterval:
    _T0 = datetime(2024, 5, 10, 22, 0, 0, tzinfo=UTC)
    _T1 = datetime(2024, 5, 10, 22, 30, 0, tzinfo=UTC)

    def _valid(self, **overrides: object) -> dict:
        base: dict = {
            "start_time": self._T0,
            "end_time": self._T1,
            "stage": SleepStage.LIGHT,
            "duration_seconds": 1800.0,
        }
        base.update(overrides)
        return base

    def test_valid_interval(self) -> None:
        iv = SleepStageInterval(**self._valid())
        assert iv.stage == SleepStage.LIGHT

    def test_naive_timestamp_raises(self) -> None:
        # Line 29 in sleep.py: must_be_timezone_aware on SleepStageInterval
        naive = datetime(2024, 5, 10, 22, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            SleepStageInterval(**self._valid(start_time=naive))

    def test_end_before_start_raises(self) -> None:
        # Line 35 in sleep.py: end_after_start on SleepStageInterval
        with pytest.raises(ValidationError, match="end_time must be after start_time"):
            SleepStageInterval(**self._valid(start_time=self._T1, end_time=self._T0))


# ---------------------------------------------------------------------------
# HeartRateSample
# ---------------------------------------------------------------------------


class TestHeartRateSample:
    def test_valid_sample(self) -> None:
        s = HeartRateSample(
            user_id=_UID,
            provider=_PROVIDER,
            timestamp=_T0,
            hr_bpm=65.0,
        )
        assert s.hr_bpm == 65.0

    def test_hr_too_high_raises(self) -> None:
        with pytest.raises(ValidationError):
            HeartRateSample(user_id=_UID, provider=_PROVIDER, timestamp=_T0, hr_bpm=300.0)

    def test_hr_too_low_raises(self) -> None:
        with pytest.raises(ValidationError):
            HeartRateSample(user_id=_UID, provider=_PROVIDER, timestamp=_T0, hr_bpm=5.0)


# ---------------------------------------------------------------------------
# PPISample
# ---------------------------------------------------------------------------


class TestPPISample:
    def test_valid_sample(self) -> None:
        s = PPISample(user_id=_UID, provider=_PROVIDER, timestamp=_T0, ppi_ms=850)
        assert s.ppi_ms == 850
        assert s.is_valid is True

    def test_hr_auto_derived(self) -> None:
        s = PPISample(user_id=_UID, provider=_PROVIDER, timestamp=_T0, ppi_ms=1000)
        assert s.hr_bpm == pytest.approx(60.0, abs=0.1)

    def test_ppi_below_minimum_raises(self) -> None:
        with pytest.raises(ValidationError):
            PPISample(user_id=_UID, provider=_PROVIDER, timestamp=_T0, ppi_ms=100)

    def test_ppi_above_maximum_raises(self) -> None:
        with pytest.raises(ValidationError):
            PPISample(user_id=_UID, provider=_PROVIDER, timestamp=_T0, ppi_ms=3000)

    def test_invalid_sample_retained(self) -> None:
        s = PPISample(
            user_id=_UID, provider=_PROVIDER, timestamp=_T0, ppi_ms=400, is_valid=False
        )
        assert s.is_valid is False


# ---------------------------------------------------------------------------
# TemperatureSample
# ---------------------------------------------------------------------------


class TestTemperatureSample:
    def test_valid_sample(self) -> None:
        s = TemperatureSample(
            user_id=_UID, provider=_PROVIDER, timestamp=_T0, skin_temperature_celsius=34.5
        )
        assert s.skin_temperature_celsius == 34.5

    def test_temp_above_max_raises(self) -> None:
        with pytest.raises(ValidationError):
            TemperatureSample(
                user_id=_UID,
                provider=_PROVIDER,
                timestamp=_T0,
                skin_temperature_celsius=50.0,
            )


# ---------------------------------------------------------------------------
# StrainMetrics
# ---------------------------------------------------------------------------


class TestStrainMetrics:
    def _valid(self, **overrides: object) -> dict:
        base: dict = {
            "record_date": _T0.date(),
            "user_id": _UID,
            "provider": _PROVIDER,
            "strain_score": 55.0,
            "cardio_load": 320.0,
        }
        base.update(overrides)
        return base

    def test_valid_metrics(self) -> None:
        m = StrainMetrics(**self._valid())
        assert m.strain_score == 55.0

    def test_acwr_risk_property_low(self) -> None:
        m = StrainMetrics(**self._valid(acwr=1.2))
        assert m.acwr_risk is False

    def test_acwr_risk_property_high(self) -> None:
        m = StrainMetrics(**self._valid(acwr=1.6))
        assert m.acwr_risk is True

    def test_score_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            StrainMetrics(**self._valid(strain_score=150.0))


# ---------------------------------------------------------------------------
# SleepMetrics
# ---------------------------------------------------------------------------


class TestSleepMetrics:
    def _valid(self, **overrides: object) -> dict:
        base: dict = {
            "record_date": _T0.date(),
            "user_id": _UID,
            "provider": _PROVIDER,
            "sleep_score": 72.0,
            "total_sleep_seconds": 25_200.0,
        }
        base.update(overrides)
        return base

    def test_valid_metrics(self) -> None:
        m = SleepMetrics(**self._valid())
        assert m.sleep_score == 72.0

    def test_architecture_valid_four_components(self) -> None:
        # DEEP + REM + LIGHT + INTERRUPTIONS as % of time in bed
        m = SleepMetrics(
            **self._valid(
                deep_sleep_pct=17.0, rem_sleep_pct=20.0,
                light_sleep_pct=55.0, awake_pct=8.0,
            )
        )
        assert m.deep_sleep_pct == 17.0

    def test_architecture_over_110_raises(self) -> None:
        with pytest.raises(ValidationError, match="stage percentages sum"):
            SleepMetrics(
                **self._valid(
                    deep_sleep_pct=40.0, rem_sleep_pct=40.0,
                    light_sleep_pct=40.0, awake_pct=5.0,
                )
            )


# ---------------------------------------------------------------------------
# RecoveryMetrics
# ---------------------------------------------------------------------------


class TestRecoveryMetrics:
    def test_valid_metrics(self) -> None:
        m = RecoveryMetrics(
            record_date=_T0.date(),
            user_id=_UID,
            provider=_PROVIDER,
            recovery_score=78.0,
            contributors=RecoveryContributors(hrv_z_score=1.2, sleep_score=80.0),
        )
        assert m.recovery_score == 78.0
        assert m.contributors.hrv_z_score == 1.2

    def test_score_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            RecoveryMetrics(
                record_date=_T0.date(),
                user_id=_UID,
                provider=_PROVIDER,
                recovery_score=120.0,
            )
