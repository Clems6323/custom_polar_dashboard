"""DuckDB implementations for daily metrics repositories.

All three metrics tables share the pattern:
  - composite PK (user_id, record_date)
  - upsert via ON CONFLICT ... DO UPDATE
  - no stage-interval subquery (flat tables)
"""

from __future__ import annotations

import json
import logging
from datetime import date

import duckdb

from domain.models import RecoveryMetrics, SleepMetrics, StrainMetrics
from domain.models.enums import Provider
from domain.models.recovery import RecoveryContributors

logger = logging.getLogger(__name__)


def _fetch_all(result: duckdb.DuckDBPyRelation) -> list[dict]:
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]


# ---------------------------------------------------------------------------
# RecoveryMetrics
# ---------------------------------------------------------------------------

_RECOVERY_UPSERT = """
INSERT INTO recovery_metrics (
    user_id, record_date, provider, recovery_score,
    rmssd_ms, sdnn_ms, resting_hr_bpm, mean_skin_temperature_celsius,
    hrv_baseline_ms, resting_hr_baseline_bpm,
    contrib_hrv_z_score, contrib_resting_hr_z_score, contrib_sleep_score,
    contrib_previous_strain_score, contrib_temperature_deviation_celsius,
    contrib_nightly_recharge_score, contrib_fitness_load_z_score
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (user_id, record_date) DO UPDATE SET
    provider                             = EXCLUDED.provider,
    recovery_score                       = EXCLUDED.recovery_score,
    rmssd_ms                             = EXCLUDED.rmssd_ms,
    sdnn_ms                              = EXCLUDED.sdnn_ms,
    resting_hr_bpm                       = EXCLUDED.resting_hr_bpm,
    mean_skin_temperature_celsius        = EXCLUDED.mean_skin_temperature_celsius,
    hrv_baseline_ms                      = EXCLUDED.hrv_baseline_ms,
    resting_hr_baseline_bpm             = EXCLUDED.resting_hr_baseline_bpm,
    contrib_hrv_z_score                  = EXCLUDED.contrib_hrv_z_score,
    contrib_resting_hr_z_score           = EXCLUDED.contrib_resting_hr_z_score,
    contrib_sleep_score                  = EXCLUDED.contrib_sleep_score,
    contrib_previous_strain_score        = EXCLUDED.contrib_previous_strain_score,
    contrib_temperature_deviation_celsius = EXCLUDED.contrib_temperature_deviation_celsius,
    contrib_nightly_recharge_score       = EXCLUDED.contrib_nightly_recharge_score,
    contrib_fitness_load_z_score         = EXCLUDED.contrib_fitness_load_z_score,
    updated_at                           = now()
"""


def _recovery_to_row(m: RecoveryMetrics) -> list:
    c = m.contributors
    return [
        m.user_id, m.record_date, str(m.provider), m.recovery_score,
        m.rmssd_ms, m.sdnn_ms, m.resting_hr_bpm, m.mean_skin_temperature_celsius,
        m.hrv_baseline_ms, m.resting_hr_baseline_bpm,
        c.hrv_z_score, c.resting_hr_z_score, c.sleep_score,
        c.previous_strain_score, c.temperature_deviation_celsius, c.nightly_recharge_score,
        c.fitness_load_z_score,
    ]


def _recovery_from_row(row: dict) -> RecoveryMetrics:
    return RecoveryMetrics(
        user_id=row["user_id"],
        record_date=row["record_date"],
        provider=Provider(row["provider"]),
        recovery_score=row["recovery_score"],
        rmssd_ms=row.get("rmssd_ms"),
        sdnn_ms=row.get("sdnn_ms"),
        resting_hr_bpm=row.get("resting_hr_bpm"),
        mean_skin_temperature_celsius=row.get("mean_skin_temperature_celsius"),
        hrv_baseline_ms=row.get("hrv_baseline_ms"),
        resting_hr_baseline_bpm=row.get("resting_hr_baseline_bpm"),
        contributors=RecoveryContributors(
            hrv_z_score=row.get("contrib_hrv_z_score"),
            resting_hr_z_score=row.get("contrib_resting_hr_z_score"),
            sleep_score=row.get("contrib_sleep_score"),
            previous_strain_score=row.get("contrib_previous_strain_score"),
            temperature_deviation_celsius=row.get("contrib_temperature_deviation_celsius"),
            nightly_recharge_score=row.get("contrib_nightly_recharge_score"),
            fitness_load_z_score=row.get("contrib_fitness_load_z_score"),
        ),
    )


class DuckDBRecoveryMetricsRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def upsert(self, metrics: RecoveryMetrics) -> None:
        self._conn.execute(_RECOVERY_UPSERT, _recovery_to_row(metrics))

    def get(self, user_id: str, record_date: date) -> RecoveryMetrics | None:
        result = self._conn.execute(
            "SELECT * FROM recovery_metrics WHERE user_id = ? AND record_date = ?",
            [user_id, record_date],
        )
        rows = _fetch_all(result)
        return _recovery_from_row(rows[0]) if rows else None

    def list_by_date_range(
        self, user_id: str, start: date, end: date
    ) -> list[RecoveryMetrics]:
        result = self._conn.execute(
            """
            SELECT * FROM recovery_metrics
            WHERE user_id = ? AND record_date BETWEEN ? AND ?
            ORDER BY record_date
            """,
            [user_id, start, end],
        )
        return [_recovery_from_row(r) for r in _fetch_all(result)]


# ---------------------------------------------------------------------------
# StrainMetrics
# ---------------------------------------------------------------------------

_STRAIN_UPSERT = """
INSERT INTO strain_metrics (
    user_id, record_date, provider, strain_score, cardio_load,
    muscle_load, acute_load, chronic_load, acwr,
    session_count, session_ids
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (user_id, record_date) DO UPDATE SET
    provider      = EXCLUDED.provider,
    strain_score  = EXCLUDED.strain_score,
    cardio_load   = EXCLUDED.cardio_load,
    muscle_load   = EXCLUDED.muscle_load,
    acute_load    = EXCLUDED.acute_load,
    chronic_load  = EXCLUDED.chronic_load,
    acwr          = EXCLUDED.acwr,
    session_count = EXCLUDED.session_count,
    session_ids   = EXCLUDED.session_ids,
    updated_at    = now()
"""


def _strain_to_row(m: StrainMetrics) -> list:
    return [
        m.user_id, m.record_date, str(m.provider), m.strain_score, m.cardio_load,
        m.muscle_load, m.acute_load, m.chronic_load, m.acwr,
        m.session_count, json.dumps(m.session_ids),
    ]


def _strain_from_row(row: dict) -> StrainMetrics:
    raw_ids = row.get("session_ids")
    session_ids: list[str] = json.loads(raw_ids) if isinstance(raw_ids, str) else (raw_ids or [])
    return StrainMetrics(
        user_id=row["user_id"],
        record_date=row["record_date"],
        provider=Provider(row["provider"]),
        strain_score=row["strain_score"],
        cardio_load=row["cardio_load"],
        muscle_load=row.get("muscle_load"),
        acute_load=row.get("acute_load"),
        chronic_load=row.get("chronic_load"),
        acwr=row.get("acwr"),
        session_count=row.get("session_count") or 0,
        session_ids=session_ids,
    )


class DuckDBStrainMetricsRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def upsert(self, metrics: StrainMetrics) -> None:
        self._conn.execute(_STRAIN_UPSERT, _strain_to_row(metrics))

    def get(self, user_id: str, record_date: date) -> StrainMetrics | None:
        result = self._conn.execute(
            "SELECT * FROM strain_metrics WHERE user_id = ? AND record_date = ?",
            [user_id, record_date],
        )
        rows = _fetch_all(result)
        return _strain_from_row(rows[0]) if rows else None

    def list_by_date_range(
        self, user_id: str, start: date, end: date
    ) -> list[StrainMetrics]:
        result = self._conn.execute(
            """
            SELECT * FROM strain_metrics
            WHERE user_id = ? AND record_date BETWEEN ? AND ?
            ORDER BY record_date
            """,
            [user_id, start, end],
        )
        return [_strain_from_row(r) for r in _fetch_all(result)]


# ---------------------------------------------------------------------------
# SleepMetrics
# ---------------------------------------------------------------------------

