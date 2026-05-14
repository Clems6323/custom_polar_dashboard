"""Write physiological time-series samples to Parquet files.

Strategy: one Parquet file per (sample_type, user_id, date).  When a file
already exists for that partition, the new samples are merged and de-duplicated
by timestamp to maintain idempotent ingest.

Polars is used for all DataFrame operations (vectorised, no GIL issues).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from pathlib import Path

import polars as pl

from domain.models import HeartRateSample, PPISample, TemperatureSample
from storage.parquet.partitions import (
    hr_partition,
    parquet_path,
    ppi_partition,
    temperature_partition,
)

logger = logging.getLogger(__name__)


def _group_by_date(
    samples: list, date_fn: object  # callable: sample -> date
) -> dict[date, list]:
    groups: dict[date, list] = defaultdict(list)
    for s in samples:
        groups[date_fn(s)].append(s)  # type: ignore[operator]
    return groups


def _merge_and_write(df_new: pl.DataFrame, path: Path, dedup_cols: list[str]) -> None:
    """Merge df_new with existing Parquet at path, de-duplicate, and save."""
    if path.exists():
        df_existing = pl.read_parquet(path)
        df_merged = pl.concat([df_existing, df_new])
    else:
        df_merged = df_new

    df_final = df_merged.unique(subset=dedup_cols, keep="last")
    path.parent.mkdir(parents=True, exist_ok=True)
    df_final.write_parquet(path)
    logger.debug("Wrote %d rows to %s", len(df_final), path)


def write_hr_samples(samples: list[HeartRateSample], base_dir: Path) -> None:
    """Persist HeartRateSamples, partitioned by user and date."""
    if not samples:
        return

    groups = _group_by_date(samples, lambda s: s.timestamp.date())
    for record_date, day_samples in groups.items():
        user_id = day_samples[0].user_id
        partition = hr_partition(base_dir, user_id, record_date)

        df = pl.DataFrame(
            [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "timestamp": s.timestamp,
                    "provider": str(s.provider),
                    "hr_bpm": s.hr_bpm,
                    "confidence": s.confidence,
                }
                for s in day_samples
            ]
        )
        _merge_and_write(df, parquet_path(partition), dedup_cols=["timestamp", "user_id"])


def write_ppi_samples(samples: list[PPISample], base_dir: Path) -> None:
    """Persist PPISamples, partitioned by user and date."""
    if not samples:
        return

    groups = _group_by_date(samples, lambda s: s.timestamp.date())
    for record_date, day_samples in groups.items():
        user_id = day_samples[0].user_id
        partition = ppi_partition(base_dir, user_id, record_date)

        df = pl.DataFrame(
            [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "timestamp": s.timestamp,
                    "provider": str(s.provider),
                    "ppi_ms": s.ppi_ms,
                    "error_estimate_ms": s.error_estimate_ms,
                    "hr_bpm": s.hr_bpm,
                    "is_valid": s.is_valid,
                }
                for s in day_samples
            ]
        )
        _merge_and_write(df, parquet_path(partition), dedup_cols=["timestamp", "user_id"])


def write_temperature_samples(samples: list[TemperatureSample], base_dir: Path) -> None:
    """Persist TemperatureSamples, partitioned by user and date."""
    if not samples:
        return

    groups = _group_by_date(samples, lambda s: s.timestamp.date())
    for record_date, day_samples in groups.items():
        user_id = day_samples[0].user_id
        partition = temperature_partition(base_dir, user_id, record_date)

        df = pl.DataFrame(
            [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "timestamp": s.timestamp,
                    "provider": str(s.provider),
                    "skin_temperature_celsius": s.skin_temperature_celsius,
                    "ambient_temperature_celsius": s.ambient_temperature_celsius,
                }
                for s in day_samples
            ]
        )
        _merge_and_write(df, parquet_path(partition), dedup_cols=["timestamp", "user_id"])
