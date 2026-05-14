"""Tests for recovery MCP tool query functions."""

from __future__ import annotations

from datetime import date

import pytest

from polar_mcp.tools.recovery import query_recovery_score


class TestQueryRecoveryScore:
    def test_returns_score_for_existing_record(self, seeded_recovery_db, user_id, record_date):
        result = query_recovery_score(seeded_recovery_db, user_id, record_date)
        assert result["recovery_score"] == pytest.approx(68.0)
        assert result["user_id"] == user_id

    def test_readiness_zone_optimal(self, seeded_recovery_db, user_id, record_date):
        # Score 68 → optimal zone
        result = query_recovery_score(seeded_recovery_db, user_id, record_date)
        assert result["readiness_zone"]["zone"] == "optimal"

    def test_readiness_zone_poor(self, db_conn, user_id, record_date):
        from storage.repositories.metrics import DuckDBRecoveryMetricsRepository
        from domain.models.recovery import RecoveryMetrics, RecoveryContributors
        from domain.models.enums import Provider

        repo = DuckDBRecoveryMetricsRepository(db_conn)
        repo.upsert(
            RecoveryMetrics(
                user_id=user_id,
                record_date=record_date,
                provider=Provider.POLAR,
                recovery_score=20.0,
            )
        )
        result = query_recovery_score(db_conn, user_id, record_date)
        assert result["readiness_zone"]["zone"] == "poor"

    def test_readiness_zone_moderate(self, db_conn, user_id, record_date):
        from storage.repositories.metrics import DuckDBRecoveryMetricsRepository
        from domain.models.recovery import RecoveryMetrics
        from domain.models.enums import Provider

        repo = DuckDBRecoveryMetricsRepository(db_conn)
        repo.upsert(
            RecoveryMetrics(
                user_id=user_id,
                record_date=record_date,
                provider=Provider.POLAR,
                recovery_score=50.0,
            )
        )
        result = query_recovery_score(db_conn, user_id, record_date)
        assert result["readiness_zone"]["zone"] == "moderate"

    def test_contributors_included(self, seeded_recovery_db, user_id, record_date):
        result = query_recovery_score(seeded_recovery_db, user_id, record_date)
        contributors = result["contributors"]
        assert contributors["hrv_z_score"] == pytest.approx(0.5)
        assert contributors["sleep_score"] == pytest.approx(72.5)
        assert contributors["previous_strain_score"] == pytest.approx(40.0)

    def test_physiological_signals_included(self, seeded_recovery_db, user_id, record_date):
        result = query_recovery_score(seeded_recovery_db, user_id, record_date)
        assert result["rmssd_ms"] == pytest.approx(43.0)
        assert result["resting_hr_bpm"] == pytest.approx(52.0)
        assert result["hrv_baseline_ms"] == pytest.approx(40.0)

    def test_not_found_returns_error_structure(self, db_conn, user_id):
        result = query_recovery_score(db_conn, user_id, date(2000, 1, 1))
        assert result["error"] == "not_found"
        assert result["metadata"]["data_available"] is False

    def test_metadata_confidence_high_with_full_data(self, seeded_recovery_db, user_id, record_date):
        result = query_recovery_score(seeded_recovery_db, user_id, record_date)
        assert result["metadata"]["confidence"] == pytest.approx(1.0)

    def test_metadata_missing_signals_when_fields_absent(self, db_conn, user_id, record_date):
        from storage.repositories.metrics import DuckDBRecoveryMetricsRepository
        from domain.models.recovery import RecoveryMetrics
        from domain.models.enums import Provider

        repo = DuckDBRecoveryMetricsRepository(db_conn)
        repo.upsert(
            RecoveryMetrics(
                user_id=user_id,
                record_date=record_date,
                provider=Provider.POLAR,
                recovery_score=50.0,
                # all physiological signals absent
            )
        )
        result = query_recovery_score(db_conn, user_id, record_date)
        missing = result["metadata"]["missing_signals"]
        assert "rmssd_ms" in missing
        assert "hrv_z_score" in missing
