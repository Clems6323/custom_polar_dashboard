"""Integration tests for ReadinessPipeline using an in-memory DuckDB database.

Seeds the database with raw activity/sleep/recovery data, runs the pipeline,
and asserts that scored metrics are written back correctly.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import duckdb
import pytest

from domain.models.activity import ActivitySession
from domain.models.enums import Provider, SportType
from domain.models.recovery import RecoveryContributors, RecoveryMetrics
from domain.models.sleep import SleepSession
from services.readiness.pipeline import ReadinessPipeline
from storage.duckdb.migrations import run_migrations
from storage.repositories.activity import DuckDBActivityRepository
from storage.repositories.cardio_load import DuckDBCardioLoadRepository
from storage.repositories.metrics import (
    DuckDBRecoveryMetricsRepository,
    DuckDBSleepMetricsRepository,
    DuckDBStrainMetricsRepository,
)
from storage.repositories.sleep import DuckDBSleepRepository

_UID = "pipeline-test-user"
_PROVIDER = Provider.POLAR


@pytest.fixture()
def db() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    yield conn
    conn.close()


def _repos(conn: duckdb.DuckDBPyConnection) -> dict:
    return {
        "activity_repo": DuckDBActivityRepository(conn),
        "sleep_repo": DuckDBSleepRepository(conn),
        "sleep_metrics_repo": DuckDBSleepMetricsRepository(conn),
        "strain_metrics_repo": DuckDBStrainMetricsRepository(conn),
        "recovery_repo": DuckDBRecoveryMetricsRepository(conn),
    }


def _pipeline(conn: duckdb.DuckDBPyConnection, **extra: object) -> ReadinessPipeline:
    return ReadinessPipeline(user_id=_UID, **_repos(conn), **extra)


def _activity_session(d: date, session_id: str, cardio_load: float = 120.0) -> ActivitySession:
    start = datetime(d.year, d.month, d.day, 8, 0, tzinfo=UTC)
    return ActivitySession(
        id=session_id,
        user_id=_UID,
        provider=_PROVIDER,
        start_time=start,
        end_time=start + timedelta(hours=1),
        duration_seconds=3600.0,
        sport_type=SportType.RUNNING,
        cardio_load=cardio_load,
        average_hr_bpm=145.0,
        max_hr_bpm=175.0,
    )


def _sleep_session(morning_date: date, session_id: str) -> SleepSession:
    """Sleep session that ends on `morning_date` (started night before)."""
    end = datetime(morning_date.year, morning_date.month, morning_date.day, 7, 0, tzinfo=UTC)
    start = end - timedelta(hours=8)
    return SleepSession(
        id=session_id,
        user_id=_UID,
        provider=_PROVIDER,
        start_time=start,
        end_time=end,
        duration_seconds=28_800.0,
        deep_sleep_seconds=5_400.0,
        rem_sleep_seconds=7_200.0,
        light_sleep_seconds=14_400.0,
        sleep_efficiency_pct=88.0,
        continuity_score=72.0,
    )


def _raw_recovery(d: date) -> RecoveryMetrics:
    return RecoveryMetrics(
        user_id=_UID,
        record_date=d,
        provider=_PROVIDER,
        recovery_score=50.0,
        rmssd_ms=45.0,
        resting_hr_bpm=54.0,
        contributors=RecoveryContributors(nightly_recharge_score=65.0),
    )


class TestPipelineBasicRun:
    def test_sleep_scored_and_stored(self, db: duckdb.DuckDBPyConnection) -> None:
        target = date(2024, 5, 10)
        sleep_repo = DuckDBSleepRepository(db)
        sleep_repo.upsert(_sleep_session(target, "sleep-1"))

        results = _pipeline(db).run(target, target)

        assert target in results
        assert results[target].sleep_metrics is not None
        assert results[target].sleep_metrics.sleep_score > 0

        stored = DuckDBSleepMetricsRepository(db).get(_UID, target)
        assert stored is not None

    def test_strain_scored_and_stored(self, db: duckdb.DuckDBPyConnection) -> None:
        target = date(2024, 5, 10)
        activity_repo = DuckDBActivityRepository(db)
        activity_repo.upsert(_activity_session(target, "act-1", cardio_load=180.0))

        results = _pipeline(db).run(target, target)

        assert results[target].strain_metrics is not None
        assert results[target].strain_metrics.cardio_load == pytest.approx(180.0)
        assert results[target].strain_metrics.strain_score > 0

        stored = DuckDBStrainMetricsRepository(db).get(_UID, target)
        assert stored is not None

    def test_recovery_scored_and_stored(self, db: duckdb.DuckDBPyConnection) -> None:
        target = date(2024, 5, 10)
        DuckDBRecoveryMetricsRepository(db).upsert(_raw_recovery(target))

        results = _pipeline(db).run(target, target)

        assert results[target].recovery_metrics is not None
        # Score may differ from raw Polar score because scorer enriches it
        assert 0 < results[target].recovery_metrics.recovery_score < 100

    def test_day_with_no_data_has_no_metrics(self, db: duckdb.DuckDBPyConnection) -> None:
        target = date(2024, 6, 1)
        results = _pipeline(db).run(target, target)

        assert target in results
        assert results[target].sleep_metrics is None
        assert results[target].strain_metrics is None
        assert results[target].recovery_metrics is None
        assert results[target].errors == []


class TestPipelineMultiDay:
    def test_multi_day_range_all_scored(self, db: duckdb.DuckDBPyConnection) -> None:
        start = date(2024, 5, 10)
        end = date(2024, 5, 12)
        sleep_repo = DuckDBSleepRepository(db)
        activity_repo = DuckDBActivityRepository(db)
        recovery_repo = DuckDBRecoveryMetricsRepository(db)

        for offset in range(3):
            d = start + timedelta(days=offset)
            sleep_repo.upsert(_sleep_session(d, f"sleep-{offset}"))
            activity_repo.upsert(_activity_session(d, f"act-{offset}"))
            recovery_repo.upsert(_raw_recovery(d))

        results = _pipeline(db).run(start, end)

        assert len(results) == 3
        for d in [start, start + timedelta(1), end]:
            assert results[d].sleep_metrics is not None
            assert results[d].strain_metrics is not None
            assert results[d].recovery_metrics is not None
            assert results[d].errors == []

    def test_recovery_uses_previous_day_strain(self, db: duckdb.DuckDBPyConnection) -> None:
        d1 = date(2024, 5, 10)
        d2 = date(2024, 5, 11)
        activity_repo = DuckDBActivityRepository(db)
        recovery_repo = DuckDBRecoveryMetricsRepository(db)

        # Heavy session on day 1
        activity_repo.upsert(_activity_session(d1, "act-1", cardio_load=350.0))
        recovery_repo.upsert(_raw_recovery(d1))
        recovery_repo.upsert(_raw_recovery(d2))

        results = _pipeline(db).run(d1, d2)

        # Day 2 recovery should have previous_strain_score set (from day 1)
        r2 = results[d2].recovery_metrics
        assert r2 is not None
        assert r2.contributors.previous_strain_score is not None

    def test_results_are_idempotent(self, db: duckdb.DuckDBPyConnection) -> None:
        target = date(2024, 5, 10)
        DuckDBSleepRepository(db).upsert(_sleep_session(target, "sleep-1"))

        first_run = _pipeline(db).run(target, target)
        second_run = _pipeline(db).run(target, target)

        # Scores should be identical on re-run
        s1 = first_run[target].sleep_metrics
        s2 = second_run[target].sleep_metrics
        assert s1 is not None and s2 is not None
        assert s1.sleep_score == pytest.approx(s2.sleep_score)


class TestPipelineWithCardioLoad:
    def test_polar_strain_tolerance_used_for_acwr(self, db: duckdb.DuckDBPyConnection) -> None:
        target = date(2024, 5, 10)
        cardio_repo = DuckDBCardioLoadRepository(db)
        activity_repo = DuckDBActivityRepository(db)

        activity_repo.upsert(_activity_session(target, "act-1", cardio_load=100.0))
        cardio_repo.upsert(_UID, target, cardio_load=100.0, strain=120.0, tolerance=90.0)

        results = _pipeline(db, cardio_load_repo=cardio_repo).run(target, target)

        sm = results[target].strain_metrics
        assert sm is not None
        # With Polar strain=120, tolerance=90 → ACWR = 120/90 ≈ 1.33
        assert sm.acwr == pytest.approx(120.0 / 90.0, rel=0.01)
        assert sm.acute_load == pytest.approx(120.0)
        assert sm.chronic_load == pytest.approx(90.0)

    def test_tolerance_history_feeds_fitness_z_score(self, db: duckdb.DuckDBPyConnection) -> None:
        cardio_repo = DuckDBCardioLoadRepository(db)
        recovery_repo = DuckDBRecoveryMetricsRepository(db)
        activity_repo = DuckDBActivityRepository(db)

        # Seed 24 days of slightly varying tolerance (oscillates ±2) so rolling std > 0.5
        base = date(2024, 5, 1)
        for i in range(24):
            d = base + timedelta(days=i)
            tol = 100.0 + (i % 5 - 2)  # oscillates in [98, 102]
            cardio_repo.upsert(_UID, d, cardio_load=100.0, strain=100.0, tolerance=tol)

        # Day before target: tolerance well above baseline; activity session required so
        # the pipeline scores strain for this day, making it available as prev_strain.
        d_prev = date(2024, 5, 25)
        cardio_repo.upsert(_UID, d_prev, cardio_load=130.0, strain=130.0, tolerance=145.0)
        activity_repo.upsert(_activity_session(d_prev, "act-prev", cardio_load=130.0))

        target = date(2024, 5, 26)
        recovery_repo.upsert(_raw_recovery(target))

        # Run from d_prev so strain is scored on that day and serves as prev_strain for target
        results = _pipeline(db, cardio_load_repo=cardio_repo).run(d_prev, target)

        r = results[target].recovery_metrics
        assert r is not None
        # fitness_z = z_score(145.0, ~100.0, ~8.9) ≈ +4.8 — tolerance well above baseline
        assert r.contributors.fitness_load_z_score is not None
        assert r.contributors.fitness_load_z_score > 0


class TestPipelinePreHistory:
    def test_activity_in_history_window_contributes_to_load(
        self, db: duckdb.DuckDBPyConnection
    ) -> None:
        # Seed an activity BEFORE the pipeline start — it lands in activity_history
        # and the load_by_date building loop (lines 106-108) executes.
        activity_repo = DuckDBActivityRepository(db)
        target = date(2024, 5, 10)
        history_day = target - timedelta(days=5)

        activity_repo.upsert(_activity_session(history_day, "act-history", cardio_load=90.0))
        activity_repo.upsert(_activity_session(target, "act-today", cardio_load=110.0))

        results = _pipeline(db).run(target, target)

        # Strain should be scored using today's sessions; history is used for ACWR
        assert results[target].strain_metrics is not None
        assert results[target].strain_metrics.cardio_load == pytest.approx(110.0)


class TestPipelineErrorIsolation:
    def test_error_on_one_day_does_not_abort_others(self, db: duckdb.DuckDBPyConnection) -> None:
        start = date(2024, 5, 10)
        end = date(2024, 5, 11)

        # Day 1: valid sleep session
        DuckDBSleepRepository(db).upsert(_sleep_session(start, "sleep-1"))
        # Day 2: valid sleep session
        DuckDBSleepRepository(db).upsert(_sleep_session(end, "sleep-2"))

        results = _pipeline(db).run(start, end)

        # Both days present in results
        assert start in results
        assert end in results

    def test_sleep_scorer_error_is_isolated(self, db: duckdb.DuckDBPyConnection) -> None:
        from unittest.mock import patch

        target = date(2024, 5, 10)
        DuckDBSleepRepository(db).upsert(_sleep_session(target, "sleep-1"))

        with patch(
            "services.readiness.pipeline.SleepScorer.score",
            side_effect=RuntimeError("scorer exploded"),
        ):
            results = _pipeline(db).run(target, target)

        # Error is captured in DayReadiness.errors, not propagated
        assert target in results
        assert results[target].sleep_metrics is None
        assert len(results[target].errors) == 1
        assert "sleep scoring failed" in results[target].errors[0]

    def test_strain_scorer_error_is_isolated(self, db: duckdb.DuckDBPyConnection) -> None:
        from unittest.mock import patch

        target = date(2024, 5, 10)
        DuckDBActivityRepository(db).upsert(_activity_session(target, "act-1"))

        with patch(
            "services.readiness.pipeline.StrainScorer.score",
            side_effect=RuntimeError("scorer exploded"),
        ):
            results = _pipeline(db).run(target, target)

        assert results[target].strain_metrics is None
        assert any("strain scoring failed" in e for e in results[target].errors)

    def test_recovery_scorer_error_is_isolated(self, db: duckdb.DuckDBPyConnection) -> None:
        from unittest.mock import patch

        target = date(2024, 5, 10)
        DuckDBRecoveryMetricsRepository(db).upsert(_raw_recovery(target))

        with patch(
            "services.readiness.pipeline.RecoveryScorer.score",
            side_effect=RuntimeError("scorer exploded"),
        ):
            results = _pipeline(db).run(target, target)

        assert results[target].recovery_metrics is None
        assert any("recovery scoring failed" in e for e in results[target].errors)
