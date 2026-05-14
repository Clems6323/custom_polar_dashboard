"""MCP tool implementations for sleep quality queries.

``query_*`` functions are pure query functions that accept a DuckDB connection.
They can be called directly in tests without a running MCP server.
The ``@mcp.tool()`` functions in server.py are thin wrappers that extract the
connection from the lifespan context.
"""

from __future__ import annotations

from datetime import date

import duckdb

from polar_mcp.schemas.common import NotFoundOutput, ToolMeta
from polar_mcp.schemas.sleep import SleepScoreOutput, SleepTrendsOutput
from storage.repositories.metrics import DuckDBSleepMetricsRepository


def query_sleep_score(
    conn: duckdb.DuckDBPyConnection,
    user_id: str,
    record_date: date,
) -> dict:
    """Return SleepScoreOutput for a single night, or NotFoundOutput."""
    repo = DuckDBSleepMetricsRepository(conn)
    metrics = repo.get(user_id, record_date)
    if metrics is None:
        return NotFoundOutput(
            message=f"No sleep metrics for user '{user_id}' on {record_date}",
            metadata=ToolMeta(data_available=False, confidence=0.0),
        ).model_dump(mode="json")
    return SleepScoreOutput.from_domain(metrics).model_dump(mode="json")


def query_sleep_trends(
    conn: duckdb.DuckDBPyConnection,
    user_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """Return SleepTrendsOutput for a date range."""
    repo = DuckDBSleepMetricsRepository(conn)
    records = repo.list_by_date_range(user_id, start_date, end_date)
    output = SleepTrendsOutput.from_domain(user_id, start_date, end_date, records)
    return output.model_dump(mode="json")
