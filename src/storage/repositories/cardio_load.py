"""DuckDB repository for Polar daily cardio load records."""

from __future__ import annotations

import logging
from datetime import date

import duckdb

logger = logging.getLogger(__name__)


class DuckDBCardioLoadRepository:
    """Stores and retrieves daily cardio load records from polar_cardio_load."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def upsert(
        self,
        user_id: str,
        record_date: date,
        cardio_load: float | None,
        strain: float | None,
        tolerance: float | None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO polar_cardio_load (user_id, date, cardio_load, strain, tolerance)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (user_id, date) DO UPDATE SET
                cardio_load = EXCLUDED.cardio_load,
                strain      = EXCLUDED.strain,
                tolerance   = EXCLUDED.tolerance,
                updated_at  = now()
            """,
            [user_id, record_date, cardio_load, strain, tolerance],
        )
        logger.debug("Upserted cardio load for %s on %s", user_id, record_date)

    def get(self, user_id: str, record_date: date) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM polar_cardio_load WHERE user_id = ? AND date = ?",
            [user_id, record_date],
        ).fetchone()
        if row is None:
            return None
        cols = ["user_id", "date", "cardio_load", "strain", "tolerance", "updated_at"]
        return dict(zip(cols, row, strict=False))

    def list_by_date_range(
        self, user_id: str, start: date, end: date
    ) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT user_id, date, cardio_load, strain, tolerance
            FROM polar_cardio_load
            WHERE user_id = ? AND date BETWEEN ? AND ?
            ORDER BY date
            """,
            [user_id, start, end],
        ).fetchall()
        return [
            {"user_id": r[0], "date": r[1], "cardio_load": r[2], "strain": r[3], "tolerance": r[4]}
            for r in rows
        ]
