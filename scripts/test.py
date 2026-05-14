from __future__ import annotations

import logging
import sys
from pathlib import Path
import json

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
    data = client.get('/exercises')
    print(json.dumps(data, indent=2))
    
if __name__ == "__main__":
    main()