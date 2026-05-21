"""MCP action tool: sync Polar data then score the analytics pipeline in one call."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta

import duckdb
from pydantic import BaseModel, Field

from configs.settings import get_settings
from ingestion.polar_accesslink.auth import PolarOAuth2, TokenStore
from ingestion.polar_accesslink.client import PolarClient
from ingestion.polar_accesslink.sync import SyncOrchestrator
from services.readiness.pipeline import ReadinessPipeline
from storage.duckdb.connection import DuckDBConnectionManager
from storage.duckdb.migrations import run_migrations
from storage.repositories.activity import DuckDBActivityRepository
from storage.repositories.cardio_load import DuckDBCardioLoadRepository
from storage.repositories.metrics import (
    DuckDBRecoveryMetricsRepository,
    DuckDBSleepMetricsRepository,
    DuckDBStrainMetricsRepository,
)
from storage.repositories.sleep import DuckDBSleepRepository


class SyncAndAnalyzeOutput(BaseModel):
    user_id: str
    # Sync counts
    exercises_synced: int
    sleep_nights_synced: int
    recharge_nights_synced: int
    activity_days_synced: int
    cardio_load_days_synced: int
    # Analytics window
    analytics_start: date
    analytics_end: date
    days_processed: int
    sleep_scored: int
    strain_scored: int
    recovery_scored: int
    # Errors from both phases
    sync_errors: list[str]
    analytics_errors: list[str]
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def run_sync_and_analyze(
    analytics_days: int = 90,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> SyncAndAnalyzeOutput:
    """Sync Polar AccessLink data then run the readiness analytics pipeline.

    When ``conn`` is provided (e.g. the lifespan singleton from the MCP server)
    it is used directly and no new DuckDB connection is opened.  When omitted,
    a read-write connection is opened with exponential-backoff retry (up to 63 s)
    for file-lock contention.

    Args:
        analytics_days: Number of trailing days to score (default 90).
        conn: Optional existing DuckDB connection to reuse.

    Raises:
        RuntimeError: token missing / corrupt, credentials missing, DB locked.
    """
    settings = get_settings()
    settings.polar.require_credentials()

    token_store = TokenStore(settings.storage.token_path)
    if not token_store.is_available:
        raise RuntimeError("No Polar token found. Complete authorization first.")

    token = token_store.load()
    if token is None:
        raise RuntimeError("Polar token file is empty or corrupt.")

    oauth = PolarOAuth2(
        client_id=str(settings.polar.client_id),
        client_secret=str(settings.polar.client_secret),
        redirect_uri=str(settings.polar.redirect_uri),
    )
    client = PolarClient(token_store, oauth)

    if conn is None:
        db_manager: DuckDBConnectionManager | None = None
        for attempt in range(6):
            try:
                db_manager = DuckDBConnectionManager(settings.storage.duckdb_path)
                break
            except duckdb.IOException as exc:
                if attempt == 5:
                    raise RuntimeError(f"Database locked after 6 attempts: {exc}") from exc
                time.sleep(2 ** attempt)
        assert db_manager is not None
        conn = db_manager.conn

    run_migrations(conn)

    user_id = str(token.polar_user_id)

    # --- Phase 1: sync ---
    orchestrator = SyncOrchestrator(
        client=client,
        canonical_user_id=user_id,
        activity_repo=DuckDBActivityRepository(conn),
        sleep_repo=DuckDBSleepRepository(conn),
        sleep_metrics_repo=DuckDBSleepMetricsRepository(conn),
        recovery_repo=DuckDBRecoveryMetricsRepository(conn),
        cardio_load_repo=DuckDBCardioLoadRepository(conn),
    )
    sync_result = orchestrator.sync_all()

    # --- Phase 2: analytics ---
    analytics_end = date.today()
    analytics_start = analytics_end - timedelta(days=analytics_days)

    pipeline = ReadinessPipeline(
        user_id=user_id,
        activity_repo=DuckDBActivityRepository(conn),
        sleep_repo=DuckDBSleepRepository(conn),
        sleep_metrics_repo=DuckDBSleepMetricsRepository(conn),
        strain_metrics_repo=DuckDBStrainMetricsRepository(conn),
        recovery_repo=DuckDBRecoveryMetricsRepository(conn),
        cardio_load_repo=DuckDBCardioLoadRepository(conn),
    )
    pipeline_results = pipeline.run(analytics_start, analytics_end)

    return SyncAndAnalyzeOutput(
        user_id=user_id,
        exercises_synced=sync_result.exercises_synced,
        sleep_nights_synced=sync_result.sleep_nights_synced,
        recharge_nights_synced=sync_result.recharge_nights_synced,
        activity_days_synced=sync_result.activity_days_synced,
        cardio_load_days_synced=sync_result.cardio_load_days_synced,
        analytics_start=analytics_start,
        analytics_end=analytics_end,
        days_processed=len(pipeline_results),
        sleep_scored=sum(1 for d in pipeline_results.values() if d.sleep_metrics),
        strain_scored=sum(1 for d in pipeline_results.values() if d.strain_metrics),
        recovery_scored=sum(1 for d in pipeline_results.values() if d.recovery_metrics),
        sync_errors=sync_result.errors,
        analytics_errors=[e for day in pipeline_results.values() for e in day.errors],
    )
