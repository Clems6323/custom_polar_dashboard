"""Integration tests for all DuckDB repository implementations.

All tests use an in-memory DuckDB connection (db_conn fixture) — no disk I/O,
no clean-up needed.  Focus: round-trip fidelity (save → retrieve → compare).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import duckdb
import pytest

from domain.models import (
    ActivitySession,
    RecoveryMetrics,
    SleepMetrics,
    SleepSession,
    StrainMetrics,
)
from domain.models.enums import Provider, SleepStage, SportType
from domain.models.recovery import RecoveryContributors
from domain.models.sleep import SleepStageInterval
from storage.repositories.activity import DuckDBActivityRepository
from storage.repositories.cardio_load import DuckDBCardioLoadRepository
from storage.repositories.metrics import (
    DuckDBRecoveryMetricsRepository,
    DuckDBSleepMetricsRepository,
    DuckDBStrainMetricsRepository,
)
from storage.repositories.sleep import DuckDBSleepRepository

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_UID = "user-001"
_T0 = datetime(2024, 5, 10, 6, 0, 0, tzinfo=UTC)
_T1 = datetime(2024, 5, 10, 7, 0, 0, tzinfo=UTC)
_DATE = date(2024, 5, 10)
_PROVIDER = Provider.POLAR


def _activity(**overrides: object) -> ActivitySession:
    base: dict = {
        "id": "act-001",
        "user_id": _UID,
        "provider": _PROVIDER,
        "start_time": _T0,
        "end_time": _T1,
        "duration_seconds": 3600.0,
        "sport_type": SportType.RUNNING,
        "cardio_load": 250.0,
        "average_hr_bpm": 145.0,
    }
    base.update(overrides)
    return ActivitySession(**base)


def _sleep(**overrides: object) -> SleepSession:
    base: dict = {
        "id": "sleep-001",
        "user_id": _UID,
        "provider": _PROVIDER,
        "start_time": datetime(2024, 5, 9, 22, 0, 0, tzinfo=UTC),
        "end_time": datetime(2024, 5, 10, 6, 0, 0, tzinfo=UTC),
        "duration_seconds": 28_800.0,
        "rmssd_ms": 48.5,
        "average_hr_bpm": 52.0,
        "deep_sleep_seconds": 5400.0,
        "rem_sleep_seconds": 7200.0,
        "light_sleep_seconds": 14_400.0,
    }
    base.update(overrides)
    return SleepSession(**base)


# ---------------------------------------------------------------------------
# ActivityRepository
# ---------------------------------------------------------------------------


class TestActivityRepository:
    def test_upsert_and_get(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBActivityRepository(db_conn)
        session = _activity()
        repo.upsert(session)

        retrieved = repo.get("act-001")
        assert retrieved is not None
        assert retrieved.id == "act-001"
        assert retrieved.sport_type == SportType.RUNNING
        assert retrieved.cardio_load == pytest.approx(250.0)
        assert retrieved.average_hr_bpm == pytest.approx(145.0)
        assert retrieved.start_time.tzinfo is not None

    def test_get_missing_returns_none(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBActivityRepository(db_conn)
        assert repo.get("no-such-id") is None

    def test_upsert_updates_existing(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBActivityRepository(db_conn)
        repo.upsert(_activity(cardio_load=100.0))
        repo.upsert(_activity(cardio_load=200.0))

        retrieved = repo.get("act-001")
        assert retrieved is not None
        assert retrieved.cardio_load == pytest.approx(200.0)

    def test_list_by_date_range(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBActivityRepository(db_conn)
        repo.upsert(_activity(id="act-001"))
        repo.upsert(_activity(id="act-002", start_time=datetime(2024, 5, 20, 6, 0, 0, tzinfo=UTC),
                              end_time=datetime(2024, 5, 20, 7, 0, 0, tzinfo=UTC)))

        in_range = repo.list_by_date_range(_UID, date(2024, 5, 9), date(2024, 5, 11))
        assert len(in_range) == 1
        assert in_range[0].id == "act-001"

    def test_list_latest(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBActivityRepository(db_conn)
        for i in range(5):
            repo.upsert(_activity(
                id=f"act-{i:03d}",
                start_time=datetime(2024, 5, i + 1, 6, 0, 0, tzinfo=UTC),
                end_time=datetime(2024, 5, i + 1, 7, 0, 0, tzinfo=UTC),
            ))
        latest = repo.list_latest(_UID, n=3)
        assert len(latest) == 3
        assert latest[0].start_time > latest[1].start_time  # descending order

    def test_upsert_batch(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBActivityRepository(db_conn)
        sessions = [
            _activity(id=f"act-{i}", start_time=datetime(2024, 5, i + 1, 6, 0, 0, tzinfo=UTC),
                      end_time=datetime(2024, 5, i + 1, 7, 0, 0, tzinfo=UTC))
            for i in range(3)
        ]
        repo.upsert_batch(sessions)
        assert repo.get("act-0") is not None
        assert repo.get("act-2") is not None

    def test_delete(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBActivityRepository(db_conn)
        repo.upsert(_activity())
        repo.delete("act-001")
        assert repo.get("act-001") is None

    def test_hr_zone_distribution_round_trip(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBActivityRepository(db_conn)
        zones = {"zone_1": 0.2, "zone_2": 0.5, "zone_3": 0.3}
        repo.upsert(_activity(hr_zone_distribution=zones))
        retrieved = repo.get("act-001")
        assert retrieved is not None
        assert retrieved.hr_zone_distribution == zones


# ---------------------------------------------------------------------------
# SleepRepository
# ---------------------------------------------------------------------------


class TestSleepRepository:
    def test_upsert_and_get(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBSleepRepository(db_conn)
        session = _sleep()
        repo.upsert(session)

        retrieved = repo.get("sleep-001")
        assert retrieved is not None
        assert retrieved.rmssd_ms == pytest.approx(48.5)
        assert retrieved.average_hr_bpm == pytest.approx(52.0)
        assert retrieved.start_time.tzinfo is not None

    def test_stage_intervals_round_trip(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBSleepRepository(db_conn)
        intervals = [
            SleepStageInterval(
                start_time=datetime(2024, 5, 9, 22, 0, tzinfo=UTC),
                end_time=datetime(2024, 5, 9, 23, 0, tzinfo=UTC),
                stage=SleepStage.LIGHT,
                duration_seconds=3600.0,
            ),
            SleepStageInterval(
                start_time=datetime(2024, 5, 9, 23, 0, tzinfo=UTC),
                end_time=datetime(2024, 5, 10, 1, 0, tzinfo=UTC),
                stage=SleepStage.DEEP,
                duration_seconds=7200.0,
            ),
        ]
        repo.upsert(_sleep(stage_intervals=intervals))
        retrieved = repo.get("sleep-001")
        assert retrieved is not None
        assert len(retrieved.stage_intervals) == 2
        assert retrieved.stage_intervals[0].stage == SleepStage.LIGHT
        assert retrieved.stage_intervals[1].stage == SleepStage.DEEP

    def test_upsert_replaces_intervals(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBSleepRepository(db_conn)
        interval = SleepStageInterval(
            start_time=datetime(2024, 5, 9, 22, 0, tzinfo=UTC),
            end_time=datetime(2024, 5, 9, 23, 0, tzinfo=UTC),
            stage=SleepStage.REM,
            duration_seconds=3600.0,
        )
        repo.upsert(_sleep(stage_intervals=[interval]))
        # Re-upsert with no intervals
        repo.upsert(_sleep(stage_intervals=[]))
        retrieved = repo.get("sleep-001")
        assert retrieved is not None
        assert retrieved.stage_intervals == []

    def test_list_by_date_range(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBSleepRepository(db_conn)
        repo.upsert(_sleep(id="sleep-001"))
        in_range = repo.list_by_date_range(_UID, date(2024, 5, 9), date(2024, 5, 10))
        assert len(in_range) == 1

    def test_delete_cascades_intervals(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBSleepRepository(db_conn)
        interval = SleepStageInterval(
            start_time=datetime(2024, 5, 9, 22, 0, tzinfo=UTC),
            end_time=datetime(2024, 5, 9, 23, 0, tzinfo=UTC),
            stage=SleepStage.LIGHT,
            duration_seconds=3600.0,
        )
        repo.upsert(_sleep(stage_intervals=[interval]))
        repo.delete("sleep-001")
        assert repo.get("sleep-001") is None
        count = db_conn.execute(
            "SELECT COUNT(*) FROM sleep_stage_intervals WHERE sleep_session_id = 'sleep-001'"
        ).fetchone()[0]
        assert count == 0

    def test_upsert_batch(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBSleepRepository(db_conn)
        sessions = [
            _sleep(
                id=f"sleep-{i:03d}",
                start_time=datetime(2024, 5, i, 22, 0, 0, tzinfo=UTC),
                end_time=datetime(2024, 5, i + 1, 6, 0, 0, tzinfo=UTC),
            )
            for i in range(1, 4)
        ]
        repo.upsert_batch(sessions)
        assert repo.get("sleep-001") is not None
        assert repo.get("sleep-003") is not None

    def test_list_latest(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBSleepRepository(db_conn)
        for i in range(1, 6):
            repo.upsert(_sleep(
                id=f"sleep-{i:03d}",
                start_time=datetime(2024, 5, i, 22, 0, 0, tzinfo=UTC),
                end_time=datetime(2024, 5, i + 1, 6, 0, 0, tzinfo=UTC),
            ))
        latest = repo.list_latest(_UID, n=3)
        assert len(latest) == 3
        # Descending order: most recent first
        assert latest[0].start_time > latest[1].start_time


# ---------------------------------------------------------------------------
# RecoveryMetricsRepository
# ---------------------------------------------------------------------------


class TestRecoveryMetricsRepository:
    def _metrics(self, **overrides: object) -> RecoveryMetrics:
        base: dict = {
            "user_id": _UID,
            "record_date": _DATE,
            "provider": _PROVIDER,
            "recovery_score": 72.0,
            "rmssd_ms": 52.3,
            "contributors": RecoveryContributors(hrv_z_score=0.8, sleep_score=75.0),
        }
        base.update(overrides)
        return RecoveryMetrics(**base)

    def test_upsert_and_get(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBRecoveryMetricsRepository(db_conn)
        repo.upsert(self._metrics())
        retrieved = repo.get(_UID, _DATE)
        assert retrieved is not None
        assert retrieved.recovery_score == pytest.approx(72.0)
        assert retrieved.contributors.hrv_z_score == pytest.approx(0.8)

    def test_upsert_updates(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBRecoveryMetricsRepository(db_conn)
        repo.upsert(self._metrics(recovery_score=60.0))
        repo.upsert(self._metrics(recovery_score=80.0))
        retrieved = repo.get(_UID, _DATE)
        assert retrieved is not None
        assert retrieved.recovery_score == pytest.approx(80.0)

    def test_list_by_date_range(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBRecoveryMetricsRepository(db_conn)
        for offset in range(3):
            repo.upsert(self._metrics(record_date=date(2024, 5, 10 + offset)))
        results = repo.list_by_date_range(_UID, date(2024, 5, 10), date(2024, 5, 11))
        assert len(results) == 2


# ---------------------------------------------------------------------------
# StrainMetricsRepository
# ---------------------------------------------------------------------------


class TestStrainMetricsRepository:
    def _metrics(self, **overrides: object) -> StrainMetrics:
        base: dict = {
            "user_id": _UID,
            "record_date": _DATE,
            "provider": _PROVIDER,
            "strain_score": 55.0,
            "cardio_load": 320.0,
            "session_ids": ["act-001", "act-002"],
        }
        base.update(overrides)
        return StrainMetrics(**base)

    def test_upsert_and_get(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBStrainMetricsRepository(db_conn)
        repo.upsert(self._metrics())
        retrieved = repo.get(_UID, _DATE)
        assert retrieved is not None
        assert retrieved.strain_score == pytest.approx(55.0)
        assert retrieved.session_ids == ["act-001", "act-002"]

    def test_session_ids_round_trip(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBStrainMetricsRepository(db_conn)
        repo.upsert(self._metrics(session_ids=["x", "y", "z"]))
        retrieved = repo.get(_UID, _DATE)
        assert retrieved is not None
        assert retrieved.session_ids == ["x", "y", "z"]


# ---------------------------------------------------------------------------
# SleepMetricsRepository
# ---------------------------------------------------------------------------


class TestSleepMetricsRepository:
    def _metrics(self, **overrides: object) -> SleepMetrics:
        base: dict = {
            "user_id": _UID,
            "record_date": _DATE,
            "provider": _PROVIDER,
            "sleep_score": 78.0,
            "total_sleep_seconds": 25_200.0,
            "deep_sleep_pct": 20.0,
            "rem_sleep_pct": 25.0,
            "light_sleep_pct": 55.0,
        }
        base.update(overrides)
        return SleepMetrics(**base)

    def test_upsert_and_get(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBSleepMetricsRepository(db_conn)
        repo.upsert(self._metrics())
        retrieved = repo.get(_UID, _DATE)
        assert retrieved is not None
        assert retrieved.sleep_score == pytest.approx(78.0)
        assert retrieved.deep_sleep_pct == pytest.approx(20.0)

    def test_list_by_date_range_empty(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBSleepMetricsRepository(db_conn)
        results = repo.list_by_date_range(_UID, date(2024, 1, 1), date(2024, 1, 31))
        assert results == []


# ---------------------------------------------------------------------------
# CardioLoadRepository
# ---------------------------------------------------------------------------


class TestCardioLoadRepository:
    def test_upsert_and_get(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBCardioLoadRepository(db_conn)
        repo.upsert(_UID, _DATE, cardio_load=120.0, strain=95.0, tolerance=88.0)
        row = repo.get(_UID, _DATE)
        assert row is not None
        assert row["cardio_load"] == pytest.approx(120.0)
        assert row["strain"] == pytest.approx(95.0)
        assert row["tolerance"] == pytest.approx(88.0)

    def test_get_missing_returns_none(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBCardioLoadRepository(db_conn)
        assert repo.get(_UID, date(2020, 1, 1)) is None

    def test_upsert_overwrites_existing(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBCardioLoadRepository(db_conn)
        repo.upsert(_UID, _DATE, cardio_load=100.0, strain=80.0, tolerance=75.0)
        repo.upsert(_UID, _DATE, cardio_load=150.0, strain=110.0, tolerance=90.0)
        row = repo.get(_UID, _DATE)
        assert row is not None
        assert row["cardio_load"] == pytest.approx(150.0)
        assert row["tolerance"] == pytest.approx(90.0)

    def test_null_fields_stored(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBCardioLoadRepository(db_conn)
        repo.upsert(_UID, _DATE, cardio_load=None, strain=None, tolerance=None)
        row = repo.get(_UID, _DATE)
        assert row is not None
        assert row["cardio_load"] is None
        assert row["strain"] is None

    def test_list_by_date_range(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBCardioLoadRepository(db_conn)
        for offset, load in enumerate([80.0, 120.0, 160.0]):
            repo.upsert(_UID, date(2024, 5, 10 + offset), cardio_load=load, strain=load, tolerance=load * 0.9)

        rows = repo.list_by_date_range(_UID, date(2024, 5, 10), date(2024, 5, 11))
        assert len(rows) == 2
        assert rows[0]["cardio_load"] == pytest.approx(80.0)
        assert rows[1]["cardio_load"] == pytest.approx(120.0)

    def test_list_excludes_other_users(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBCardioLoadRepository(db_conn)
        repo.upsert(_UID, _DATE, cardio_load=100.0, strain=80.0, tolerance=70.0)
        repo.upsert("other-user", _DATE, cardio_load=200.0, strain=180.0, tolerance=160.0)
        rows = repo.list_by_date_range(_UID, date(2024, 5, 1), date(2024, 5, 31))
        assert len(rows) == 1
        assert rows[0]["user_id"] == _UID

    def test_list_empty_range(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        repo = DuckDBCardioLoadRepository(db_conn)
        assert repo.list_by_date_range(_UID, date(2024, 1, 1), date(2024, 1, 31)) == []
