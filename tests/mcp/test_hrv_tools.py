"""Tests for HRV baseline MCP tool query functions."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from polar_mcp.tools.hrv import query_hrv_baseline


class TestQueryHRVBaseline:
    def test_mean_rmssd_computed(self, seeded_range_db, user_id):
        # seeded_range_db has 7 days with rmssd_ms 38, 39, 40, 41, 42, 43, 44
        end = date(2025, 11, 16)
        result = query_hrv_baseline(seeded_range_db, user_id, end, window_days=7)
        assert result["mean_rmssd_ms"] == pytest.approx(41.0, abs=0.5)

    def test_latest_rmssd_is_most_recent(self, seeded_range_db, user_id):
        end = date(2025, 11, 16)
        result = query_hrv_baseline(seeded_range_db, user_id, end, window_days=7)
        assert result["latest_rmssd_ms"] == pytest.approx(44.0, abs=0.5)

    def test_current_vs_baseline_pct_above_100_when_latest_high(self, seeded_range_db, user_id):
        # latest (44) > mean (41) → pct > 100
        end = date(2025, 11, 16)
        result = query_hrv_baseline(seeded_range_db, user_id, end, window_days=7)
        assert result["current_vs_baseline_pct"] > 100.0

    def test_std_rmssd_computed(self, seeded_range_db, user_id):
        end = date(2025, 11, 16)
        result = query_hrv_baseline(seeded_range_db, user_id, end, window_days=7)
        assert result["std_rmssd_ms"] is not None
        assert result["std_rmssd_ms"] > 0

    def test_empty_window_returns_none_stats(self, db_conn, user_id):
        end = date(2020, 1, 1)
        result = query_hrv_baseline(db_conn, user_id, end, window_days=30)
        assert result["mean_rmssd_ms"] is None
        assert result["latest_rmssd_ms"] is None
        assert result["current_vs_baseline_pct"] is None
        assert result["metadata"]["data_available"] is False

    def test_metadata_confidence_reflects_coverage(self, seeded_range_db, user_id):
        # 7 records in a 7-day window → confidence = 1.0
        end = date(2025, 11, 16)
        result = query_hrv_baseline(seeded_range_db, user_id, end, window_days=7)
        assert result["metadata"]["confidence"] == pytest.approx(1.0)

    def test_confidence_below_1_when_window_larger_than_data(self, seeded_range_db, user_id):
        # 7 records but 30-day window → confidence < 1
        end = date(2025, 11, 16)
        result = query_hrv_baseline(seeded_range_db, user_id, end, window_days=30)
        assert result["metadata"]["confidence"] < 1.0
        assert result["metadata"]["confidence"] == pytest.approx(7 / 30, abs=0.01)

    def test_data_points_returned_oldest_first(self, seeded_range_db, user_id):
        end = date(2025, 11, 16)
        result = query_hrv_baseline(seeded_range_db, user_id, end, window_days=7)
        dates = [p["record_date"] for p in result["data"]]
        assert dates == sorted(dates)

    def test_mean_recovery_score_computed(self, seeded_range_db, user_id):
        end = date(2025, 11, 16)
        result = query_hrv_baseline(seeded_range_db, user_id, end, window_days=7)
        # Recovery scores are 60, 62, 64, 66, 68, 70, 72 → mean = 66
        assert result["mean_recovery_score"] == pytest.approx(66.0, abs=1.0)

    def test_missing_rmssd_listed_in_missing_signals(self, db_conn, user_id):
        from storage.repositories.metrics import DuckDBRecoveryMetricsRepository
        from domain.models.recovery import RecoveryMetrics
        from domain.models.enums import Provider

        repo = DuckDBRecoveryMetricsRepository(db_conn)
        repo.upsert(
            RecoveryMetrics(
                user_id=user_id,
                record_date=date(2025, 11, 15),
                provider=Provider.POLAR,
                recovery_score=60.0,
                # rmssd_ms absent
            )
        )
        result = query_hrv_baseline(db_conn, user_id, date(2025, 11, 15), window_days=7)
        assert "rmssd_ms" in result["metadata"]["missing_signals"]
