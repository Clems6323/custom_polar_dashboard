"""Polar AccessLink exercises endpoint.

Correct v3 URL pattern (no user ID in path — user identified by Bearer token):
  GET /v3/exercises                → list of full exercise objects (last 30 days)
  GET /v3/exercises/{exerciseId}   → single exercise object

Note: only exercises uploaded to Polar Flow after the user registered with
your client application are returned by the API.
"""

from __future__ import annotations

import logging

import httpx

from ingestion.polar_accesslink.client import PolarClient
from ingestion.polar_accesslink.models import PolarExercise, PolarExerciseListResponse

logger = logging.getLogger(__name__)


def _is_404(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404


class ExerciseEndpoint:
    """Wraps the ``/exercises`` AccessLink v3 endpoint."""

    def __init__(self, client: PolarClient) -> None:
        self._client = client

    def list_exercise_data(self) -> list[PolarExercise]:
        """Return all available exercises as full objects.

        Returns an empty list on 404, which Polar returns when no exercises
        are available or the permission is not enabled.
        """
        try:
            data = self._client.get("/exercises")
        except Exception as exc:
            if _is_404(exc):
                logger.warning(
                    "Exercises endpoint returned 404 — ensure 'Exercise' is enabled "
                    "for your application at admin.polaraccesslink.com."
                )
                return []
            raise
        if data is None:
            return []
        # API returns a JSON array directly, not a wrapped object
        if isinstance(data, list):
            exercises = [PolarExercise(**item) for item in data]
        else:
            exercises = PolarExerciseListResponse(**data).exercises
        logger.info("Exercise data available: %d exercises", len(exercises))
        return exercises

    def get(self, exercise_id: str) -> PolarExercise | None:
        """Fetch a single exercise by ID."""
        try:
            data = self._client.get(f"/exercises/{exercise_id}")
        except Exception:
            logger.warning("Failed to fetch exercise %s", exercise_id, exc_info=True)
            return None
        if data is None:
            return None
        return PolarExercise(**data)
