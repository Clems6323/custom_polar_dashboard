"""MCP tool implementation for HRV baseline queries."""

from __future__ import annotations

import math
from datetime import date, timedelta

import duckdb

from polar_mcp.schemas.common import ToolMeta
from polar_mcp.schemas.hrv import HRVBaselineOutput, HRVDataPoint
from storage.repositories.metrics import DuckDBRecoveryMetricsRepository


def query_hrv_baseline(
    conn: duckdb.DuckDBPyConnection,
    user_id: str,
    end_date: date,
    window_days: int = 30,
) -> dict:
    """Return HRVBaselineOutput covering ``window_days`` up to ``end_date``.

    Stats are derived from RecoveryMetrics records (which store overnight RMSSD
    and resting HR alongside the composite recovery score).
    """
    start_date = end_date - timedelta(days=window_days - 1)
    repo = DuckDBRecoveryMetricsRepository(conn)
    records = repo.list_by_date_range(user_id, start_date, end_date)

    data_points = [
        HRVDataPoint(
            record_date=r.record_date,
            rmssd_ms=r.rmssd_ms,
            resting_hr_bpm=r.resting_hr_bpm,
            recovery_score=r.recovery_score,
        )
        for r in records
    ]

    rmssd_vals = [r.rmssd_ms for r in records if r.rmssd_ms is not None]
    hr_vals = [r.resting_hr_bpm for r in records if r.resting_hr_bpm is not None]
    recovery_vals = [r.recovery_score for r in records]

    def _mean(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 2) if vals else None

    def _std(vals: list[float]) -> float | None:
        if len(vals) < 2:
            return None
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        return round(math.sqrt(variance), 2)

    mean_rmssd = _mean(rmssd_vals)
    latest_rmssd = rmssd_vals[-1] if rmssd_vals else None

    current_vs_baseline: float | None = None
    if mean_rmssd and latest_rmssd and mean_rmssd > 0:
        current_vs_baseline = round(latest_rmssd / mean_rmssd * 100.0, 1)

    missing = []
    if not rmssd_vals:
        missing.append("rmssd_ms")
    if not hr_vals:
        missing.append("resting_hr_bpm")
    confidence = len(records) / window_days if window_days > 0 else 0.0

    output = HRVBaselineOutput(
        user_id=user_id,
        window_days=window_days,
        start_date=start_date,
        end_date=end_date,
        mean_rmssd_ms=mean_rmssd,
        std_rmssd_ms=_std(rmssd_vals),
        latest_rmssd_ms=latest_rmssd,
        current_vs_baseline_pct=current_vs_baseline,
        mean_resting_hr_bpm=_mean(hr_vals),
        latest_resting_hr_bpm=hr_vals[-1] if hr_vals else None,
        mean_recovery_score=_mean(recovery_vals),
        data=data_points,
        metadata=ToolMeta(
            data_available=len(records) > 0,
            confidence=round(min(confidence, 1.0), 3),
            missing_signals=missing,
        ),
    )
    return output.model_dump(mode="json")
