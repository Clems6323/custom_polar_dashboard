"""SyncOrchestrator — coordinates all Polar AccessLink ingestion pipelines.

Sync order (matches data dependency):
  1. Exercises  → ActivitySession objects stored via ActivityRepository
  2. Sleep      → SleepSession + SleepMetrics stored via their repositories
  3. Nightly recharge → RecoveryMetrics stored via RecoveryMetricsRepository
  4. Activity summaries → daily steps/calories counts

All endpoints use the token-based user identification pattern (no user ID in
path).  All repositories are injected so the orchestrator is testable without
a real Polar API connection.
"""

from __future__ import annotations

import logging

from datetime import date

from ingestion.normalization.activity import normalize_activity_summary
from ingestion.normalization.exercise import normalize_exercise
from ingestion.normalization.nightly_recharge import normalize_nightly_recharge
from ingestion.normalization.sleep import normalize_sleep
from ingestion.polar_accesslink.client import PolarClient
from ingestion.polar_accesslink.endpoints import (
    ActivityEndpoint,
    CardioLoadEndpoint,
    ExerciseEndpoint,
    NightlyRechargeEndpoint,
    SleepEndpoint,
)
from storage.repositories.cardio_load import DuckDBCardioLoadRepository
from storage.repositories.protocols import (
    ActivityRepository,
    RecoveryMetricsRepository,
    SleepMetricsRepository,
    SleepRepository,
)

logger = logging.getLogger(__name__)


class SyncResult:
    """Summary of a completed sync run."""

    __slots__ = (
        "activity_days_synced",
        "cardio_load_days_synced",
        "errors",
        "exercises_synced",
        "recharge_nights_synced",
        "sleep_nights_synced",
    )

    def __init__(self) -> None:
        self.exercises_synced = 0
        self.sleep_nights_synced = 0
        self.recharge_nights_synced = 0
        self.activity_days_synced = 0
        self.cardio_load_days_synced = 0
        self.errors: list[str] = []

    def __repr__(self) -> str:
        return (
            f"SyncResult("
            f"exercises={self.exercises_synced}, "
            f"sleep={self.sleep_nights_synced}, "
            f"recharge={self.recharge_nights_synced}, "
            f"activity={self.activity_days_synced}, "
            f"cardio_load={self.cardio_load_days_synced}, "
            f"errors={len(self.errors)})"
        )


