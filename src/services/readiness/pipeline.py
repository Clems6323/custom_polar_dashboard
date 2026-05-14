"""ReadinessPipeline — orchestrates sleep, strain, and recovery scoring for a date range.

Execution order per date:
  1. Score sleep (requires history for consistency score)
  2. Score strain (requires load history for ACWR)
  3. Score recovery (requires baselines, sleep score, prior-day strain)

All computed metrics are persisted via repository upserts so subsequent
runs are idempotent (re-scoring overwrites previous results).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from domain.models.enums import Provider
from domain.models.recovery import RecoveryMetrics
from domain.models.sleep_metrics import SleepMetrics
from domain.models.strain import StrainMetrics
from services.scoring.recovery_scorer import RecoveryScorer
from services.scoring.sleep_scorer import SleepScorer
from services.scoring.strain_scorer import StrainScorer
from storage.repositories.cardio_load import DuckDBCardioLoadRepository
from storage.repositories.protocols import (
    ActivityRepository,
    RecoveryMetricsRepository,
    SleepMetricsRepository,
    SleepRepository,
    StrainMetricsRepository,
)

logger = logging.getLogger(__name__)

# How many days of history to pre-load before the requested start date
_HISTORY_DAYS = 30
# Window for sleep consistency (used in sleep_scorer internally)
_SLEEP_HISTORY_DAYS = 7


@dataclass
class DayReadiness:
    """Scoring outputs for a single calendar date."""

    date: date
    sleep_metrics: SleepMetrics | None = None
    strain_metrics: StrainMetrics | None = None
    recovery_metrics: RecoveryMetrics | None = None
    errors: list[str] = field(default_factory=list)


class ReadinessPipeline:
    """Score and persist readiness metrics for a user over a date range.

    Repositories are injected so the pipeline is testable without a real
    database.  All errors within a single date are caught, logged, and stored
    in ``DayReadiness.errors`` — failures on one date do not abort others.
    """

    def __init__(
        self,
        user_id: str,
        activity_repo: ActivityRepository,
        sleep_repo: SleepRepository,
        sleep_metrics_repo: SleepMetricsRepository,
        strain_metrics_repo: StrainMetricsRepository,
        recovery_repo: RecoveryMetricsRepository,
        provider: Provider = Provider.POLAR,
        cardio_load_repo: DuckDBCardioLoadRepository | None = None,
    ) -> None:
        self._user_id = user_id
        self._activity_repo = activity_repo
        self._sleep_repo = sleep_repo
        self._sleep_metrics_repo = sleep_metrics_repo
        self._strain_metrics_repo = strain_metrics_repo
        self._recovery_repo = recovery_repo
        self._provider = provider
        self._cardio_load_repo = cardio_load_repo

        self._sleep_scorer = SleepScorer()
        self._strain_scorer = StrainScorer()
        self._recovery_scorer = RecoveryScorer()

    def run(self, start: date, end: date) -> dict[date, DayReadiness]:
        """Score every date in [start, end] and persist results.

        Returns a mapping of date → DayReadiness for inspection / testing.
        """
        history_start = start - timedelta(days=_HISTORY_DAYS)

        # Pre-load history needed for rolling windows
        sleep_history = self._sleep_repo.list_by_date_range(
            self._user_id, history_start, start - timedelta(days=1)
        )
        activity_history = self._activity_repo.list_by_date_range(
            self._user_id, history_start, start - timedelta(days=1)
        )
        recovery_history = self._recovery_repo.list_by_date_range(
            self._user_id, history_start, start - timedelta(days=1)
        )

        # Build ordered daily load history (oldest first) for ACWR fallback
        load_by_date: dict[date, float] = {}
        for session in activity_history:
            d = session.start_time.date()
            from services.analytics.strain import estimate_session_load
            load_by_date[d] = load_by_date.get(d, 0.0) + estimate_session_load(session)

        # Pre-load Polar server-side rolling loads for the full date range.
        # These are more accurate than our local rolling window.
        cardio_load_by_date: dict[date, dict] = {}
        tolerance_by_date: dict[date, float] = {}
        if self._cardio_load_repo is not None:
            for rec in self._cardio_load_repo.list_by_date_range(
                self._user_id, history_start, end
            ):
                cardio_load_by_date[rec["date"]] = rec
                if rec["tolerance"] is not None:
                    tolerance_by_date[rec["date"]] = rec["tolerance"]

        # Build HRV and HR history for recovery baselines
        hrv_by_date: dict[date, float] = {
            r.record_date: r.rmssd_ms for r in recovery_history if r.rmssd_ms is not None
        }
        hr_by_date: dict[date, float] = {
            r.record_date: r.resting_hr_bpm
            for r in recovery_history
            if r.resting_hr_bpm is not None
        }

        results: dict[date, DayReadiness] = {}
        scored_sleep: dict[date, SleepMetrics] = {}
        scored_strain: dict[date, StrainMetrics] = {}
        # Track SleepSessions scored within this run so later nights
        # can use them as history for the consistency score.
        intra_run_sessions: list = []

        current = start
        while current <= end:
            day = DayReadiness(date=current)

            # --- Sleep scoring ---
            day = self._score_sleep(
                day, sleep_history, scored_sleep, intra_run_sessions
            )
            if day.sleep_metrics:
                scored_sleep[current] = day.sleep_metrics

            # --- Strain scoring ---
            day = self._score_strain(
                day, activity_history, load_by_date, scored_strain, cardio_load_by_date
            )
            if day.strain_metrics:
                scored_strain[current] = day.strain_metrics
                load_by_date[current] = day.strain_metrics.cardio_load

            # --- Recovery scoring ---
            day = self._score_recovery(
                day, recovery_history, hrv_by_date, hr_by_date,
                scored_sleep, scored_strain, tolerance_by_date
            )
            if day.recovery_metrics:
                if day.recovery_metrics.rmssd_ms is not None:
                    hrv_by_date[current] = day.recovery_metrics.rmssd_ms
                if day.recovery_metrics.resting_hr_bpm is not None:
                    hr_by_date[current] = day.recovery_metrics.resting_hr_bpm

            results[current] = day
            current += timedelta(days=1)

        logger.info(
            "ReadinessPipeline complete: %d dates scored, %d errors",
            len(results),
            sum(len(d.errors) for d in results.values()),
        )
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _score_sleep(
        self,
        day: DayReadiness,
        sleep_history: list,
        scored_sleep: dict[date, SleepMetrics],
        intra_run_sessions: list,
    ) -> DayReadiness:
        """Score sleep session(s) for day.date and persist."""
        # Query the day before through today so we catch sessions that start
        # before midnight (start_time::DATE = day.date - 1) and end at
        # morning on day.date.  The end_time filter keeps only the right night.
        sessions_today = [
            s for s in self._sleep_repo.list_by_date_range(
                self._user_id,
                day.date - timedelta(days=1),
                day.date,
            )
            if s.end_time.date() == day.date
        ]

        if not sessions_today:
            return day

        session = sessions_today[0]  # one sleep session per night
        # Combine pre-window history with sessions already scored this run
        combined_history = sleep_history + [
            s for s in intra_run_sessions if s.end_time.date() < day.date
        ]
        recent_history = [
            s for s in combined_history
            if s.end_time.date() < day.date
        ][-_SLEEP_HISTORY_DAYS:]

        try:
            metrics = self._sleep_scorer.score(session, recent_history, self._provider)
            self._sleep_metrics_repo.upsert(metrics)
            intra_run_sessions.append(session)
            return DayReadiness(
                date=day.date,
                sleep_metrics=metrics,
                strain_metrics=day.strain_metrics,
                recovery_metrics=day.recovery_metrics,
                errors=day.errors,
            )
        except Exception as exc:
            msg = f"sleep scoring failed for {day.date}: {exc}"
            logger.error(msg, exc_info=True)
            return DayReadiness(
                date=day.date,
                sleep_metrics=day.sleep_metrics,
                strain_metrics=day.strain_metrics,
                recovery_metrics=day.recovery_metrics,
                errors=[*day.errors, msg],
            )

    def _score_strain(
        self,
        day: DayReadiness,
        activity_history: list,
        load_by_date: dict[date, float],
        scored_strain: dict[date, StrainMetrics],
        cardio_load_by_date: dict[date, dict] | None = None,
    ) -> DayReadiness:
        """Score training strain for day.date and persist."""
        sessions_today = self._activity_repo.list_by_date_range(
            self._user_id, day.date, day.date
        )

        if not sessions_today:
            return day

        # Build daily load history up to (not including) today
        history_dates = sorted(d for d in load_by_date if d < day.date)
        load_history: list[float | None] = [load_by_date.get(d) for d in history_dates]

        # Use Polar's server-side rolling loads when available for this date
        cl_rec = (cardio_load_by_date or {}).get(day.date)
        polar_strain = cl_rec["strain"] if cl_rec else None
        polar_tolerance = cl_rec["tolerance"] if cl_rec else None

        try:
            metrics = self._strain_scorer.score(
                day.date, sessions_today, load_history, self._provider,
                polar_strain=polar_strain, polar_tolerance=polar_tolerance,
            )
            self._strain_metrics_repo.upsert(metrics)
            return DayReadiness(
                date=day.date,
                sleep_metrics=day.sleep_metrics,
                strain_metrics=metrics,
                recovery_metrics=day.recovery_metrics,
                errors=day.errors,
            )
        except Exception as exc:
            msg = f"strain scoring failed for {day.date}: {exc}"
            logger.error(msg, exc_info=True)
            return DayReadiness(
                date=day.date,
                sleep_metrics=day.sleep_metrics,
                strain_metrics=day.strain_metrics,
                recovery_metrics=day.recovery_metrics,
                errors=[*day.errors, msg],
            )

    def _score_recovery(
        self,
        day: DayReadiness,
        recovery_history: list,
        hrv_by_date: dict[date, float],
        hr_by_date: dict[date, float],
        scored_sleep: dict[date, SleepMetrics],
        scored_strain: dict[date, StrainMetrics],
        tolerance_by_date: dict[date, float] | None = None,
    ) -> DayReadiness:
        """Score recovery for day.date using raw Polar data and enriched context."""
        raw = self._recovery_repo.get(self._user_id, day.date)
        if raw is None:
            return day

        sleep_metrics = day.sleep_metrics or scored_sleep.get(day.date)
        prev_date = day.date - timedelta(days=1)
        prev_strain = scored_strain.get(prev_date) or self._strain_metrics_repo.get(
            self._user_id, prev_date
        )

        # Build ordered baseline sequences (oldest first, up to but not including today).
        all_dates = hrv_by_date.keys() | hr_by_date.keys() | (tolerance_by_date or {}).keys()
        history_dates = sorted(d for d in all_dates if d < day.date)
        hrv_history: list[float | None] = [hrv_by_date.get(d) for d in history_dates]
        hr_history: list[float | None] = [hr_by_date.get(d) for d in history_dates]
        tol_history: list[float | None] = [
            (tolerance_by_date or {}).get(d) for d in history_dates
        ]

        try:
            enriched = self._recovery_scorer.score(
                raw, sleep_metrics, prev_strain, hrv_history, hr_history, tol_history
            )
            self._recovery_repo.upsert(enriched)
            return DayReadiness(
                date=day.date,
                sleep_metrics=day.sleep_metrics,
                strain_metrics=day.strain_metrics,
                recovery_metrics=enriched,
                errors=day.errors,
            )
        except Exception as exc:
            msg = f"recovery scoring failed for {day.date}: {exc}"
            logger.error(msg, exc_info=True)
            return DayReadiness(
                date=day.date,
                sleep_metrics=day.sleep_metrics,
                strain_metrics=day.strain_metrics,
                recovery_metrics=day.recovery_metrics,
                errors=[*day.errors, msg],
            )
