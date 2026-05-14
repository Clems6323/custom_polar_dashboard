"""Integration tests for SleepScorer and StrainScorer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domain.models.activity import ActivitySession
from domain.models.enums import Provider, SportType
from domain.models.sleep import SleepSession
from services.scoring.sleep_scorer import SleepScorer
from services.scoring.strain_scorer import StrainScorer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sleep_session(
    date_str: str = "2024-05-10",
    *,
    bed_hour: int = 23,
    wake_hour: int = 7,
    light_s: float = 9_000,
    deep_s: float = 5_400,
    rem_s: float = 5_400,
    efficiency: float | None = 88.0,
    continuity: float | None = 70.0,
    session_id: str = "s1",
) -> SleepSession:
    y, m, d = (int(x) for x in date_str.split("-"))
    start = datetime(y, m, d, bed_hour, 0, tzinfo=UTC)
    end = datetime(y, m, d + 1 if wake_hour < bed_hour else d, wake_hour, 0, tzinfo=UTC)
    duration = (end - start).total_seconds()
    return SleepSession(
        id=session_id,
        user_id="u1",
        provider=Provider.POLAR,
        start_time=start,
        end_time=end,
        duration_seconds=duration,
        light_sleep_seconds=light_s,
        deep_sleep_seconds=deep_s,
        rem_sleep_seconds=rem_s,
        sleep_efficiency_pct=efficiency,
        continuity_score=continuity,
    )


def _activity_session(
    date_str: str = "2024-05-10",
    *,
    duration_s: float = 3_600,
    cardio_load: float | None = 120.0,
    session_id: str = "a1",
) -> ActivitySession:
    y, m, d = (int(x) for x in date_str.split("-"))
    start = datetime(y, m, d, 8, 0, tzinfo=UTC)
    end = start + timedelta(seconds=duration_s)
    return ActivitySession(
        id=session_id,
        user_id="u1",
        provider=Provider.POLAR,
        start_time=start,
        end_time=end,
        duration_seconds=duration_s,
        sport_type=SportType.RUNNING,
        cardio_load=cardio_load,
    )


# ---------------------------------------------------------------------------
# SleepScorer tests
# ---------------------------------------------------------------------------


class TestSleepScorer:
    scorer = SleepScorer()

    def test_produces_sleep_metrics(self) -> None:
        session = _sleep_session()
        metrics = self.scorer.score(session, [])
        assert metrics.sleep_score is not None
        assert 0.0 <= metrics.sleep_score <= 100.0

    def test_record_date_is_wake_date(self) -> None:
        session = _sleep_session("2024-05-09")  # beds 23:00 May 9, wakes May 10
        metrics = self.scorer.score(session, [])
        from datetime import date
        assert metrics.record_date == date(2024, 5, 10)

    def test_architecture_percentages_of_time_in_bed(self) -> None:
        # DEEP + REM + LIGHT + INTERRUPTIONS + UNKNOWN are all fractions of time in bed
        session = _sleep_session()
        metrics = self.scorer.score(session, [])
        total = (
            (metrics.deep_sleep_pct or 0.0)
            + (metrics.rem_sleep_pct or 0.0)
            + (metrics.light_sleep_pct or 0.0)
            + (metrics.awake_pct or 0.0)
            + (metrics.unknown_sleep_pct or 0.0)
        )
        assert total <= 110.0

    def test_consistency_score_with_history(self) -> None:
        history = [_sleep_session(f"2024-05-0{i}", session_id=f"s{i}") for i in range(1, 8)]
        session = _sleep_session("2024-05-10")
        metrics = self.scorer.score(session, history)
        assert metrics.sleep_consistency_score is not None
        assert 0.0 <= metrics.sleep_consistency_score <= 100.0

    def test_no_history_still_produces_score(self) -> None:
        session = _sleep_session()
        metrics = self.scorer.score(session, [])
        assert metrics.sleep_score > 0

    def test_user_id_preserved(self) -> None:
        session = _sleep_session()
        metrics = self.scorer.score(session, [])
        assert metrics.user_id == "u1"

    def test_session_id_linked(self) -> None:
        session = _sleep_session()
        metrics = self.scorer.score(session, [])
        assert metrics.sleep_session_id == "s1"


# ---------------------------------------------------------------------------
# StrainScorer tests
# ---------------------------------------------------------------------------


class TestStrainScorer:
    scorer = StrainScorer()

    def _date(self, s: str):  # type: ignore[no-untyped-def]
        from datetime import date
        return date.fromisoformat(s)

    def test_produces_strain_metrics(self) -> None:
        session = _activity_session()
        metrics = self.scorer.score(self._date("2024-05-10"), [session], [])
        assert 0.0 <= metrics.strain_score <= 100.0

    def test_training_load_matches_session(self) -> None:
        session = _activity_session(cardio_load=150.0)
        metrics = self.scorer.score(self._date("2024-05-10"), [session], [])
        assert metrics.cardio_load == pytest.approx(150.0)

    def test_session_ids_recorded(self) -> None:
        s1 = _activity_session(session_id="a1")
        s2 = _activity_session(session_id="a2", cardio_load=80.0)
        metrics = self.scorer.score(self._date("2024-05-10"), [s1, s2], [])
        assert set(metrics.session_ids) == {"a1", "a2"}

    def test_session_count(self) -> None:
        sessions = [_activity_session(session_id=f"a{i}") for i in range(3)]
        metrics = self.scorer.score(self._date("2024-05-10"), sessions, [])
        assert metrics.session_count == 3

    def test_acwr_computed_with_enough_history(self) -> None:
        loads = [100.0] * 28
        session = _activity_session(cardio_load=200.0)
        metrics = self.scorer.score(self._date("2024-05-10"), [session], loads)
        assert metrics.acwr is not None

    def test_acwr_none_with_insufficient_history(self) -> None:
        loads = [100.0] * 10  # fewer than 28 days
        session = _activity_session(cardio_load=100.0)
        metrics = self.scorer.score(self._date("2024-05-10"), [session], loads)
        assert metrics.acwr is None

    def test_no_sessions_zero_load(self) -> None:
        metrics = self.scorer.score(self._date("2024-05-10"), [], [])
        assert metrics.cardio_load == pytest.approx(0.0)
        assert metrics.strain_score == pytest.approx(0.0, abs=1.0)

    def test_polar_rolling_loads_used_as_primary_for_acwr(self) -> None:
        # Polar strain=18, tolerance=22 → ACWR = 18/22 ≈ 0.818
        # Local history is empty (would give None) — proves Polar values take priority
        session = _activity_session(cardio_load=20.0)
        metrics = self.scorer.score(
            self._date("2024-05-10"), [session], [],
            polar_strain=18.0, polar_tolerance=22.0,
        )
        assert metrics.acwr == pytest.approx(18.0 / 22.0, abs=0.001)
        assert metrics.acute_load == pytest.approx(18.0)
        assert metrics.chronic_load == pytest.approx(22.0)

    def test_fallback_to_local_acwr_when_polar_loads_absent(self) -> None:
        loads = [100.0] * 28
        session = _activity_session(cardio_load=100.0)
        metrics = self.scorer.score(self._date("2024-05-10"), [session], loads)
        assert metrics.acwr is not None  # computed from local history
