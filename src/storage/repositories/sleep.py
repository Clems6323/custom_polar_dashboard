"""DuckDB implementation of SleepRepository.

SleepSession and its SleepStageIntervals are saved atomically in a single
transaction: the session row first, then all interval rows.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime

import duckdb

from domain.models import SleepSession
from domain.models.enums import Provider, SleepStage
from domain.models.sleep import SleepStageInterval

logger = logging.getLogger(__name__)

_SESSION_COLS = (
    "id", "user_id", "provider", "start_time", "end_time", "duration_seconds",
    "sleep_latency_seconds", "continuity_score", "sleep_efficiency_pct",
    "light_sleep_seconds", "deep_sleep_seconds", "rem_sleep_seconds",
    "awake_seconds", "interruptions",
    "short_interruption_duration_seconds", "long_interruption_duration_seconds",
    "unknown_sleep_seconds",
    "average_hr_bpm", "min_hr_bpm",
    "average_ppi_ms", "rmssd_ms", "sdnn_ms", "breathing_rate_bpm",
    "snoring_seconds", "mean_skin_temperature_celsius", "temperature_deviation_celsius",
)

_SESSION_UPSERT = f"""
INSERT INTO sleep_sessions ({', '.join(_SESSION_COLS)})
VALUES ({', '.join('?' * len(_SESSION_COLS))})
ON CONFLICT (id) DO UPDATE SET
    sleep_latency_seconds         = EXCLUDED.sleep_latency_seconds,
    continuity_score              = EXCLUDED.continuity_score,
    sleep_efficiency_pct          = EXCLUDED.sleep_efficiency_pct,
    light_sleep_seconds           = EXCLUDED.light_sleep_seconds,
    deep_sleep_seconds            = EXCLUDED.deep_sleep_seconds,
    rem_sleep_seconds             = EXCLUDED.rem_sleep_seconds,
    awake_seconds                 = EXCLUDED.awake_seconds,
    interruptions                 = EXCLUDED.interruptions,
    short_interruption_duration_seconds = EXCLUDED.short_interruption_duration_seconds,
    long_interruption_duration_seconds  = EXCLUDED.long_interruption_duration_seconds,
    unknown_sleep_seconds         = EXCLUDED.unknown_sleep_seconds,
    average_hr_bpm                = EXCLUDED.average_hr_bpm,
    min_hr_bpm                    = EXCLUDED.min_hr_bpm,
    average_ppi_ms                = EXCLUDED.average_ppi_ms,
    rmssd_ms                      = EXCLUDED.rmssd_ms,
    sdnn_ms                       = EXCLUDED.sdnn_ms,
    breathing_rate_bpm            = EXCLUDED.breathing_rate_bpm,
    snoring_seconds               = EXCLUDED.snoring_seconds,
    mean_skin_temperature_celsius = EXCLUDED.mean_skin_temperature_celsius,
    temperature_deviation_celsius = EXCLUDED.temperature_deviation_celsius
"""

_INTERVAL_INSERT = """
INSERT INTO sleep_stage_intervals
    (sleep_session_id, start_time, end_time, stage, duration_seconds)
