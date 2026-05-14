"""DuckDB connection lifecycle management.

One connection per process is the correct DuckDB usage pattern.
Tests pass ':memory:' to get a per-test isolated database.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)


class DuckDBConnectionManager:
    """Holds a single DuckDB connection for the application.

    Usage::

        manager = DuckDBConnectionManager("data/polar.duckdb")
        conn = manager.conn          # opens lazily on first access
        manager.close()              # or use as context manager

        with DuckDBConnectionManager(":memory:") as manager:
            manager.conn.execute("SELECT 1")
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._path = str(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Return the live connection, opening it on first access."""
        if self._conn is None:
            logger.info("Opening DuckDB: %s", self._path)
            self._conn = duckdb.connect(self._path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.debug("DuckDB connection closed: %s", self._path)

    def __enter__(self) -> DuckDBConnectionManager:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
