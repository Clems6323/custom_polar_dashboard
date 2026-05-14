"""StrainScorer — produces StrainMetrics from activity sessions and load history."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from domain.models.activity import ActivitySession
from domain.models.enums import Provider
from domain.models.strain import StrainMetrics
from services.analytics.strain import acwr, daily_training_load, strain_score

_ACUTE_WINDOW = 7
_CHRONIC_WINDOW = 28


class StrainScorer:
    """Compute StrainMetrics for a single day.

    Args:
        sessions:     All ActivitySession records that fall on ``record_date``.
        load_history: Daily training loads for the preceding days (oldest first,
                      ``None`` = rest day / missing).  Must cover at least
                      ``chronic_window`` days for ACWR to be computed.
        record_date:  The calendar date being scored.
        provider:     Data source label for the produced record.
    """

    def score(
        self,
        record_date: date,
        sessions: Sequence[ActivitySession],
        load_history: Sequence[float | None],
        provider: Provider = Provider.POLAR,
        polar_strain: float | None = None,
        polar_tolerance: float | None = None,
    ) -> StrainMetrics:
        """Return a populated StrainMetrics for ``record_date``.

        Args:
            polar_strain:    Polar 7-day rolling cardio load from /v3/users/cardio-load.
                             When provided together with polar_tolerance, used as the
                             primary source for acute_load and ACWR (more accurate than
                             our local rolling window which is limited to the sync window).
            polar_tolerance: Polar 28-day rolling cardio load from /v3/users/cardio-load.
        """
        total_load = daily_training_load(sessions)

        # Muscle load — sum when available
        muscle_total: float | None = None
        for s in sessions:
            if s.muscle_load is not None:
                muscle_total = (muscle_total or 0.0) + s.muscle_load

        # Prefer Polar's server-side rolling loads over our local computation —
        # Polar uses the user's full history, we only cover the sync window.
        if polar_strain is not None and polar_tolerance is not None:
            acute_load: float | None = polar_strain
            chronic_load: float | None = polar_tolerance
            ratio: float | None = polar_strain / polar_tolerance if polar_tolerance > 0 else None
        else:
            full_history = [*list(load_history), total_load]
            ratio = acwr(full_history, acute_window=_ACUTE_WINDOW, chronic_window=_CHRONIC_WINDOW)
            acute_vals = [v for v in full_history[-_ACUTE_WINDOW:] if v is not None]
            chronic_vals = [v for v in full_history[-_CHRONIC_WINDOW:] if v is not None]
            acute_load = sum(acute_vals) / len(acute_vals) if acute_vals else None
            chronic_load = sum(chronic_vals) / len(chronic_vals) if chronic_vals else None

        score = strain_score(total_load, ratio)

        return StrainMetrics(
            record_date=record_date,
            user_id=sessions[0].user_id if sessions else "",
            provider=provider,
            strain_score=round(score, 2),
            cardio_load=round(total_load, 2),
            muscle_load=round(muscle_total, 2) if muscle_total is not None else None,
            acute_load=round(acute_load, 2) if acute_load is not None else None,
            chronic_load=round(chronic_load, 2) if chronic_load is not None else None,
            acwr=round(ratio, 3) if ratio is not None else None,
            session_count=len(sessions),
            session_ids=[s.id for s in sessions],
        )
