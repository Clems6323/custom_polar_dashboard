"""Start the full stack and auto-patch .env with the Cloudflare quick-tunnel URL.

Usage (works on Windows, macOS, Linux):
    uv run python scripts/tunnel_up.py

What it does:
  1. docker compose up -d dashboard n8n
  2. Wait for n8n to pass its health check
  3. docker compose up -d --force-recreate cloudflared
     (force-recreate gives a fresh container with fresh logs — no stale URL)
  4. Poll cloudflared logs until the *.trycloudflare.com URL appears
  5. Write N8N_WEBHOOK_URL=<url> into .env
  6. docker compose restart n8n  (picks up the new WEBHOOK_URL)
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
COMPOSE = ["docker", "compose", "-f", str(ROOT / "docker-compose.yml")]

_TUNNEL_URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


def compose(*args: str) -> None:
    subprocess.run([*COMPOSE, *args], check=True)


def cloudflared_logs() -> str:
    result = subprocess.run(
        [*COMPOSE, "logs", "cloudflared"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout + result.stderr


def find_tunnel_url(text: str) -> str | None:
    """Return the first trycloudflare.com URL found in the log text."""
    m = _TUNNEL_URL_RE.search(text)
    return m.group(0) if m else None


def patch_env(url: str) -> None:
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    if re.search(r"^N8N_WEBHOOK_URL=", text, re.MULTILINE):
        text = re.sub(r"(?m)^N8N_WEBHOOK_URL=.*", f"N8N_WEBHOOK_URL={url}", text)
    else:
        text = text.rstrip("\n") + f"\nN8N_WEBHOOK_URL={url}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


def main() -> None:
    print("Starting dashboard and n8n...")
    compose("up", "-d", "dashboard", "n8n")

    print("Waiting for n8n to be healthy...")
    for _ in range(40):
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Health.Status}}", "polar-n8n"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip() == "healthy":
            break
        time.sleep(3)
    else:
        print("ERROR: n8n did not become healthy within 2 minutes.", file=sys.stderr)
        sys.exit(1)

    print("n8n is healthy.")

    # Force-recreate so cloudflared starts fresh — new container, new logs,
    # new URL. No timestamp filtering needed: any URL in the logs is from
    # this run.
    print("Recreating cloudflared to get a fresh tunnel URL...")
    compose("up", "-d", "--force-recreate", "cloudflared")

    print("Waiting for Cloudflare quick tunnel URL (up to 2 minutes)...")
    tunnel_url: str | None = None
    for _ in range(40):
        tunnel_url = find_tunnel_url(cloudflared_logs())
        if tunnel_url:
            break
        time.sleep(3)

    if not tunnel_url:
        print("ERROR: Tunnel URL not found in cloudflared logs after 2 minutes.", file=sys.stderr)
        print("Run: docker compose logs cloudflared", file=sys.stderr)
        sys.exit(1)

    print(f"Got tunnel URL: {tunnel_url}")

    patch_env(tunnel_url)
    print(f"Updated .env -> N8N_WEBHOOK_URL={tunnel_url}")

    print("Restarting n8n to apply new webhook URL...")
    compose("up", "-d", "--force-recreate", "n8n")

    print()
    print("Stack is up:")
    print("  Dashboard -> http://localhost:8501")
    print("  n8n       -> http://localhost:5678")
    print(f"  Webhook   -> {tunnel_url}")


if __name__ == "__main__":
    main()
