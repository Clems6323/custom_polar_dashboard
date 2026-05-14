"""Tests for Parquet time-series writer and reader.

Uses pytest's tmp_path fixture for isolated, auto-cleaned file I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from domain.models import HeartRateSample, PPISample, TemperatureSample
from domain.models.enums import Provider
from storage.parquet.reader import read_hr_samples, read_ppi_samples, read_temperature_samples
from storage.parquet.writer import write_hr_samples, write_ppi_samples, write_temperature_samples

_UID = "user-001"
_PROVIDER = Provider.POLAR
_DATE = datetime(2024, 5, 10, 8, 0, 0, tzinfo=UTC)


def _hr(offset_minutes: int = 0, **kw: object) -> HeartRateSample:
    return HeartRateSample(
        user_id=_UID,
        provider=_PROVIDER,
        timestamp=datetime(2024, 5, 10, 8, offset_minutes, 0, tzinfo=UTC),
        hr_bpm=kw.get("hr_bpm", 65.0),  # type: ignore[arg-type]
        confidence=kw.get("confidence"),  # type: ignore[arg-type]
    )


def _ppi(offset_minutes: int = 0, **kw: object) -> PPISample:
    return PPISample(
        user_id=_UID,
        provider=_PROVIDER,
        timestamp=datetime(2024, 5, 10, 8, offset_minutes, 0, tzinfo=UTC),
        ppi_ms=kw.get("ppi_ms", 900),  # type: ignore[arg-type]
        is_valid=kw.get("is_valid", True),  # type: ignore[arg-type]
    )


def _temp(offset_minutes: int = 0) -> TemperatureSample:
    return TemperatureSample(
        user_id=_UID,
        provider=_PROVIDER,
        timestamp=datetime(2024, 5, 10, 8, offset_minutes, 0, tzinfo=UTC),
        skin_temperature_celsius=34.2,
    )


# ---------------------------------------------------------------------------
# HeartRateSample round-trip
# ---------------------------------------------------------------------------


class TestHRParquet:
    def test_write_and_read_single_day(self, tmp_path: Path) -> None:
        samples = [_hr(i, hr_bpm=60.0 + i) for i in range(5)]
        write_hr_samples(samples, tmp_path)

        date = _DATE.date()
        result = read_hr_samples(_UID, date, date, tmp_path)
        assert len(result) == 5
        hr_values = {s.hr_bpm for s in result}
        assert hr_values == {60.0, 61.0, 62.0, 63.0, 64.0}

    def test_idempotent_write(self, tmp_path: Path) -> None:
        samples = [_hr(i) for i in range(3)]
        write_hr_samples(samples, tmp_path)
        write_hr_samples(samples, tmp_path)  # write same samples again

        date = _DATE.date()
        result = read_hr_samples(_UID, date, date, tmp_path)
        assert len(result) == 3  # no duplicates

    def test_empty_samples_no_error(self, tmp_path: Path) -> None:
        write_hr_samples([], tmp_path)  # should not raise

    def test_read_empty_range_returns_empty(self, tmp_path: Path) -> None:
        from datetime import date
        result = read_hr_samples(_UID, date(2020, 1, 1), date(2020, 1, 7), tmp_path)
        assert result == []

    def test_timestamps_are_timezone_aware(self, tmp_path: Path) -> None:
        write_hr_samples([_hr(0)], tmp_path)
        date = _DATE.date()
        result = read_hr_samples(_UID, date, date, tmp_path)
        assert result[0].timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# PPISample round-trip
# ---------------------------------------------------------------------------


class TestPPIParquet:
    def test_write_and_read(self, tmp_path: Path) -> None:
        samples = [_ppi(i, ppi_ms=800 + i * 10) for i in range(4)]
        write_ppi_samples(samples, tmp_path)

        date = _DATE.date()
        result = read_ppi_samples(_UID, date, date, tmp_path)
        assert len(result) == 4

    def test_valid_only_filter(self, tmp_path: Path) -> None:
        samples = [
            _ppi(0, ppi_ms=900, is_valid=True),
            _ppi(1, ppi_ms=850, is_valid=False),
            _ppi(2, ppi_ms=920, is_valid=True),
        ]
        write_ppi_samples(samples, tmp_path)
        date = _DATE.date()

        all_results = read_ppi_samples(_UID, date, date, tmp_path, valid_only=False)
        valid_results = read_ppi_samples(_UID, date, date, tmp_path, valid_only=True)
        assert len(all_results) == 3
        assert len(valid_results) == 2

    def test_hr_bpm_preserved(self, tmp_path: Path) -> None:
        s = PPISample(
            user_id=_UID, provider=_PROVIDER,
            timestamp=_DATE, ppi_ms=1000,
        )
        write_ppi_samples([s], tmp_path)
        date = _DATE.date()
        result = read_ppi_samples(_UID, date, date, tmp_path)
        assert result[0].hr_bpm == pytest.approx(60.0, abs=0.1)


# ---------------------------------------------------------------------------
# TemperatureSample round-trip
# ---------------------------------------------------------------------------


class TestTemperatureParquet:
    def test_write_and_read(self, tmp_path: Path) -> None:
        samples = [_temp(i) for i in range(3)]
        write_temperature_samples(samples, tmp_path)

        date = _DATE.date()
        result = read_temperature_samples(_UID, date, date, tmp_path)
        assert len(result) == 3
        assert all(s.skin_temperature_celsius == pytest.approx(34.2) for s in result)

    def test_read_empty_range_returns_empty(self, tmp_path: Path) -> None:
        from datetime import date
        result = read_temperature_samples(_UID, date(2020, 1, 1), date(2020, 1, 3), tmp_path)
        assert result == []


class TestParquetEdgeCases:
    def test_ppi_read_empty_range_returns_empty(self, tmp_path: Path) -> None:
        from datetime import date
        result = read_ppi_samples(_UID, date(2020, 1, 1), date(2020, 1, 3), tmp_path)
        assert result == []

    def test_corrupted_parquet_file_returns_none_and_no_crash(
        self, tmp_path: Path
    ) -> None:
        # Write a valid file first so the partition directory exists
        write_hr_samples([_hr(0)], tmp_path)
        d = _DATE.date()

        # Overwrite with garbage bytes (lines 42-44: _read_parquet_or_none exception path)
        from storage.parquet.partitions import hr_partition, parquet_path
        p = parquet_path(hr_partition(tmp_path, _UID, d))
        p.write_bytes(b"not a parquet file")

        result = read_hr_samples(_UID, d, d, tmp_path)
        assert result == []  # graceful empty result, no exception raised
