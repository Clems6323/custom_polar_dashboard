"""Tests for sleep quality analytics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain.models.enums import Provider, SleepStage
from domain.models.sleep import SleepSession
from services.analytics.sleep import (
    architecture_score,
    compute_sleep_score,
    duration_score,
    efficiency_score,
    interruption_score,
    sleep_consistency_score,
)


def _make_session(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    light_s: float = 10_800,   # 3 h
    deep_s: float = 5_400,     # 1.5 h
    rem_s: float = 5_400,      # 1.5 h
    awake_s: float = 1_800,    # 0.5 h
    efficiency: float | None = 92.0,
    continuity: float | None = 75.0,
) -> SleepSession:
    if start is None:
        start = datetime(2024, 5, 9, 23, 0, tzinfo=UTC)
    if end is None:
        end = datetime(2024, 5, 10, 7, 30, tzinfo=UTC)
    duration = (end - start).total_seconds()
    return SleepSession(
        id="test-sleep",
        user_id="u1",
        provider=Provider.POLAR,
        start_time=start,
        end_time=end,
        duration_seconds=duration,
        light_sleep_seconds=light_s,
        deep_sleep_seconds=deep_s,
        rem_sleep_seconds=rem_s,
        awake_seconds=awake_s,
        sleep_efficiency_pct=efficiency,
        continuity_score=continuity,
    )


class TestDurationScore:
    def test_optimal_7_5h(self) -> None:
        assert duration_score(7.5 * 3600) == pytest.approx(100.0)

    def test_one_sigma_low(self) -> None:
        # 7.5 - 1.5 = 6.0 h → e^(-0.5) ≈ 60.65
        score = duration_score(6.0 * 3600)
        assert 58.0 < score < 65.0

    def test_very_short_penalized(self) -> None:
        assert duration_score(4.0 * 3600) < 20.0

    def test_too_long_penalized(self) -> None:
        assert duration_score(11.0 * 3600) < 20.0

    def test_zero_duration(self) -> None:
        # 0 h is very far from target, should be near 0
        assert duration_score(0) < 5.0


class TestEfficiencyScore:
    def test_at_target_100(self) -> None:
        assert efficiency_score(90.0) == pytest.approx(100.0)

    def test_above_target_capped(self) -> None:
        assert efficiency_score(98.0) == pytest.approx(100.0)

    def test_below_target(self) -> None:
        assert efficiency_score(72.0) == pytest.approx(80.0)

    def test_none_neutral(self) -> None:
        assert efficiency_score(None) == pytest.approx(50.0)

    def test_zero(self) -> None:
        assert efficiency_score(0.0) == pytest.approx(0.0)


class TestArchitectureScore:
    def test_optimal_both_present(self) -> None:
        # deep=17%, rem=20% (targets) → both at 100, no interruptions → 100
        assert architecture_score(17.0, 20.0) == pytest.approx(100.0)

    def test_capped_above_optimal(self) -> None:
        assert architecture_score(25.0, 30.0) == pytest.approx(100.0)

    def test_only_deep(self) -> None:
        assert architecture_score(17.0, None) == pytest.approx(100.0)

    def test_only_rem(self) -> None:
        assert architecture_score(None, 20.0) == pytest.approx(100.0)

    def test_both_none_neutral(self) -> None:
        assert architecture_score(None, None) == pytest.approx(50.0)

    def test_interruption_at_max_penalises_to_zero(self) -> None:
        # 15% interruption → sub-score 0, averaged with deep(100) and rem(100) → 66.7
        score = architecture_score(17.0, 20.0, 15.0)
        assert score == pytest.approx((100.0 + 100.0 + 0.0) / 3, abs=0.1)

    def test_no_interruptions_perfect(self) -> None:
        assert architecture_score(17.0, 20.0, 0.0) == pytest.approx(100.0)

    def test_interruption_only_neutral_without_stages(self) -> None:
        # Only interruption data → single component averaged
        assert architecture_score(None, None, 0.0) == pytest.approx(100.0)

    def test_interruption_none_ignored(self) -> None:
        # interruption_pct=None → same as before (deep + rem only)
        assert architecture_score(17.0, 20.0, None) == pytest.approx(100.0)


class TestComputeSleepScore:
    def test_good_night(self) -> None:
        session = _make_session(
            light_s=9_000,   # 2.5 h
            deep_s=5_400,    # 1.5 h  → 20% of 7.5h
            rem_s=9_000,     # 2.5 h
            efficiency=93.0,
            continuity=80.0,
        )
        score = compute_sleep_score(session)
        assert 60.0 < score <= 100.0

    def test_poor_night_short_sleep(self) -> None:
        session = _make_session(
            start=datetime(2024, 5, 9, 1, 0, tzinfo=UTC),
            end=datetime(2024, 5, 9, 5, 0, tzinfo=UTC),  # 4h only
            light_s=7_200,
            deep_s=900,
            rem_s=3_600,
            efficiency=75.0,
            continuity=40.0,
        )
        score = compute_sleep_score(session)
        assert score < 60.0

    def test_score_range(self) -> None:
        session = _make_session()
        score = compute_sleep_score(session)
        assert 0.0 <= score <= 100.0

    def test_missing_architecture_uses_neutral(self) -> None:
        session = _make_session(light_s=0, deep_s=0, rem_s=0)
        score = compute_sleep_score(session)
        assert 0.0 <= score <= 100.0


class TestInterruptionScore:
    def test_no_interruptions_perfect(self) -> None:
        assert interruption_score(0.0, 28_800.0) == pytest.approx(100.0)

    def test_none_data_neutral(self) -> None:
        assert interruption_score(None, 28_800.0) == pytest.approx(50.0)
        assert interruption_score(600.0, None) == pytest.approx(50.0)
        assert interruption_score(None, None) == pytest.approx(50.0)

    def test_ten_percent_long_interruption_zero(self) -> None:
        # 10% of 28800 = 2880s → score = 0
        assert interruption_score(2880.0, 28_800.0) == pytest.approx(0.0)

    def test_five_percent_long_interruption_half(self) -> None:
        # 5% of 28800 = 1440s → score = 50
        assert interruption_score(1440.0, 28_800.0) == pytest.approx(50.0)

    def test_clamped_to_zero_below(self) -> None:
        # More than 10% → clamped to 0
        assert interruption_score(5_000.0, 28_800.0) == pytest.approx(0.0)

    def test_zero_time_in_bed_neutral(self) -> None:
        assert interruption_score(600.0, 0.0) == pytest.approx(50.0)


class TestComputeSleepScoreWithInterruptions:
    def test_more_awake_time_lowers_score(self) -> None:
        # awake_seconds drives the interruption penalty inside architecture_score
        good = _make_session(awake_s=900.0)   # ~3% of 8.5h bed
        bad = _make_session(awake_s=4320.0)   # ~14% of 8.5h bed → near max penalty
        assert compute_sleep_score(bad) < compute_sleep_score(good)

    def test_no_awake_data_neutral(self) -> None:
        session = _make_session(awake_s=0.0)
        score = compute_sleep_score(session)
        assert 0.0 <= score <= 100.0


class TestSleepConsistencyScore:
    def _make_sessions(self, offsets_h: list[float]) -> list[SleepSession]:
        """Create sessions with bedtimes offset from 23:00."""
        sessions = []
        for i, offset in enumerate(offsets_h):
            bed_hour = int(23 + offset)
            bed_min = int((23 + offset - bed_hour) * 60)
            start = datetime(2024, 5, i + 1, bed_hour % 24, bed_min, tzinfo=UTC)
            end = datetime(2024, 5, i + 1, 7, 0, tzinfo=UTC)
            if end <= start:
                end = datetime(2024, 5, i + 2, 7, 0, tzinfo=UTC)
            duration = (end - start).total_seconds()
            sessions.append(
                SleepSession(
                    id=f"sleep-{i}",
                    user_id="u1",
                    provider=Provider.POLAR,
                    start_time=start,
                    end_time=end,
                    duration_seconds=duration,
                )
            )
        return sessions

    def test_perfect_consistency_100(self) -> None:
        # All sessions at exactly the same time
        sessions = self._make_sessions([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        score = sleep_consistency_score(sessions)
        assert score is not None
        assert score == pytest.approx(100.0)

    def test_high_variability_lower_than_perfect(self) -> None:
        # 4-hour swing in bedtimes → significantly lower than perfect (100)
        perfect = sleep_consistency_score(self._make_sessions([0.0] * 7))
        variable = sleep_consistency_score(self._make_sessions([0.0, 4.0, 0.0, 4.0, 0.0, 4.0, 0.0]))
        assert perfect is not None
        assert variable is not None
        assert variable < perfect

    def test_single_session_returns_none(self) -> None:
        sessions = self._make_sessions([0.0])
        assert sleep_consistency_score(sessions) is None

    def test_two_sessions_returns_value(self) -> None:
        sessions = self._make_sessions([0.0, 0.5])
        result = sleep_consistency_score(sessions)
        assert result is not None
        assert 0.0 <= result <= 100.0
