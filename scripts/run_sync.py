"""Headless Polar data sync — runs the full ingest + analytics pipeline.

Useful for cron jobs or container-based scheduled syncs without opening the UI:

    uv run python scripts/run_sync.py
    # or:
    make sync

Requires a valid Polar OAuth token at the path configured in STORAGE_TOKEN_PATH
(default: data/tokens/polar.json).  Run the Streamlit dashboard first (or
scripts/polar_auth.py) to complete the OAuth2 flow and persist the token.
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

from utils.logging import configure_logging

configure_logging()

from ui.streamlit.sync import is_token_available, run_full_sync

if not is_token_available():
    print(
        "No Polar token found. Complete the OAuth2 flow first:\n"
        "  1. Run `make dashboard` and connect via the sidebar, or\n"
        "  2. Run `make auth` to use the standalone callback server."
    )
    sys.exit(1)


def _progress(msg: str) -> None:
    print(f"  {msg}")


print("Starting Polar sync...")
result = run_full_sync(progress_callback=_progress)

synced_at = result.get("synced_at", "unknown")
counts = result.get("counts", {})
errors = result.get("errors", [])

print(f"\nSync complete at {synced_at}")
for key, val in counts.items():
    print(f"  {key}: {val}")

if errors:
    print(f"\n{len(errors)} error(s):")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)
