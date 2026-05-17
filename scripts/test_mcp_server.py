"""Smoke-test the polar-mcp server over the streamable-http transport.

Usage:
    # Against the Docker-internal service (run from inside a container on polar-net):
    uv run python scripts/test_mcp_server.py --url http://polar-mcp:8000/mcp/

    # Against a locally exposed port (add 'ports: ["8000:8000"]' to polar-mcp in docker-compose):
    uv run python scripts/test_mcp_server.py

The script:
  1. Connects and lists all registered tools.
  2. Calls every tool with minimal valid arguments and prints the result.
  3. Reports PASS / FAIL per tool and exits non-zero if any call failed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, timedelta

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_URL = "http://localhost:8000/mcp/"
DEFAULT_USER_ID = "63407527"


def _today() -> str:
    return date.today().isoformat()


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


# Minimal arguments for each known tool.
TOOL_ARGS: dict[str, dict] = {
    "get_sleep_score": {"user_id": DEFAULT_USER_ID, "record_date": _today()},
    "get_sleep_trends": {
        "user_id": DEFAULT_USER_ID,
        "start_date": _days_ago(7),
        "end_date": _today(),
    },
    "get_strain_score": {"user_id": DEFAULT_USER_ID, "record_date": _today()},
    "get_training_load": {
        "user_id": DEFAULT_USER_ID,
        "start_date": _days_ago(7),
        "end_date": _today(),
    },
    "get_recovery_score": {"user_id": DEFAULT_USER_ID, "record_date": _today()},
    "get_hrv_baseline": {"user_id": DEFAULT_USER_ID},
}


async def run(url: str) -> bool:
    print(f"Connecting to {url}\n")
    all_passed = True

    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ── List tools ────────────────────────────────────────────────────
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            print(f"Registered tools ({len(tool_names)}):")
            for name in tool_names:
                print(f"  • {name}")
            print()

            # ── Call each tool ────────────────────────────────────────────────
            for tool in tools_result.tools:
                args = TOOL_ARGS.get(tool.name, {})
                label = f"  {tool.name}"
                try:
                    result = await session.call_tool(tool.name, args)
                    if result.isError:
                        raise RuntimeError(result.content)
                    payload = result.content[0].text if result.content else "{}"
                    parsed = json.loads(payload)
                    meta = parsed.get("metadata", {})
                    available = meta.get("data_available", "—")
                    confidence = meta.get("confidence", "—")
                    if available is True:
                        print(f"PASS  {label}  (data_available=True, confidence={confidence})")
                    else:
                        print(f"PASS  {label}  (data_available={available})  ← no data found")
                        print(f"      payload: {json.dumps(parsed, indent=2)[:300]}")
                except Exception as exc:
                    print(f"FAIL  {label}  → {exc}")
                    all_passed = False

    return all_passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the polar-mcp server.")
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"MCP server endpoint (default: {DEFAULT_URL})",
    )
    args = parser.parse_args()

    passed = asyncio.run(run(args.url))
    if passed:
        print("\nAll tools passed.")
    else:
        print("\nSome tools failed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
