"""Shared fixtures for MCP layer tests.

Uses in-memory DuckDB databases — no filesystem side effects.
Each fixture is function-scoped for full isolation between tests.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import duckdb
import pytest

from domain.models.enums import Provider
from domain.models.recovery import RecoveryContributors, RecoveryMetrics
from domain.models.sleep_metrics import SleepMetrics
from domain.models.strain import StrainMetrics
from storage.duckdb.migrations import run_migrations
from storage.repositories.metrics import (
    DuckDBRecoveryMetricsRepository,
    DuckDBSleepMetricsRepository,
    DuckDBStrainMetricsRepository,
)


@pytest.fixture()
def db_conn() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB connection with full schema applied."""
    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    return conn


@pytest.fixture()
def user_id() -> str:
    return "test-user-mcp"


@pytest.fixture()
def record_date() -> date:
    return date(2025, 11, 15)


# ---------------------------------------------------------------------------
# Seed fixtures
# ---------------------------------------------------------------------------


def _make_sleep_metrics(user_id: str, record_date: date, **overrides) -> SleepMetrics:
    defaults = dict(
        user_id=user_id,
        record_date=record_date,
        provider=Provider.POLAR,
        sleep_score=72.5,
        total_sleep_seconds=7.0 * 3600,
        time_in_bed_seconds=7.5 * 3600,
        sleep_efficiency_pct=93.3,
        sleep_latency_seconds=600.0,
        deep_sleep_pct=22.0,
        rem_sleep_pct=26.0,
        light_sleep_pct=45.3,
        awake_pct=6.7,
        rmssd_ms=42.5,
        average_hr_bpm=55.0,
        sleep_consistency_score=81.0,
    )
    defaults.update(overrides)
    return SleepMetrics(**defaults)


def _make_strain_metrics(user_id: str, record_date: date, **overrides) -> StrainMetrics:
    defaults = dict(
        user_id=user_id,
        record_date=record_date,
        provider=Provider.POLAR,
        strain_score=55.0,
        cardio_load=180.0,
        muscle_load=60.0,
        acute_load=150.0,
        chronic_load=140.0,
        acwr=1.07,
        session_count=2,
        session_ids=["session-a", "session-b"],
    )
    defaults.update(overrides)
    return StrainMetrics(**defaults)


def _make_recovery_metrics(user_id: str, record_date: date, **overrides) -> RecoveryMetrics:
    defaults = dict(
        user_id=user_id,
        record_date=record_date,
        provider=Provider.POLAR,
        recovery_score=68.0,
        rmssd_ms=43.0,
        sdnn_ms=55.0,
        resting_hr_bpm=52.0,
        mean_skin_temperature_celsius=35.8,
        hrv_baseline_ms=40.0,
        resting_hr_baseline_bpm=54.0,
        contributors=RecoveryContributors(
            hrv_z_score=0.5,
            resting_hr_z_score=-0.3,
            sleep_score=72.5,
            previous_strain_score=40.0,
            temperature_deviation_celsius=0.1,
            nightly_recharge_score=65.0,
        ),
    )
    defaults.update(overrides)
    return RecoveryMetrics(**defaults)


@pytest.fixture()
def seeded_sleep_db(db_conn, user_id, record_date) -> duckdb.DuckDBPyConnection:
    """DB with one SleepMetrics record."""
    repo = DuckDBSleepMetricsRepository(db_conn)
    repo.upsert(_make_sleep_metrics(user_id, record_date))
    return db_conn


@pytest.fixture()
def seeded_strain_db(db_conn, user_id, record_date) -> duckdb.DuckDBPyConnection:
    """DB with one StrainMetrics record."""
    repo = DuckDBStrainMetricsRepository(db_conn)
    repo.upsert(_make_strain_metrics(user_id, record_date))
    return db_conn


@pytest.fixture()
def seeded_recovery_db(db_conn, user_id, record_date) -> duckdb.DuckDBPyConnection:
    """DB with one RecoveryMetrics record."""
    repo = DuckDBRecoveryMetricsRepository(db_conn)
    repo.upsert(_make_recovery_metrics(user_id, record_date))
    return db_conn


@pytest.fixture()
def seeded_range_db(db_conn, user_id) -> duckdb.DuckDBPyConnection:
    """DB with 7 consecutive days of all three metric types."""
    sleep_repo = DuckDBSleepMetricsRepository(db_conn)
    strain_repo = DuckDBStrainMetricsRepository(db_conn)
    recovery_repo = DuckDBRecoveryMetricsRepository(db_conn)

    base = date(2025, 11, 10)
    for i in range(7):
        d = date(base.year, base.month, base.day + i) if base.day + i <= 30 else base
        # Vary the scores slightly so averages are meaningful
        sleep_repo.upsert(_make_sleep_metrics(user_id, d, sleep_score=65.0 + i, total_sleep_seconds=(6.5 + i * 0.1) * 3600))
        strain_repo.upsert(_make_strain_metrics(user_id, d, cardio_load=100.0 + i * 20, strain_score=40.0 + i * 3))
        recovery_repo.upsert(_make_recovery_metrics(user_id, d, recovery_score=60.0 + i * 2, rmssd_ms=38.0 + i))

    return db_conn
