"""Polar Dashboard MCP Server.

Exposes a set of deterministic, typed tools that AI agents can call to query
physiological analytics stored in the local DuckDB database.

Entry point:
    mcp run src/polar_mcp/server.py

Or programmatically:
    from polar_mcp.server import mcp
    mcp.run()

Database path is resolved from the POLAR_DB_PATH environment variable,
falling back to the project-default ``data/polar.duckdb``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date, datetime

from mcp.server.fastmcp import Context, FastMCP

from polar_mcp.tools.hrv import query_hrv_baseline
from polar_mcp.tools.recovery import query_recovery_score
from polar_mcp.tools.sleep import query_sleep_score, query_sleep_trends
from polar_mcp.tools.strain import query_strain_score, query_training_load
from storage.duckdb.connection import DuckDBConnectionManager

_DEFAULT_DB_PATH = "data/polar.duckdb"

# Singleton — opened once at first session, reused across all subsequent sessions.
# FastMCP streamable-http calls the lifespan on every new client session, so without
# this guard each healthcheck poll would open a new DuckDB connection.
_manager: DuckDBConnectionManager | None = None


@asynccontextmanager
async def _lifespan(app: FastMCP) -> AsyncGenerator[dict, None]:  # type: ignore[type-arg]
    global _manager
    if _manager is None:
        db_path = os.environ.get("POLAR_DB_PATH", _DEFAULT_DB_PATH)
        _manager = DuckDBConnectionManager(db_path, read_only=True)
    yield {"conn": _manager.conn}


mcp = FastMCP(
    name="polar-dashboard",
    instructions=(
        "Provides physiological analytics from a Polar wearable device database. "
        "All tools return structured JSON with a 'metadata' field indicating data "
        "availability and confidence. Dates are ISO 8601 strings (YYYY-MM-DD)."
    ),
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8000")),
    stateless_http=os.environ.get("MCP_STATELESS_HTTP", "false").lower() == "true",
    lifespan=_lifespan,
)


# ---------------------------------------------------------------------------
# Sleep tools
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Get composite sleep quality score and architecture breakdown for a single night. "
        "Returns duration, efficiency, deep/REM/light/awake percentages, HRV, and a 7-night "
        "consistency score. All times in minutes; percentages 0-100."
    )
)
def get_sleep_score(user_id: str, record_date: str, ctx: Context) -> dict:  # type: ignore[type-arg]
    """
    Args:
        user_id:     Platform-agnostic user identifier.
        record_date: ISO date of the night to query (YYYY-MM-DD, wake date).
    """
    conn = ctx.request_context.lifespan_context["conn"]
    return query_sleep_score(conn, user_id, date.fromisoformat(record_date))


@mcp.tool(
    description=(
        "Get sleep quality trends over a date range. "
        "Returns per-night scores with summary averages. "
        "Use this for weekly/monthly reviews or trend detection."
    )
)
def get_sleep_trends(user_id: str, start_date: str, end_date: str, ctx: Context) -> dict:  # type: ignore[type-arg]
    """
    Args:
        user_id:    Platform-agnostic user identifier.
        start_date: Start of the date range (YYYY-MM-DD, inclusive).
        end_date:   End of the date range (YYYY-MM-DD, inclusive).
    """
    conn = ctx.request_context.lifespan_context["conn"]
    return query_sleep_trends(
        conn,
        user_id,
        date.fromisoformat(start_date),
        date.fromisoformat(end_date),
    )


# ---------------------------------------------------------------------------
# Strain tools
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Get daily training strain score and ACWR (Acute/Chronic Workload Ratio) "
        "for a specific date. ACWR 0.8-1.3 = sweet spot; >1.5 = elevated injury risk "
        "(Gabbett 2016). Strain score 0-100: 0-33 low, 34-66 moderate, 67-100 high."
    )
)
def get_strain_score(user_id: str, record_date: str, ctx: Context) -> dict:  # type: ignore[type-arg]
    """
    Args:
        user_id:     Platform-agnostic user identifier.
        record_date: ISO date to query (YYYY-MM-DD).
    """
    conn = ctx.request_context.lifespan_context["conn"]
    return query_strain_score(conn, user_id, date.fromisoformat(record_date))


@mcp.tool(
    description=(
        "Get training load time-series for a date range with peak and average summaries. "
        "Useful for load management, periodisation reviews, and overtraining detection."
    )
)
def get_training_load(user_id: str, start_date: str, end_date: str, ctx: Context) -> dict:  # type: ignore[type-arg]
    """
    Args:
        user_id:    Platform-agnostic user identifier.
        start_date: Start of the date range (YYYY-MM-DD, inclusive).
        end_date:   End of the date range (YYYY-MM-DD, inclusive).
    """
    conn = ctx.request_context.lifespan_context["conn"]
    return query_training_load(
        conn,
        user_id,
        date.fromisoformat(start_date),
        date.fromisoformat(end_date),
    )


# ---------------------------------------------------------------------------
# Recovery tool
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Get composite recovery/readiness score for a specific date with full contributor "
        "breakdown (HRV z-score, resting HR z-score, sleep quality, previous strain, "
        "nightly recharge, skin temperature). Score 0-100: 0-33 poor, 34-66 moderate, "
        "67-100 optimal. Missing contributors fall back to neutral (50)."
    )
)
def get_recovery_score(user_id: str, record_date: str, ctx: Context) -> dict:  # type: ignore[type-arg]
    """
    Args:
        user_id:     Platform-agnostic user identifier.
        record_date: ISO date to query (YYYY-MM-DD).
    """
    conn = ctx.request_context.lifespan_context["conn"]
    return query_recovery_score(conn, user_id, date.fromisoformat(record_date))


# ---------------------------------------------------------------------------
# HRV tool
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Get rolling HRV baseline statistics from overnight RMSSD data. "
        "Returns mean, std, and latest RMSSD alongside a current-vs-baseline percentage. "
        "Values >100% indicate above-baseline HRV (good recovery signal). "
        "Default window is 30 days; adjust for shorter or longer baselines."
    )
)
def get_hrv_baseline(
    user_id: str,
    ctx: Context,  # type: ignore[type-arg]
    end_date: str | None = None,
    window_days: int = 30,
) -> dict:
    """
    Args:
        user_id:     Platform-agnostic user identifier.
        end_date:    Last day of the window (YYYY-MM-DD). Defaults to today.
        window_days: Number of trailing days to include (default 30, max recommended 90).
    """
    conn = ctx.request_context.lifespan_context["conn"]
    resolved_end = date.fromisoformat(end_date) if end_date else datetime.now().date()
    return query_hrv_baseline(conn, user_id, resolved_end, window_days)


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
