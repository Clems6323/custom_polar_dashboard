"""RecoveryScorer — enriches raw RecoveryMetrics with baselines and a composite score."""

from __future__ import annotations

from collections.abc import Sequence

from domain.models.recovery import RecoveryContributors, RecoveryMetrics
from domain.models.sleep_metrics import SleepMetrics
from domain.models.strain import StrainMetrics
from services.analytics.hrv import rolling_mean, rolling_std, z_score
from services.analytics.recovery import recovery_score

_BASELINE_WINDOW = 30  # days


class RecoveryScorer:
    """Enrich a raw RecoveryMetrics record with rolling baselines and a composite score.

    The raw record (from Polar ingestion) already carries physical measurements
    (rmssd_ms, resting_hr_bpm, mean_skin_temperature_celsius, recovery_score
    from ANS rate).  This scorer adds:
      - 30-day personal baselines for HRV and resting HR
      - z-scores relative to those baselines
      - sleep quality from the preceding night (via SleepMetrics)
      - previous day strain load (via StrainMetrics)
      - composite recovery score using the analytics formula

    Args:
        raw:            RecoveryMetrics from the ingestion layer (Polar data).
        sleep_metrics:  Scored SleepMetrics for the same calendar date, if available.
        prev_strain:    StrainMetrics from the day before, if available.
        hrv_history:    30-day RMSSD time series (oldest first, ``None`` = missing).
        hr_history:     30-day resting HR time series (oldest first, ``None`` = missing).
    """

    def score(
        self,
        raw: RecoveryMetrics,
        sleep_metrics: SleepMetrics | None,
        prev_strain: StrainMetrics | None,
        hrv_history: Sequence[float | None],
        hr_history: Sequence[float | None],
        tolerance_history: Sequence[float | None] = (),
    ) -> RecoveryMetrics:
        """Return an enriched RecoveryMetrics with computed score and contributors.

        Args:
            tolerance_history: 30-day history of Polar tolerance values (28-day rolling
                               cardio load), oldest first. Used to compute a z-score that
                               represents whether current aerobic fitness is above or below
                               the user's own baseline.
        """
        # --- Baseline computation ---
        hrv_means = rolling_mean(hrv_history, _BASELINE_WINDOW)
        hrv_stds = rolling_std(hrv_history, _BASELINE_WINDOW)
        hr_means = rolling_mean(hr_history, _BASELINE_WINDOW)
        hr_stds = rolling_std(hr_history, _BASELINE_WINDOW)
        tol_means = rolling_mean(tolerance_history, _BASELINE_WINDOW)
        tol_stds = rolling_std(tolerance_history, _BASELINE_WINDOW)

        hrv_baseline = hrv_means[-1] if hrv_means else None
        hrv_std = hrv_stds[-1] if hrv_stds else None
        hr_baseline = hr_means[-1] if hr_means else None
        hr_std = hr_stds[-1] if hr_stds else None
        tol_baseline = tol_means[-1] if tol_means else None
        tol_std = tol_stds[-1] if tol_stds else None

        # --- Z-scores ---
        hrv_z: float | None = None
        if raw.rmssd_ms is not None and hrv_baseline is not None and hrv_std is not None:
            hrv_z = z_score(raw.rmssd_ms, hrv_baseline, hrv_std)

        hr_z: float | None = None
        if raw.resting_hr_bpm is not None and hr_baseline is not None and hr_std is not None:
            hr_z = z_score(raw.resting_hr_bpm, hr_baseline, hr_std)

        # Fitness z-score uses prev_strain.chronic_load (today's tolerance from Polar)
        fitness_z: float | None = None
        current_tolerance = prev_strain.chronic_load if prev_strain else None
        if current_tolerance is not None and tol_baseline is not None and tol_std is not None:
            fitness_z = z_score(current_tolerance, tol_baseline, tol_std)

        # --- Build contributors ---
        contributors = RecoveryContributors(
            hrv_z_score=round(hrv_z, 3) if hrv_z is not None else None,
            resting_hr_z_score=round(hr_z, 3) if hr_z is not None else None,
            sleep_score=round(sleep_metrics.sleep_score, 2) if sleep_metrics else None,
            previous_strain_score=(
                round(prev_strain.strain_score, 2) if prev_strain else None
            ),
            temperature_deviation_celsius=raw.contributors.temperature_deviation_celsius,
            nightly_recharge_score=raw.contributors.nightly_recharge_score,
            fitness_load_z_score=round(fitness_z, 3) if fitness_z is not None else None,
        )

        # --- Composite score ---
        composite = recovery_score(contributors)

        return raw.model_copy(
            update={
                "recovery_score": round(composite, 2),
                "hrv_baseline_ms": round(hrv_baseline, 2) if hrv_baseline is not None else None,
                "resting_hr_baseline_bpm": (
                    round(hr_baseline, 2) if hr_baseline is not None else None
                ),
                "contributors": contributors,
            }
        )
