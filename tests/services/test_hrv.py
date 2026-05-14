"""Tests for HRV analytics functions."""

from __future__ import annotations

import math

import pytest

from services.analytics.hrv import rmssd, rolling_mean, rolling_std, sdnn, z_score


class TestRmssd:
    def test_basic(self) -> None:
        # diffs: [10, -10] → sq: [100, 100] → mean: 100 → sqrt: 10
        assert rmssd([800.0, 810.0, 800.0]) == pytest.approx(10.0)

    def test_identical_intervals_zero(self) -> None:
        assert rmssd([800.0, 800.0, 800.0]) == pytest.approx(0.0)

    def test_two_samples(self) -> None:
        assert rmssd([700.0, 750.0]) == pytest.approx(50.0)

    def test_requires_two_samples(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            rmssd([800.0])

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            rmssd([])

    def test_high_hrv_signal(self) -> None:
        # Alternating intervals — high variability
        result = rmssd([800.0, 900.0, 800.0, 900.0])
        assert result == pytest.approx(100.0)


class TestSdnn:
    def test_basic(self) -> None:
        vals = [800.0, 820.0, 800.0, 820.0]
        mean = 810.0
        variance = sum((x - mean) ** 2 for x in vals) / 4
        expected = math.sqrt(variance)
        assert sdnn(vals) == pytest.approx(expected)

    def test_identical_zero(self) -> None:
        assert sdnn([800.0, 800.0, 800.0]) == pytest.approx(0.0)

    def test_requires_two_samples(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            sdnn([800.0])


class TestRollingMean:
    def test_basic_window(self) -> None:
        result = rolling_mean([1.0, 2.0, 3.0, 4.0], window=2)
        assert result == pytest.approx([1.0, 1.5, 2.5, 3.5])

    def test_skips_none(self) -> None:
        result = rolling_mean([1.0, None, 3.0], window=3)
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(1.0)  # only 1.0 in window
        assert result[2] == pytest.approx(2.0)  # (1.0 + 3.0) / 2

    def test_min_periods_returns_none(self) -> None:
        # window=3, min_periods=2: need ≥2 non-null values in the window
        result = rolling_mean([None, 3.0, 5.0], window=3, min_periods=2)
        assert result[0] is None   # only 1 non-null (3.0 not yet in window)
        assert result[1] is None   # window=[None, 3.0] → 1 non-null < min_periods
        assert result[2] is not None  # window=[None, 3.0, 5.0] → 2 non-null ≥ min_periods

    def test_window_1(self) -> None:
        result = rolling_mean([5.0, 10.0, 15.0], window=1)
        assert result == pytest.approx([5.0, 10.0, 15.0])

    def test_invalid_window(self) -> None:
        with pytest.raises(ValueError):
            rolling_mean([1.0], window=0)


class TestRollingStd:
    def test_constant_series_zero(self) -> None:
        result = rolling_std([5.0, 5.0, 5.0, 5.0], window=3)
        # First entry has only 1 value → None (min_periods=2)
        assert result[0] is None
        assert result[1] == pytest.approx(0.0)
        assert result[2] == pytest.approx(0.0)

    def test_alternating_series(self) -> None:
        result = rolling_std([0.0, 10.0, 0.0, 10.0], window=2)
        assert result[0] is None
        assert result[1] == pytest.approx(5.0)  # pop std of [0, 10]

    def test_insufficient_data_none(self) -> None:
        result = rolling_std([None, None, 5.0], window=3)
        assert result[0] is None
        assert result[1] is None

    def test_invalid_window(self) -> None:
        with pytest.raises(ValueError):
            rolling_std([1.0, 2.0], window=1)


class TestZScore:
    def test_positive(self) -> None:
        assert z_score(60.0, 50.0, 10.0) == pytest.approx(1.0)

    def test_negative(self) -> None:
        assert z_score(40.0, 50.0, 10.0) == pytest.approx(-1.0)

    def test_at_mean(self) -> None:
        assert z_score(50.0, 50.0, 10.0) == pytest.approx(0.0)

    def test_small_std_returns_none(self) -> None:
        assert z_score(50.0, 50.0, 0.1) is None

    def test_zero_std_returns_none(self) -> None:
        assert z_score(50.0, 50.0, 0.0) is None
