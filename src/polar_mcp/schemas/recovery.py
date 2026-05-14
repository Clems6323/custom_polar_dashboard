"""MCP output schemas for recovery/readiness tools."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from domain.models.recovery import RecoveryMetrics
from polar_mcp.schemas.common import ToolMeta


def _recovery_confidence(m: RecoveryMetrics) -> tuple[float, list[str]]:
    c = m.contributors
    optional_fields = [
        ("rmssd_ms", m.rmssd_ms),
        ("sdnn_ms", m.sdnn_ms),
        ("resting_hr_bpm", m.resting_hr_bpm),
        ("mean_skin_temperature_celsius", m.mean_skin_temperature_celsius),
        ("hrv_baseline_ms", m.hrv_baseline_ms),
        ("resting_hr_baseline_bpm", m.resting_hr_baseline_bpm),
        ("hrv_z_score", c.hrv_z_score),
        ("resting_hr_z_score", c.resting_hr_z_score),
        ("sleep_score", c.sleep_score),
        ("previous_strain_score", c.previous_strain_score),
        ("temperature_deviation_celsius", c.temperature_deviation_celsius),
        ("nightly_recharge_score", c.nightly_recharge_score),
    ]
    missing = [name for name, val in optional_fields if val is None]
    confidence = (len(optional_fields) - len(missing)) / len(optional_fields)
    return round(confidence, 3), missing


class RecoveryReadinessZone(BaseModel):
    zone: str = Field(description="poor | moderate | optimal")
    description: str

    @classmethod
    def from_score(cls, score: float) -> RecoveryReadinessZone:
        if score < 34:
            return cls(zone="poor", description="Recovery is compromised; prioritise rest")
        if score < 67:
            return cls(
                zone="moderate",
                description="Moderate recovery; light-to-moderate training is appropriate",
            )
        return cls(zone="optimal", description="Well recovered; ready for high-intensity work")


class RecoveryContributorsOutput(BaseModel):
    """Per-signal contribution breakdown for explainability."""

    hrv_z_score: float | None = Field(
        default=None,
        description="z-score of overnight RMSSD vs 30-day baseline (positive = above baseline)",
    )
    resting_hr_z_score: float | None = Field(
        default=None,
        description="z-score of resting HR vs 30-day baseline (negative = lower than usual = good)",
    )
    sleep_score: float | None = Field(
        default=None,
        description="Sleep quality score from preceding night (0-100)",
    )
    previous_strain_score: float | None = Field(
        default=None,
        description="Strain score from the prior day (high strain reduces recovery)",
    )
    temperature_deviation_celsius: float | None = Field(
        default=None,
        description="Overnight skin temp deviation from baseline in degC (>0.5 = stress signal)",
    )
    nightly_recharge_score: float | None = Field(
        default=None,
        description="Provider ANS recharge score (0-100)",
    )


class RecoveryScoreOutput(BaseModel):
    """Daily recovery/readiness metrics with full contributor breakdown."""

    record_date: date
    user_id: str
    provider: str

    recovery_score: float = Field(
        ge=0,
        le=100,
        description="Composite readiness score (0-100)",
    )
    readiness_zone: RecoveryReadinessZone

    rmssd_ms: float | None = Field(default=None, description="Overnight RMSSD in milliseconds")
    sdnn_ms: float | None = Field(default=None, description="Overnight SDNN in milliseconds")
    resting_hr_bpm: float | None = Field(default=None, description="Resting heart rate in BPM")
    mean_skin_temperature_celsius: float | None = Field(
        default=None,
        description="Overnight mean wrist skin temperature in degC",
    )

    hrv_baseline_ms: float | None = Field(
        default=None,
        description="Rolling 30-day RMSSD personal baseline in milliseconds",
    )
    resting_hr_baseline_bpm: float | None = Field(
        default=None,
        description="Rolling 30-day resting HR baseline in BPM",
    )

    contributors: RecoveryContributorsOutput

    metadata: ToolMeta

    @classmethod
    def from_domain(cls, m: RecoveryMetrics) -> RecoveryScoreOutput:
        confidence, missing = _recovery_confidence(m)
        c = m.contributors
        return cls(
            record_date=m.record_date,
            user_id=m.user_id,
            provider=str(m.provider),
            recovery_score=m.recovery_score,
            readiness_zone=RecoveryReadinessZone.from_score(m.recovery_score),
            rmssd_ms=m.rmssd_ms,
            sdnn_ms=m.sdnn_ms,
            resting_hr_bpm=m.resting_hr_bpm,
            mean_skin_temperature_celsius=m.mean_skin_temperature_celsius,
            hrv_baseline_ms=m.hrv_baseline_ms,
            resting_hr_baseline_bpm=m.resting_hr_baseline_bpm,
            contributors=RecoveryContributorsOutput(
                hrv_z_score=c.hrv_z_score,
                resting_hr_z_score=c.resting_hr_z_score,
                sleep_score=c.sleep_score,
                previous_strain_score=c.previous_strain_score,
                temperature_deviation_celsius=c.temperature_deviation_celsius,
                nightly_recharge_score=c.nightly_recharge_score,
            ),
            metadata=ToolMeta(
                data_available=True,
                confidence=confidence,
                missing_signals=missing,
            ),
        )
