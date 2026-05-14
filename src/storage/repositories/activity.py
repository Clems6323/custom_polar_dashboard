"""DuckDB implementation of ActivityRepository."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime

import duckdb

from domain.models import ActivitySession
from domain.models.enums import Provider, SportType

logger = logging.getLogger(__name__)

_COLUMNS = (
    "id", "user_id", "provider", "start_time", "end_time", "duration_seconds",
    "sport_type", "sport_label", "average_hr_bpm", "max_hr_bpm",
    "hr_zone_distribution", "cardio_load", "muscle_load",
    "perceived_exertion", "calories_kcal", "distance_meters",
    "average_pace_sec_per_km", "average_power_watts",
)

_UPSERT_SQL = f"""
INSERT INTO activity_sessions ({', '.join(_COLUMNS)})
VALUES ({', '.join('?' * len(_COLUMNS))})
ON CONFLICT (id) DO UPDATE SET
    average_hr_bpm          = EXCLUDED.average_hr_bpm,
    max_hr_bpm              = EXCLUDED.max_hr_bpm,
    hr_zone_distribution    = EXCLUDED.hr_zone_distribution,
    cardio_load             = EXCLUDED.cardio_load,
    muscle_load             = EXCLUDED.muscle_load,
    perceived_exertion      = EXCLUDED.perceived_exertion,
    calories_kcal           = EXCLUDED.calories_kcal,
    distance_meters         = EXCLUDED.distance_meters,
    average_pace_sec_per_km = EXCLUDED.average_pace_sec_per_km,
    average_power_watts     = EXCLUDED.average_power_watts
"""


def _to_row(s: ActivitySession) -> tuple:
    return (
        s.id,
        s.user_id,
        str(s.provider),
        s.start_time,
        s.end_time,
        s.duration_seconds,
        str(s.sport_type),
        s.sport_label,
        s.average_hr_bpm,
        s.max_hr_bpm,
        json.dumps(s.hr_zone_distribution) if s.hr_zone_distribution else None,
        s.cardio_load,
        s.muscle_load,
        s.perceived_exertion,
        s.calories_kcal,
        s.distance_meters,
        s.average_pace_sec_per_km,
        s.average_power_watts,
    )


def _from_row(row: dict) -> ActivitySession:
    """Reconstruct an ActivitySession from a DuckDB result dict."""
    return ActivitySession(
        id=row["id"],
        user_id=row["user_id"],
        provider=Provider(row["provider"]),
        start_time=_utc(row["start_time"]),
        end_time=_utc(row["end_time"]),
        duration_seconds=row["duration_seconds"],
        sport_type=SportType(row["sport_type"]),
        sport_label=row.get("sport_label"),
        average_hr_bpm=row.get("average_hr_bpm"),
        max_hr_bpm=row.get("max_hr_bpm"),
        hr_zone_distribution=(
            json.loads(row["hr_zone_distribution"])
            if row.get("hr_zone_distribution")
            else None
        ),
        cardio_load=row.get("cardio_load"),
        muscle_load=row.get("muscle_load"),
        perceived_exertion=row.get("perceived_exertion"),
        calories_kcal=row.get("calories_kcal"),
        distance_meters=row.get("distance_meters"),
        average_pace_sec_per_km=row.get("average_pace_sec_per_km"),
        average_power_watts=row.get("average_power_watts"),
    )


def _utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is UTC-aware (DuckDB may return naive datetimes)."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _fetch_all(result: duckdb.DuckDBPyRelation) -> list[dict]:
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]


class DuckDBActivityRepository:
    """ActivityRepository backed by DuckDB."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def upsert(self, session: ActivitySession) -> None:
        self._conn.execute(_UPSERT_SQL, list(_to_row(session)))
        logger.debug("Upserted activity session %s", session.id)

    def upsert_batch(self, sessions: Sequence[ActivitySession]) -> None:
        if not sessions:
            return
        rows = [list(_to_row(s)) for s in sessions]
        self._conn.executemany(_UPSERT_SQL, rows)
        logger.debug("Upserted %d activity sessions", len(sessions))

    def get(self, session_id: str) -> ActivitySession | None:
        result = self._conn.execute(
            "SELECT * FROM activity_sessions WHERE id = ?", [session_id]
        )
        rows = _fetch_all(result)
        return _from_row(rows[0]) if rows else None

    def list_by_date_range(
        self, user_id: str, start: date, end: date
    ) -> list[ActivitySession]:
        result = self._conn.execute(
            """
            SELECT * FROM activity_sessions
            WHERE user_id = ? AND start_time::DATE BETWEEN ? AND ?
            ORDER BY start_time
            """,
            [user_id, start, end],
        )
        return [_from_row(r) for r in _fetch_all(result)]

    def list_latest(self, user_id: str, n: int = 30) -> list[ActivitySession]:
        result = self._conn.execute(
            """
            SELECT * FROM activity_sessions
            WHERE user_id = ?
            ORDER BY start_time DESC
            LIMIT ?
            """,
            [user_id, n],
        )
        return [_from_row(r) for r in _fetch_all(result)]

    def delete(self, session_id: str) -> None:
        self._conn.execute(
            "DELETE FROM activity_sessions WHERE id = ?", [session_id]
        )
