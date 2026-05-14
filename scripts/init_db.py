"""Initialise the DuckDB database by running all pending migrations.

Run once on first setup, or after pulling a new version that adds migrations:

    uv run python scripts/init_db.py
    # or:
    make init-db
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ and project root are importable when invoked from the repo root
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

import duckdb

from configs.settings import get_settings
from storage.duckdb.migrations import run_migrations
from utils.logging import configure_logging

configure_logging()

settings = get_settings()
db_path = settings.storage.duckdb_path

print(f"Database : {db_path}")
conn = duckdb.connect(str(db_path))
run_migrations(conn)
conn.close()

print("Database initialised successfully.")
