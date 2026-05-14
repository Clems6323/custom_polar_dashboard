"""Polar AccessLink OAuth2 authentication and token persistence."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_AUTH_URL = "https://flow.polar.com/oauth2/authorization"
_TOKEN_URL = "https://polarremote.com/v2/oauth2/token"
_API_BASE = "https://www.polaraccesslink.com/v3"


class TokenData(BaseModel, frozen=True):
    """OAuth2 token data stored on disk between sessions."""

    access_token: str
    token_type: str = "bearer"
    polar_user_id: int
    expires_in: int | None = None
    refresh_token: str | None = None
    x_refresh_token_expire_in: int | None = None


class TokenStore:
    """Persists a single user's token to a JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def is_available(self) -> bool:
        return self._path.exists()

    def load(self) -> TokenData | None:
        if not self._path.exists():
            return None
        return TokenData(**json.loads(self._path.read_text(encoding="utf-8")))

    def save(self, token: TokenData) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(token.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Token saved to %s", self._path)


class PolarOAuth2:
    """Handles the Polar AccessLink OAuth2 Authorization Code flow.

    Usage:
        1. Direct the user to ``authorization_url()``.
        2. Receive the ``code`` query-param at your redirect_uri.
        3. Call ``exchange_code(code)`` → ``TokenData``.
        4. Persist via ``TokenStore.save()``.
    """

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def authorization_url(self) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenData:
        """Exchange an authorization code for an access token."""
        resp = httpx.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._redirect_uri,
            },
            auth=(self._client_id, self._client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        polar_user_id: int = payload["x_user_id"]
        return TokenData(
            access_token=payload["access_token"],
            token_type=payload.get("token_type", "bearer"),
            polar_user_id=polar_user_id,
            expires_in=payload.get("expires_in"),
            refresh_token=payload.get("refresh_token"),
            x_refresh_token_expire_in=payload.get("x_refresh_token_expire_in"),
        )

    def refresh(self, refresh_token: str, polar_user_id: int) -> TokenData:
        """Obtain a new access token using a refresh token."""
        resp = httpx.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(self._client_id, self._client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        return TokenData(
            access_token=payload["access_token"],
            token_type=payload.get("token_type", "bearer"),
            polar_user_id=payload.get("x_user_id", polar_user_id),
            expires_in=payload.get("expires_in"),
            refresh_token=payload.get("refresh_token", refresh_token),
            x_refresh_token_expire_in=payload.get("x_refresh_token_expire_in"),
        )

    def register_user(self, access_token: str, polar_user_id: int) -> None:
        """Register user with AccessLink (one-time, after first OAuth2 grant).

        Polar requires POST /users before any data endpoint can be used.
        A 409 means the user is already registered; that is treated as success.
        """
        resp = httpx.post(
            f"{_API_BASE}/users",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            json={"member-id": str(polar_user_id)},
            timeout=30,
        )
        if resp.status_code == 409:
            logger.info("User %d already registered with Polar AccessLink", polar_user_id)
            return
        resp.raise_for_status()
        logger.info("Registered user %d with Polar AccessLink", polar_user_id)
