"""Read physiological time-series samples from Parquet files.

Date-range reads iterate over daily partition directories.  Missing partitions
(days with no data) are silently skipped so callers don't need to handle gaps.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, timedelta
from pathlib import Path

import polars as pl

from domain.models import HeartRateSample, PPISample, TemperatureSample
from domain.models.enums import Provider
from storage.parquet.partitions import (
    hr_partition,
    parquet_path,
    ppi_partition,
    temperature_partition,
)

logger = logging.getLogger(__name__)


def _date_range(start: date, end: date) -> list[date]:
    """Return every date in [start, end] inclusive."""
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _read_parquet_or_none(path: Path) -> pl.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pl.read_parquet(path)
    except Exception:
        logger.warning("Failed to read Parquet: %s", path, exc_info=True)
        return None


def read_hr_samples(
    user_id: str,
    start: date,
    end: date,
    base_dir: Path,
    *,
    valid_only: bool = False,
) -> list[HeartRateSample]:
    """Return HeartRateSamples for user_id in [start, end]."""
    frames: list[pl.DataFrame] = []
    for d in _date_range(start, end):
        df = _read_parquet_or_none(parquet_path(hr_partition(base_dir, user_id, d)))
        if df is not None:
            frames.append(df)

    if not frames:
        return []

    combined = pl.concat(frames).filter(pl.col("user_id") == user_id)
    samples = []
    for row in combined.iter_rows(named=True):
        ts = row["timestamp"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        samples.append(
            HeartRateSample(
                session_id=row.get("session_id"),
                user_id=row["user_id"],
                timestamp=ts,
                provider=Provider(row["provider"]),
                hr_bpm=float(row["hr_bpm"]),
                confidence=row.get("confidence"),
            )
        )
    return samples


def read_ppi_samples(
    user_id: str,
    start: date,
    end: date,
    base_dir: Path,
    *,
    valid_only: bool = True,
) -> list[PPISample]:
    """Return PPISamples for user_id in [start, end].

    Args:
        valid_only: When True (default), exclude samples with is_valid=False.
    """
    frames: list[pl.DataFrame] = []
    for d in _date_range(start, end):
        df = _read_parquet_or_none(parquet_path(ppi_partition(base_dir, user_id, d)))
        if df is not None:
            frames.append(df)

    if not frames:
        return []

    combined = pl.concat(frames).filter(pl.col("user_id") == user_id)
    if valid_only:
        combined = combined.filter(pl.col("is_valid"))

    samples = []
    for row in combined.iter_rows(named=True):
        ts = row["timestamp"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        samples.append(
            PPISample(
                session_id=row.get("session_id"),
                user_id=row["user_id"],
                timestamp=ts,
                provider=Provider(row["provider"]),
                ppi_ms=int(row["ppi_ms"]),
                error_estimate_ms=row.get("error_estimate_ms"),
                hr_bpm=row.get("hr_bpm"),
                is_valid=bool(row.get("is_valid", True)),
            )
        )
    return samples


def read_temperature_samples(
    user_id: str,
    start: date,
    end: date,
    base_dir: Path,
) -> list[TemperatureSample]:
    """Return TemperatureSamples for user_id in [start, end]."""
    frames: list[pl.DataFrame] = []
    for d in _date_range(start, end):
        df = _read_parquet_or_none(
            parquet_path(temperature_partition(base_dir, user_id, d))
        )
        if df is not None:
            frames.append(df)

    if not frames:
        return []

    combined = pl.concat(frames).filter(pl.col("user_id") == user_id)
    samples = []
    for row in combined.iter_rows(named=True):
        ts = row["timestamp"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        samples.append(
            TemperatureSample(
                session_id=row.get("session_id"),
                user_id=row["user_id"],
                timestamp=ts,
                provider=Provider(row["provider"]),
                skin_temperature_celsius=float(row["skin_temperature_celsius"]),
                ambient_temperature_celsius=row.get("ambient_temperature_celsius"),
            )
        )
    return samples
