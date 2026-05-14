"""MCP tool implementations for strain and training load queries."""

from __future__ import annotations

from datetime import date

import duckdb

from polar_mcp.schemas.common import NotFoundOutput, ToolMeta
from polar_mcp.schemas.strain import StrainScoreOutput, TrainingLoadOutput
from storage.repositories.metrics import DuckDBStrainMetricsRepository


def query_strain_score(
    conn: duckdb.DuckDBPyConnection,
    user_id: str,
    record_date: date,
) -> dict:
    """Return StrainScoreOutput for a single day, or NotFoundOutput."""
    repo = DuckDBStrainMetricsRepository(conn)
    metrics = repo.get(user_id, record_date)
    if metrics is None:
        return NotFoundOutput(
            message=f"No strain metrics for user '{user_id}' on {record_date}",
            metadata=ToolMeta(data_available=False, confidence=0.0),
        ).model_dump(mode="json")
    return StrainScoreOutput.from_domain(metrics).model_dump(mode="json")


def query_training_load(
    conn: duckdb.DuckDBPyConnection,
    user_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """Return TrainingLoadOutput for a date range."""
    repo = DuckDBStrainMetricsRepository(conn)
    records = repo.list_by_date_range(user_id, start_date, end_date)
    output = TrainingLoadOutput.from_domain(user_id, start_date, end_date, records)
    return output.model_dump(mode="json")
