"""MCP tool implementation for recovery/readiness queries."""

from __future__ import annotations

from datetime import date

import duckdb

from polar_mcp.schemas.common import NotFoundOutput, ToolMeta
from polar_mcp.schemas.recovery import RecoveryScoreOutput
from storage.repositories.metrics import DuckDBRecoveryMetricsRepository


def query_recovery_score(
    conn: duckdb.DuckDBPyConnection,
    user_id: str,
    record_date: date,
) -> dict:
    """Return RecoveryScoreOutput for a single day, or NotFoundOutput."""
    repo = DuckDBRecoveryMetricsRepository(conn)
    metrics = repo.get(user_id, record_date)
    if metrics is None:
        return NotFoundOutput(
            message=f"No recovery metrics for user '{user_id}' on {record_date}",
            metadata=ToolMeta(data_available=False, confidence=0.0),
        ).model_dump(mode="json")
    return RecoveryScoreOutput.from_domain(metrics).model_dump(mode="json")
