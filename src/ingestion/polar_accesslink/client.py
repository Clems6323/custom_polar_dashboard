"""Polar AccessLink HTTP client.

Wraps httpx with:
- Bearer token injection from ``TokenStore``
- Automatic token refresh on 401 (if a refresh token is available)
- Exponential back-off retry on 5xx errors (via tenacity)
- Structured logging of every request/response
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ingestion.polar_accesslink.auth import PolarOAuth2, TokenData, TokenStore

logger = logging.getLogger(__name__)

_API_BASE = "https://www.polaraccesslink.com/v3"
_MAX_RETRIES = 3


def _is_server_error(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500


def _retry_on_server_error(f: Callable[..., Any]) -> Callable[..., Any]:
    return retry(
        retry=retry_if_exception(_is_server_error),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(_MAX_RETRIES),
        reraise=True,
    )(f)


class PolarClient:
    """Authenticated HTTP client for the Polar AccessLink v3 API.

    Token refresh is attempted transparently on a single 401 response.
    After a successful refresh the ``TokenStore`` is updated so the new
    token survives process restarts.
    """

    def __init__(
        self,
        token_store: TokenStore,
        oauth: PolarOAuth2,
    ) -> None:
        self._token_store = token_store
        self._oauth = oauth
        self._token: TokenData | None = token_store.load()

    # ------------------------------------------------------------------
    # Public request helpers
    # ------------------------------------------------------------------

    def get(self, path: str, *, params: dict[str, str] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def get_url(self, url: str) -> Any:
        """Perform a GET request against an absolute URL (e.g. exercise links)."""
        return self._request_url("GET", url)

    def post(self, path: str, *, json: Any = None) -> httpx.Response:
        return self._raw_request("POST", path, json=json)

    def put(self, path: str) -> httpx.Response:
        return self._raw_request("PUT", path)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        if self._token is None:
            raise RuntimeError("No token available — run polar_auth.py first")
        return {
            "Authorization": f"Bearer {self._token.access_token}",
            "Accept": "application/json",
        }

    @_retry_on_server_error
    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{_API_BASE}{path}"
        return self._request_url(method, url, **kwargs)

    @_retry_on_server_error
    def _request_url(self, method: str, url: str, **kwargs: Any) -> Any:
        with httpx.Client(timeout=60) as client:
            resp = client.request(method, url, headers=self._headers(), **kwargs)
            if resp.status_code == 401:
                logger.warning("401 — attempting token refresh")
                self._refresh_token()
                resp = client.request(method, url, headers=self._headers(), **kwargs)
            resp.raise_for_status()
            logger.debug("%s %s → %d", method, url, resp.status_code)
            if resp.text:
                return resp.json()
            return None

    @_retry_on_server_error
    def _raw_request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{_API_BASE}{path}"
        with httpx.Client(timeout=60) as client:
            resp = client.request(method, url, headers=self._headers(), **kwargs)
            if resp.status_code == 401:
                logger.warning("401 — attempting token refresh")
                self._refresh_token()
                resp = client.request(method, url, headers=self._headers(), **kwargs)
            logger.debug("%s %s → %d", method, url, resp.status_code)
            return resp

    def _refresh_token(self) -> None:
        if self._token is None or not self._token.refresh_token:
            raise RuntimeError(
                "Token expired and no refresh token is available. "
                "Re-run the OAuth flow with polar_auth.py."
            )
        logger.info("Refreshing Polar access token")
        new_token = self._oauth.refresh(
            self._token.refresh_token,
            self._token.polar_user_id,
        )
        self._token = new_token
        self._token_store.save(new_token)
