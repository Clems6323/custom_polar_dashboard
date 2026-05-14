"""Shared storage-test fixtures.

``db_conn`` provides an in-memory DuckDB connection with the full schema
applied.  Each test that uses it gets a fresh connection because the fixture
scope is 'function' — no state bleeds between tests.
"""

from __future__ import annotations

import duckdb
import pytest

from storage.duckdb.migrations import run_migrations


@pytest.fixture()
def db_conn() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB connection with migrations applied."""
    conn = duckdb.connect(":memory:")
    run_migrations(conn)
    yield conn
    conn.close()
