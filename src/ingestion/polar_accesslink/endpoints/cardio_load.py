"""Polar AccessLink cardio load endpoint.

URL pattern (user identified by Bearer token):
  GET /v3/users/cardio-load  → list of daily cardio load records

Each record carries:
  cardio-load  — daily cardio load for that date
  strain       — 7-day rolling cardio load (Polar "acute" load)
  tolerance    — 28-day rolling cardio load (Polar "chronic" load / fitness)
"""

from __future__ import annotations

import logging

import httpx

from ingestion.polar_accesslink.client import PolarClient
from ingestion.polar_accesslink.models import PolarCardioLoadRecord, PolarCardioLoadResponse

logger = logging.getLogger(__name__)


def _is_404(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404


class CardioLoadEndpoint:
    """Wraps the ``/users/cardio-load`` AccessLink v3 endpoint."""

    def __init__(self, client: PolarClient) -> None:
        self._client = client

    def list_cardio_load(self) -> list[PolarCardioLoadRecord]:
        """Return all available daily cardio load records.

        Returns an empty list on 404 (permission not enabled or no data).
        """
        try:
            data = self._client.get("/users/cardio-load")
        except Exception as exc:
            if _is_404(exc):
                logger.warning(
                    "Cardio load endpoint returned 404 — ensure 'Training Load Pro' is "
                    "enabled for your application at admin.polaraccesslink.com."
                )
                return []
            raise
        if data is None:
            return []
        if isinstance(data, list):
            records = [PolarCardioLoadRecord(**item) for item in data]
        else:
            records = PolarCardioLoadResponse(**data).cardio_load
        logger.info("Cardio load data available for %d days", len(records))
        return records
