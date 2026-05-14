"""MCP output schemas for sleep quality tools."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from domain.models.sleep_metrics import SleepMetrics
from polar_mcp.schemas.common import ToolMeta


def _sleep_confidence(m: SleepMetrics) -> tuple[float, list[str]]:
    """Compute confidence score and list of missing signals for a SleepMetrics record."""
    optional_fields = [
        ("sleep_efficiency_pct", m.sleep_efficiency_pct),
        ("sleep_latency_seconds", m.sleep_latency_seconds),
        ("deep_sleep_pct", m.deep_sleep_pct),
        ("rem_sleep_pct", m.rem_sleep_pct),
        ("light_sleep_pct", m.light_sleep_pct),
        ("awake_pct", m.awake_pct),
        ("rmssd_ms", m.rmssd_ms),
        ("average_hr_bpm", m.average_hr_bpm),
        ("sleep_consistency_score", m.sleep_consistency_score),
    ]
    missing = [name for name, val in optional_fields if val is None]
    confidence = (len(optional_fields) - len(missing)) / len(optional_fields)
    return round(confidence, 3), missing


class SleepArchitecture(BaseModel):
    deep_sleep_pct: float | None = Field(
        default=None,
        description="Fraction of total sleep in deep (slow-wave) stage (%)",
    )
    rem_sleep_pct: float | None = Field(
        default=None,
        description="Fraction of total sleep in REM stage (%)",
    )
    light_sleep_pct: float | None = Field(
        default=None,
        description="Fraction of total sleep in light NREM stage (%)",
    )
    awake_pct: float | None = Field(
        default=None,
        description="Fraction of recording window spent awake (%)",
    )


class SleepScoreOutput(BaseModel):
    """Full sleep quality metrics for a single night."""

    record_date: date = Field(description="Night being scored (wake date)")
    user_id: str
    provider: str

    sleep_score: float = Field(
        ge=0,
        le=100,
        description="Composite sleep quality score (0-100); 0-33 poor, 34-66 fair, 67-100 good",
    )

    total_sleep_minutes: float = Field(
        ge=0,
        description="Total time asleep in minutes (excluding awake time)",
    )
    time_in_bed_minutes: float | None = Field(
        default=None,
        description="Total recording window in minutes",
    )
    sleep_efficiency_pct: float | None = Field(
        default=None,
        description="total_sleep / time_in_bed * 100",
    )
    sleep_latency_minutes: float | None = Field(
        default=None,
        description="Time from lights-out to sleep onset in minutes",
    )

    architecture: SleepArchitecture

    rmssd_ms: float | None = Field(
        default=None,
        description="Overnight mean RMSSD (primary HRV metric) in milliseconds",
    )
    average_hr_bpm: float | None = Field(
        default=None,
        description="Overnight mean heart rate in BPM",
    )

    sleep_consistency_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Rolling 7-night consistency score (0-100); rewards regular schedules",
    )

    metadata: ToolMeta

    @classmethod
    def from_domain(cls, m: SleepMetrics) -> SleepScoreOutput:
        confidence, missing = _sleep_confidence(m)
        return cls(
            record_date=m.record_date,
            user_id=m.user_id,
            provider=str(m.provider),
            sleep_score=m.sleep_score,
            total_sleep_minutes=round(m.total_sleep_seconds / 60.0, 1),
            time_in_bed_minutes=(
                round(m.time_in_bed_seconds / 60.0, 1)
                if m.time_in_bed_seconds is not None
                else None
            ),
            sleep_efficiency_pct=m.sleep_efficiency_pct,
            sleep_latency_minutes=(
                round(m.sleep_latency_seconds / 60.0, 1)
                if m.sleep_latency_seconds is not None
                else None
            ),
            architecture=SleepArchitecture(
                deep_sleep_pct=m.deep_sleep_pct,
                rem_sleep_pct=m.rem_sleep_pct,
                light_sleep_pct=m.light_sleep_pct,
                awake_pct=m.awake_pct,
            ),
            rmssd_ms=m.rmssd_ms,
            average_hr_bpm=m.average_hr_bpm,
            sleep_consistency_score=m.sleep_consistency_score,
            metadata=ToolMeta(
                data_available=True,
                confidence=confidence,
                missing_signals=missing,
            ),
        )


class SleepTrendPoint(BaseModel):
    """Single-night data point within a sleep trends response."""

    record_date: date
    sleep_score: float
    total_sleep_minutes: float
    sleep_efficiency_pct: float | None = None
    deep_sleep_pct: float | None = None
    rem_sleep_pct: float | None = None
    rmssd_ms: float | None = None
    sleep_consistency_score: float | None = None


class SleepTrendsSummary(BaseModel):
    """Descriptive statistics computed from the requested date range."""

    nights: int = Field(description="Number of nights with data")
    avg_sleep_score: float | None = None
    avg_sleep_minutes: float | None = None
    avg_efficiency_pct: float | None = None
    avg_rmssd_ms: float | None = None
    avg_deep_pct: float | None = None
    avg_rem_pct: float | None = None


class SleepTrendsOutput(BaseModel):
    """Sleep quality time-series for a date range."""

    user_id: str
    start_date: date
    end_date: date
    data: list[SleepTrendPoint]
    summary: SleepTrendsSummary
    metadata: ToolMeta

    @classmethod
    def from_domain(
        cls, user_id: str, start: date, end: date, records: list[SleepMetrics]
    ) -> SleepTrendsOutput:
        points = [
            SleepTrendPoint(
                record_date=r.record_date,
                sleep_score=r.sleep_score,
                total_sleep_minutes=round(r.total_sleep_seconds / 60.0, 1),
                sleep_efficiency_pct=r.sleep_efficiency_pct,
                deep_sleep_pct=r.deep_sleep_pct,
                rem_sleep_pct=r.rem_sleep_pct,
                rmssd_ms=r.rmssd_ms,
                sleep_consistency_score=r.sleep_consistency_score,
            )
            for r in records
        ]

        def _avg(vals: list[float | None]) -> float | None:
            non_null = [v for v in vals if v is not None]
            return round(sum(non_null) / len(non_null), 2) if non_null else None

        summary = SleepTrendsSummary(
            nights=len(records),
            avg_sleep_score=_avg([r.sleep_score for r in records]),
            avg_sleep_minutes=_avg([r.total_sleep_seconds / 60.0 for r in records]),
            avg_efficiency_pct=_avg([r.sleep_efficiency_pct for r in records]),
            avg_rmssd_ms=_avg([r.rmssd_ms for r in records]),
            avg_deep_pct=_avg([r.deep_sleep_pct for r in records]),
            avg_rem_pct=_avg([r.rem_sleep_pct for r in records]),
        )

        confidence = len(records) / max((end - start).days + 1, 1)
        return cls(
            user_id=user_id,
            start_date=start,
            end_date=end,
            data=points,
            summary=summary,
            metadata=ToolMeta(
                data_available=len(records) > 0,
                confidence=round(min(confidence, 1.0), 3),
                missing_signals=([] if records else ["no_records_in_range"]),
            ),
        )
