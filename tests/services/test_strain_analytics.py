"""Tests for strain analytics functions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain.models.activity import ActivitySession
from domain.models.enums import Provider, SportType
from services.analytics.strain import acwr, daily_training_load, estimate_session_load, strain_score


def _make_session(
    *,
    duration_s: float = 3_600,
    cardio_load: float | None = None,
    avg_hr: float | None = None,
    max_hr: float | None = None,
) -> ActivitySession:
    start = datetime(2024, 5, 10, 8, 0, tzinfo=UTC)
    end = datetime(2024, 5, 10, 8, 0, tzinfo=UTC).replace(
        second=0, microsecond=0
    )
    from datetime import timedelta
    end = start + timedelta(seconds=duration_s)
    return ActivitySession(
        id="test-session",
        user_id="u1",
        provider=Provider.POLAR,
        start_time=start,
        end_time=end,
        duration_seconds=duration_s,
        sport_type=SportType.RUNNING,
        cardio_load=cardio_load,
        average_hr_bpm=avg_hr,
        max_hr_bpm=max_hr,
    )


class TestEstimateSessionLoad:
    def test_uses_provider_load_when_available(self) -> None:
        session = _make_session(cardio_load=150.0)
        assert estimate_session_load(session) == pytest.approx(150.0)

    def test_intensity_fallback(self) -> None:
        # 60 min, avg_hr=160, max_hr=200 → intensity=0.8, load=60*0.8*2=96
        session = _make_session(duration_s=3_600, avg_hr=160.0, max_hr=200.0)
        assert estimate_session_load(session) == pytest.approx(96.0)

    def test_duration_only_floor(self) -> None:
        # No HR data → 1 unit/min
        session = _make_session(duration_s=3_600)
        assert estimate_session_load(session) == pytest.approx(60.0)

    def test_short_session(self) -> None:
        session = _make_session(duration_s=1_800, cardio_load=50.0)
        assert estimate_session_load(session) == pytest.approx(50.0)


class TestDailyTrainingLoad:
    def test_single_session(self) -> None:
        s = _make_session(cardio_load=100.0)
        assert daily_training_load([s]) == pytest.approx(100.0)

    def test_multiple_sessions_sum(self) -> None:
        s1 = _make_session(cardio_load=80.0)
        s2 = _make_session(cardio_load=120.0)
        assert daily_training_load([s1, s2]) == pytest.approx(200.0)

    def test_empty_sessions(self) -> None:
        assert daily_training_load([]) == pytest.approx(0.0)


class TestAcwr:
    def _loads(self, values: list[float | None]) -> list[float | None]:
        return values

    def test_insufficient_history_returns_none(self) -> None:
        assert acwr([100.0] * 27) is None  # need 28 days

    def test_balanced_load_near_one(self) -> None:
        # 28 days all at 100 → acute=100, chronic=100 → ACWR=1.0
        result = acwr([100.0] * 28)
        assert result == pytest.approx(1.0)

    def test_spike_above_one(self) -> None:
        # 28 days at 50, last 7 at 150 → acute=150, chronic≈75 → ACWR≈2.0
        loads = [50.0] * 21 + [150.0] * 7
        result = acwr(loads)
        assert result is not None
        assert result > 1.5

    def test_deload_below_one(self) -> None:
        # 28 days at 100, last 7 at 20 → ACWR < 1
        loads = [100.0] * 21 + [20.0] * 7
        result = acwr(loads)
        assert result is not None
        assert result < 0.8

    def test_none_entries_skipped(self) -> None:
        # Rest days (None) should not pull the mean to zero
        loads = [100.0 if i % 2 == 0 else None for i in range(28)]
        result = acwr(loads)
        assert result is not None
        assert result == pytest.approx(1.0)

    def test_zero_chronic_returns_none(self) -> None:
        loads = [0.0] * 28
        assert acwr(loads) is None

    def test_custom_windows(self) -> None:
        loads = [100.0] * 14
        result = acwr(loads, acute_window=3, chronic_window=14)
        assert result == pytest.approx(1.0)


class TestStrainScore:
    def test_zero_load(self) -> None:
        assert strain_score(0.0) == pytest.approx(0.0, abs=1.0)

    def test_moderate_load(self) -> None:
        # 200 units → tanh(1) ≈ 76
        score = strain_score(200.0)
        assert 70.0 < score < 85.0

    def test_high_load(self) -> None:
        score = strain_score(400.0)
        assert score > 90.0

    def test_capped_at_100(self) -> None:
        assert strain_score(10_000.0) <= 100.0

    def test_acwr_spike_adds_modifier(self) -> None:
        base = strain_score(200.0)
        with_spike = strain_score(200.0, acwr_value=2.0)
        assert with_spike > base

    def test_acwr_sweet_spot_no_modifier(self) -> None:
        base = strain_score(200.0)
        sweet_spot = strain_score(200.0, acwr_value=1.0)
        assert sweet_spot == pytest.approx(base)

    def test_never_below_zero(self) -> None:
        assert strain_score(0.0, acwr_value=0.1) >= 0.0
