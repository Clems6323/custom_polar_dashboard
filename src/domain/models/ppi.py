"""Canonical domain model for a single PPI (Peak-to-Peak Interval) sample.

PPI is the time between consecutive heartbeat peaks, equivalent to the RR
interval used in clinical HRV analysis.  It is the primary input to all HRV
metrics (RMSSD, SDNN, pNN50, etc.) computed in the physiology analytics layer.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from domain.models.base import BaseTimeSeriesSample

# Physiological PPI bounds: 300 ms ≈ 200 BPM, 2500 ms ≈ 24 BPM
_PPI_MIN_MS: int = 300
_PPI_MAX_MS: int = 2500


class PPISample(BaseTimeSeriesSample):
    """A single peak-to-peak interval measurement.

    Polar H10 / Verity Sense devices stream PPI data directly over BLE and
    include an error estimate per sample.  Samples marked as not valid (e.g.
    artefacts, motion noise) must be filtered before HRV computation.
    """

    ppi_ms: int = Field(
        ge=_PPI_MIN_MS,
        le=_PPI_MAX_MS,
        description="Peak-to-peak interval in milliseconds",
    )
    error_estimate_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Estimated measurement uncertainty in milliseconds reported by the device. "
            "Samples with high error should be excluded from sensitive HRV calculations."
        ),
    )
    hr_bpm: float | None = Field(
        default=None,
        ge=20,
        le=250,
        description="Heart rate derived from this PPI (60_000 / ppi_ms), for convenience",
    )
    is_valid: bool = Field(
        default=True,
        description=(
            "Whether this sample passes device-side quality checks. "
            "Invalid samples are retained in storage but excluded from analytics."
        ),
    )

    @field_validator("timestamp")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:  # noqa: F821
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v

    @model_validator(mode="after")
    def sync_hr_from_ppi(self) -> PPISample:
        """Populate hr_bpm from ppi_ms when not explicitly provided."""
        if self.hr_bpm is None:
            object.__setattr__(self, "hr_bpm", round(60_000 / self.ppi_ms, 1))
        return self
