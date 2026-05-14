"""Polar AccessLink activities endpoint.

Correct v3 URL pattern (no user ID in path — user identified by Bearer token):
  GET /v3/users/activities  → list of full activity summary objects
"""

from __future__ import annotations

import logging

import httpx

from ingestion.polar_accesslink.client import PolarClient
from ingestion.polar_accesslink.models import PolarActivityListResponse, PolarActivitySummary

logger = logging.getLogger(__name__)


def _is_404(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404


class ActivityEndpoint:
    """Wraps the ``/users/activities`` AccessLink v3 endpoint."""

    def __init__(self, client: PolarClient) -> None:
        self._client = client

    def list_activity_data(self) -> list[PolarActivitySummary]:
        """Return all available daily activity summaries as full objects.

        Returns an empty list on 404, which Polar returns when Activity Summary
        is not enabled for the application in the developer console.
        """
        try:
            data = self._client.get("/users/activities")
        except Exception as exc:
            if _is_404(exc):
                logger.warning(
                    "Activities endpoint returned 404 — ensure 'Activity Summary' is enabled "
                    "for your application at admin.polaraccesslink.com."
                )
                return []
            raise
        if data is None:
            return []
        # API returns a JSON array directly, not a wrapped object
        if isinstance(data, list):
            activities = [PolarActivitySummary(**item) for item in data]
        else:
            activities = PolarActivityListResponse(**data).activity_log
        logger.info("Activity data available for %d days", len(activities))
        return activities
