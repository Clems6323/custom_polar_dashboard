"""Run a full Polar AccessLink data sync.

Usage:
    uv run scripts/polar_sync.py

Requires a valid token at the configured token path (run polar_auth.py first).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure src/ and project root are on the path when running as a script
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import time  # noqa: E402

import duckdb  # noqa: E402
from configs.settings import get_settings  # noqa: E402

from ingestion.polar_accesslink.auth import PolarOAuth2, TokenStore  # noqa: E402
from ingestion.polar_accesslink.client import PolarClient  # noqa: E402
from ingestion.polar_accesslink.sync import SyncOrchestrator  # noqa: E402
from storage.duckdb.connection import DuckDBConnectionManager  # noqa: E402
from storage.duckdb.migrations import run_migrations  # noqa: E402
from storage.repositories.activity import DuckDBActivityRepository  # noqa: E402
from storage.repositories.cardio_load import DuckDBCardioLoadRepository  # noqa: E402
from storage.repositories.metrics import (  # noqa: E402
    DuckDBRecoveryMetricsRepository,
    DuckDBSleepMetricsRepository,
)
from storage.repositories.sleep import DuckDBSleepRepository  # noqa: E402
from utils.logging import configure_logging  # noqa: E402


def main() -> None:
    settings = get_settings()
    configure_logging(level=settings.app.log_level, debug=settings.app.debug)
    logger = logging.getLogger(__name__)

    polar_cfg = settings.polar
    polar_cfg.require_credentials()

    token_path = settings.storage.data_dir / "tokens" / "polar.json"
    token_store = TokenStore(token_path)

    if not token_store.is_available:
        logger.error(
            "No token found at %s. Run scripts/polar_auth.py first.", token_path
        )
        sys.exit(1)

    token = token_store.load()
    if token is None:
        logger.error("Token file is empty or corrupt.")
        sys.exit(1)

    oauth = PolarOAuth2(
        client_id=str(polar_cfg.client_id),
        client_secret=str(polar_cfg.client_secret),
        redirect_uri=str(polar_cfg.redirect_uri),
    )
    client = PolarClient(token_store, oauth)

    db_path = settings.storage.duckdb_path
    db_manager: DuckDBConnectionManager | None = None
    for attempt in range(6):
        try:
            db_manager = DuckDBConnectionManager(db_path)
            break
        except duckdb.IOException as exc:
            if attempt == 5:
                logger.error("Cannot open database after 6 attempts: %s", exc)
                sys.exit(1)
            wait = 2 ** attempt
            logger.warning(
                "Database locked (attempt %d/6), retrying in %ds…", attempt + 1, wait
            )
            time.sleep(wait)
    assert db_manager is not None
    conn: duckdb.DuckDBPyConnection = db_manager.conn
    run_migrations(conn)

    canonical_user_id = str(token.polar_user_id)
    logger.info("Starting sync for user %s (Polar ID: %d)", canonical_user_id, token.polar_user_id)

    orchestrator = SyncOrchestrator(
        client=client,
        canonical_user_id=canonical_user_id,
        activity_repo=DuckDBActivityRepository(conn),
        sleep_repo=DuckDBSleepRepository(conn),
        sleep_metrics_repo=DuckDBSleepMetricsRepository(conn),
        recovery_repo=DuckDBRecoveryMetricsRepository(conn),
        cardio_load_repo=DuckDBCardioLoadRepository(conn),
    )

    result = orchestrator.sync_all()
    logger.info("Sync complete: %s", result)

    if result.errors:
        logger.warning("%d error(s) during sync:", len(result.errors))
        for err in result.errors:
            logger.warning("  - %s", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
