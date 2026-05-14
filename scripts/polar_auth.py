"""One-time Polar OAuth2 authorization flow.

Usage:
    uv run scripts/polar_auth.py

Opens the Polar authorization URL, starts a local HTTP server to capture
the authorization code, exchanges it for an access token, and saves the
token to the configured token path.
"""

from __future__ import annotations

import logging
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Ensure src/ and project root are on the path when running as a script
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from configs.settings import get_settings  # noqa: E402

from ingestion.polar_accesslink.auth import PolarOAuth2, TokenStore  # noqa: E402
from utils.logging import configure_logging  # noqa: E402

configure_logging(level="INFO", debug=False)
logger = logging.getLogger(__name__)

_auth_code: str | None = None
_server_ready = threading.Event()


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _auth_code = params["code"][0]
            body = b"Authorization successful! You may close this window."
            self.send_response(200)
        else:
            body = b"Authorization failed - no code in response."
            self.send_response(400)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass  # suppress default access log


def _run_server(host: str, port: int) -> None:
    server = HTTPServer((host, port), _CallbackHandler)
    _server_ready.set()
    server.handle_request()  # handle exactly one request then stop
    server.server_close()


def main() -> None:
    settings = get_settings()
    polar_cfg = settings.polar
    polar_cfg.require_credentials()

    redirect_uri = polar_cfg.redirect_uri
    parsed = urllib.parse.urlparse(str(redirect_uri))
    host = parsed.hostname or "localhost"
    port = parsed.port or 8000

    token_path = settings.storage.data_dir / "tokens" / "polar.json"
    token_store = TokenStore(token_path)

    oauth = PolarOAuth2(
        client_id=str(polar_cfg.client_id),
        client_secret=str(polar_cfg.client_secret),
        redirect_uri=str(redirect_uri),
    )

    if token_store.is_available:
        token = token_store.load()
        if token is None:
            logger.error("Token file is corrupt. Delete %s and re-run.", token_path)
            sys.exit(1)
        logger.info(
            "Token already exists for Polar user %d. Ensuring AccessLink registration...",
            token.polar_user_id,
        )
        oauth.register_user(token.access_token, token.polar_user_id)
        logger.info("Done. Delete %s to start a fresh OAuth2 flow.", token_path)
        return

    # Start callback server in background thread
    server_thread = threading.Thread(target=_run_server, args=(host, port), daemon=True)
    server_thread.start()
    _server_ready.wait(timeout=5)

    auth_url = oauth.authorization_url()
    logger.info("Opening browser for Polar authorization...")
    logger.info("URL: %s", auth_url)
    webbrowser.open(auth_url)

    server_thread.join(timeout=300)

    if _auth_code is None:
        logger.error("Authorization timed out or failed. No code received.")
        sys.exit(1)

    logger.info("Authorization code received, exchanging for token...")
    token = oauth.exchange_code(_auth_code)

    logger.info("Registering user %d with Polar AccessLink...", token.polar_user_id)
    oauth.register_user(token.access_token, token.polar_user_id)

    token_store.save(token)
    logger.info(
        "Setup complete. Polar user ID: %d. Token path: %s",
        token.polar_user_id,
        token_path,
    )


if __name__ == "__main__":
    main()
