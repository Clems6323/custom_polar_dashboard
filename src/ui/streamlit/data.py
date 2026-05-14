"""Cached database access layer for the Streamlit dashboard.

Each @st.cache_data function opens a fresh read-only DuckDB connection,
executes its query, then closes the connection immediately. Query RESULTS
are cached for TTL seconds so subsequent rerenders return the cached data
without touching the file. This keeps the lock window to milliseconds per
query, allowing the sync script to acquire a write lock between requests.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import duckdb
import streamlit as st

from domain.models.recovery import RecoveryMetrics
from domain.models.sleep import SleepSession
from domain.models.sleep_metrics import SleepMetrics
from domain.models.strain import StrainMetrics
from storage.repositories.metrics import (
    DuckDBRecoveryMetricsRepository,
    DuckDBSleepMetricsRepository,
    DuckDBStrainMetricsRepository,
)
from storage.repositories.sleep import DuckDBSleepRepository

_DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "polar_dashboard.duckdb"


def _db_path() -> str:
    return os.environ.get("POLAR_DB_PATH", str(_DEFAULT_DB))


@contextmanager
def _ro_conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    conn = duckdb.connect(_db_path(), read_only=True)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# User identity
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600)
def resolve_user_id() -> str | None:
    """Resolve the active user ID.

    Priority:
    1. POLAR_USER_ID env var
    2. polar.json token file (polar_user_id field)
    3. First user_id found in sleep_metrics
    """
    if uid := os.environ.get("POLAR_USER_ID"):
        return uid

    _root = Path(__file__).resolve().parents[3]
    token_candidates = [
        _root / "data" / "tokens" / "polar_token.json",
        _root / "data" / "tokens" / "polar.json",
    ]
    for token_path in token_candidates:
        if token_path.exists():
            try:
                data = json.loads(token_path.read_text())
                if pid := data.get("polar_user_id"):
                    return str(pid)
            except Exception:
                pass

    # Fallback: first user in DB
    try:
        with _ro_conn() as conn:
            row = conn.execute("SELECT user_id FROM sleep_metrics LIMIT 1").fetchone()
            return row[0] if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------------


@st.cache_data(ttl=300)
def load_sleep_metrics(user_id: str, start: date, end: date) -> list[SleepMetrics]:
    with _ro_conn() as conn:
        return DuckDBSleepMetricsRepository(conn).list_by_date_range(user_id, start, end)


@st.cache_data(ttl=300)
def load_sleep_sessions(user_id: str, start: date, end: date) -> list[SleepSession]:
    with _ro_conn() as conn:
        return DuckDBSleepRepository(conn).list_by_date_range(user_id, start, end)


# ---------------------------------------------------------------------------
# Strain
# ---------------------------------------------------------------------------


@st.cache_data(ttl=300)
def load_strain_metrics(user_id: str, start: date, end: date) -> list[StrainMetrics]:
    with _ro_conn() as conn:
        return DuckDBStrainMetricsRepository(conn).list_by_date_range(user_id, start, end)


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


@st.cache_data(ttl=300)
def load_recovery_metrics(user_id: str, start: date, end: date) -> list[RecoveryMetrics]:
    with _ro_conn() as conn:
        return DuckDBRecoveryMetricsRepository(conn).list_by_date_range(user_id, start, end)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def date_range(days_back: int = 30) -> tuple[date, date]:
    """Return (start, end) = (today - days_back, today)."""
    today = date.today()
    return today - timedelta(days=days_back), today


def latest_sleep(user_id: str) -> SleepMetrics | None:
    start, end = date_range(60)
    rows = load_sleep_metrics(user_id, start, end)
    return rows[-1] if rows else None


def latest_recovery(user_id: str) -> RecoveryMetrics | None:
    start, end = date_range(60)
    rows = load_recovery_metrics(user_id, start, end)
    return rows[-1] if rows else None


def latest_strain(user_id: str) -> StrainMetrics | None:
    start, end = date_range(60)
    rows = load_strain_metrics(user_id, start, end)
    return rows[-1] if rows else None
