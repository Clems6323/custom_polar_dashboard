"""Tests for sleep MCP tool query functions."""

from __future__ import annotations

from datetime import date

import pytest

from polar_mcp.tools.sleep import query_sleep_score, query_sleep_trends


class TestQuerySleepScore:
    def test_returns_score_for_existing_record(self, seeded_sleep_db, user_id, record_date):
        result = query_sleep_score(seeded_sleep_db, user_id, record_date)
        assert result["sleep_score"] == pytest.approx(72.5)
        assert result["user_id"] == user_id
        assert result["record_date"] == str(record_date)

    def test_total_sleep_converted_to_minutes(self, seeded_sleep_db, user_id, record_date):
        result = query_sleep_score(seeded_sleep_db, user_id, record_date)
        assert result["total_sleep_minutes"] == pytest.approx(7.0 * 60, abs=0.1)

    def test_sleep_latency_converted_to_minutes(self, seeded_sleep_db, user_id, record_date):
        result = query_sleep_score(seeded_sleep_db, user_id, record_date)
        # 600 seconds = 10 minutes
        assert result["sleep_latency_minutes"] == pytest.approx(10.0, abs=0.1)

    def test_architecture_fields_present(self, seeded_sleep_db, user_id, record_date):
        result = query_sleep_score(seeded_sleep_db, user_id, record_date)
        arch = result["architecture"]
        assert arch["deep_sleep_pct"] == pytest.approx(22.0)
        assert arch["rem_sleep_pct"] == pytest.approx(26.0)
        assert arch["light_sleep_pct"] == pytest.approx(45.3)

    def test_metadata_data_available_true(self, seeded_sleep_db, user_id, record_date):
        result = query_sleep_score(seeded_sleep_db, user_id, record_date)
        assert result["metadata"]["data_available"] is True
        assert result["metadata"]["confidence"] > 0.9

    def test_not_found_returns_error_structure(self, db_conn, user_id):
        result = query_sleep_score(db_conn, user_id, date(2000, 1, 1))
        assert result["error"] == "not_found"
        assert result["metadata"]["data_available"] is False
        assert result["metadata"]["confidence"] == 0.0

    def test_missing_optional_fields_lower_confidence(self, db_conn, user_id, record_date):
        from storage.repositories.metrics import DuckDBSleepMetricsRepository
        from domain.models.sleep_metrics import SleepMetrics
        from domain.models.enums import Provider

        repo = DuckDBSleepMetricsRepository(db_conn)
        repo.upsert(
            SleepMetrics(
                user_id=user_id,
                record_date=record_date,
                provider=Provider.POLAR,
                sleep_score=60.0,
                total_sleep_seconds=6.5 * 3600,
                # all optional fields absent
            )
        )
        result = query_sleep_score(db_conn, user_id, record_date)
        meta = result["metadata"]
        assert meta["data_available"] is True
        assert meta["confidence"] < 0.2
        assert len(meta["missing_signals"]) > 5

    def test_consistency_score_included(self, seeded_sleep_db, user_id, record_date):
        result = query_sleep_score(seeded_sleep_db, user_id, record_date)
        assert result["sleep_consistency_score"] == pytest.approx(81.0)


class TestQuerySleepTrends:
    def test_returns_all_records_in_range(self, seeded_range_db, user_id):
        start = date(2025, 11, 10)
        end = date(2025, 11, 16)
        result = query_sleep_trends(seeded_range_db, user_id, start, end)
        assert result["summary"]["nights"] == 7

    def test_summary_averages_computed(self, seeded_range_db, user_id):
        start = date(2025, 11, 10)
        end = date(2025, 11, 16)
        result = query_sleep_trends(seeded_range_db, user_id, start, end)
        # Scores are 65 through 71 so avg should be 68
        assert result["summary"]["avg_sleep_score"] == pytest.approx(68.0, abs=0.5)

    def test_empty_range_returns_no_data(self, db_conn, user_id):
        start = date(2020, 1, 1)
        end = date(2020, 1, 7)
        result = query_sleep_trends(db_conn, user_id, start, end)
        assert result["summary"]["nights"] == 0
        assert result["metadata"]["data_available"] is False
        assert "no_records_in_range" in result["metadata"]["missing_signals"]

    def test_data_points_ordered_by_date(self, seeded_range_db, user_id):
        start = date(2025, 11, 10)
        end = date(2025, 11, 16)
        result = query_sleep_trends(seeded_range_db, user_id, start, end)
        dates = [p["record_date"] for p in result["data"]]
        assert dates == sorted(dates)

    def test_metadata_confidence_reflects_coverage(self, seeded_range_db, user_id):
        # 7 days of data over a 7-day range → confidence = 1.0
        start = date(2025, 11, 10)
        end = date(2025, 11, 16)
        result = query_sleep_trends(seeded_range_db, user_id, start, end)
        assert result["metadata"]["confidence"] == pytest.approx(1.0)
