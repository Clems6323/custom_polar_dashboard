"""MCP output schemas for HRV baseline tools."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from polar_mcp.schemas.common import ToolMeta


class HRVDataPoint(BaseModel):
    """Single-day HRV data point within a baseline response."""

    record_date: date
    rmssd_ms: float | None = None
    resting_hr_bpm: float | None = None
    recovery_score: float | None = None


class HRVBaselineOutput(BaseModel):
    """Rolling HRV baseline statistics for a user over a given window.

    The baseline is derived from RecoveryMetrics records (which store overnight
    RMSSD and resting HR alongside their 30-day rolling baselines computed at
    score time).  Callers can use ``current_vs_baseline_pct`` to detect acute
    departures from normal.
    """

    user_id: str
    window_days: int = Field(description="Number of trailing days included in this response")
    start_date: date
    end_date: date

    mean_rmssd_ms: float | None = Field(
        default=None,
        description="Mean overnight RMSSD over the window in milliseconds",
    )
    std_rmssd_ms: float | None = Field(
        default=None,
        description="Standard deviation of overnight RMSSD over the window",
    )
    latest_rmssd_ms: float | None = Field(
        default=None,
        description="Most recent overnight RMSSD value in the window",
    )
    current_vs_baseline_pct: float | None = Field(
        default=None,
        description=(
            "Latest RMSSD as a percentage of the window mean "
            "(> 100 = above baseline; < 100 = below baseline)"
        ),
    )

    mean_resting_hr_bpm: float | None = Field(
        default=None,
        description="Mean resting heart rate over the window in BPM",
    )
    latest_resting_hr_bpm: float | None = Field(
        default=None,
        description="Most recent resting heart rate in BPM",
    )

    mean_recovery_score: float | None = Field(
        default=None,
        description="Mean composite recovery score over the window (0-100)",
    )

    data: list[HRVDataPoint] = Field(
        default_factory=list,
        description="Per-day data points, oldest first",
    )

    metadata: ToolMeta
