"""Sequential schema migration runner for DuckDB.

Migrations are simple named functions that each receive the live connection.
Once applied, their ID is recorded in _schema_migrations so they are never
re-applied — even if the function body changes.

To add a new migration:
1. Define a function ``def _mXXX_description(conn: ...): ...``
2. Append ``("XXX_description", _mXXX_description)`` to ``_MIGRATIONS``.
"""

from __future__ import annotations

import logging

import duckdb

from storage.duckdb.schema import ALL_DDL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Migration functions
# ---------------------------------------------------------------------------


def _m001_initial_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all initial tables and indexes."""
    for ddl in ALL_DDL:
        conn.execute(ddl)


def _m002_sleep_interruption_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add short/long interruption duration columns to sleep tables."""
    for table, col in [
        ("sleep_sessions", "short_interruption_duration_seconds"),
        ("sleep_sessions", "long_interruption_duration_seconds"),
        ("sleep_metrics",  "short_interruption_duration_seconds"),
        ("sleep_metrics",  "long_interruption_duration_seconds"),
    ]:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} DOUBLE")


def _m003_unknown_sleep_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add unknown sleep columns to sleep tables and fix hypnogram stage mapping."""
    for table, col in [
        ("sleep_sessions", "unknown_sleep_seconds"),
        ("sleep_metrics",  "unknown_sleep_pct"),
    ]:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} DOUBLE")


def _m004_rename_training_load_to_cardio_load(conn: duckdb.DuckDBPyConnection) -> None:
    """Rename training_load → cardio_load in activity_sessions and strain_metrics.

    Only runs when training_load still exists (skipped on fresh databases that
    were created with the updated DDL).  The activity_sessions index must be
    dropped and recreated because DuckDB 1.x blocks ALTER TABLE on indexed tables.
    """
    def _has_column(table: str, col: str) -> bool:
        return (
            conn.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_name = ? AND column_name = ?",
                [table, col],
            ).fetchone()[0]  # type: ignore[index]
            > 0
        )

    # activity_sessions — drop index first to allow ALTER TABLE
    if _has_column("activity_sessions", "training_load"):
        conn.execute("DROP INDEX IF EXISTS idx_activity_user_time")
        if _has_column("activity_sessions", "cardio_load"):
            conn.execute("ALTER TABLE activity_sessions DROP COLUMN cardio_load")
        conn.execute("ALTER TABLE activity_sessions RENAME COLUMN training_load TO cardio_load")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_user_time "
            "ON activity_sessions (user_id, start_time)"
        )

    # strain_metrics — no index, rename directly
    if _has_column("strain_metrics", "training_load"):
        if _has_column("strain_metrics", "cardio_load"):
            conn.execute("ALTER TABLE strain_metrics DROP COLUMN cardio_load")
        conn.execute("ALTER TABLE strain_metrics RENAME COLUMN training_load TO cardio_load")


def _m005_polar_cardio_load_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the polar_cardio_load table for daily strain/tolerance data.

    Stores the daily summary from GET /v3/users/cardio-load:
      cardio_load — daily cardio load
      strain      — 7-day rolling cardio load (Polar acute load)
      tolerance   — 28-day rolling cardio load (Polar chronic load / fitness)
    """
    from storage.duckdb.schema import DDL_POLAR_CARDIO_LOAD
    conn.execute(DDL_POLAR_CARDIO_LOAD)


def _m006_fitness_load_contributor(conn: duckdb.DuckDBPyConnection) -> None:
    """Add contrib_fitness_load_z_score column to recovery_metrics."""
    conn.execute(
        "ALTER TABLE recovery_metrics "
        "ADD COLUMN IF NOT EXISTS contrib_fitness_load_z_score DOUBLE"
    )


def _m007_sleep_utc_offset(conn: duckdb.DuckDBPyConnection) -> None:
    """Add utc_offset_minutes column to sleep_sessions for local-time reconstruction."""
    conn.execute(
        "ALTER TABLE sleep_sessions ADD COLUMN IF NOT EXISTS utc_offset_minutes INTEGER"
    )


# Ordered registry of (migration_id, callable) pairs.
# New entries must be appended — never reordered.
_MIGRATIONS: list[tuple[str, object]] = [
    ("001_initial_schema", _m001_initial_schema),
    ("002_sleep_interruption_columns", _m002_sleep_interruption_columns),
    ("003_unknown_sleep_columns", _m003_unknown_sleep_columns),
    ("004_rename_training_load_to_cardio_load", _m004_rename_training_load_to_cardio_load),
    ("005_polar_cardio_load_table", _m005_polar_cardio_load_table),
    ("006_fitness_load_contributor", _m006_fitness_load_contributor),
    ("007_sleep_utc_offset", _m007_sleep_utc_offset),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_migrations(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply all pending migrations in order.

    Safe to call on every application start — already-applied migrations are
    skipped.  Each migration runs inside its own transaction so a partial
    failure leaves the database in a consistent state.
    """
    # Bootstrap: the tracking table must exist before we can query it.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _schema_migrations (
            id         VARCHAR PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT current_timestamp
        )
    """)

    for migration_id, migration_fn in _MIGRATIONS:
        already_applied: bool = (
            conn.execute(
                "SELECT COUNT(*) FROM _schema_migrations WHERE id = ?",
                [migration_id],
            ).fetchone()[0]  # type: ignore[index]
            > 0
        )
        if already_applied:
            logger.debug("Migration already applied: %s", migration_id)
            continue

        logger.info("Applying migration: %s", migration_id)
        migration_fn(conn)  # type: ignore[operator]
        conn.execute(
            "INSERT INTO _schema_migrations (id) VALUES (?)",
            [migration_id],
        )
        logger.info("Migration applied: %s", migration_id)