class SyncOrchestrator:
    """Orchestrates all Polar AccessLink ingestion pipelines for one user.

    Each sync method is independent; failures in one pipeline do not abort
    others.  All errors are accumulated in ``SyncResult.errors``.
    """

    def __init__(
        self,
        client: PolarClient,
        canonical_user_id: str,
        activity_repo: ActivityRepository,
        sleep_repo: SleepRepository,
        sleep_metrics_repo: SleepMetricsRepository,
        recovery_repo: RecoveryMetricsRepository,
        cardio_load_repo: DuckDBCardioLoadRepository | None = None,
    ) -> None:
        self._client = client
        self._user_id = canonical_user_id
        self._activity_repo = activity_repo
        self._sleep_repo = sleep_repo
        self._sleep_metrics_repo = sleep_metrics_repo
        self._recovery_repo = recovery_repo
        self._cardio_load_repo = cardio_load_repo

    def sync_all(self) -> SyncResult:
        """Run all sync pipelines and return a consolidated result."""
        result = SyncResult()
        self._sync_exercises(result)
        self._sync_sleep(result)
        self._sync_nightly_recharge(result)
        self._sync_activity_summaries(result)
        self._sync_cardio_load(result)
        logger.info("Sync complete: %s", result)
        return result

    # ------------------------------------------------------------------
    # Exercise sync (list-based)
    # ------------------------------------------------------------------

    def _sync_exercises(self, result: SyncResult) -> None:
        endpoint = ExerciseEndpoint(self._client)
        try:
            exercise_records = endpoint.list_exercise_data()
        except Exception:
            result.errors.append("exercise list fetch failed")
            logger.error("Exercise list fetch failed", exc_info=True)
            return

        sessions = []
        for polar_ex in exercise_records:
            try:
                session = normalize_exercise(polar_ex, self._user_id)
                sessions.append(session)
            except Exception:
                result.errors.append(f"normalization failed for exercise {polar_ex.id}")
                logger.error("Exercise normalization failed", exc_info=True)

        if sessions:
            self._activity_repo.upsert_batch(sessions)
            result.exercises_synced += len(sessions)

    # ------------------------------------------------------------------
    # Sleep sync (list-based)
    # ------------------------------------------------------------------

    def _sync_sleep(self, result: SyncResult) -> None:
        endpoint = SleepEndpoint(self._client)
        try:
            sleep_records = endpoint.list_sleep_data()
        except Exception:
            result.errors.append("sleep list fetch failed")
            logger.error("Sleep list fetch failed", exc_info=True)
            return

        for polar_sleep in sleep_records:
            try:
                session, metrics = normalize_sleep(polar_sleep, self._user_id)
                self._sleep_repo.upsert(session)
                self._sleep_metrics_repo.upsert(metrics)
                result.sleep_nights_synced += 1
            except Exception:
                result.errors.append(f"sleep normalization failed for {polar_sleep.date}")
                logger.error(
                    "Sleep normalization failed for %s", polar_sleep.date, exc_info=True
                )

    # ------------------------------------------------------------------
    # Nightly recharge sync (list-based)
    # ------------------------------------------------------------------

    def _sync_nightly_recharge(self, result: SyncResult) -> None:
        endpoint = NightlyRechargeEndpoint(self._client)
        try:
            recharge_records = endpoint.list_recharge_data()
        except Exception:
            result.errors.append("nightly recharge list fetch failed")
            logger.error("Nightly recharge list fetch failed", exc_info=True)
            return

        for polar_nr in recharge_records:
            try:
                recovery = normalize_nightly_recharge(polar_nr, self._user_id)
                self._recovery_repo.upsert(recovery)
                result.recharge_nights_synced += 1
            except Exception:
                result.errors.append(f"recharge normalization failed for {polar_nr.date}")
                logger.error(
                    "Recharge normalization failed for %s", polar_nr.date, exc_info=True
                )

    # ------------------------------------------------------------------
    # Activity summary sync (list-based)
    # ------------------------------------------------------------------

    def _sync_activity_summaries(self, result: SyncResult) -> None:
        endpoint = ActivityEndpoint(self._client)
        try:
            activity_records = endpoint.list_activity_data()
        except Exception:
            result.errors.append("activity list fetch failed")
            logger.error("Activity list fetch failed", exc_info=True)
            return

        for polar_act in activity_records:
            try:
                normalize_activity_summary(polar_act)
                result.activity_days_synced += 1
            except Exception:
                result.errors.append(f"normalization failed for activity {polar_act.id}")
                logger.error("Activity normalization failed", exc_info=True)

    # ------------------------------------------------------------------
    # Cardio load sync (list-based, daily records)
    # ------------------------------------------------------------------

    def _sync_cardio_load(self, result: SyncResult) -> None:
        if self._cardio_load_repo is None:
            return
        endpoint = CardioLoadEndpoint(self._client)
        try:
            records = endpoint.list_cardio_load()
        except Exception:
            result.errors.append("cardio load list fetch failed")
            logger.error("Cardio load fetch failed", exc_info=True)
            return

        for rec in records:
            try:
                record_date = date.fromisoformat(rec.date)
                self._cardio_load_repo.upsert(
                    user_id=self._user_id,
                    record_date=record_date,
                    cardio_load=rec.cardio_load,
                    strain=rec.strain,
                    tolerance=rec.tolerance,
                )
                result.cardio_load_days_synced += 1
            except Exception:
                result.errors.append(f"cardio load upsert failed for {rec.date}")
                logger.error("Cardio load upsert failed for %s", rec.date, exc_info=True)

