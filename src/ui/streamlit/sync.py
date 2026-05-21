"""In-process sync and authentication helpers for the Streamlit dashboard.

All heavy imports (duckdb, domain models, etc.) are deferred to function
bodies so that importing this module at startup is fast.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[3]
_LAST_SYNC_PATH = _ROOT / "data" / "last_sync.json"


# ---------------------------------------------------------------------------
# Token state
# ---------------------------------------------------------------------------


def _token_path() -> Path:
    from configs.settings import get_settings
    s = get_settings()
    return s.storage.data_dir / "tokens" / "polar.json"


def is_token_available() -> bool:
    """Return True when a saved Polar OAuth2 token file exists."""
    return _token_path().exists()


# ---------------------------------------------------------------------------
# Last-sync metadata
# ---------------------------------------------------------------------------


def get_last_sync_info() -> dict | None:
    """Return the metadata dict from the last successful sync, or None."""
    if not _LAST_SYNC_PATH.exists():
        return None
    try:
        return json.loads(_LAST_SYNC_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_last_sync(info: dict) -> None:
    _LAST_SYNC_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LAST_SYNC_PATH.write_text(json.dumps(info, default=str, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# OAuth2 helpers
# ---------------------------------------------------------------------------


def get_auth_url() -> str:
    """Return the Polar OAuth2 authorization URL."""
    from configs.settings import get_settings
    from ingestion.polar_accesslink.auth import PolarOAuth2

    s = get_settings()
    s.polar.require_credentials()
    oauth = PolarOAuth2(
        client_id=str(s.polar.client_id),
        client_secret=str(s.polar.client_secret),
        redirect_uri=str(s.polar.redirect_uri),
    )
    return oauth.authorization_url()


def exchange_auth_code(code: str) -> int:
    """Exchange an authorization code for a token; return Polar user ID."""
    from configs.settings import get_settings
    from ingestion.polar_accesslink.auth import PolarOAuth2, TokenStore

    s = get_settings()
    s.polar.require_credentials()
    oauth = PolarOAuth2(
        client_id=str(s.polar.client_id),
        client_secret=str(s.polar.client_secret),
        redirect_uri=str(s.polar.redirect_uri),
    )
    token = oauth.exchange_code(code)
    oauth.register_user(token.access_token, token.polar_user_id)
    TokenStore(_token_path()).save(token)
    return token.polar_user_id


# ---------------------------------------------------------------------------
# Full sync + analytics pipeline
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[str], None]


def run_full_sync(
    progress_callback: ProgressCallback | None = None,
    analytics_days: int = 90,
) -> dict:
    """Run a full Polar data sync followed by the analytics pipeline.

    Args:
        progress_callback: Optional callable(str) for step-by-step status.
        analytics_days:    How many days of history to (re)score.

    Returns:
        A dict summarising what was synced and scored.

    Raises:
        RuntimeError: token missing, credentials missing, DB locked.
    """
    import duckdb
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

    def _log(msg: str) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    # --- Token ---
    s = get_settings()
    s.polar.require_credentials()
    token_store = TokenStore(_token_path())

    if not token_store.is_available:
        raise RuntimeError("No Polar token found. Complete authorization first.")

    token = token_store.load()
    if token is None:
        raise RuntimeError("Token file is empty or corrupt.")

    oauth = PolarOAuth2(
        client_id=str(s.polar.client_id),
        client_secret=str(s.polar.client_secret),
        redirect_uri=str(s.polar.redirect_uri),
    )
    client = PolarClient(token_store, oauth)

    # --- Database ---
    _log("Connecting to database…")
    db_manager: DuckDBConnectionManager | None = None
    for attempt in range(6):
        try:
            db_manager = DuckDBConnectionManager(s.storage.duckdb_path)
            break
        except duckdb.IOException as exc:
            if attempt == 5:
                raise RuntimeError(f"Database locked after 6 attempts: {exc}") from exc
            wait = 2 ** attempt
            _log(f"Database locked — retrying in {wait}s…")
            time.sleep(wait)

    assert db_manager is not None
    conn = db_manager.conn
    run_migrations(conn)

    canonical_user_id = str(token.polar_user_id)

    # --- Sync ---
    _log("Fetching data from Polar AccessLink…")
    orchestrator = SyncOrchestrator(
        client=client,
        canonical_user_id=canonical_user_id,
        activity_repo=DuckDBActivityRepository(conn),
        sleep_repo=DuckDBSleepRepository(conn),
        sleep_metrics_repo=DuckDBSleepMetricsRepository(conn),
        recovery_repo=DuckDBRecoveryMetricsRepository(conn),
        cardio_load_repo=DuckDBCardioLoadRepository(conn),
    )
    sync_result = orchestrator.sync_all()
    _log(
        f"Polar sync done — {sync_result.exercises_synced} workouts, "
        f"{sync_result.sleep_nights_synced} sleep nights, "
        f"{sync_result.cardio_load_days_synced} cardio-load days"
    )

    # --- Analytics ---
    _log("Running analytics pipeline…")
    end = date.today()
    start = end - timedelta(days=analytics_days)

    pipeline = ReadinessPipeline(
        user_id=canonical_user_id,
        activity_repo=DuckDBActivityRepository(conn),
        sleep_repo=DuckDBSleepRepository(conn),
        sleep_metrics_repo=DuckDBSleepMetricsRepository(conn),
        strain_metrics_repo=DuckDBStrainMetricsRepository(conn),
        recovery_repo=DuckDBRecoveryMetricsRepository(conn),
        cardio_load_repo=DuckDBCardioLoadRepository(conn),
    )
    pipeline_results = pipeline.run(start, end)

    scored_sleep = sum(1 for d in pipeline_results.values() if d.sleep_metrics)
    scored_strain = sum(1 for d in pipeline_results.values() if d.strain_metrics)
    scored_recovery = sum(1 for d in pipeline_results.values() if d.recovery_metrics)
    total_errors = sum(len(d.errors) for d in pipeline_results.values())

    _log(
        f"Analytics done — {scored_sleep} sleep, "
        f"{scored_strain} strain, {scored_recovery} recovery scored"
    )

    info: dict = {
        "synced_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "exercises": sync_result.exercises_synced,
        "sleep_nights": sync_result.sleep_nights_synced,
        "recharge_nights": sync_result.recharge_nights_synced,
        "cardio_load_days": sync_result.cardio_load_days_synced,
        "scored_sleep": scored_sleep,
        "scored_strain": scored_strain,
        "scored_recovery": scored_recovery,
        "errors": total_errors,
        "sync_errors": sync_result.errors[:5],
    }
    _save_last_sync(info)
    return info