_SLEEP_METRICS_UPSERT = """
INSERT INTO sleep_metrics (
    user_id, record_date, provider, sleep_session_id, sleep_score,
    total_sleep_seconds, time_in_bed_seconds, sleep_efficiency_pct,
    sleep_latency_seconds, deep_sleep_pct, rem_sleep_pct, light_sleep_pct,
    awake_pct, unknown_sleep_pct,
    short_interruption_duration_seconds, long_interruption_duration_seconds,
    rmssd_ms, average_hr_bpm, sleep_consistency_score
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (user_id, record_date) DO UPDATE SET
    provider                             = EXCLUDED.provider,
    sleep_session_id                     = EXCLUDED.sleep_session_id,
    sleep_score                          = EXCLUDED.sleep_score,
    total_sleep_seconds                  = EXCLUDED.total_sleep_seconds,
    time_in_bed_seconds                  = EXCLUDED.time_in_bed_seconds,
    sleep_efficiency_pct                 = EXCLUDED.sleep_efficiency_pct,
    sleep_latency_seconds                = EXCLUDED.sleep_latency_seconds,
    deep_sleep_pct                       = EXCLUDED.deep_sleep_pct,
    rem_sleep_pct                        = EXCLUDED.rem_sleep_pct,
    light_sleep_pct                      = EXCLUDED.light_sleep_pct,
    awake_pct                            = EXCLUDED.awake_pct,
    unknown_sleep_pct                    = EXCLUDED.unknown_sleep_pct,
    short_interruption_duration_seconds  = EXCLUDED.short_interruption_duration_seconds,
    long_interruption_duration_seconds   = EXCLUDED.long_interruption_duration_seconds,
    rmssd_ms                             = EXCLUDED.rmssd_ms,
    average_hr_bpm                       = EXCLUDED.average_hr_bpm,
    sleep_consistency_score              = EXCLUDED.sleep_consistency_score,
    updated_at                           = now()
"""


def _sleep_metrics_to_row(m: SleepMetrics) -> list:
    return [
        m.user_id, m.record_date, str(m.provider), m.sleep_session_id,
        m.sleep_score, m.total_sleep_seconds, m.time_in_bed_seconds,
        m.sleep_efficiency_pct, m.sleep_latency_seconds,
        m.deep_sleep_pct, m.rem_sleep_pct, m.light_sleep_pct, m.awake_pct,
        m.unknown_sleep_pct,
        m.short_interruption_duration_seconds, m.long_interruption_duration_seconds,
        m.rmssd_ms, m.average_hr_bpm, m.sleep_consistency_score,
    ]


def _sleep_metrics_from_row(row: dict) -> SleepMetrics:
    return SleepMetrics(
        user_id=row["user_id"],
        record_date=row["record_date"],
        provider=Provider(row["provider"]),
        sleep_session_id=row.get("sleep_session_id"),
        sleep_score=row["sleep_score"],
        total_sleep_seconds=row["total_sleep_seconds"],
        time_in_bed_seconds=row.get("time_in_bed_seconds"),
        sleep_efficiency_pct=row.get("sleep_efficiency_pct"),
        sleep_latency_seconds=row.get("sleep_latency_seconds"),
        deep_sleep_pct=row.get("deep_sleep_pct"),
        rem_sleep_pct=row.get("rem_sleep_pct"),
        light_sleep_pct=row.get("light_sleep_pct"),
        awake_pct=row.get("awake_pct"),
        unknown_sleep_pct=row.get("unknown_sleep_pct"),
        short_interruption_duration_seconds=row.get("short_interruption_duration_seconds"),
        long_interruption_duration_seconds=row.get("long_interruption_duration_seconds"),
        rmssd_ms=row.get("rmssd_ms"),
        average_hr_bpm=row.get("average_hr_bpm"),
        sleep_consistency_score=row.get("sleep_consistency_score"),
    )


class DuckDBSleepMetricsRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def upsert(self, metrics: SleepMetrics) -> None:
        self._conn.execute(_SLEEP_METRICS_UPSERT, _sleep_metrics_to_row(metrics))

    def get(self, user_id: str, record_date: date) -> SleepMetrics | None:
        result = self._conn.execute(
            "SELECT * FROM sleep_metrics WHERE user_id = ? AND record_date = ?",
            [user_id, record_date],
        )
        rows = _fetch_all(result)
        return _sleep_metrics_from_row(rows[0]) if rows else None

    def list_by_date_range(
        self, user_id: str, start: date, end: date
    ) -> list[SleepMetrics]:
        result = self._conn.execute(
            """
            SELECT * FROM sleep_metrics
            WHERE user_id = ? AND record_date BETWEEN ? AND ?
            ORDER BY record_date
            """,
            [user_id, start, end],
        )
        return [_sleep_metrics_from_row(r) for r in _fetch_all(result)]
