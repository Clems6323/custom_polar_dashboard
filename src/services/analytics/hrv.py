"""HRV metrics: RMSSD, SDNN, rolling baselines, z-score deviation.

All functions operate on plain Python sequences — no I/O, fully deterministic.

References:
  - Task Force of ESC/NASPE (1996) — HRV standards of measurement
  - Gabbett (2016) — ACWR and injury risk (rolling load context)
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def rmssd(ppi_ms: Sequence[float]) -> float:
    """Root mean square of successive PPI differences (milliseconds).

    Primary overnight HRV metric; higher values indicate better
    parasympathetic tone and autonomic recovery.

    Raises ``ValueError`` when fewer than 2 samples are provided.
    """
    if len(ppi_ms) < 2:
        raise ValueError(f"RMSSD requires at least 2 PPI samples; got {len(ppi_ms)}")
    diffs_sq = [(ppi_ms[i + 1] - ppi_ms[i]) ** 2 for i in range(len(ppi_ms) - 1)]
    return math.sqrt(sum(diffs_sq) / len(diffs_sq))


def sdnn(ppi_ms: Sequence[float]) -> float:
    """Standard deviation of all PPI intervals (milliseconds).

    Captures both short and long-term heart rate variability; used as a
    secondary HRV metric alongside RMSSD.

    Raises ``ValueError`` when fewer than 2 samples are provided.
    """
    if len(ppi_ms) < 2:
        raise ValueError(f"SDNN requires at least 2 PPI samples; got {len(ppi_ms)}")
    n = len(ppi_ms)
    mean = sum(ppi_ms) / n
    return math.sqrt(sum((x - mean) ** 2 for x in ppi_ms) / n)


def rolling_mean(
    values: Sequence[float | None],
    window: int,
    *,
    min_periods: int = 1,
) -> list[float | None]:
    """Compute a trailing rolling mean over ``window`` observations.

    ``None`` entries in ``values`` are skipped when computing the window
    average.  Returns ``None`` for positions where fewer than ``min_periods``
    non-null values exist in the window.

    Args:
        values:      Time-ordered sequence (oldest first).
        window:      Number of trailing observations to include.
        min_periods: Minimum non-null values required to produce a result.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if min_periods < 1:
        raise ValueError("min_periods must be >= 1")

    result: list[float | None] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        window_vals = [v for v in values[start : i + 1] if v is not None]
        if len(window_vals) >= min_periods:
            result.append(sum(window_vals) / len(window_vals))
        else:
            result.append(None)
    return result


def rolling_std(
    values: Sequence[float | None],
    window: int,
    *,
    min_periods: int = 2,
) -> list[float | None]:
    """Compute a trailing rolling population standard deviation.

    Returns ``None`` where fewer than ``min_periods`` non-null values exist.
    """
    if window < 2:
        raise ValueError("window must be >= 2")

    result: list[float | None] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        window_vals = [v for v in values[start : i + 1] if v is not None]
        if len(window_vals) < min_periods:
            result.append(None)
            continue
        mean = sum(window_vals) / len(window_vals)
        variance = sum((x - mean) ** 2 for x in window_vals) / len(window_vals)
        result.append(math.sqrt(variance))
    return result


def z_score(value: float, baseline_mean: float, baseline_std: float) -> float | None:
    """Z-score of ``value`` relative to a personal rolling baseline.

    Returns ``None`` when ``baseline_std`` is too small to produce a
    meaningful result (avoids division noise for very stable signals).

    A positive z-score means the value is above the baseline:
      - HRV: positive = more recovered than usual (good)
      - Resting HR: positive = elevated (bad) — callers must interpret direction
    """
    if baseline_std < 0.5:
        return None
    return (value - baseline_mean) / baseline_std