VALUES (?, ?, ?, ?, ?)
"""


def _to_session_row(s: SleepSession) -> list:
    return [
        s.id, s.user_id, str(s.provider), s.start_time, s.end_time,
        s.duration_seconds, s.sleep_latency_seconds, s.continuity_score,
        s.sleep_efficiency_pct, s.light_sleep_seconds, s.deep_sleep_seconds,
        s.rem_sleep_seconds, s.awake_seconds, s.interruptions,
        s.short_interruption_duration_seconds, s.long_interruption_duration_seconds,
        s.unknown_sleep_seconds,
        s.average_hr_bpm, s.min_hr_bpm, s.average_ppi_ms, s.rmssd_ms,
        s.sdnn_ms, s.breathing_rate_bpm, s.snoring_seconds,
        s.mean_skin_temperature_celsius, s.temperature_deviation_celsius,
    ]


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _fetch_all(result: duckdb.DuckDBPyRelation) -> list[dict]:
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]


def _load_intervals(conn: duckdb.DuckDBPyConnection, session_id: str) -> list[SleepStageInterval]:
    result = conn.execute(
        "SELECT * FROM sleep_stage_intervals WHERE sleep_session_id = ? ORDER BY start_time",
        [session_id],
    )
    rows = _fetch_all(result)
    return [
        SleepStageInterval(
            start_time=_utc(r["start_time"]),  # type: ignore[arg-type]
            end_time=_utc(r["end_time"]),  # type: ignore[arg-type]
            stage=SleepStage(r["stage"]),
            duration_seconds=r["duration_seconds"],
        )
        for r in rows
    ]


def _from_row(row: dict, intervals: list[SleepStageInterval]) -> SleepSession:
    return SleepSession(
        id=row["id"],
        user_id=row["user_id"],
        provider=Provider(row["provider"]),
        start_time=_utc(row["start_time"]),  # type: ignore[arg-type]
        end_time=_utc(row["end_time"]),  # type: ignore[arg-type]
        duration_seconds=row["duration_seconds"],
        sleep_latency_seconds=row.get("sleep_latency_seconds"),
        continuity_score=row.get("continuity_score"),
        sleep_efficiency_pct=row.get("sleep_efficiency_pct"),
        light_sleep_seconds=row.get("light_sleep_seconds"),
        deep_sleep_seconds=row.get("deep_sleep_seconds"),
        rem_sleep_seconds=row.get("rem_sleep_seconds"),
        awake_seconds=row.get("awake_seconds"),
        interruptions=row.get("interruptions"),
        short_interruption_duration_seconds=row.get("short_interruption_duration_seconds"),
        long_interruption_duration_seconds=row.get("long_interruption_duration_seconds"),
        unknown_sleep_seconds=row.get("unknown_sleep_seconds"),
        average_hr_bpm=row.get("average_hr_bpm"),
        min_hr_bpm=row.get("min_hr_bpm"),
        average_ppi_ms=row.get("average_ppi_ms"),
        rmssd_ms=row.get("rmssd_ms"),
        sdnn_ms=row.get("sdnn_ms"),
        breathing_rate_bpm=row.get("breathing_rate_bpm"),
        snoring_seconds=row.get("snoring_seconds"),
        mean_skin_temperature_celsius=row.get("mean_skin_temperature_celsius"),
        temperature_deviation_celsius=row.get("temperature_deviation_celsius"),
        stage_intervals=intervals,
    )


class DuckDBSleepRepository:
    """SleepRepository backed by DuckDB.

    Stage intervals are replaced entirely on each upsert to avoid duplicates.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def upsert(self, session: SleepSession) -> None:
        self._conn.execute(_SESSION_UPSERT, _to_session_row(session))
        # Replace all intervals for this session
        self._conn.execute(
            "DELETE FROM sleep_stage_intervals WHERE sleep_session_id = ?",
            [session.id],
        )
        if session.stage_intervals:
            interval_rows = [
                [session.id, iv.start_time, iv.end_time, str(iv.stage), iv.duration_seconds]
                for iv in session.stage_intervals
            ]
            self._conn.executemany(_INTERVAL_INSERT, interval_rows)
        n = len(session.stage_intervals)
        logger.debug("Upserted sleep session %s with %d intervals", session.id, n)

    def upsert_batch(self, sessions: Sequence[SleepSession]) -> None:
        for session in sessions:
            self.upsert(session)

    def get(self, session_id: str) -> SleepSession | None:
        result = self._conn.execute(
            "SELECT * FROM sleep_sessions WHERE id = ?", [session_id]
        )
        rows = _fetch_all(result)
        if not rows:
            return None
        intervals = _load_intervals(self._conn, session_id)
        return _from_row(rows[0], intervals)

    def list_by_date_range(
        self, user_id: str, start: date, end: date
    ) -> list[SleepSession]:
        result = self._conn.execute(
            """
            SELECT * FROM sleep_sessions
            WHERE user_id = ? AND start_time::DATE BETWEEN ? AND ?
            ORDER BY start_time
            """,
            [user_id, start, end],
        )
        rows = _fetch_all(result)
        sessions = []
        for row in rows:
            intervals = _load_intervals(self._conn, row["id"])
            sessions.append(_from_row(row, intervals))
        return sessions

    def list_latest(self, user_id: str, n: int = 30) -> list[SleepSession]:
        result = self._conn.execute(
            """
            SELECT * FROM sleep_sessions
            WHERE user_id = ?
            ORDER BY start_time DESC
            LIMIT ?
            """,
            [user_id, n],
        )
        rows = _fetch_all(result)
        sessions = []
        for row in rows:
            intervals = _load_intervals(self._conn, row["id"])
            sessions.append(_from_row(row, intervals))
        return sessions

    def delete(self, session_id: str) -> None:
        self._conn.execute(
            "DELETE FROM sleep_stage_intervals WHERE sleep_session_id = ?",
            [session_id],
        )
        self._conn.execute(
            "DELETE FROM sleep_sessions WHERE id = ?", [session_id]
        )
