"""Tests for strain MCP tool query functions."""

from __future__ import annotations

from datetime import date

import pytest

from polar_mcp.tools.strain import query_strain_score, query_training_load


class TestQueryStrainScore:
    def test_returns_score_for_existing_record(self, seeded_strain_db, user_id, record_date):
        result = query_strain_score(seeded_strain_db, user_id, record_date)
        assert result["strain_score"] == pytest.approx(55.0)
        assert result["cardio_load"] == pytest.approx(180.0)

    def test_acwr_in_sweet_spot_zone(self, seeded_strain_db, user_id, record_date):
        result = query_strain_score(seeded_strain_db, user_id, record_date)
        acwr = result["acwr_analysis"]
        assert acwr is not None
        assert acwr["value"] == pytest.approx(1.07, abs=0.01)
        assert acwr["zone"] == "sweet_spot"

    def test_acwr_elevated_risk_zone(self, db_conn, user_id, record_date):
        from storage.repositories.metrics import DuckDBStrainMetricsRepository
        from domain.models.strain import StrainMetrics
        from domain.models.enums import Provider

        repo = DuckDBStrainMetricsRepository(db_conn)
        repo.upsert(
            StrainMetrics(
                user_id=user_id,
                record_date=record_date,
                provider=Provider.POLAR,
                strain_score=85.0,
                cardio_load=350.0,
                acwr=1.7,
            )
        )
        result = query_strain_score(db_conn, user_id, record_date)
        assert result["acwr_analysis"]["zone"] == "elevated_risk"

    def test_acwr_under_training_zone(self, db_conn, user_id, record_date):
        from storage.repositories.metrics import DuckDBStrainMetricsRepository
        from domain.models.strain import StrainMetrics
        from domain.models.enums import Provider

        repo = DuckDBStrainMetricsRepository(db_conn)
        repo.upsert(
            StrainMetrics(
                user_id=user_id,
                record_date=record_date,
                provider=Provider.POLAR,
                strain_score=20.0,
                cardio_load=50.0,
                acwr=0.5,
            )
        )
        result = query_strain_score(db_conn, user_id, record_date)
        assert result["acwr_analysis"]["zone"] == "under_training"

    def test_session_ids_included(self, seeded_strain_db, user_id, record_date):
        result = query_strain_score(seeded_strain_db, user_id, record_date)
        assert "session-a" in result["session_ids"]
        assert result["session_count"] == 2

    def test_not_found_returns_error_structure(self, db_conn, user_id):
        result = query_strain_score(db_conn, user_id, date(2000, 1, 1))
        assert result["error"] == "not_found"
        assert result["metadata"]["data_available"] is False

    def test_confidence_full_when_all_fields_present(self, seeded_strain_db, user_id, record_date):
        result = query_strain_score(seeded_strain_db, user_id, record_date)
        assert result["metadata"]["confidence"] == pytest.approx(1.0)

    def test_acwr_none_when_absent(self, db_conn, user_id, record_date):
        from storage.repositories.metrics import DuckDBStrainMetricsRepository
        from domain.models.strain import StrainMetrics
        from domain.models.enums import Provider

        repo = DuckDBStrainMetricsRepository(db_conn)
        repo.upsert(
            StrainMetrics(
                user_id=user_id,
                record_date=record_date,
                provider=Provider.POLAR,
                strain_score=30.0,
                cardio_load=80.0,
                # acwr absent — insufficient history
            )
        )
        result = query_strain_score(db_conn, user_id, record_date)
        assert result["acwr_analysis"] is None
        assert "acwr" in result["metadata"]["missing_signals"]


class TestQueryTrainingLoad:
    def test_returns_all_records_in_range(self, seeded_range_db, user_id):
        start = date(2025, 11, 10)
        end = date(2025, 11, 16)
        result = query_training_load(seeded_range_db, user_id, start, end)
        assert result["summary"]["days_with_data"] == 7

    def test_total_load_computed(self, seeded_range_db, user_id):
        start = date(2025, 11, 10)
        end = date(2025, 11, 16)
        result = query_training_load(seeded_range_db, user_id, start, end)
        # Loads are 100, 120, 140, 160, 180, 200, 220 → sum = 1120
        assert result["summary"]["total_load"] == pytest.approx(1120.0, abs=1.0)

    def test_peak_load_identified(self, seeded_range_db, user_id):
        start = date(2025, 11, 10)
        end = date(2025, 11, 16)
        result = query_training_load(seeded_range_db, user_id, start, end)
        assert result["summary"]["peak_load"] == pytest.approx(220.0, abs=1.0)

    def test_empty_range_returns_zero_total(self, db_conn, user_id):
        start = date(2020, 1, 1)
        end = date(2020, 1, 7)
        result = query_training_load(db_conn, user_id, start, end)
        assert result["summary"]["days_with_data"] == 0
        assert result["summary"]["total_load"] == 0.0
        assert result["metadata"]["data_available"] is False
