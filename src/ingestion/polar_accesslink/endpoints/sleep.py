"""Polar AccessLink sleep and nightly recharge endpoints.

Correct v3 URL pattern (no user ID in path — user identified by Bearer token):
  GET /v3/users/sleep                    → list of full sleep objects
  GET /v3/users/sleep/{date}             → single sleep object
  GET /v3/users/nightly-recharge         → list of full recharge objects
  GET /v3/users/nightly-recharge/{date}  → single recharge object
"""

from __future__ import annotations

import logging

import httpx

from ingestion.polar_accesslink.client import PolarClient
from ingestion.polar_accesslink.models import (
    PolarNightlyRecharge,
    PolarNightlyRechargeListResponse,
    PolarSleepData,
    PolarSleepListResponse,
)

logger = logging.getLogger(__name__)


def _is_404(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404


class SleepEndpoint:
    """Wraps the ``/users/sleep`` family of AccessLink v3 endpoints."""

    def __init__(self, client: PolarClient) -> None:
        self._client = client

    def list_sleep_data(self) -> list[PolarSleepData]:
        """Return all available sleep records as full objects.

        Returns an empty list on 404, which Polar returns when Sleep and
        Recovery has not been enabled for the application in the developer
        console at admin.polaraccesslink.com.
        """
        try:
            data = self._client.get("/users/sleep")
        except Exception as exc:
            if _is_404(exc):
                logger.warning(
                    "Sleep endpoint returned 404 — ensure 'Sleep and Recovery' is enabled "
                    "for your application at admin.polaraccesslink.com, and that your "
                    "device has synced sleep data to Polar Flow."
                )
                return []
            raise
        if data is None:
            return []
        resp = PolarSleepListResponse(**data)
        logger.info("Sleep data available for %d nights", len(resp.nights))
        return resp.nights

    def get(self, date: str) -> PolarSleepData | None:
        """Fetch sleep data for a specific date (YYYY-MM-DD)."""
        try:
            data = self._client.get(f"/users/sleep/{date}")
        except Exception:
            logger.warning("Failed to fetch sleep data for %s", date, exc_info=True)
            return None
        if data is None:
            return None
        return PolarSleepData(**data)


class NightlyRechargeEndpoint:
    """Wraps the ``/users/nightly-recharge`` family of AccessLink v3 endpoints."""

    def __init__(self, client: PolarClient) -> None:
        self._client = client

    def list_recharge_data(self) -> list[PolarNightlyRecharge]:
        """Return all available nightly recharge records as full objects.

        Returns an empty list on 404, which Polar returns when Nightly Recharge
        is not enabled for the application or the device doesn't support it.
        """
        try:
            data = self._client.get("/users/nightly-recharge")
        except Exception as exc:
            if _is_404(exc):
                logger.warning(
                    "Nightly Recharge endpoint returned 404 — ensure 'Nightly Recharge' "
                    "is enabled for your application at admin.polaraccesslink.com, and "
                    "that your device supports and has recorded Nightly Recharge data."
                )
                return []
            raise
        if data is None:
            return []
        resp = PolarNightlyRechargeListResponse(**data)
        logger.info("Nightly recharge data available for %d nights", len(resp.recharges))
        return resp.recharges

    def get(self, date: str) -> PolarNightlyRecharge | None:
        """Fetch nightly recharge data for a specific date (YYYY-MM-DD)."""
        try:
            data = self._client.get(f"/users/nightly-recharge/{date}")
        except Exception:
            logger.warning("Failed to fetch recharge data for %s", date, exc_info=True)
            return None
        if data is None:
            return None
        return PolarNightlyRecharge(**data)
