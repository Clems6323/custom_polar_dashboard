"""Run the readiness analytics pipeline over all synced data.

Usage:
    uv run scripts/run_analytics.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]

Defaults to the last 90 days when no date range is supplied.
Requires a valid token and at least one completed polar_sync.py run.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import duckdb  # noqa: E402
from configs.settings import get_settings  # noqa: E402

from ingestion.polar_accesslink.auth import TokenStore  # noqa: E402
from services.readiness.pipeline import ReadinessPipeline  # noqa: E402
from storage.duckdb.connection import DuckDBConnectionManager  # noqa: E402
from storage.duckdb.migrations import run_migrations  # noqa: E402
from storage.repositories.activity import DuckDBActivityRepository  # noqa: E402
from storage.repositories.metrics import (  # noqa: E402
    DuckDBRecoveryMetricsRepository,
    DuckDBSleepMetricsRepository,
    DuckDBStrainMetricsRepository,
)
from storage.repositories.cardio_load import DuckDBCardioLoadRepository  # noqa: E402
from storage.repositories.sleep import DuckDBSleepRepository  # noqa: E402
from utils.logging import configure_logging  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run readiness analytics pipeline")
    parser.add_argument("--start", type=date.fromisoformat, default=None)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    configure_logging(level=settings.app.log_level, debug=settings.app.debug)
    logger = logging.getLogger(__name__)

    token_path = settings.storage.data_dir / "tokens" / "polar.json"
    token_store = TokenStore(token_path)

    if not token_store.is_available:
        logger.error("No token found at %s. Run scripts/polar_auth.py first.", token_path)
        sys.exit(1)

    token = token_store.load()
    if token is None:
        logger.error("Token file is empty or corrupt.")
        sys.exit(1)

    end = args.end or date.today()
    start = args.start or (end - timedelta(days=90))

    logger.info("Running analytics for user %d from %s to %s", token.polar_user_id, start, end)

    db_manager = DuckDBConnectionManager(settings.storage.duckdb_path)
    conn: duckdb.DuckDBPyConnection = db_manager.conn
    run_migrations(conn)

    user_id = str(token.polar_user_id)

    pipeline = ReadinessPipeline(
        user_id=user_id,
        activity_repo=DuckDBActivityRepository(conn),
        sleep_repo=DuckDBSleepRepository(conn),
        sleep_metrics_repo=DuckDBSleepMetricsRepository(conn),
        strain_metrics_repo=DuckDBStrainMetricsRepository(conn),
        recovery_repo=DuckDBRecoveryMetricsRepository(conn),
        cardio_load_repo=DuckDBCardioLoadRepository(conn),
    )

    results = pipeline.run(start, end)

    total_errors = sum(len(d.errors) for d in results.values())
    scored_sleep = sum(1 for d in results.values() if d.sleep_metrics)
    scored_strain = sum(1 for d in results.values() if d.strain_metrics)
    scored_recovery = sum(1 for d in results.values() if d.recovery_metrics)

    logger.info(
        "Analytics complete — sleep: %d, strain: %d, recovery: %d, errors: %d",
        scored_sleep,
        scored_strain,
        scored_recovery,
        total_errors,
    )

    if total_errors:
        for day in results.values():
            for err in day.errors:
                logger.warning("  [%s] %s", day.date, err)
        sys.exit(1)


if __name__ == "__main__":
    main()
