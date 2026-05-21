"""Tests for the sync_and_analyze MCP tool (polar_mcp.tools.sync_and_analyze)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from polar_mcp.tools.sync_and_analyze import SyncAndAnalyzeOutput, run_sync_and_analyze

_MOD = "polar_mcp.tools.sync_and_analyze"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings() -> MagicMock:
    settings = MagicMock()
    settings.polar.client_id = "cid"
    settings.polar.client_secret = "csec"
    settings.polar.redirect_uri = "http://localhost/cb"
    settings.polar.require_credentials.return_value = ("cid", "csec")
    settings.storage.token_path = "/fake/token.json"
    settings.storage.duckdb_path = ":memory:"
    return settings


def _make_sync_result(**overrides) -> MagicMock:
    r = MagicMock()
    r.exercises_synced = overrides.get("exercises_synced", 3)
    r.sleep_nights_synced = overrides.get("sleep_nights_synced", 2)
    r.recharge_nights_synced = overrides.get("recharge_nights_synced", 2)
    r.activity_days_synced = overrides.get("activity_days_synced", 5)
    r.cardio_load_days_synced = overrides.get("cardio_load_days_synced", 5)
    r.errors = overrides.get("errors", [])
    return r


def _make_day(*, sleep: bool = True, strain: bool = True, recovery: bool = True,
               errors: list[str] | None = None) -> MagicMock:
    d = MagicMock()
    d.sleep_metrics = MagicMock() if sleep else None
    d.strain_metrics = MagicMock() if strain else None
    d.recovery_metrics = MagicMock() if recovery else None
    d.errors = errors or []
    return d


def _run(
    analytics_days: int = 90,
    sync_result=None,
    pipeline_results: dict | None = None,
    token_user_id: int = 42,
    settings=None,
):
    """Run run_sync_and_analyze() with all external dependencies mocked."""
    sync_result = sync_result or _make_sync_result()
    if pipeline_results is None:
        pipeline_results = {date(2025, 11, 15): _make_day()}

    token = MagicMock()
    token.polar_user_id = token_user_id

    with (
        patch(f"{_MOD}.get_settings", return_value=settings or _make_settings()),
        patch(f"{_MOD}.TokenStore") as mock_ts,
        patch(f"{_MOD}.PolarOAuth2"),
        patch(f"{_MOD}.PolarClient"),
        patch(f"{_MOD}.DuckDBConnectionManager") as mock_db,
        patch(f"{_MOD}.run_migrations"),
        patch(f"{_MOD}.DuckDBActivityRepository"),
        patch(f"{_MOD}.DuckDBSleepRepository"),
        patch(f"{_MOD}.DuckDBSleepMetricsRepository"),
        patch(f"{_MOD}.DuckDBStrainMetricsRepository"),
        patch(f"{_MOD}.DuckDBRecoveryMetricsRepository"),
        patch(f"{_MOD}.DuckDBCardioLoadRepository"),
        patch(f"{_MOD}.SyncOrchestrator") as mock_orch,
        patch(f"{_MOD}.ReadinessPipeline") as mock_pl,
    ):
        mock_ts.return_value.is_available = True
        mock_ts.return_value.load.return_value = token
        mock_db.return_value.conn = MagicMock()
        mock_orch.return_value.sync_all.return_value = sync_result
        mock_pl.return_value.run.return_value = pipeline_results
        return run_sync_and_analyze(analytics_days), mock_orch, mock_pl


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestRunSyncAndAnalyzeErrors:
    def test_raises_when_token_not_available(self):
        with patch(f"{_MOD}.get_settings", return_value=_make_settings()):
            with patch(f"{_MOD}.TokenStore") as mock_ts:
                mock_ts.return_value.is_available = False
                with pytest.raises(RuntimeError, match="No Polar token"):
                    run_sync_and_analyze()

    def test_raises_when_token_corrupt(self):
        with patch(f"{_MOD}.get_settings", return_value=_make_settings()):
            with patch(f"{_MOD}.TokenStore") as mock_ts:
                mock_ts.return_value.is_available = True
                mock_ts.return_value.load.return_value = None
                with pytest.raises(RuntimeError, match="empty or corrupt"):
                    run_sync_and_analyze()

    def test_raises_when_credentials_missing(self):
        settings = _make_settings()
        settings.polar.require_credentials.side_effect = RuntimeError("No credentials")
        with patch(f"{_MOD}.get_settings", return_value=settings):
            with pytest.raises(RuntimeError, match="No credentials"):
                run_sync_and_analyze()


# ---------------------------------------------------------------------------
# Happy path — output fields
# ---------------------------------------------------------------------------


class TestRunSyncAndAnalyzeHappyPath:
    def test_returns_output_instance(self):
        result, _, _ = _run()
        assert isinstance(result, SyncAndAnalyzeOutput)

    def test_user_id_derived_from_token(self):
        result, _, _ = _run(token_user_id=99)
        assert result.user_id == "99"

    def test_sync_counts_populated(self):
        sr = _make_sync_result(exercises_synced=7, sleep_nights_synced=4,
                               recharge_nights_synced=3, activity_days_synced=10,
                               cardio_load_days_synced=9)
        result, _, _ = _run(sync_result=sr)
        assert result.exercises_synced == 7
        assert result.sleep_nights_synced == 4
        assert result.recharge_nights_synced == 3
        assert result.activity_days_synced == 10
        assert result.cardio_load_days_synced == 9

    def test_analytics_window_defaults_to_90_days(self):
        result, _, _ = _run()
        assert result.analytics_end == date.today()
        assert result.analytics_start == date.today() - timedelta(days=90)

    def test_analytics_days_parameter_respected(self):
        result, _, mock_pl = _run(analytics_days=30)
        assert result.analytics_start == date.today() - timedelta(days=30)
        mock_pl.return_value.run.assert_called_once_with(
            date.today() - timedelta(days=30), date.today()
        )

    def test_days_processed_equals_pipeline_result_length(self):
        days = {date(2025, 11, i): _make_day() for i in range(10, 16)}
        result, _, _ = _run(pipeline_results=days)
        assert result.days_processed == 6

    def test_scored_counts_when_all_metrics_present(self):
        days = {date(2025, 11, i): _make_day() for i in range(10, 15)}
        result, _, _ = _run(pipeline_results=days)
        assert result.sleep_scored == 5
        assert result.strain_scored == 5
        assert result.recovery_scored == 5

    def test_partial_scoring_counted_correctly(self):
        days = {
            date(2025, 11, 10): _make_day(sleep=True, strain=False, recovery=False),
            date(2025, 11, 11): _make_day(sleep=True, strain=True, recovery=False),
            date(2025, 11, 12): _make_day(sleep=True, strain=True, recovery=True),
        }
        result, _, _ = _run(pipeline_results=days)
        assert result.sleep_scored == 3
        assert result.strain_scored == 2
        assert result.recovery_scored == 1

    def test_zero_counts_on_empty_pipeline_results(self):
        result, _, _ = _run(pipeline_results={})
        assert result.days_processed == 0
        assert result.sleep_scored == 0
        assert result.strain_scored == 0
        assert result.recovery_scored == 0

    def test_completed_at_is_set(self):
        result, _, _ = _run()
        assert result.completed_at is not None

    def test_sync_orchestrator_called_once(self):
        _, mock_orch, _ = _run()
        mock_orch.return_value.sync_all.assert_called_once()

    def test_pipeline_called_once(self):
        _, _, mock_pl = _run()
        mock_pl.return_value.run.assert_called_once()


# ---------------------------------------------------------------------------
# Error aggregation
# ---------------------------------------------------------------------------


class TestRunSyncAndAnalyzeErrorAggregation:
    def test_no_errors_on_clean_run(self):
        result, _, _ = _run()
        assert result.sync_errors == []
        assert result.analytics_errors == []

    def test_sync_errors_propagated(self):
        sr = _make_sync_result(errors=["exercise fetch failed", "sleep 404"])
        result, _, _ = _run(sync_result=sr)
        assert result.sync_errors == ["exercise fetch failed", "sleep 404"]

    def test_analytics_errors_aggregated_across_days(self):
        days = {
            date(2025, 11, 10): _make_day(errors=["hrv error", "temp missing"]),
            date(2025, 11, 11): _make_day(errors=["strain error"]),
            date(2025, 11, 12): _make_day(),
        }
        result, _, _ = _run(pipeline_results=days)
        assert len(result.analytics_errors) == 3
        assert set(result.analytics_errors) == {"hrv error", "temp missing", "strain error"}

    def test_sync_and_analytics_errors_are_independent_fields(self):
        sr = _make_sync_result(errors=["sync-err"])
        days = {date(2025, 11, 10): _make_day(errors=["analytic-err"])}
        result, _, _ = _run(sync_result=sr, pipeline_results=days)
        assert result.sync_errors == ["sync-err"]
        assert result.analytics_errors == ["analytic-err"]


# ---------------------------------------------------------------------------
# SyncAndAnalyzeOutput schema
# ---------------------------------------------------------------------------


class TestSyncAndAnalyzeOutput:
    def _valid(self, **overrides) -> SyncAndAnalyzeOutput:
        defaults = dict(
            user_id="1",
            exercises_synced=3,
            sleep_nights_synced=2,
            recharge_nights_synced=2,
            activity_days_synced=5,
            cardio_load_days_synced=5,
            analytics_start=date(2025, 8, 17),
            analytics_end=date(2025, 11, 15),
            days_processed=90,
            sleep_scored=88,
            strain_scored=85,
            recovery_scored=87,
            sync_errors=[],
            analytics_errors=[],
        )
        defaults.update(overrides)
        return SyncAndAnalyzeOutput(**defaults)

    def test_model_dump_is_json_serializable(self):
        json.dumps(self._valid().model_dump(mode="json"))

    def test_all_fields_present_in_dump(self):
        d = self._valid().model_dump()
        for field in (
            "user_id",
            "exercises_synced", "sleep_nights_synced", "recharge_nights_synced",
            "activity_days_synced", "cardio_load_days_synced",
            "analytics_start", "analytics_end",
            "days_processed", "sleep_scored", "strain_scored", "recovery_scored",
            "sync_errors", "analytics_errors",
            "completed_at",
        ):
            assert field in d

    def test_zero_counts_are_valid(self):
        out = self._valid(exercises_synced=0, sleep_nights_synced=0,
                          days_processed=0, sleep_scored=0)
        assert out.exercises_synced == 0
        assert out.days_processed == 0

    def test_completed_at_set_automatically(self):
        assert self._valid().completed_at is not None


# ---------------------------------------------------------------------------
# Server wrapper
# ---------------------------------------------------------------------------


class TestSyncAndAnalyzeServerWrapper:
    def test_returns_dict_from_output(self):
        from polar_mcp.server import sync_and_analyze as server_fn

        mock_output, _, _ = _run()
        with patch("polar_mcp.server._run_sync_and_analyze", return_value=mock_output):
            result = server_fn()

        assert isinstance(result, dict)
        assert "user_id" in result
        assert "exercises_synced" in result
        assert "sleep_scored" in result

    def test_runtime_error_becomes_error_dict(self):
        from polar_mcp.server import sync_and_analyze as server_fn

        with patch("polar_mcp.server._run_sync_and_analyze",
                   side_effect=RuntimeError("no token")):
            result = server_fn()

        assert result == {"error": "no token"}

    def test_analytics_days_forwarded_to_implementation(self):
        from polar_mcp.server import sync_and_analyze as server_fn

        mock_output, _, _ = _run(analytics_days=30)
        with patch("polar_mcp.server._run_sync_and_analyze",
                   return_value=mock_output) as mock_fn:
            server_fn(analytics_days=30)

        mock_fn.assert_called_once_with(30)

    def test_default_analytics_days_is_90(self):
        from polar_mcp.server import sync_and_analyze as server_fn

        mock_output, _, _ = _run()
        with patch("polar_mcp.server._run_sync_and_analyze",
                   return_value=mock_output) as mock_fn:
            server_fn()

        mock_fn.assert_called_once_with(90)
