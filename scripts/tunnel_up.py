"""Start the full stack and auto-patch .env with the Cloudflare quick-tunnel URL.

Usage (works on Windows, macOS, Linux):
    uv run python scripts/tunnel_up.py

What it does:
  1. docker compose up -d          (all services; cloudflared starts after n8n is healthy)
  2. Poll cloudflared logs until the *.trycloudflare.com URL appears
  3. Write N8N_WEBHOOK_URL=<url> into .env
  4. docker compose restart n8n   (picks up the new WEBHOOK_URL)
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


def compose(*args: str) -> None:
    subprocess.run([*COMPOSE, *args], check=True)


def cloudflared_logs() -> str:
    result = subprocess.run(
        [*COMPOSE, "logs", "cloudflared"],
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


def find_tunnel_url(text: str) -> str | None:
    m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", text)
    return m.group(0) if m else None


def patch_env(url: str) -> None:
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    if re.search(r"^N8N_WEBHOOK_URL=", text, re.MULTILINE):
        text = re.sub(r"(?m)^N8N_WEBHOOK_URL=.*", f"N8N_WEBHOOK_URL={url}", text)
    else:
        text = text.rstrip("\n") + f"\nN8N_WEBHOOK_URL={url}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


def main() -> None:
    print("Starting all services...")
    compose("up", "-d")

    print("Waiting for Cloudflare quick tunnel URL (up to 2 minutes)...")
    tunnel_url: str | None = None
    for _ in range(40):
        tunnel_url = find_tunnel_url(cloudflared_logs())
        if tunnel_url:
            break
        time.sleep(3)

    if not tunnel_url:
        print("ERROR: Tunnel URL not found in cloudflared logs after 2 minutes.", file=sys.stderr)
        print("Check logs with: docker compose logs cloudflared", file=sys.stderr)
        sys.exit(1)

    print(f"Got tunnel URL: {tunnel_url}")

    patch_env(tunnel_url)
    print(f"Updated .env -> N8N_WEBHOOK_URL={tunnel_url}")

    print("Restarting n8n to apply new webhook URL...")
    compose("restart", "n8n")

    print()
    print("Stack is up:")
    print("  Dashboard -> http://localhost:8501")
    print("  n8n       -> http://localhost:5678")
    print(f"  Webhook   -> {tunnel_url}")


if __name__ == "__main__":
    main()
