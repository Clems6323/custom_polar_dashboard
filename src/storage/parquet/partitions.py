"""Parquet partition path helpers.

Partition layout:
    {base_dir}/{sample_type}/{user_id}/{YYYY-MM-DD}/data.parquet

This simple structure keeps date-range reads cheap (iterate known dates)
and is compatible with DuckDB's hive-partitioning scanner when needed.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path


def hr_partition(base_dir: Path, user_id: str, record_date: date) -> Path:
    return base_dir / "heart_rate" / user_id / record_date.isoformat()


def ppi_partition(base_dir: Path, user_id: str, record_date: date) -> Path:
    return base_dir / "ppi" / user_id / record_date.isoformat()


def temperature_partition(base_dir: Path, user_id: str, record_date: date) -> Path:
    return base_dir / "temperature" / user_id / record_date.isoformat()


def parquet_path(partition_dir: Path) -> Path:
    return partition_dir / "data.parquet"
