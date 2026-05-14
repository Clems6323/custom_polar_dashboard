"""Tests for DuckDB migration runner."""

from __future__ import annotations

import duckdb
import pytest

from storage.duckdb.migrations import run_migrations


@pytest.fixture()
def fresh_db() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


class TestRunMigrations:
    def test_applies_all_migrations(self, fresh_db: duckdb.DuckDBPyConnection) -> None:
        run_migrations(fresh_db)
        tables = {
            r[0]
            for r in fresh_db.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        assert "sleep_sessions" in tables
        assert "activity_sessions" in tables
        assert "recovery_metrics" in tables
        assert "_schema_migrations" in tables

    def test_idempotent_double_run(self, fresh_db: duckdb.DuckDBPyConnection) -> None:
        # Second call must skip already-applied migrations (covers line 150-151)
        run_migrations(fresh_db)
        run_migrations(fresh_db)

        count = fresh_db.execute(
            "SELECT COUNT(*) FROM _schema_migrations"
        ).fetchone()[0]
        # Each migration recorded exactly once
        assert count == 6  # one row per migration

    def test_migration_ids_recorded(self, fresh_db: duckdb.DuckDBPyConnection) -> None:
        run_migrations(fresh_db)
        ids = {
            r[0]
            for r in fresh_db.execute("SELECT id FROM _schema_migrations").fetchall()
        }
        assert "001_initial_schema" in ids
        assert "006_fitness_load_contributor" in ids

    def test_rename_migration_runs_on_old_schema(
        self, fresh_db: duckdb.DuckDBPyConnection
    ) -> None:
        """m004 rename path: activity_sessions/strain_metrics have training_load column."""
        # Run all migrations on a fresh DB to get a complete schema
        run_migrations(fresh_db)

        # Simulate the old schema by adding training_load back alongside cardio_load
        # then marking m004 as not applied so it re-runs on the next call.
        fresh_db.execute(
            "ALTER TABLE activity_sessions ADD COLUMN IF NOT EXISTS training_load DOUBLE"
        )
        fresh_db.execute(
            "ALTER TABLE strain_metrics ADD COLUMN IF NOT EXISTS training_load DOUBLE"
        )
        fresh_db.execute(
            "DELETE FROM _schema_migrations WHERE id = '004_rename_training_load_to_cardio_load'"
        )

        # Re-run — m004 should detect both columns exist and drop cardio_load before rename
        run_migrations(fresh_db)

        cols_activity = {
            r[0]
            for r in fresh_db.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'activity_sessions'"
            ).fetchall()
        }
        assert "cardio_load" in cols_activity
        assert "training_load" not in cols_activity
