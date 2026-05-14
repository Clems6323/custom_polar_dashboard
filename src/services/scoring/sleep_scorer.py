"""SleepScorer — produces SleepMetrics from a SleepSession and its history."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from domain.models.enums import Provider
from domain.models.sleep import SleepSession
from domain.models.sleep_metrics import SleepMetrics
from services.analytics.sleep import (
    compute_sleep_score,
    sleep_consistency_score,
)

# Consistency window: 7 preceding nights (not including current)
_CONSISTENCY_WINDOW = 7


class SleepScorer:
    """Compute SleepMetrics for a single night from raw session data.

    ``history`` should be the N most recent sessions *before* the night being
    scored, oldest-first.  Used only for the 7-night consistency score.
    """

    def score(
        self,
        session: SleepSession,
        history: Sequence[SleepSession],
        provider: Provider = Provider.POLAR,
    ) -> SleepMetrics:
        """Return a fully populated SleepMetrics for ``session``."""
        composite = compute_sleep_score(session)

        # Architecture percentages relative to time in bed so that
        # DEEP + REM + LIGHT + INTERRUPTIONS ≈ 100 %.
        time_in_bed = session.duration_seconds
        total_sleep = (
            (session.light_sleep_seconds or 0.0)
            + (session.deep_sleep_seconds or 0.0)
            + (session.rem_sleep_seconds or 0.0)
        )

        def _pct(seconds: float | None) -> float | None:
            if seconds is None or time_in_bed <= 0:
                return None
            return seconds / time_in_bed * 100.0

        deep_pct = _pct(session.deep_sleep_seconds)
        rem_pct = _pct(session.rem_sleep_seconds)
        light_pct = _pct(session.light_sleep_seconds)
        awake_pct = _pct(session.awake_seconds)
        unknown_pct = _pct(session.unknown_sleep_seconds)

        # 7-night consistency uses the last CONSISTENCY_WINDOW sessions from
        # history plus the current session
        recent = [*list(history[-_CONSISTENCY_WINDOW:]), session]
        consistency = sleep_consistency_score(recent)

        time_in_bed = session.duration_seconds

        return SleepMetrics(
            record_date=date(
                session.end_time.year,
                session.end_time.month,
                session.end_time.day,
            ),
            user_id=session.user_id,
            provider=provider,
            sleep_session_id=session.id,
            sleep_score=round(composite, 2),
            total_sleep_seconds=total_sleep if total_sleep > 0 else session.duration_seconds,
            time_in_bed_seconds=time_in_bed,
            sleep_efficiency_pct=session.sleep_efficiency_pct,
            sleep_latency_seconds=session.sleep_latency_seconds,
            deep_sleep_pct=deep_pct,
            rem_sleep_pct=rem_pct,
            light_sleep_pct=light_pct,
            awake_pct=awake_pct,
            unknown_sleep_pct=unknown_pct,
            short_interruption_duration_seconds=session.short_interruption_duration_seconds,
            long_interruption_duration_seconds=session.long_interruption_duration_seconds,
            rmssd_ms=session.rmssd_ms,
            average_hr_bpm=session.average_hr_bpm,
            sleep_consistency_score=round(consistency, 2) if consistency is not None else None,
        )
